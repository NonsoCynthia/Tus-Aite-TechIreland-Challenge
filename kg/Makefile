# Re-apply KG database objects after a `make reset` at the repo root.
# 002 will error on CREATE ROLE if kg_loader survived; that error is harmless.
# The loader password is not in SQL — set it from kg/.env afterwards:
#   ALTER ROLE kg_loader PASSWORD '<KG_LOADER_PASSWORD>';
#
# docker-compose.yml lives at the repo root (consolidated there alongside
# oxigraph and the retrieval service), not in dataset/ any more.

HERE := $(CURDIR)
DB := cd "$(CURDIR)/.." && docker compose exec -T db psql -U triage_admin -d triage

.PHONY: kg-views
kg-views:
	$(DB) < "$(HERE)/sql/001_v_referral_state.sql"
	-$(DB) < "$(HERE)/sql/002_kg_loader_role.sql"
