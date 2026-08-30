# Hugging Face Access

How to get at the dataset, and how access is managed.

The dataset lives at **`Thabang/irish-referral-prioritisation`** and is **private**.

---

## Why it is private

Two reasons, and both will change before they stop applying:

1. **The data will change again** before the challenge deadline. A dataset that is
   published and then superseded cannot be cleanly unpublished — people have already
   downloaded it, and links keep working.
2. **No licence has been chosen.** Until one is, the terms under which anyone could use
   it are undefined.

Neither reason is about privacy. Every record is synthetic and there is nothing
confidential in it.

---

## Getting access — two steps

### Step 1. The owner invites you

Ask **Thabang** to add you. What they do:

1. Open the dataset page: `https://huggingface.co/datasets/Thabang/irish-referral-prioritisation`
2. **Settings** → **Collaborators**
3. Add by Hugging Face **username**, with **read** access

Read is enough. Nobody except the person publishing new versions needs write.

You will get an email. You can check it worked by opening the dataset URL — if you can
see the page rather than a 404, you are in.

### Step 2. You create your own token

**Every person creates their own token. Do not use somebody else's.**

1. Go to [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens)
2. **New token**
3. Type: **Read**
4. Name: something identifiable, such as `triage-dataset-read`
5. **Create**, then copy it. Hugging Face shows it once.

Put it in your own `.env`, on the `HF_TOKEN` line:

```
HF_TOKEN=hf_PASTE_YOUR_OWN_READ_TOKEN_HERE
```

(The placeholder above is deliberately not token-shaped. A realistic-looking dummy trips
GitHub's secret scanning and every alert people learn to ignore makes the real one less
likely to be noticed.)

`.env` is git-ignored, so it will not be committed.

---

## Never share one token between people

This matters more than it sounds.

A token is a password that identifies **you**. If the team passes one around:

- It ends up pasted into a commit, a Slack message or a screenshot. Not through
  carelessness — through nine people and seven days.
- When it leaks, it cannot be revoked for one person. Revoking it breaks **everyone**,
  at whatever moment you discover the leak.
- Nothing in the access log distinguishes who did what.

Individual tokens cost thirty seconds each and remove all three problems. A person
leaving the project means deleting one token; nobody else notices.

**If a token does leak:** delete it at
[huggingface.co/settings/tokens](https://huggingface.co/settings/tokens) immediately and
create a new one. Deleting is instant and only affects you.

---

## What failure looks like

If `HF_TOKEN` is missing, wrong, or you have not been invited, `make load` stops at the
fetch step with something like:

```
Could not read Thabang/irish-referral-prioritisation @ v1.0.
  RepositoryNotFoundError: 401 Client Error. Repository Not Found for url: ...

If the dataset is private, set HF_TOKEN in your .env and re-run.
Not falling back to local generation -- data that quietly differs between
team members is worse than no data.
```

A private repository you cannot see returns **404 / Repository Not Found**, not "access
denied" — Hugging Face does not confirm that a private repo exists. So the same message
covers three different causes:

| Cause | How to tell |
|---|---|
| No `HF_TOKEN` in `.env` | `grep HF_TOKEN .env` shows an empty value |
| Wrong or deleted token | Open the dataset URL in a browser while logged in — if that works, the token is the problem |
| Not invited yet | The dataset URL shows 404 in your browser too |

The fetch **will not** fall back to generating data locally. That is deliberate: two team
members silently holding different data is far harder to notice than a download that
failed, and much worse when someone presents a result from it.

---

## Making this public later

Going public would remove the token step entirely. Nobody would need an invitation, a
token, or an `HF_TOKEN` line — `make load` would just work.

There is **no privacy barrier** to doing it. The data is wholly synthetic: no real
patient, clinician or hospital, and hospital codes in a reserved range that matches no
real facility.

It needs two decisions first, and both belong to the project owner:

1. **Freeze the data version.** Public means permanent in practice. Publish when the
   schema and the generator have stopped moving.
2. **Choose a licence.** None is declared at present, so the dataset is
   all-rights-reserved by default. `CC-BY-4.0` would be the conventional choice for
   synthetic research data, but it is a decision, not a default.

**Neither decision has been made.** Until they are, it stays private.

---

## Publishing a new version

For whoever holds write access. After `make test` passes:

```bash
python scripts/make_sample.py                    # rebuild the sample from out/
HF_TOKEN=<write-token> python scripts/publish_to_hf.py
```

Then bump `hf_revision` in `versions.yml` and open a pull request rather than pushing
straight to the branch. A data change should be visible to the team before it lands.

The revision in `versions.yml` is a **tag**, never a branch. `main` or `latest` would
mean two people running the same command on different days get different data, and
neither would know.
