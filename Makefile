# Top-level orchestration for the whole stack: Postgres + pgAdmin (dataset),
# the knowledge graph build (kg), Oxigraph, and the retrieval service --
# everything docker-compose.yml at this level defines.
#
# This delegates to dataset/ and kg/ for the logic that actually lives there
# (the Python loader/generator, the SQL views, the R2RML mappings) rather than
# reimplementing it -- see dataset/Makefile and kg/Makefile for what each
# target actually runs.

-include .env
export

PROFILE ?= small
FETCH_PROFILE ?= sample
HOSPITAL ?= 9001
AS_OF ?= 2026-08-30
RUN_ID ?= run-local-001
PATHWAY ?=
DEMO_PATHWAY ?= PW-$(HOSPITAL)-000007
CAPACITY_DIRECTION ?= pressure
RATIONALE_STYLE ?= technical
RATIONALE_ENGINE ?= deterministic
TOP_K ?= 10
BENCHMARK_FORMAT ?= text
EVALUATION_FORMAT ?= text

.PHONY: up down build migrate seed fetch load generate calibrate verify \
        kg-views retrieval-build retrieval-test retrieval-lint retrieval-typecheck \
        urgency-run capacity-run coordinator-run rationale-build rationale-run \
        rationale-api-up rationale-api-down rationale-test rationale-lint \
        rationale-typecheck rationale-check demo-run \
        agent-benchmark kg-audit evaluation-suite evaluation-run evaluation-test \
        orchestrator-run orchestrator-ask orchestrator-chat \
        orchestrator-test orchestrator-lint orchestrator-typecheck orchestrator-check \
        dataset-test test reset psql logs volumes

## --- Bring the stack up ---

up:
	docker compose up -d db pgadmin oxigraph retrieval
	@echo "Postgres   on localhost:$${POSTGRES_PORT:-5433}"
	@echo "pgAdmin    on http://localhost:$${PGADMIN_PORT:-5050}"
	@echo "Oxigraph   on http://localhost:7878"
	@echo "Retrieval  on http://localhost:$${RETRIEVAL_PORT:-8000}"

down:
	docker compose down

build:
	docker compose build loader retrieval rationale

## --- Dataset: Postgres load pipeline (see dataset/loader/) ---

migrate:
	docker compose run --rm loader python -m loader.load --migrate-only

seed:
	docker compose run --rm loader python -m loader.load --seeds-only

fetch:
	docker compose run --rm loader python -m loader.fetch --profile $(FETCH_PROFILE)

load: migrate seed fetch
	docker compose run --rm loader python -m loader.load --profile $(FETCH_PROFILE)

generate:
	docker compose run --rm loader python -m generator.generate --profile $(PROFILE)

calibrate:
	docker compose run --rm loader python -m generator.calibrate

verify:
	cd dataset && ./scripts/verify_install.sh

## --- Knowledge graph: database objects (mapping/build steps stay manual,
## see kg/docs/GETTING_THE_GRAPH.md -- Morph-KGC and pySHACL run on the host,
## not in a container, so there's nothing this target can safely automate) ---

kg-views:
	$(MAKE) -C kg kg-views

## --- Retrieval service ---

retrieval-build:
	docker compose build retrieval

retrieval-test:
	docker compose run --rm retrieval pytest tests/ -v

retrieval-lint:
	docker compose run --rm retrieval ruff check .

retrieval-typecheck:
	docker compose run --rm retrieval mypy app

## --- Agent CLI jobs ---

urgency-run:
	docker run --rm \
		--network container:triage_retrieval \
		--env-file .env \
		-v "$(CURDIR):/app" \
		-w /app \
		python:3.12-slim \
		sh -lc "pip install -q -r urgency-agent/requirements.txt && PYTHONPATH=urgency-agent python -m urgency_agent --hospital $(HOSPITAL) --as-of-date $(AS_OF) --run-id $(RUN_ID)"

capacity-run:
	docker run --rm \
		--network container:triage_retrieval \
		--env-file .env \
		-v "$(CURDIR):/app" \
		-w /app \
		python:3.12-slim \
		sh -lc "pip install -q -r capacity-agent/requirements.txt && PYTHONPATH=capacity-agent python -m capacity_agent --hospital $(HOSPITAL) --as-of-date $(AS_OF) --run-id $(RUN_ID)"

coordinator-run:
	docker run --rm \
		--network container:triage_retrieval \
		--env-file .env \
		-v "$(CURDIR):/app" \
		-w /app \
		python:3.12-slim \
		sh -lc "pip install -q -r coordinator/requirements-dev.txt && python -m coordinator --hospital $(HOSPITAL) --as-of $(AS_OF) --run-id $(RUN_ID) --capacity-direction $(CAPACITY_DIRECTION)"

## --- Rationale CLI ---

rationale-build:
	docker compose build rationale

rationale-api-up:
	docker compose up -d rationale-api

rationale-api-down:
	docker compose rm -f -s rationale-api

rationale-run:
	docker compose run --rm rationale \
		--hospital $(HOSPITAL) \
		--as-of $(AS_OF) \
		$(if $(PATHWAY),--pathway $(PATHWAY),) \
		--style $(RATIONALE_STYLE) \
		--engine $(RATIONALE_ENGINE)

rationale-test:
	docker run --rm \
		-v "$(CURDIR):/app" \
		-w /app \
		python:3.12-slim \
		sh -lc "pip install -q -r rationale/requirements-dev.txt && python -m pytest rationale/tests/ -q"

rationale-lint:
	docker run --rm \
		-v "$(CURDIR):/app" \
		-w /app \
		python:3.12-slim \
		sh -lc "pip install -q -r rationale/requirements-dev.txt && python -m ruff check --config rationale/ruff.toml rationale/"

rationale-typecheck:
	docker run --rm \
		-v "$(CURDIR):/app" \
		-w /app \
		python:3.12-slim \
		sh -lc "pip install -q -r rationale/requirements-dev.txt && python -m mypy --config-file rationale/mypy.ini rationale"

rationale-check: rationale-test rationale-lint rationale-typecheck

demo-run: urgency-run capacity-run coordinator-run
	$(MAKE) rationale-run \
		HOSPITAL=$(HOSPITAL) \
		AS_OF=$(AS_OF) \
		PATHWAY=$(if $(PATHWAY),$(PATHWAY),$(DEMO_PATHWAY)) \
		RATIONALE_STYLE=$(RATIONALE_STYLE) \
		RATIONALE_ENGINE=$(RATIONALE_ENGINE)

## --- Agent benchmark + outcome evaluation ---

agent-benchmark:
	docker run --rm \
		-v "$(CURDIR):/app" \
		-w /app \
		python:3.12-slim \
		sh -lc "pip install -q -r evaluation/requirements.txt && PYTHONPATH=urgency-agent:capacity-agent:coordinator:. python -m evaluation.agent_benchmark --format $(BENCHMARK_FORMAT)"

kg-audit:
	docker run --rm \
		-v "$(CURDIR):/app" \
		-w /app \
		python:3.12-slim \
		sh -lc "pip install -q -r evaluation/requirements.txt && PYTHONPATH=urgency-agent:capacity-agent:coordinator:. python -m evaluation.kg_audit --format $(EVALUATION_FORMAT)"

evaluation-suite:
	docker run --rm \
		-v "$(CURDIR):/app" \
		-w /app \
		python:3.12-slim \
		sh -lc "pip install -q -r evaluation/requirements.txt && PYTHONPATH=urgency-agent:capacity-agent:coordinator:. python -m evaluation.suite --format $(EVALUATION_FORMAT)"

evaluation-run:
	docker run --rm \
		--env-file .env \
		-v "$(CURDIR):/app" \
		-w /app \
		python:3.12-slim \
		sh -lc "pip install -q -r evaluation/requirements.txt && EVALUATOR_DB_URL=postgresql://$${POSTGRES_USER}:$${POSTGRES_PASSWORD}@host.docker.internal:$${POSTGRES_PORT}/$${POSTGRES_DB} python -m evaluation.cli --decision-id $(DECISION_ID) --top-k $(TOP_K)"

evaluation-test:
	docker run --rm \
		-v "$(CURDIR):/app" \
		-w /app \
		python:3.12-slim \
		sh -lc "pip install -q -r evaluation/requirements-dev.txt && PYTHONPATH=urgency-agent:capacity-agent:coordinator:. python -m pytest evaluation/tests/ -q"

## --- Orchestrator agent (tool-calling: urgency -> capacity -> coordinator ->
## rationale, orchestrator-agent/README.md) ---
##
## Runs on the HOST, not in a container: its tools shell out to the
## *-run targets above, which themselves manage Docker -- containerising the
## agent too would need Docker-in-Docker for no real benefit. Requires
## `python3.12`, `make`, and OPENAI_API_KEY set (root .env).

orchestrator-run:
	cd orchestrator-agent && \
	  ( [ -d .venv ] || python3.12 -m venv .venv ) && \
	  .venv/bin/pip install -q -r requirements.txt && \
	  .venv/bin/python -m orchestrator_agent run \
	    --hospital $(HOSPITAL) --as-of-date $(AS_OF) --run-id $(RUN_ID)

## Q&A mode: `make orchestrator-ask QUESTION="why is PW-1 ranked here?"`
orchestrator-ask:
	cd orchestrator-agent && \
	  ( [ -d .venv ] || python3.12 -m venv .venv ) && \
	  .venv/bin/pip install -q -r requirements.txt && \
	  .venv/bin/python -m orchestrator_agent ask "$(QUESTION)"

## Interactive Q&A session -- run this one directly, not through a pipe.
orchestrator-chat:
	cd orchestrator-agent && \
	  ( [ -d .venv ] || python3.12 -m venv .venv ) && \
	  .venv/bin/pip install -q -r requirements.txt && \
	  .venv/bin/python -m orchestrator_agent chat

orchestrator-test:
	docker run --rm \
		-v "$(CURDIR):/app" \
		-w /app \
		python:3.12-slim \
		sh -lc "pip install -q -r orchestrator-agent/requirements-dev.txt && PYTHONPATH=orchestrator-agent:rationale python -m pytest orchestrator-agent/tests/ -q"

orchestrator-lint:
	docker run --rm \
		-v "$(CURDIR):/app" \
		-w /app \
		python:3.12-slim \
		sh -lc "pip install -q -r orchestrator-agent/requirements-dev.txt && python -m ruff check --config orchestrator-agent/ruff.toml orchestrator-agent/"

orchestrator-typecheck:
	docker run --rm \
		-v "$(CURDIR):/app" \
		-w /app \
		python:3.12-slim \
		sh -lc "pip install -q -r orchestrator-agent/requirements-dev.txt && python -m mypy --config-file orchestrator-agent/mypy.ini orchestrator-agent"

orchestrator-check: orchestrator-test orchestrator-lint orchestrator-typecheck

## --- Everything ---

dataset-test:
	docker compose run --rm loader pytest tests/ -v

test: dataset-test retrieval-test rationale-test

# Scoped to db + pgadmin's own named volumes only -- this project also owns
# oxigraph_data, which a blanket `docker compose down -v` would remove too.
# `rm -s` stops and removes just these two service containers; volumes are
# then removed explicitly by name.
reset:
	@echo "Removing only: triage_referral_data_db_data, triage_referral_data_pgadmin_data"
	docker compose rm -f -s db pgadmin
	-docker volume rm triage_referral_data_db_data triage_referral_data_pgadmin_data
	docker compose up -d db pgadmin
	sleep 5
	$(MAKE) load

psql:
	docker compose exec db psql -U $${POSTGRES_USER} -d $${POSTGRES_DB}

logs:
	docker compose logs -f

volumes:
	@echo "Volumes owned by this project (the only ones 'make reset' can touch):"
	@docker volume ls --filter label=com.docker.compose.project=triage_referral_data --format '  {{.Name}}'
	@echo "Total volumes on this machine (untouched by this project):"
	@docker volume ls -q | wc -l | xargs echo "  "
