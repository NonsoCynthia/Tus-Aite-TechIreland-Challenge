.PHONY: up down migrate seed calibrate fetch load generate reset test verify logs psql volumes

# Which slice to generate: small (fast, ~200 referrals) or full (~5,200 referrals).
PROFILE ?= small
# Which slice to fetch from Hugging Face: sample (~1 MB) or full (~20 MB).
FETCH_PROFILE ?= sample

up:
	docker compose up -d db pgadmin
	@echo "Postgres on localhost:$${POSTGRES_PORT:-5433}"
	@echo "pgAdmin  on http://localhost:$${PGADMIN_PORT:-5050}"

down:
	docker compose down

migrate:
	docker compose run --rm loader python -m loader.load --migrate-only

seed:
	docker compose run --rm loader python -m loader.load --seeds-only

calibrate:
	docker compose run --rm loader python -m generator.calibrate

fetch:
	docker compose run --rm loader python -m loader.fetch --profile $(FETCH_PROFILE)

load: migrate seed fetch
	docker compose run --rm loader python -m loader.load

generate:
	docker compose run --rm loader python -m generator.generate --profile $(PROFILE)

# Shows exactly which volumes this project owns. Everything else on your machine
# is out of scope for every target in this file.
volumes:
	@echo "Volumes owned by this project (the only ones 'make reset' can remove):"
	@docker volume ls --filter label=com.docker.compose.project=triage_referral_data --format '  {{.Name}}'
	@echo "Total volumes on this machine (untouched by this project):"
	@docker volume ls -q | wc -l | xargs echo "  "

# `down -v` removes ONLY the volumes declared in docker-compose.yml, scoped to the
# pinned project name triage_referral_data. It never touches other projects.
# This project never runs `docker system prune` or `docker volume prune`.
reset:
	@echo "Removing only: triage_referral_data_db_data, triage_referral_data_pgadmin_data"
	docker compose down -v
	docker compose up -d db pgadmin
	sleep 5
	$(MAKE) load

test:
	docker compose run --rm loader pytest tests/ -v

verify:
	./scripts/verify_install.sh

logs:
	docker compose logs -f

psql:
	docker compose exec db psql -U $${POSTGRES_USER} -d $${POSTGRES_DB}
