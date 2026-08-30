# Tus-Aite-TechIreland-Challenge — dataset

A synthetic Irish hospital outpatient waiting list, and the pipeline that generates,
validates and publishes it. Built for the TechIreland National AI Challenge 2026.

**This branch is the data.** The agents, the graph layer and the clinician interface are
built on other branches and are not described here.

Every record is invented. No real patient, clinician or hospital appears anywhere in it,
and the hospital codes use a reserved range that matches no real facility.

## Get it running

```bash
cp .env.example .env      # add your Hugging Face token
make up                   # Postgres and pgAdmin
make load                 # download and load
```

You need Docker, a Hugging Face account and an invitation to the dataset — it is private.
Full setup in [docs/GETTING_THE_DATA.md](docs/GETTING_THE_DATA.md).

## Documentation

| | |
|---|---|
| [docs/GETTING_THE_DATA.md](docs/GETTING_THE_DATA.md) | **Start here.** Access, setup, loading, checking it worked |
| [docs/HOW_THE_DATA_WAS_MADE.md](docs/HOW_THE_DATA_WAS_MADE.md) | Sources, what was measured versus chosen, what the data disproved |
| [DATASET_README.md](DATASET_README.md) | What every table and column means. The specification. |

The original build specification is kept in [docs/BUILD_MANUAL.md](docs/BUILD_MANUAL.md)
and its [addendum](docs/BUILD_MANUAL_ADDENDUM.md); code comments cite them by section.

## What is in it

24 tables. 17 hold the input data, 7 are written by whatever consumes it, and one is a
held-out answer key that is never loaded. Six fictitious hospitals — four public with
waiting lists, two private that carry capacity but no queue.

The referral side follows the NTPF Outpatient Waiting List Minimum Data Set: real field
names, real code values, real rules. The clinical layer — conditions and observations — is
ours, because the national record contains no clinical detail at all. That absence is the
problem the dataset exists to illustrate.

Distributions are fitted from public sources rather than invented. Generation is
deterministic: the same seed produces byte-identical output, checked at both profiles.

## How it is versioned

Three things move separately and `versions.yml` pins them together: the schema as numbered
migrations in git, the data as tagged releases on Hugging Face, and the code. Nothing
fetches "latest".
