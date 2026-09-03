# Decisions — Map the six capacity tables to RDF

## 1. `namespaces.md` §4's `BedStatus` template was wrong — corrected

**Found, not invented.** The template read
`bed-status/{hospital_hipe}/{ward_id}/{status_datetime}`; `core.bed_status` has no
`status_datetime` column — the real column is `snapshot_datetime`. This wasn't flagged as
needing confirmation the way `clinic_sessions` was, so it would have silently broken the
mapping (an R2RML template referencing a non-existent column errors at materialisation time,
not silently — but the fix still needed a decision on whether to also correct the doc).
**Confirmed with the user: fix `namespaces.md` too**, not just use the right column in the
mapping, since leaving the doc wrong would trip the next person who reads it before writing
code. `clinic_sessions`, by contrast, needed no correction — both `clinic_code` and
`session_date` are real columns, exactly as templated; its row was updated only to record
that the confirmation happened.

## 2. No `IS NOT NULL` filtered maps anywhere in this mapping

Not a judgement call — checked live. Every column across `hospitals`, `hospital_specialty`,
`wards`, `ward_specialty`, `bed_status`, and `clinic_sessions` is `NOT NULL` in the schema.
Every other mapping in this project (`referral_state`, `reference_layer`, `events`) needed
at least one filtered companion map for a nullable column; this one needed none. Recorded
here so a future reader doesn't wonder whether the omission was an oversight.
