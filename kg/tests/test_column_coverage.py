#!/usr/bin/env python3
"""
Column coverage check for kg/ontology/eat.ttl.

For every source table, list columns that have no corresponding property in the
ontology and no documented reason to be absent. A column is legitimately absent
when it is carried by a relationship, by an event node, by the change-detection
view, or when it is deliberately not modelled — each of those needs an explicit
entry in EXCLUSIONS below, with a reason.

Anything else is a gap. This exists because the ontology can be entirely
self-consistent and still be missing half of what the data says: reading the
file will not tell you what is not in it.

Run from the repo root:
    python kg/tests/test_column_coverage.py
Exits non-zero if any column is uncovered.
"""

import os
import re
import sys
from collections import defaultdict

import psycopg

DB_URL = os.environ.get(
    "KG_DB_URL_PSYCOPG",
    "postgresql://kg_loader@localhost:5433/triage",
)
ONTOLOGY = "kg/ontology/eat.ttl"

# Columns that are correctly absent from the ontology, and why.
# Key: "schema.table.column". Value: the reason.
EXCLUSIONS = {
    # Composite key parts carried by the IRI itself
    "core.referral_daily.hospital_hipe": "in the IRI, and via eat:atHospital",
    "core.referral_daily.patient_id": "via eat:forPatient",
    "core.referral_daily.as_of_date": "collapses into ReferralState validFrom/validTo",
    # Derived counters — R2 says these are never materialised
    "core.referral_daily.days_since_referral": "R2: derived at query time",
    "core.referral_daily.days_since_received": "R2: derived at query time",
    "core.referral_daily.adjusted_wait_days": "R2: derived at query time",
    "core.referral_daily.days_awaiting_triage": "R2: derived at query time",
    # Carried by event nodes rather than as literals on the referral
    "core.referral_daily.last_cancellation_date": "via eat:hasCancellation",
    "core.referral_daily.last_cancellation_reason": "via eat:hasCancellation",
    "core.referral_daily.suspension_start_date": "via eat:hasSuspension",
    "core.referral_daily.suspension_end_date": "via eat:hasSuspension",
    "core.referral_daily.suspension_reason": "via eat:hasSuspension",
    "core.referral_daily.triage_event_id": "via eat:hasTriageEvent",
    # referral_daily: further name divergences and re-expressed columns
    "core.referral_daily.pathway_number": "in the IRI, and via eat:forPatient's referral",
    "core.referral_daily.specialty_hipe": "via eat:referredToService (on eat:ReferralState, moved by add-missing-data-layer_20260903)",
    "core.referral_daily.priority_level_gp": "via eat:gpPriority (requirements.md §4 divergence table)",
    "core.referral_daily.removal_date": "via eat:validTo, closed at removal_date per decisions.md §1",
    "core.referral_daily.high_clinical_or_social_needs": "via eat:hasHighClinicalOrSocialNeeds (requirements.md §4 divergence table)",

    # Own IRI-key columns of a class with no reason to point at itself
    "core.hospitals.hospital_hipe": "the IRI key of eat:Hospital itself",
    "core.persons.ihi_number": "the IRI key of eat:Person itself",
    "core.patients.patient_id": "the IRI key of eat:Patient itself (with hospital_hipe)",
    "core.wards.ward_id": "the IRI key of eat:Ward itself (with hospital_hipe)",
    "core.triage_events.triage_event_id": "the IRI key of eat:TriageEvent itself; namespaces.md §4 deliberately omits hospital_hipe/pathway_number from this IRI, already globally unique",

    # Composite-key columns carried by an object property, per the IRI templates
    # in namespaces.md §4
    "core.wards.hospital_hipe": "in the IRI, and via eat:atHospital (domain widened for Ward in add-missing-data-layer_20260903)",
    "core.hospital_specialty.hospital_hipe": "in the IRI, and via eat:providedBy",
    "core.hospital_specialty.specialty_hipe": "in the IRI, and via eat:forSpecialty",
    "core.ward_specialty.hospital_hipe": "in the IRI, and via eat:inWard -> eat:atHospital",
    "core.ward_specialty.ward_id": "in the IRI, and via eat:inWard",
    "core.ward_specialty.specialty_hipe": "in the IRI, and via eat:forSpecialty",
    "core.bed_status.hospital_hipe": "in the IRI, and via eat:statusOf -> eat:atHospital",
    "core.bed_status.ward_id": "in the IRI, and via eat:statusOf",
    "core.bed_status.occupied": "via eat:occupiedBeds (requirements.md §4 divergence table)",
    "core.bed_status.free": "via eat:freeBeds (requirements.md §4 divergence table)",
    "core.bed_status.outliers": "via eat:outlierPatients (requirements.md §4 divergence table)",
    "core.clinic_sessions.hospital_hipe": "in the IRI, and via eat:sessionOf -> eat:providedBy",
    "core.clinic_sessions.specialty_hipe": "in the IRI, and via eat:sessionOf -> eat:forSpecialty",
    "core.cancellation_events.hospital_hipe": "in the IRI, and via eat:hasCancellation",
    "core.cancellation_events.pathway_number": "in the IRI, and via eat:hasCancellation",
    "core.conditions.hospital_hipe": "in the IRI, and via eat:hasCondition",
    "core.conditions.pathway_number": "in the IRI, and via eat:hasCondition",
    "core.conditions.snomed_ct_id": "via eat:snomedCode (requirements.md §4 divergence table)",
    "core.suspension_events.hospital_hipe": "in the IRI, and via eat:hasSuspension",
    "core.suspension_events.pathway_number": "in the IRI, and via eat:hasSuspension",
    "core.triage_events.hospital_hipe": "via eat:hasTriageEvent (inverse traversal from eat:Referral); omitted from the TriageEvent IRI by design, see namespaces.md §4",
    "core.triage_events.pathway_number": "via eat:hasTriageEvent, same reasoning as hospital_hipe above",
    "core.triage_events.triage_category": "via eat:assignedCategory (requirements.md §4 divergence table)",

    # patients / persons: name divergences on shared sex/DOB properties
    "core.patients.hospital_hipe": "in the IRI, and via eat:atHospital",
    "core.patients.ihi_number": "via eat:isRecordOf when present; also the IRI key of eat:Person",
    "core.patients.patient_sex": "via eat:sex (requirements.md §4 divergence table)",
    "core.patients.patient_date_of_birth": "via eat:dateOfBirth (requirements.md §4 divergence table)",
    "core.persons.person_sex": "via eat:sex (requirements.md §4 divergence table)",
    "core.persons.person_date_of_birth": "via eat:dateOfBirth (requirements.md §4 divergence table)",

    # observations: event-node IRI keys, a name divergence, and the six vitals
    # that are deliberately never literals -- each becomes its own
    # sosa:Observation node (sosa:observedProperty + sosa:hasSimpleResult).
    "core.observations.hospital_hipe": "in the IRI, and via eat:hasObservationEvent",
    "core.observations.pathway_number": "in the IRI, and via eat:hasObservationEvent",
    "core.observations.obs_datetime": "via sosa:resultTime",
    "core.observations.hr": "modelled as a sosa:Observation node (observedProperty eat:heartRate, hasSimpleResult), never a literal -- decisions.md §3 / ontology.md §5",
    "core.observations.sbp": "modelled as a sosa:Observation node (observedProperty eat:systolicBP, hasSimpleResult), never a literal",
    "core.observations.dbp": "modelled as a sosa:Observation node (observedProperty eat:diastolicBP, hasSimpleResult), never a literal",
    "core.observations.rr": "modelled as a sosa:Observation node (observedProperty eat:respiratoryRate, hasSimpleResult), never a literal",
    "core.observations.temp": "modelled as a sosa:Observation node (observedProperty eat:temperature, hasSimpleResult), never a literal",
    "core.observations.spo2": "modelled as a sosa:Observation node (observedProperty eat:oxygenSaturation, hasSimpleResult), never a literal",

    # suspension_events: the interval, not literals on the event itself
    "core.suspension_events.suspension_start_date": "carried by the time:Interval reached via time:hasTime (time:hasBeginning), not a literal on eat:SuspensionEvent",
    "core.suspension_events.suspension_end_date": "carried by the time:Interval reached via time:hasTime (time:hasEnd), not a literal on eat:SuspensionEvent",

    # Add further exclusions here as they are agreed. A column with no entry
    # and no property is a failure, not a judgement call.
}

# Source table -> the ontology class it maps to. Extend as mappings land.
TABLES = [
    "core.referral_daily",
    "core.triage_events",
    "core.patients",
    "core.persons",
    "core.conditions",
    "core.observations",
    "core.hospitals",
    "core.hospital_specialty",
    "core.wards",
    "core.ward_specialty",
    "core.bed_status",
    "core.clinic_sessions",
    "core.cancellation_events",
    "core.suspension_events",
]


def ontology_local_names(path):
    """Local names of every eat: term declared in the ontology."""
    text = open(path, encoding="utf-8").read()
    names = set(re.findall(r"\beat:([A-Za-z][A-Za-z0-9_]*)", text))
    names |= set(
        re.findall(r"/kg/ns#([A-Za-z][A-Za-z0-9_]*)", text)
    )
    return {n.lower() for n in names}


def camel(column):
    head, *rest = column.split("_")
    return head + "".join(p.title() for p in rest)


def main():
    names = ontology_local_names(ONTOLOGY)
    misses = defaultdict(list)

    with psycopg.connect(DB_URL) as conn:
        for qualified in TABLES:
            schema, table = qualified.split(".")
            rows = conn.execute(
                """
                SELECT column_name FROM information_schema.columns
                WHERE table_schema = %s AND table_name = %s
                ORDER BY ordinal_position
                """,
                (schema, table),
            ).fetchall()
            if not rows:
                misses[qualified].append("(table not found)")
                continue
            for (col,) in rows:
                key = f"{qualified}.{col}"
                if key in EXCLUSIONS:
                    continue
                if camel(col).lower() in names:
                    continue
                misses[qualified].append(col)

    if not misses:
        print("PASS: every source column is carried or explicitly excluded")
        return 0

    total = sum(len(v) for v in misses.values())
    print(f"FAIL: {total} column(s) with no property and no documented exclusion\n")
    for table, cols in sorted(misses.items()):
        print(f"  {table}")
        for c in cols:
            print(f"      {c}  ->  suggested: eat:{camel(c)}")
        print()
    print("Either add a property to ontology.md and eat.ttl, or add an")
    print("EXCLUSIONS entry in this file stating why the column is absent.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
