# Building an Agent with Conductor

The process the coordinating agent was built with, written so the urgency, capacity and
rationale agents can follow the same path quickly.

This is a **process** document. What the coordinator decided is in
[`HOW_THE_COORDINATOR_WAS_BUILT.md`](HOW_THE_COORDINATOR_WAS_BUILT.md); how to run it is in
[`RUNNING_THE_COORDINATOR.md`](RUNNING_THE_COORDINATOR.md).

Assumes Conductor is already installed. If not, follow
[`../../conductor/conductor-setup-log.md`](../../conductor/conductor-setup-log.md) first — the plugin
commands only exist inside an interactive `claude` session started from the repo root.

---

## The shape of it

**Specification before code, and specification in git.** Every design question that gets
answered in your head becomes a decision nobody can reconstruct in a week. Every one written
into `decisions.md` becomes a decision a compliance reviewer can read. The coordinator
produced nine ADRs before and during a build of about 300 statements, and three of them
turned out to be questions for other people rather than answers.

The whole loop, per phase: **failing tests → implementation → four gates → mutation check →
manual verification recorded as observation → commit.**

---

## Step 1 — Set up the environment before anything else

```bash
conda create -n <agent> python=3.12 -y
conda activate <agent>
```

Not conda base. `kg/docs/GETTING_THE_GRAPH.md` warns that conda base conflicts with its own
`ruamel-yaml` and `pydantic`, and `pydantic` matters — you will import the retrieval
service's models.

Install from the retrieval service's requirements to start, then **freeze immediately** into
your own component's file:

```bash
pip install -r retrieval/requirements.txt -r retrieval/requirements-dev.txt
pip freeze > <agent>/requirements-dev.txt
```

That service pins floors (`pydantic>=2.9`), so resolving it tomorrow gives someone else a
different dependency set. Freeze what you actually ran.

Copy the shared configuration rather than inventing your own:

```bash
cp retrieval/ruff.toml   <agent>/ruff.toml     # 100 columns, py312
cp retrieval/mypy.ini    <agent>/mypy.ini      # disallow_untyped_defs
touch <agent>/__init__.py <agent>/app/__init__.py <agent>/tests/__init__.py
```

The top-level `__init__.py` matters. Without it mypy sees `<agent>/app/` as both `app` and
`<agent>.app` and refuses to check anything at all.

> **Known repo-wide disagreement:** `conductor/code_styleguides/python.md` says 80 columns;
> both `ruff.toml` files say 100. The formatter reads the `.toml`, so 100 wins in practice
> and your carefully wrapped 80-column lines will be unwrapped. Unresolved — worth settling
> as a team.

## Step 2 — Write the track before writing code

Five files in `conductor/tracks/<name>_<YYYYMMDD>/`:

| File | What it holds |
|---|---|
| `spec.md` | Overview, background, functional requirements, non-functional requirements, acceptance criteria, out of scope |
| `plan.md` | Phased tasks as `[ ]` checkboxes, each phase ending in a manual verification task |
| `decisions.md` | ADRs: date, status, context, decision, rationale, trade-off accepted |
| `index.md` | Narrative summary and current status |
| `metadata.json` | `track_id`, `type`, `status`, `description`, `created_at`, `updated_at` |

Match the existing tracks exactly — read `conductor/tracks/retrieval-service_20260904/` for
the format. Two things that are easy to get wrong: `status` accepts `pending`, `done` or
`superseded` (check with `grep -h '"status"' conductor/tracks/*/metadata.json | sort -u`),
and `conductor/tracks.md` needs a matching row in its Active Tracks table.

Commit the track on its own branch **before any code exists**:

```bash
git checkout -b <agent>
git add conductor/tracks/<name>_<date> conductor/tracks.md
git commit -m "conductor(<scope>): Add <name> track spec, plan and ADRs"
git push -u origin <agent>
```

Then start the session and let Conductor drive from the plan:

```bash
claude
```

```
Read conductor/tracks/<name>_<date>/ — spec.md, plan.md and decisions.md.
Then do task 1.1. Do not write any other code yet.
```

**One task per prompt.** The discipline is what makes Phase 1 work: its whole purpose is not
guessing at contracts, and the moment the session starts writing logic before the contracts
are pinned, the plan has stopped doing its job.

## Step 3 — Phase 1 is contracts, and nothing else

Read every enum, model and validator your agent will produce output against, **from the
source**, and record the exact values in `decisions.md`. For the coordinator that was
`EvidenceType`, `CitationRole` and `iri.validate_segment`.

Then **capture a real response as a committed fixture**:

```bash
curl -s -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/hospitals/9004/cohort/2026-08-30" \
  > <agent>/tests/fixtures/cohort_9004_2026-08-30.json
```

Read the token from the repo-root `.env`; never commit it, never print it. Write a
`fixtures/README.md` saying what the fixture contains and how to recapture it.

This step caught a real defect. See Step 6.

Where your output contract is wrong or missing, **build against what you are asking for and
let a test fail loudly** rather than working around it silently:

```python
def test_role_evidence_types_are_valid_evidence_types() -> None:
    """EXPECTED TO FAIL. Tracks an open change request (ADR-009).

    NOTE THE POLARITY: this test fails today and goes green when the
    change lands. Its mirror in test_decision.py passes today and goes
    red on the same event. One signal, not two problems.
    """
```

A deliberately failing test is a legitimate commit. Say in the docstring what a future
change of state *means*, in both directions — otherwise someone hits a red test on a green
day and does something unhelpful.

On the coordinator, this is not hypothetical: when ADR-009 landed, both tests flipped exactly
as their docstrings predicted — the tracking test went green, its mirror in `test_decision.py`
went red and was inverted to assert success. That is the evidence the technique works, not
just the theory of it.

## Step 4 — Per phase: tests first, then implementation

Two prompts per phase, never one.

```
Phase N of conductor/tracks/<name>_<date>/plan.md, tasks N.1 to N.x ONLY.
Write the tests. Do NOT implement — that is task N.y and these must fail first.
[the specific assertions, with the ADRs they enforce]
```

Run them. You want a clean `ModuleNotFoundError` at collection — that proves the tests exist
and nothing is implemented.

Before implementing, **read the interface the tests designed**:

```bash
grep -n "^from <agent>.app" -A 12 <agent>/tests/test_<module>.py
grep -n "^def test_" <agent>/tests/test_<module>.py
```

This is the cheapest moment to correct a bad shape. On the coordinator it caught that
`compute_scarcity` took the cohort rather than a referral, which is what ADR-005 required.

Then:

```
Task N.y. Implement <agent>/app/<module>.py so every test passes. Nothing
beyond what those tests require — that is Phase N+1.
[the ADRs it must honour]
Precise type annotations; mypy runs with disallow_untyped_defs.
```

## Step 5 — Run the four gates separately

```bash
python -m pytest <agent>/tests/ -q
ruff format --check <agent>/
ruff check <agent>/
python -m mypy --config-file <agent>/mypy.ini --explicit-package-bases <agent>
```

**Never chain them with `&&`.** With a deliberately failing test in the suite, pytest always
exits non-zero and everything after the first `&&` silently never runs. On the coordinator
this hid a broken mypy invocation for a whole phase — it was erroring out before checking a
single file, and the `&&` made that look like success.

Coverage per `conductor/workflow.md`: **Tier 1** (scoring, ranking, rule validation) 80%
enforced; **Tier 2** (clients, graph helpers) 60%; **Tier 3** (CLI, templates) no gate, one
smoke test.

```bash
python -m pytest <agent>/tests/ --cov=<agent>/app --cov-report=term-missing -q
```

Writing tests first means coverage is a byproduct rather than something you chase. The
coordinator reached 100% on all six Tier 1 modules without ever targeting it.

## Step 6 — Mutation-check the Tier 1 tests

100% coverage means every line executed, not that any behaviour is correct. Before trusting
a Tier 1 module, break it on purpose and confirm the right tests notice.

The coordinator's `SEVERITY_RANK` maps NTPF codes to clinical order — 1→1, **3→2**, **2→3** —
because the codes do not sort numerically. Swapping the last two reproduces the bug the
mapping exists to prevent:

```bash
git checkout <agent>/app/bands.py      # your undo — commit before mutating
# swap the two values, then:
python -m pytest <agent>/tests/test_bands.py -v
git checkout <agent>/app/bands.py      # revert
```

**Result: 2 failed, 3 passed.** The two tests that should catch it did; the three about tails
and drops correctly did not. That is the check passing. All five failing would mean the tests
are coupled; none failing would mean the test does not do what its name says.

You can only do this on a **committed** file — `git checkout` cannot revert something git has
never seen.

## Step 7 — Meet real data early, and expect it to disprove something

Two of the coordinator's three real findings came from this step, and neither would have
surfaced from unit tests.

**The str/int defect.** Phase 2's tests passed, coverage was 100%, the mutation check
succeeded — and the code was still broken. `SEVERITY_RANK` was keyed by `str` while the
endpoint returns `cpc` as `int` or `None`. The tests passed because their hand-built
fixtures made the same wrong assumption as the implementation. A test written from the same
assumption as the code verifies internal consistency, not truth. **At least one test per
module has to meet a real response.**

**The distribution defect.** Min–max normalisation of waiting time put the median referral at
0.18 in every band, so the weighting parameter had nothing to trade. Only visible by looking
at the actual per-band distribution:

```bash
python3 - <<'PY'
import json, collections
from pathlib import Path
rows = json.load(Path("<agent>/tests/fixtures/<fixture>.json").open())["referrals"]
by = collections.defaultdict(list)
for r in rows:
    by[r["cpc"]].append(r["adjusted_wait_days"])
for cpc in sorted(by, key=lambda c: (c is None, c)):
    w = sorted(by[cpc])
    print(f"cpc={cpc!s:>4} n={len(w):>3} min={w[0]:>3} "
          f"median={w[len(w)//2]:>3} max={w[-1]:>3}")
PY
```

Look at your data before fixing a formula in code.

## Step 8 — Record verifications as observation, not as claim

`conductor/workflow.md`: the implementer runs the phase's demo path and reports **what they
ran and what they observed** — not that it "should work". A phase is not complete until that
is confirmed.

The honest version names what was substituted. Every coordinator verification ran on
synthetic urgency and capacity scores, because those agents did not exist:

> *Caveat first: the fixture carries no real scores. `urgency_score` was
> `(hash(pathway_number) % 1000) / 1000` — a deterministic pseudo-random number, not a
> clinical judgement — and `capacity_score` was seven evenly-spread synthetic values by
> specialty. This verifies assembly mechanics only; it says nothing about hospital 9004's
> real priorities.*

Then flag what looks wrong rather than only confirming it ran. Reading the assembled
rationale text as a clinician would produced three fixes in one pass: floating-point noise
(`0.7000000000000001`) on screen, an internal weighting parameter printed as a bare number
nobody could act on, and a CRT breach described identically whether it was one day or eight
hundred.

## Step 9 — Raise what is not yours to decide

Three of the coordinator's ADRs are open, and all three are questions for other people:

- an undocumented sign convention owned by another agent's author
- a missing enum value in a service someone else maintains
- a ranking policy that needs a clinician, not an engineer

Each is recorded as an ADR with **status: open**, states what the code does meanwhile and
why, and says plainly that no output should be treated as final until it is answered.

`workflow.md` says the responsible-AI lead reviews each agent's output against CPC/CRT rules
**as soon as that agent produces output**, not on Day 6. When you have output, you have
triggered that review. Raising a policy question while the sort key is still cheap to change
is worth far more than defending it at a pitch.

When you raise something, bring a number from the repo. *"117 of 131 urgent referrals are
breached, so the other 14 sit at positions 118–131 regardless of urgency score"* lands; *"a
lot of them breach"* does not.

## Step 10 — Commit rhythm

`<type>(<scope>): <description>`, scopes from `workflow.md` — `urgency`, `capacity`,
`coordinator`, `rationale`, `compliance`, `graph`, `data`, `web`, `sim`, `conductor`.

Commit per completed task; push daily. With nine people on one repo, long-lived branches are
the main integration risk.

Put the *reasoning* in the body, not just the change:

```
feat(coordinator): Add scarcity, alpha and within-band priority

Scarcity computed once per decision at hospital level; capacity never
reorders within a band (ADR-005). Capacity direction is required
configuration with no default (ADR-007). wait_normalised is percentile
rank within band with mid-rank ties, not min-max (ADR-010).
```

At the end of each phase, update `plan.md` checkboxes, `index.md`'s status, `metadata.json`'s
`updated_at`, and the `tracks.md` row — in one commit with the verification note.

---

## Checklist

Per phase:

- [ ] Tests written and confirmed failing before any implementation
- [ ] Interface the tests designed reviewed before implementing
- [ ] Implementation does nothing beyond what the tests require
- [ ] Four gates run **separately**; mypy actually ran
- [ ] Tier 1 modules mutation-checked, with the failure counts recorded
- [ ] At least one test exercises a real captured response
- [ ] Manual verification recorded as observation, with substitutions named
- [ ] Anything not yours to decide raised as an open ADR, with a number attached
- [ ] `plan.md`, `index.md`, `metadata.json`, `tracks.md` updated
- [ ] Committed with reasoning in the body, and pushed
