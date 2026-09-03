# Re-apply KG database objects after a `make reset` in dataset/.
# 002 will error on CREATE ROLE if kg_loader survived; that error is harmless.
# The loader password is not in SQL — set it from kg/.env afterwards:
#   ALTER ROLE kg_loader PASSWORD '<KG_LOADER_PASSWORD>';

HERE := $(CURDIR)
DB := cd $(CURDIR)/../dataset && docker compose exec -T db psql -U triage_admin -d triage

.PHONY: kg-views
kg-views:
	$(DB) < $(HERE)/sql/001_v_referral_state.sql
	-$(DB) < $(HERE)/sql/002_kg_loader_role.sql
