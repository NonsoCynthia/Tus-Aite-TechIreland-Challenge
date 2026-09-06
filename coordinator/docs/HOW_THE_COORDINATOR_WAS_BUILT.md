# How the Coordinator Was Built

The tech stack and what each piece is for, the decisions taken before any ranking code was
written, three things the build disproved along the way, and what is still open.

Companion documents: [`RUNNING_THE_COORDINATOR.md`](RUNNING_THE_COORDINATOR.md) for setup,
[`BUILDING_AN_AGENT_WITH_CONDUCTOR.md`](BUILDING_AN_AGENT_WITH_CONDUCTOR.md) for the process
another agent author can follow,
[`../../conductor/tracks/coordinating-agent_20260906/`](../../conductor/tracks/coordinating-agent_20260906/)
for the normative specification. Where that track and this document disagree, the track
wins.

---

## 1. The tech stack

Every choice below is either inherited from
[`../../conductor/tech-stack.md`](../../conductor/tech-stack.md) or recorded as an ADR in
the track's `decisions.md`.

### What the coordinator is

It takes one hospital's cohort for one day, plus the urgency and capacity scores already
written for that run, and produces a ranked, evidence-cited, rule-checked `Decision`.

It **ranks and explains**. It does not admit, schedule, discharge, diagnose, or act on a
patient, and its output language avoids any verb implying it did
(`conductor/product-guidelines.md`). It is **deterministic end to end** — no LLM is involved
anywhere in this component, and identical inputs always produce byte-identical output. That
is a tested property (NFR4), not an assertion.

### Tools

| Tool | What it does here |
|---|---|
| **Python** | 3.12, in a dedicated environment. Conda base conflicts with its own `pydantic`, which matters because the service's models are imported |
| **httpx** | The only I/O. Three GETs and one POST against `retrieval-service_20260904` |
| **Pydantic v2** | Not as the coordinator's own models — as the service's, imported and validated against before anything is sent |
| **pytest** | 73 tests. Strict TDD on Tier 1 per `conductor/workflow.md` |
| **ruff** | Lint and format, config copied from `retrieval/ruff.toml` (100 columns) |
| **mypy** | `disallow_untyped_defs = True`, 18 files including the tests |
| **Conductor** | v1.6.0. Spec-driven development: `spec.md`, `plan.md` and `decisions.md` written and committed before any code existed |

### Contracts reused rather than reimplemented

| | Why |
|---|---|
| **`retrieval.app.schemas.DecisionIn`** | The payload is validated against the real model, imported from source. A payload that validates locally validates on the wire |
| **`EvidenceType` / `CitationRole`** | Read from source in Phase 1 and pinned by a test, rather than transcribed |
| **`core.ref_rules`** | Rule IDs and thresholds trace to the seed data, FK-enforced at the Postgres layer |
| **`core.ref_codes`** | `severity_rank` is asserted against it by a test, so a change to the national code table fails a test rather than silently reordering patients |
| **`crt_breached`** | Computed by the retrieval service and taken as given, never re-derived |

### Deliberately not used

**Direct Postgres or SPARQL access.** ADR-002 makes the retrieval service the single mediator
in both directions. The coordinator holds no database credentials at all.

**An LLM, anywhere.** Scoring and ranking are deterministic and unit-tested; only rationale
*prose* is LLM-generated, and that is a separate layer
(`explainable-agent-based-triage_20260828` FR4). This is a compliance decision, not a
technical one — it is what keeps every ranked position reproducible under the EU AI Act
framing the proposal cites.

**A weighted sum over urgency and capacity.** Rejected on methods grounds. See Decision 3.

**Min–max normalisation of waiting time.** Specified, built, measured, replaced. See §4.1.

**Retry or reconciliation after a `207`.** Detect and report only, per ADR-002.

**Re-deriving `crt_breached` or the wait counters.** Both already exist upstream; duplicating
the derivation is the divergence risk `tech-stack.md` Decisions 1 and 2 exist to prevent.

## 2. The decisions

Each was taken before the ranking code was written, because each changes what order patients
appear in. Full reasoning is in
[`../../conductor/tracks/coordinating-agent_20260906/decisions.md`](../../conductor/tracks/coordinating-agent_20260906/decisions.md)
as ADR-003 to ADR-011; this is the summary.

### 1. Order on `severity_rank`, never the raw NTPF code

`core.ref_codes` gives Urgent = 1, **Semi-Urgent = 3**, **Routine = 2**. Sorting a cohort on
`cpc` ascending places every routine referral above every semi-urgent one — silently, with
plausible-looking output, and passing a `RULE-ORDER` check written against the same wrong
key. The mapping (1 → 1, 3 → 2, 2 → 3, Excluded → none) is a module-level constant asserted
against `ref_codes` by a test. (ADR-003)

### 2. Clinical priority is a hard band; scores order within it

FR3 of the parent track specified CPC → CRT breach → oldest-first with no score in the chain,
while `RankingIn` makes both scores required fields. Read literally the scores are
decorative; read the other way a high-scoring semi-urgent referral could outrank a
low-scoring urgent one, which FR3's own final bullet and `RULE-ORDER` both forbid.

The resolution is the standard MCDA distinction. An additive weighted sum is *compensatory* —
a high score on one criterion offsets a low score on another — and is valid only under
preferential independence. Clinical priority and an operational score are not exchangeable
that way. Where trade-offs between criteria are not acceptable, non-compensatory techniques
are the appropriate family. So CPC is a boundary no score can cross, and `RULE-ORDER` cannot
fail by construction. (ADR-004)

### 3. Capacity modulates the weights, never an individual referral

The intent was that scarcer capacity should make urgency matter more. The obvious
implementation does not express that.

`capacity_score` is a property of a **specialty**, not a patient — constant within a
specialty, varying only across them. Putting it in the per-patient sort key has exactly one
effect: it reorders patients by which department referred them. If availability raises rank,
the system serves whoever is cheapest to serve. If scarcity raises rank, patients advance on
a system property they did not cause. Neither survives being said aloud to a patient.

Note also that *the importance of urgency depends on capacity* is an interaction between
criteria — and preferential independence is exactly what an additive model requires. The
intent as stated rules out the aggregation it appears to suggest.

So the interaction lives in the weights:

```
priority = α · urgency + (1 − α) · wait_normalised
α        = α_min + (α_max − α_min) · scarcity          # 0.5 + 0.4·scarcity
```

`scarcity` is computed **once per decision**, at hospital level, from the distinct specialty
capacity scores in the cohort, and is identical for every referral in it. This is the move
the scarce-resource-allocation literature makes: under crisis standards, allocation shifts
away from first-come-first-served toward clinical need as constraints tighten. It is one
sentence to a clinician — *the hospital is under pressure today, so clinical urgency is
weighted more heavily than waiting time across this whole list* — and no patient is
advantaged by their department.

α_min = 0.5 and α_max = 0.9 are `modelled` parameters in the dataset's own labelling sense:
deliberate choices with a stated reason. Urgency never counts for less than waiting time;
waiting time never leaves the ordering entirely.

**A consequence worth naming:** only the *mean* of the specialty capacity scores affects α.
One desperately overcrowded specialty among six comfortable ones gives the same α as six
uniformly middling ones. That is the price of the guarantee, and it was the point of it.
(ADR-005)

### 4. Two tails, never merged

`cpc: null` and Excluded (4) both lack a `severity_rank`. Both are ranked — never dropped —
after every categorised referral, as two distinguishable groups: uncategorised first,
Excluded last. Merging them would collapse *this pathway deliberately does not apply*
together with *nobody recorded a category*, and only the second is a defect someone must fix.
A triaged referral with no CPC has fallen through triage; one undifferentiated tail is how
that stays invisible. In the real 9004 cohort this is **95 of 500 referrals, 19% of the
list**. (ADR-006)

### 5. `wait_normalised` is percentile rank within band

Mid-rank for ties: `(count_less + count_equal / 2) / n`. Ties share a percentile, so rank
never depends on input order — the precondition for NFR4. Replaced min–max after measurement;
see §4.1. (ADR-010)

### The full sort key

```
(severity_rank, crt_breached desc, priority desc, referral_date asc, pathway_number asc)
```

`crt_breached` is three-valued (`True` > `False` > `None`) and handled by an explicit
`CRT_BREACHED_RANK` constant, because Python will not order `None` against `bool`.
`pathway_number` is last purely to guarantee a total order — `referral_date` ties are common.

## 3. How it was built, in order

Six phases, strict TDD on Tier 1 per `conductor/workflow.md`. The spec, plan and ADRs were
written and committed **before any code existed**.

| Phase | What landed |
|---|---|
| **1. Contracts** | `EvidenceType` and `CitationRole` read from source and recorded; the real 9004 cohort captured as a committed fixture; configuration object with the capacity direction required and no default |
| **2. Bands** | `severity_rank` resolution and the two tails. Mutation-checked (§6) |
| **3. Priority** | Scarcity, α, percentile-rank normalisation, and the test that capacity cannot reorder two referrals within a band |
| **4. Ranking** | The full sort key, three-valued breach handling, determinism under shuffling, and the CPC/CRT rule checks — including a test that `RULE-ORDER` *fails* on a deliberately mis-ordered list |
| **5. Decision** | Citation construction, `coordinator_version`, deterministic rationale text, payload assembly against the real `DecisionIn`, and all four response codes |
| **6. Surface** | CLI with `--dry-run`, smoke test, README, and the two tasks blocked on other people |

Two tasks remain open. **6.6**, the live end-to-end run, waits on the urgency and capacity
agents producing real scores — `agent.agent_scores` is still empty. **6.7**, the compliance
review, waits on the responsible-AI lead and has been requested.

## 4. Three things the build disproved

Each was an assumption written into the spec or the code. Each was checked against real data
and failed.

### 4.1 Min–max normalisation of waiting time does not discriminate

ADR-005 originally specified min–max normalisation of `adjusted_wait_days` within band. The
real 9004 cohort shows why that fails. Per band, min / median / max in days:

| Band | n | min | median | max |
|---|---|---|---|---|
| Urgent (cpc 1) | 131 | 0 | 158 | 849 |
| Routine (cpc 2) | 141 | 0 | 179 | 893 |
| Semi-Urgent (cpc 3) | 133 | 0 | 151 | 871 |
| Uncategorised | 95 | 0 | 135 | 887 |

Every band runs 0 to roughly 870 with a median near 150–180, so min–max puts the **median
referral at about 0.18** and compresses the bulk of the queue into the bottom fifth of the
range while a handful of 800-day referrals occupy the top. Urgency spans 0–1 while waiting
time effectively spans 0–0.3 for most patients.

That defeats α. Dial α down to weight fairness more heavily and it still will not matter,
because the variable being weighted has almost no spread where the patients are. ADR-005's
mechanism would have been decorative.

The skew is **by construction** — the generator draws from NTPF's published band
distribution, and `HOW_THE_DATA_WAS_MADE.md` treats matching that shape as the point. Min–max
is the wrong summary for a skewed variable: it measures distance from the single longest
waiter, so one outlier sets the scale for 140 others.

Replaced with percentile rank within band. The median lands at exactly 0.5 in all four bands
of the real fixture, α regains a full range to trade against, and the number is directly
explainable: *waited longer than 70% of others in their category*. Log-scaled min–max was the
runner-up, recorded as the rejected alternative — it keeps magnitude but produces a number no
clinician can state plainly.

### 4.2 Hand-built fixtures agreed with the implementation, and both were wrong

Phase 2's five band tests passed. Coverage was 100%. The mutation check succeeded. The code
was still broken.

`SEVERITY_RANK` was keyed by **string** (`"1"`, `"3"`, `"2"`) while the cohort endpoint
returns `cpc` as **`int` or `None`**. Band resolution would have raised `KeyError` on the
first live referral. The tests passed because their hand-built fixtures used string `cpc`
values — they encoded the same wrong assumption the implementation did.

Capturing the real cohort exposed it immediately. The lesson is narrow and worth stating: **a
test written from the same assumption as the code under test verifies the assumption's
internal consistency, not its truth.** Isolated cases still want hand-built inputs, but at
least one test per module has to meet a real response.

The fix re-keyed the constant to `int`. It did not coerce with `str(cpc)`, which would have
accepted `"03"` and `3.0` silently.

### 4.3 `EvidenceType` cannot express what a ranked placement cites

`retrieval.app.schemas.EvidenceType` is a closed `Literal` of five primary-input types:
`observation`, `condition`, `triage_event`, `bed_status`, `clinic_session`. That fits the
urgency and capacity agents, which reason over raw clinical and capacity data.

The coordinator does not. Its inputs are the cohort and the scores the other agents wrote, so
what a `RankedPlacement` genuinely cites is different in kind:

- **`urgency` role** — the honest evidence is the urgency `Score` node, not the observations
  behind it. Citing the observations instead loses the hop that says *which agent's judgement
  produced this position*.
- **`timeframe` role** — CRT breach drives ordering after the band, and no evidence type fits
  it. `triage_event` is the nearest and records when triage happened, not how long someone
  waited against their CRT. Citing it would be inaccurate, not merely imprecise.

Both IRI templates already exist — `conductor/kg/namespaces.md` defines `Score` and
`ReferralState`, and `retrieval/app/iri.py` builds both — so the gap is the `Literal`, not the
machinery. Roles and evidence types are independent axes in the service, which is how two of
the four roles ended up with no type that fits them.

A change request is open (ADR-009). Meanwhile `--legacy-citations` provides a working path,
and two tests track the request from opposite sides.

## 5. Known limitations

**5.1 No live end-to-end run has happened.** `agent.agent_scores` is empty; the urgency and
capacity agents are built in parallel. Every verification in this track used synthetic scores
and therefore checks ordering mechanics, never clinical output.

**5.2 Excluded referrals never occur in data `v1.1`.** `core.triage_events` contains only
categories 1 (1,248), 2 (1,586) and 3 (1,378) across 4,212 rows. The Excluded tail branch is
exercised only by hand-built fixtures. It is kept deliberately — `ref_codes` defines Excluded
as a real NTPF category and a regenerated dataset could contain one — but it has never met
real data. Do not delete it as dead code.

**5.3 Only the mean of the capacity scores affects the ranking.** Per Decision 3, and by
design; see the consequence noted there.

**5.4 `cli.py` is 64% covered.** Tier 3 has no coverage gate. What is untested is the printing
and exit-code plumbing; the branch selection behind it is tested through
`interpret_decision_response`.

**5.5 A `207` is detected and reported, never retried.** Postgres committed, the graph
projection failed, the row stands and the graph is behind. Out of scope per ADR-002.

**5.6 Three items are open.** See §7 — until they are resolved, no output should be treated
as final.

## 6. What is verified, and how

```bash
python -m pytest coordinator/tests/ -q
ruff format --check coordinator/
ruff check coordinator/
python -m mypy --config-file coordinator/mypy.ini --explicit-package-bases coordinator
python -m pytest coordinator/tests/ --cov=coordinator/app --cov-report=term-missing -q
```

Run **separately**, never chained with `&&` — pytest exits non-zero because of the
deliberately failing ADR-009 test, and everything after the first `&&` silently never runs.

| | Result |
|---|---|
| Tests | 73 total, 72 passing, **1 deliberately failing** |
| Tier 1 coverage | **100%** on `bands`, `citations`, `priority`, `ranking`, `rule_checks`, `decision` — against a Tier 1 gate of 80% |
| mypy | 18 files clean, `disallow_untyped_defs = True` |
| ruff | check and format both clean at 100 columns |

**Coverage is not the strong evidence.** 100% means every line executed, not that any
behaviour is correct. Two checks carry more weight:

**The mutation check.** Swapping `SEVERITY_RANK`'s 3 and 2 values reproduces the exact bug
ADR-003 exists to prevent. Result: **2 failed, 3 passed** — the two tests that should catch it
did, the three about tails and drops correctly did not. All five failing would mean the tests
are coupled; none failing would mean the test does not do what its name says.

**The negative rule tests.** `RULE-ORDER` and `RULE-TIEBREAK` cannot fail on real output, by
construction of the sort key. Tests assert they *do* fail on hand-built mis-ordered lists, so
the checks are shown to have teeth rather than passing vacuously.

Two numbers from the manual verifications, both on synthetic scores:

- Scarcity and α invert correctly across the two conventions: `availability` gives scarcity
  0.75 / α 0.80, `pressure` gives 0.25 / 0.60, summing to exactly 1.0.
- The default-citation payload fails `DecisionIn` validation with **1000 errors** across 500
  rankings — two per ranking, every one a `literal_error` on `evidence_type` naming `score`
  and `referral_state`, and nothing else complaining. That is ADR-009 diagnosed precisely
  rather than assumed.

## 7. What is still open

Three items, none of which is an engineering task. Each is recorded as an ADR with status
**open**, states what the code does meanwhile, and names what changes when it resolves.

### ADR-007 — the capacity sign convention

**Owned by:** the capacity agent's author.

**The risk:** read backwards, `scarcity` inverts, α inverts, and the system weights clinical
urgency *least* when the hospital is under most pressure — with every number in range and
every ranking plausible. No test catches that.

**Meanwhile:** `--capacity-direction` is required with no default; the agent refuses to start
without it, and the configured value is recorded in `coordinator_version` on every decision,
so any ranking ever written is traceable to the assumption it was made under.

**When answered:** record the convention in ADR-007 and set it as the documented default in
`RUNNING_THE_COORDINATOR.md` and the README. The flag stays required — an explicit choice
recorded per decision is worth keeping — but the guesswork disappears, and any decision
written under the wrong convention can be identified from its `coordinator_version` and
re-run. **No decision this agent writes should be treated as final until this is answered.**

### ADR-009 — the `EvidenceType` change request

**Owned by:** the retrieval service's author. Two values to add to a `Literal` plus their
segment lookups; the IRI machinery already exists.

**Meanwhile:** `--legacy-citations` copies the urgency agent's own citations for the
`urgency` role and omits `timeframe`, which validates today. The audit trail is one hop
shallower than it should be — it shows the vitals behind a position rather than the score
that produced it.

**When it lands:** two tests flip in opposite directions on the same event.
`test_citation_contract.py` goes green; `test_decision.py`'s
`test_assembled_payload_fails_real_decision_in_validation_today` goes red. Invert that second
assertion to require validation, drop the legacy companion test, remove `--legacy-citations`
from the documented invocation, close ADR-009, and re-run any decision written in legacy mode
so the audit trail cites the Score and ReferralState nodes directly.

### ADR-011 — CRT breach is a hard tier above clinical priority

**Owned by:** clinical and compliance review.

Because `crt_breached` sits above `priority` in the sort key, within a band every breached
referral outranks every non-breached one at any score. A patient with urgency 0.99 one day
inside their 28-day CRT ranks below one with urgency 0.05 one day past it, and α cannot
affect it.

This was never decided. FR3 specified the chain when scores were not in the ordering at all;
ADR-004 later inserted priority below breach and the question went unasked. The data makes it
acute: in the real 9004 cohort **117 of 131 urgent referrals are breached and 14 are not**, so
those 14 — the recent urgent referrals, plausibly including the acutely unwell — occupy
positions 118 to 131 regardless of urgency score. NTPF's published bands imply 91.2% breach the
28-day target, so this is not a quirk of one hospital-day.

**Meanwhile:** the code implements the hard tier, because that is what FR3 specifies.

**When decided,** one of three things happens:

1. *Keep the hard tier.* Nothing changes in code. ADR-011 closes as accepted, and the
   rationale text should say plainly that breach status is a tier rather than a factor, so
   the ordering is not mistaken for a clinical judgement.
2. *Fold breach magnitude into `priority`.* `crt_breached` leaves the sort key; days-over-CRT
   becomes a normalised term inside `priority` alongside urgency and waiting time. Phase 4's
   sort-key tests and Phase 3's priority tests both change, `RULE-ORDER` stays unaffected
   (CPC bands are untouched), and the α formula gains a third weight that needs its own ADR.
3. *Tier only beyond a margin.* `crt_breached` stays in the key but is computed as
   "breached by more than N days", with sub-margin breaches falling through to `priority`.
   Smallest change of the three: one constant, one predicate, and the existing three-valued
   handling still applies.

In all three cases the CLI gains no new flag — this is a policy fixed in code and recorded in
an ADR, not something an operator should be able to vary per run.
