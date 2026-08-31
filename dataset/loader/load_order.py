"""Load order for the input tables.

Foreign keys mean this order is not optional. See BUILD_MANUAL.md section 9.2.

`referrals` is not a CSV. It is derived from the distinct referral identities in
referral_daily, which is why referral_daily is staged first: every child table
(conditions, observations, triage_events, cancellations, suspensions) carries a
foreign key to core.referrals, so referrals must exist before any of them load.
"""

# Dictionary tables, loaded from db/seeds/ rather than from the dataset.
SEED_TABLES = [
    "ref_specialty",
    "ref_codes",
    "ref_rules",
]

# Data tables, loaded from data/<profile>/. Order is dependency order.
LOAD_ORDER = [
    "hospitals",
    "hospital_specialty",
    "persons",
    "patients",
    "referral_daily_stage",   # unconstrained staging table
    "referrals",              # DERIVED from the stage table, not a CSV
    "triage_events",
    "referral_daily",         # from stage, now that the FKs resolve
    "conditions",
    "observations",
    "wards",
    "ward_specialty",
    "bed_status",
    "clinic_sessions",
    "cancellation_events",
    "suspension_events",
    "ground_truth",           # into the eval schema; held out
]

# Which schema each table lives in.
SCHEMA = {t: "core" for t in SEED_TABLES + LOAD_ORDER}
SCHEMA["ground_truth"] = "eval"

# Tables that are derived rather than read from a CSV.
DERIVED = {"referrals", "referral_daily_stage"}

# The CSV filename for each table that has one.
def csv_name(table: str) -> str:
    if table == "referral_daily_stage":
        return "referral_daily.csv"
    return f"{table}.csv"
