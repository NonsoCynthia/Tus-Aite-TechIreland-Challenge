"""Gets the dataset from Hugging Face into Postgres.

Reads:  versions.yml (which tagged release to pull), data/<profile>/*.csv,
        db/migrations/*.sql and db/seeds/*.csv.
Writes: the core and eval schemas in Postgres.

`loader.fetch` downloads, `loader.load` applies migrations and loads. Both are
wrapped by the Makefile as `make fetch` and `make load`.
"""
