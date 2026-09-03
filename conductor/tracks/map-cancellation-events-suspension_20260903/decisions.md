# Decisions — Map cancellation_events and suspension_events to RDF

## 1. wait_counters.rq's missing GRAPH clause: fix the test, not the fragment

**Decided**, confirmed with the user. `wait_counters.rq`'s own header describes it as a
fragment meant to be copied into a consuming query's `WHERE` clause — it deliberately has no
`GRAPH` wrapper of its own, leaving the graph context to whatever embeds it. The existing
test happened to pass because both the fragment (unwrapped) and its hand-built test data
(loaded into Oxigraph's default graph) agreed by coincidence, not by design. Once this
track's mapping produced real, correctly graph-tagged output (`…/kg/graph/inputs`, per
namespaces.md §5), that coincidence broke: the fragment matched nothing, and
`adjusted_wait_days` silently came back equal to `days_since_received` — no error, just a
wrong answer nobody would notice without comparing against `core.referral_daily` directly.

**Two options were on the table:**
1. Fix the test's methodology (load into the named graph, wrap the fragment in
   `GRAPH { … }`) — leaves `wait_counters.rq` exactly as designed.
2. Add a hardcoded `GRAPH <…/kg/graph/inputs> { … }` wrapper directly into
   `wait_counters.rq` — would make the file work standalone, but bakes in one specific graph
   name, which breaks the moment it's spliced into a query that's already inside a different
   `GRAPH` block (e.g., a rule check scoped to a run graph that also needs input-layer facts)
   or run against a store where the caller wants the default-graph union instead.

**Chosen: (1).** Confirmed empirically: wrapping the fragment where it's *used* — exactly
what its own header already instructs a consuming query to do — reproduces the correct
`adjusted_wait_days` (681, matching Postgres) without constraining how future consumers
embed it.

## 2. Both the hand-built and real-mapping test scenarios were updated

**Decided**, per the user's explicit choice. Leaving the pre-existing hand-built scenario on
its old default-graph methodology would have kept it passing for a reason that no longer
matches how the fragment is actually queried once real graph-tagged data exists — a
misleading "green" that would not have caught the same class of bug again. Both scenarios in
`kg/tests/test_wait_counters_sample.py` now load into `…/kg/graph/inputs` and wrap the
fragment identically.

## 3. The real-mapping test shells out to `morph_kgc`, not an in-process API call

`morph_kgc.materialize(config)` exists as an in-process API, but its `config` argument's
construction wasn't stable/simple enough to justify over the CLI, which the project already
uses everywhere else (`referral_state.ini`, `reference_layer.ini`, the Makefile). The test
writes a throwaway `.ini` (same directory convention as the git-ignored `mappings/*.ini`
files), shells out to `python -m morph_kgc`, reads the resulting `.nq`, and deletes both —
consistent with requirements.md §8's "materialise to files first" philosophy.
