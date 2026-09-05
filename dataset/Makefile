# Compatibility shim. docker-compose.yml (previously dataset/docker-compose.yml)
# was consolidated into the repo-root docker-compose.yml alongside oxigraph and
# the retrieval service, so every target below now runs at the root -- this
# file just forwards `make <target>` from inside dataset/ so existing habits
# (`cd dataset && make up`) keep working. See the root Makefile for the actual
# logic and ../docker-compose.yml for the merged service definitions.

PROFILE ?= small
FETCH_PROFILE ?= sample

.PHONY: up down migrate seed calibrate fetch load generate reset test dataset-test logs psql volumes verify

up down migrate seed calibrate fetch load generate reset logs psql volumes:
	$(MAKE) -C .. $@ PROFILE=$(PROFILE) FETCH_PROFILE=$(FETCH_PROFILE)

test dataset-test:
	$(MAKE) -C .. dataset-test

verify:
	./scripts/verify_install.sh
