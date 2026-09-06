# Conductor Setup Log, Explainable Agent Triage

This records everything done to get Conductor for Claude Code running on the
`explainable-agent-triage` repo, in order, so the rest of the team can reach
the same point on their own machines. Read this before you start, then follow
the "What you need to do" section at the bottom.

Repo: `NonsoCynthia/Tus-Aite-TechIreland-Challenge`
Branch: `explainable-agent-triage` (not yet merged to `main`, awaiting team
review)

**Two things to know before you start:**

- **The plugin creates its own branch automatically.** You do not need to
  create one by hand, when Conductor scaffolds its setup files, it commits
  them to a new branch named after the track or project rather than working
  directly on `main`. This is deliberate, it keeps the shared docs reviewable
  as a pull request before anyone merges them.
- **Every command below (both the `/plugin` and `/conductor:` ones) is typed
  inside the terminal**, specifically inside the interactive Claude Code
  session started by running `claude`. None of these are run in a browser,
  in the `conductor.build` app, or in a plain shell prompt, they only exist
  once you are inside that session. Section 2 below shows exactly how to get
  there.

---

## 1. Confirming Claude Code was installed correctly

```bash
claude --version
```

Output confirmed `2.1.237 (Claude Code)`. This step just verifies Claude Code
itself is present before touching the plugin, since a missing or outdated
Claude Code install is the most common reason plugin commands fail silently.

## 2. Starting an interactive session

```bash
claude
```

Run from inside the repo folder. This opens Claude Code's chat-style
interface, distinct from a normal terminal prompt, since plugin commands
(anything starting with `/`) only exist inside this interactive session.

On first run, Claude Code detected a custom API key in the environment and
asked for confirmation to use it. Selected **1. Yes**.

## 3. Checking for existing plugins

```
/plugin list
```

Output: `No plugins installed.` Confirmed nothing had been set up yet, so the
"unknown command" error seen earlier when trying `/conductor:newTrack` was
simply because the plugin was never installed, not a bug.

## 4. Adding the Conductor plugin marketplace

```
/plugin marketplace add rbarcante/claude-conductor
```

Output: `Successfully added marketplace: claude-conductor`. This step only
registers where the plugin can be found, it does not install it.

## 5. Installing the plugin itself

```
/plugin install conductor@claude-conductor
```

Output: `Installed conductor. Plugin is now active.`

## 6. Verifying installation

```
/plugin list
```

Output: `conductor@claude-conductor (v1.6.0, project) enabled`. Confirmed the
plugin was genuinely installed this time.

## 7. First attempt at a track (deliberately failed)

```
/conductor:newTrack "description of the track"
```

This was run with a literal placeholder rather than a real description, and
before any setup had been done. Conductor correctly refused, halting because:

- No `conductor/` framework docs existed yet (`product.md`, `tech-stack.md`,
  `workflow.md`)
- The track description was the literal placeholder text, not a real task

This confirmed the plugin works correctly, it will not fabricate a spec from
a missing or fake description.

## 8. Running project setup

```
/conductor:setup
```

Since the repo was near-empty (one commit, a 32-byte README), Conductor asked
scoping questions directly rather than inferring anything from existing code.

### Question 1: What does this repository cover?

| # | Option | Summary |
|---|--------|---------|
| 1 | Whole prototype | All seven components in one shared repo, tracks map to the day-by-day plan |
| 2 | Backend pipeline only | Data, graph, agents, API; UI lives in a separate repo |
| 3 | My component only | Single role's deliverable |
| 4 | Auto-generate | Infer and continue automatically |
| 5 | Type something | Free text |

**Selected: 1, Whole prototype.** Matches the nine-person, one-repo,
seven-track structure already agreed.

### Question 2: Which graph layer?

| # | Option | Summary |
|---|--------|---------|
| 1 | Fuseki in Docker | Matches proposal literally, mature, adds a JVM dependency |
| 2 | Oxigraph in Docker | Same SPARQL 1.1 protocol as Fuseki, lighter, swappable later |
| 3 | rdflib in-process | Pure Python, fastest to demo, weaker SPARQL performance at scale |
| 4 | Auto-generate | Infer and continue |
| 5 | Type something | Free text |

**Selected: 2, Oxigraph in Docker.** Same wire protocol as Fuseki means the
choice is reversible later without touching agent code, and it is faster to
start across nine laptops on Day 1.

### Question 3: How should the urgency and capacity agents reason?

| # | Option | Summary |
|---|--------|---------|
| 1 | Deterministic + LLM rationale | MTS/NEWS2/capacity logic is rule-based and auditable; LLM only writes the explanation |
| 2 | LLM agents end to end | Strongest fit with the challenge theme, but scores become non-reproducible |
| 3 | Fully deterministic | Maximally defensible, but weak against an "AI and Agents" challenge theme |
| 4 | Auto-generate | Infer and continue |
| 5 | Type something | Free text |

**Selected: 1, Deterministic + LLM rationale.** MTS and NEWS2 are published,
deterministic scoring systems in real clinical use, not judgement calls, and
this keeps every score reproducible for the validation pass in Week 1.

### Question 4: What should the clinician interface be?

| # | Option | Summary |
|---|--------|---------|
| 1 | React + FastAPI | Best-looking demo, but a separate repo boundary landing on Day 5 |
| 2 | Streamlit | Pure Python, fastest to write, weak at reorder/override interactions |
| 3 | HTMX + FastAPI | Server-rendered, one Python service, no build step |
| 4 | Auto-generate | Infer and continue |
| 5 | Type something | Free text |

**Selected: 3, HTMX + FastAPI.** Removes a cross-repo integration boundary
landing on the same day it needs to work, while still supporting real
accept/reorder/override interactions.

### Reviewed and submitted

All three answers above were shown together for confirmation, then submitted.

### Question 5: TDD coverage gate

| # | Option | Summary |
|---|--------|---------|
| 1 | TDD, tiered coverage | 80% on clinical scoring cores, relaxed elsewhere |
| 2 | Default TDD, 80% everywhere | Highest discipline, costs hours on templates and glue code |
| 3 | Tests after, no gate | Fastest, but leaves clinical scoring logic unverified |
| 4 | Type something | Free text |

**Selected: 1, TDD, tiered coverage.** Keeps rigorous testing where
correctness is the actual product (scoring, CPC/CRT validation), without
gating unrelated glue code at the same standard.

### Initial track proposal

Conductor proposed the Day 1 to Day 2 foundation track: OWL ontology,
Oxigraph bootstrap, and the HIPE/NTPF-calibrated synthetic referral
generator, ending with a seeded, queryable graph.

| # | Option | Summary |
|---|--------|---------|
| 1 | Approve foundation | Graph schema, ontology, generator, seeded Oxigraph, SPARQL round-trip proven |
| 2 | Foundation + bed sim | Also folds the SimPy bed occupancy queue into this track |
| 3 | Thin end-to-end slice | Narrowest path from one referral to one ranked, cited row |
| 4 | Type something | Free text |

**Selected: 2, Foundation + bed sim.** Matches the proposal's own team table,
which already assigns the synthetic dataset and the SimPy bed model to one
role, so splitting them across two tracks would only add coordination
overhead for work one person does anyway.

## 9. What setup generated

```
conductor/
├── product.md              # problem framing, buyer hierarchy, success criteria,
│                            # the MTS/ICTS/NEWS2/EMEWS + NTPF CPC-CRT landscape,
│                            # and the "rank and explain only" boundary
├── product-guidelines.md   # rationale-text rules, verb table, override-as-first-
│                            # class UI principles, synthetic-data labelling
├── tech-stack.md           # Python 3.12, Oxigraph, FastAPI + HTMX, three ADRs
├── workflow.md              # tiered TDD: 80% clinical scoring, 60% graph,
│                            # smoke-only on templates
├── tracks/
│   └── graph-foundation_20260826/   # spec, 6-phase plan (95 tasks), decisions
└── tracks.md                # active track plus the Day 3-7 pipeline mapped out
```

`.claude/` was deliberately left untracked (added to `.gitignore`), since it
holds plugin-local, machine-specific settings rather than shared project
configuration.

## 10. Committing and pushing

Rather than typing raw git commands, this was done by asking Claude Code
directly in plain language, inside the same session:

```
please commit and push what's been set up so far
```

Result: two commits pushed to a new remote branch.

```
fa270e5  chore: Enable conductor plugin for the project
408eabe  conductor(setup): Add conductor setup files and initial track
```

Branch `explainable-agent-triage` is now tracked against
`origin/explainable-agent-triage`. GitHub offered a pull request link, which
has deliberately **not** been opened or merged yet.

## 11. Current status

The branch is sitting ready for team review, not yet merged into `main`.
Decision made: wait until the team has looked over `product.md`,
`tech-stack.md`, `workflow.md`, and the foundation track's spec and plan
before merging, so any objections (particularly to the Oxigraph, HTMX, and
deterministic-scoring choices) surface now rather than mid-build.

---

## What you need to do, to reach the same point

1. Install Claude Code if you have not already (`npm install -g
   @anthropic-ai/claude-code`, or however your machine is set up, then
   confirm with `claude --version`)
2. Clone the repo and check out this branch:
   ```bash
   git clone https://github.com/NonsoCynthia/Tus-Aite-TechIreland-Challenge.git
   cd Tus-Aite-TechIreland-Challenge
   git checkout explainable-agent-triage
   ```
3. Start Claude Code from inside that folder: `claude`
4. Install the same plugin, so your commands match everyone else's:
   ```
   /plugin marketplace add rbarcante/claude-conductor
   /plugin install conductor@claude-conductor
   ```
5. Read through `conductor/product.md`, `conductor/tech-stack.md`,
   `conductor/workflow.md`, and `conductor/tracks/graph-foundation_20260826/`
   before we discuss it as a team
6. Come to the meeting with any objections to the decisions above, especially
   whether Phase 3's calibration configs should be split three ways so more
   of us have real work during the foundation track, rather than waiting on
   it
