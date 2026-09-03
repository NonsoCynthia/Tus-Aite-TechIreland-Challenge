# Design decisions

Five decisions taken before any triples were written. Each changes what triples exist.

This file records the **reasoning**, not just the outcome, because an agent that hits an
edge case should extend the decision the way it was meant rather than invent a local fix.
`requirements.md` states the same decisions as testable requirements.

---

## 1. One `Referral`, one `ReferralState` per material change

**Decided.** Never-changing fields sit on `eat:Referral`. An `eat:ReferralState` is minted
only when a material field differs from the previous `as_of_date` for the same
`(hospital_hipe, pathway_number)`, carrying `eat:validFrom` and `eat:validTo`. The four
wait counters are **derived at query time**, not stored.

**Why.** `referral_daily` reproduces the file hospitals send the NTPF: a full extract of
the whole list, resubmitted each cycle. The repetition is an artefact of how that file is
produced, not a fact about the patient. A state is a claim about a period, which is what
Type 2 history models, and the KG layer is where this project has the authority to choose
it. On the `full` profile the ratio is measured, not assumed: 70,022 rows collapse to
13,772 states over 5,200 referrals — 5,200 first appearances and 8,572 real transitions.

**Why counters are derived.** `days_since_referral` and `days_since_received` are date
arithmetic. `adjusted_wait_days` is not: it subtracts suspended time, so it freezes while
a suspension is open and resumes after. If each consumer computed it independently they
would disagree, which is precisely why the dataset stores it. Deriving it from **one
shared SPARQL fragment** preserves that guarantee at the graph layer — the agents and the
rule checker cannot disagree about a wait, because they run the same fragment.

**This is why `eat:SuspensionEvent` must be first-class**, with its interval in the graph.
`adjusted_wait_days` is only derivable if the suspended periods are there to subtract.

**Closed vs open intervals.** `valid_to` is set to `removal_date` where the referral was
removed, and is absent otherwise. An open interval asserts "still on the waiting list"; a
removed referral is not, and leaving it open would make every CRT breach query silently
count removed patients as still breaching.

**What it costs.** "What did the system see on the 9th" becomes a range query
(`validFrom <= 9th < validTo`) rather than a lookup. **A citation must therefore name the
state IRI, never the date alone.**

**Guard.** Type 2 only holds if states never overlap. Enforced by a shape, not by trust.

---

## 2. SHACL, adopted now

**Decided.** Structural shapes are written alongside the mappings. `sh:sparql` rule
constraints are added once the coordinating agent produces its first ranking, because they
need a placement to target.

**Why not OWL alone.** OWL reasons under the open-world assumption: it adds what must be
true from what you have said, and never objects to what you have not. Declare that Urgent
outranks Semi-Urgent, then produce a ranking that ignores it, and OWL reports nothing — no
statement said positions must respect that order, so there is no contradiction to find.
This is not a gap in OWL. Inference and validation are different jobs, and a rule check
needs the second.

**Why now rather than later.** Structural shapes catch mapping bugs on the day the mapping
is written, which is when they are cheapest. They have already earned this: the `"None"`
literal bug (§Gotchas in `requirements.md`) is exactly what `sh:datatype xsd:date` rejects.

**The deeper reason.** SHACL validation reports are themselves RDF — `sh:ValidationReport`,
`sh:focusNode`, `sh:resultPath`, `sh:sourceShape`. That structure converts almost directly
into `rule_checks` rows, with `sh:focusNode` as the citation. A pure-Python rule checker
means building that plumbing by hand and inventing the mapping from "violation" to
"citable evidence".

**Which rules fail the build, and which do not.**

| Rule | Treatment | Why |
|---|---|---|
| `RULE-ORDER` | Shape; **fails CI** | Ranking across a category boundary is a defect in our own output |
| `RULE-TIEBREAK` | Shape; **fails CI** | Ordering we produced ourselves |
| `RULE-CRT-*` | Rule check; records `passed=false` | A 41-day urgent wait is a fact about the hospital, not an invalid graph |
| `RULE-TRIAGE-TURNAROUND` | Rule check | Describes the service, not the software |

A clinician may break `RULE-ORDER` knowingly by overriding. Shapes therefore target
`eat:Decision` in the run graph and **never** the override graph.

---

## 3. A unit belongs to the measurement type

**Decided.** `qudt:hasUnit` on the observable property, declared once in the ontology. Not
on the individual observation.

```turtle
eat:heartRate        qudt:hasUnit unit:PER-MIN .
eat:respiratoryRate  qudt:hasUnit unit:PER-MIN .
eat:systolicBP       qudt:hasUnit unit:MilliM_HG .
eat:diastolicBP      qudt:hasUnit unit:MilliM_HG .
eat:temperature      qudt:hasUnit unit:DEG_C .
eat:oxygenSaturation qudt:hasUnit unit:PERCENT .
```

**Why.** A unit is a property of what is being measured, not of each measurement, and this
dataset has exactly one unit per column by construction. Six triples in the ontology
replace six per observation across roughly 12,000 of them — cheaper than the option that
was supposed to be cheapest, and the more accurate claim.

**Only six of the thirteen observation columns take a unit at all.** `pain` is a 0–10
rating, `news2` a composite score, `avpu` a four-level code, `mts_category` and
`icts_category` colour codes, `chiefcomplaint` free text. A NEWS2 of 5 is not 5 of
anything. Do not invent units for these.

**Why QUDT over UCUM.** In RDF the value of a unit vocabulary is that `unit:MilliM_HG`
resolves to something. UCUM codes end up as plain strings, which is barely better than a
bare literal. Keep the UCUM code as an annotation on the property if FHIR alignment is
wanted later.

**Pin the QUDT version** in `versions.yml`. Unit IRIs that silently change break every
triple referencing them.

**Limitation, on the record.** Unit-on-property assumes one unit per measurement type
forever. The project's own MIMIC cleaning found a Fahrenheit reading in the Celsius column
alongside a diastolic pressure of 879. Real ingestion breaks this assumption, and at that
point units must move onto the observation.

---

## 4. No identifier, no `Person` node

**Decided.** A patient with no national identifier gets **no `eat:Person` node**. No
placeholder IRI, no blank node. Two classes rather than one: `eat:Patient` always exists,
`eat:Person` only where an IHI does, and `eat:isRecordOf` — functional — joins them where
both are present.

**Why.** A placeholder would assert that a person exists while being uncitable and
uncomparable: the appearance of national identity with none of its substance. Under the
open-world assumption OWL concludes nothing about the missing link, which is the honest
position — we do not know whether this patient is waiting elsewhere. `FILTER NOT EXISTS`
is negation as failure over what is asserted, which is exactly the claim the data
supports: *we cannot link this patient*. The absence is a query result, not an axiom.

```sparql
SELECT (COUNT(?p) AS ?unlinkable) WHERE {
  ?p a eat:Patient .
  FILTER NOT EXISTS { ?p eat:isRecordOf ?person }
}
```

The dataset documentation is explicit that the gap is the point: it is what a national
shared care record would fix. A design that papers over it deletes the argument.

**Do not model the absence as an OWL axiom.** SPARQL is the correct tool.

**Limitation, on the record.** Cross-hospital linkage is not demonstrated in the published
data (`HOW_THE_DATA_WAS_MADE.md`). 3,412 patients carry an identifier and none occurs at
more than one hospital, so every `Person` node has exactly one `Patient` pointing at it.
The structure is right; the data does not yet exercise it. `PW-DEMO-06` and `PW-DEMO-07`
have the shape but do not show multi-list visibility, and `cross_hospital_share` is read by
nothing. **No demo may rest on cross-hospital linkage without checking the loaded profile
first.**

---

## 5. Rationale text in the graph, in its own graph, write-once

**Decided.** Rationales live in `…/kg/graph/rationale`, write-once, with an invariant
nobody breaks: **no agent's SPARQL reads from it.** The same discipline as `ground_truth`,
for a different reason — ground truth is withheld to prevent circularity, rationale is
isolated so generated prose is never mistaken for evidence.

**Why storing it is not optional.** Regenerate the sentence tomorrow and you get different
text: models are non-deterministic and versions are superseded. Without the stored text
you cannot answer "what was the clinician actually shown when they accepted this ranking",
and overrides become uninterpretable — you would know they overrode, not what they
overrode against.

**Why not a column.** A column stores the string and loses the link. Auditing a sentence
needs the exact set of citations that were in the prompt, and that is a set of IRIs:
natural as graph structure, painful as a foreign key.

```turtle
<…/kg/id/rationale/9001/2026-08-28/PW-0412>
    a eat:Rationale ;
    eat:rationaleText "…" ;
    prov:wasGeneratedBy <…/kg/id/activity/rationale-gen/…> ;
    prov:used <…/kg/id/citation/…> , <…/kg/id/citation/…> ;
    prov:wasAttributedTo <…/kg/id/agent/claude-opus-5> ;
    eat:promptHash "sha256:…" .
```

PROV-O has no dedicated text property. Rather than overload `prov:value` this project uses
`eat:rationaleText` with an `rdfs:comment` recording the choice. Either is defensible;
**apply one consistently.**

**The `prov:used` set is the point.** Feature 7 promises the model cannot introduce
unsupported facts. The only way to demonstrate that rather than assert it is to compare
what the rationale `used` against what it says — every entity named in the sentence must
appear in the citation set. That is a containment check that runs in CI.

**Keyed on `(hospital, date, pathway)`**, so a referral re-ranked the next day gets a new
rationale and the old one stays addressable. Never overwritten — the same append-only
discipline the output tables already follow. Store the prompt hash and the model version
string so you can tell which rationales predate a model change without re-reading them.
