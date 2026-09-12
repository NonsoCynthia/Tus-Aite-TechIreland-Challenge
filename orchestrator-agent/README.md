# Triage Orchestrator + Rationale Agent

A genuine OpenAI Agents SDK tool-calling loop that runs the known-correct pipeline --
urgency, then capacity, then the coordinator, then rationale -- and narrates the result
in plain language. See `conductor/tracks/explainable-agent-based-triage_20260828/decisions.md`
ADR-011 for the design reasoning and how this differs from (and complements) the
deterministic `orchestrator/`+`web/` demo pipeline on the `ui` branch.

## What it is, and isn't

This agent **executes a fixed sequence**, it does not discover one. Coordinator ranking
always needs urgency + capacity scores first; there is no real decision to make about
order, so the system prompt states it explicitly rather than asking the model to infer
it. What the agent actually contributes:

- A single conversational entry point for a sequence a human would otherwise run as
  four separate commands.
- Turning each step's raw CLI output into a plain-language summary, including
  exclusions/skips a script would just log (paediatric refusals, missing-evidence
  skips, a `207` partial failure) -- explained, not just logged.
- The rationale step itself: OpenAI-generated, evidence-grounded prose per ranked
  placement (rationale/'s `llm` engine, ADR-010).

**The one hard boundary:** every tool either *triggers* one of the existing
deterministic packages exactly as its own CLI already runs it, or *reads* what a
package already wrote. No tool lets the model compute a score, reorder a ranking, or
invent a citation -- see `tools.py`'s own module docstring.

## Layout

```
orchestrator_agent/
  tools.py      Plain, undecorated Python functions -- the actual tool logic.
                 Directly unit-testable, no SDK/network/API key needed.
  agent.py       Wraps tools.py's functions with `function_tool` and builds the
                 Agent with fixed-order instructions. The one place the `agents`
                 SDK dependency is required at import time.
  run.py          run_pipeline() -- the orchestration entrypoint, real SDK call
                 isolated behind an injectable runner (mirrors rationale/llm_render.py).
  config.py       Settings: OPENAI_API_KEY / OPENAI_MODEL, read from root .env.
  __main__.py     CLI: `python -m orchestrator_agent --hospital ... --as-of-date ... --run-id ...`
tests/
  test_tools.py    every tool's wiring, mocked subprocess/rationale calls
  test_config.py   settings loading
  test_agent.py    tool list / instructions, structural checks
  test_run.py      prompt composition + API-key guard, via an injected fake runner
  test_main.py     CLI argument parsing + missing-key guard
```

## The four tools

| Tool | What it does |
|---|---|
| `run_urgency_agent(hospital, as_of_date, run_id)` | `make urgency-run` -- NEWS2 scoring |
| `run_capacity_agent(hospital, as_of_date, run_id)` | `make capacity-run` -- ward/clinic pressure scoring |
| `run_coordinator(hospital, as_of_date, run_id, capacity_direction="pressure")` | `make coordinator-run` -- ranking + Decision write-back |
| `generate_rationale(hospital, as_of_date, style="clinician", limit=5)` | Fetches the Decision's cited evidence and renders rationale per placement via `rationale.llm_render` (ADR-010) |

The three trigger tools shell out to the **same root Makefile targets** a human
operator already runs by hand -- unchanged, no duplicated execution logic. `make`
owns how each one actually runs (Docker, network, env); this package has no opinion
on that and doesn't need to change if the team's execution strategy does.

`generate_rationale` imports `rationale` directly (the repo root is added to
`sys.path` at import time, the same `PYTHONPATH=<package>` convention the Makefile
itself already uses for every sibling package) rather than re-implementing evidence
fetching or rendering -- it calls the already citation-IRI-guardrailed
`render_rationale_llm` exactly as `rationale/`'s own CLI does.

## Running

**Runs on the host, not in a container.** Its trigger tools shell out to `make
*-run`, which itself manages Docker (`--network container:triage_retrieval`, its own
`pip install` per run) -- containerising this agent too would need Docker-in-Docker
for no real benefit. Requires Python 3.12, `make`, and `OPENAI_API_KEY` set in the
root `.env`.

```bash
cd orchestrator-agent
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt

pytest            # unit tests -- no infra, no key, no `agents` calls
ruff check --config ruff.toml .
mypy --config-file mypy.ini .
```

Run the full pipeline (needs `make up` + `make load` already done from the repo
root, and `triage_retrieval` reachable):

```bash
python -m orchestrator_agent --hospital 9001 --as-of-date 2026-08-30 --run-id run-0001
```

Or from the repo root:

```bash
make orchestrator-run HOSPITAL=9001 AS_OF=2026-08-30 RUN_ID=run-0001
```

`make orchestrator-test` / `orchestrator-lint` / `orchestrator-typecheck` /
`orchestrator-check` run the test suite in an isolated container (these never touch
real infra -- every SDK/subprocess/network boundary is mocked).

## Verification

- 25 tests, all passing without network/API key/`make` -- every tool's `make`
  invocation, `generate_rationale`'s wiring into `rationale`, and `run_pipeline`'s
  prompt composition and API-key guard are exercised through injected fakes. `ruff`
  and `mypy` clean.
- **Verified against a real OpenAI call**, not just mocked: ran the full agent with
  `subprocess.run` and `generate_rationale` faked to return realistic CLI output
  (no live infra touched). The model independently chose the correct tool-call
  sequence (`run_urgency_agent` -> `run_capacity_agent` -> `run_coordinator` ->
  `generate_rationale`) and produced a narrative that correctly stated "decision
  support only... clinical sign-off is required" without being fed that exact
  phrase in the tool outputs -- confirming the instructions actually constrain the
  model's summary, not just its tool selection.
