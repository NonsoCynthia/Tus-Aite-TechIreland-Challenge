# Calibration Findings

What we learned fitting the generator to real data, including three assumptions in
the build manual that the data falsified.

Companion documents: `DATASET_README.md` (what the data means),
`generator/calibration/` (the fitted parameters themselves).

---

## Contents

1. [Does an early warning score identify referral urgency?](#1-does-an-early-warning-score-identify-referral-urgency)
2. [What replaced the correlation band](#2-what-replaced-the-correlation-band)
3. [The Routine category has two patients in it](#3-the-routine-category-has-two-patients-in-it)
4. [Irish urgent referrals breach their timeframe almost always](#4-irish-urgent-referrals-breach-their-timeframe-almost-always)
5. [Three data-quality problems in the source](#5-three-data-quality-problems-in-the-source)
6. [Provenance split](#6-provenance-split)

---

## 1. Does an early warning score identify referral urgency?

**No. That is the headline finding, and it supports the project rather than damaging it.**

**Question.** The build manual required the correlation between `news2` and
`severity_rank` to land between 0.35 and 0.65, as a guard rail on a fitted
distribution.

**Method.** Fitted vitals distributions from 207 MIMIC-IV-ED Demo stays with a
recorded acuity, then swept the one free parameter, `coupling_coefficient`, across
0.3 to 5.0 and measured the resulting correlation at each point.

**Result.**

| coupling | \|r\| |
|---|---|
| 0.4 | 0.154 |
| 0.6 | 0.190 |
| 1.0 (full measured separation) | 0.239 |
| 1.5 | **0.253 — peak** |
| 3.0 | 0.105 |
| 5.0 (5x amplification, absurd) | 0.295 |

The band was unreachable at every value, including values above 1.0 that would
amplify beyond MIMIC's own measured separation.

Separately, of the highest-acuity MIMIC patients, **54 to 59 per cent score
`news2 <= 2`**, and the best possible rule based on `news2` alone recovers the
triage category only **17.5 percentage points** better than guessing the most
common category (55.7 per cent against a 38.2 per cent baseline).

**Interpretation.** This is a documented property of the instruments, not a defect
in the fit. NEWS2 was designed to detect deterioration in admitted ward patients
over time. ESI acuity is driven largely by predicted resource use and presenting
complaint. They measure different things, and most emergency department patients
score low regardless of acuity.

**Consequence for this project.** `DATASET_README.md` section 7.6 already asserts
that vitals alone do not tell you who is urgent. That was a design claim. It now has
measured backing from real triage data. It also means an urgency agent reasoning
only over vitals would perform poorly, which is exactly why the agent must also read
condition, referral pathway, referral source and the high-needs flag.

---

## 2. What replaced the correlation band

The band was falsified, and it was also measuring the wrong quantity.

A correlation between `news2` and `severity_rank` asks whether vitals predict
**which category** a patient is in. This system never assigns categories. Triage
assigns them, and `RULE-ORDER` forbids ever crossing a category boundary. The system
orders patients **within** a category. A between-category correlation is the wrong
guard rail for a within-category ranker.

It is also not a circularity check, which is what it was originally called.
`triage_category` is an **input** the urgency agent reads directly; it never predicts
it, so recovering the category from vitals gains an agent nothing it does not already
have. The circularity risk in this build lives entirely in `latent_hazard`, which
must never derive from anything the agent can see. That constraint is unchanged and
remains the guarantee that matters.

Two assertions replaced it, in `tests/test_plausibility.py`.

### A. Realism, anchored in the source

```
auc_mimic     = AUC(news2, Urgent vs Semi-Urgent) on MIMIC   = 0.6516
                95% CI [0.5789, 0.7230], 4000 bootstrap resamples
assert auc_generated <= auc_mimic + 0.05
```

The threshold is measured from the same file the distributions came from, not chosen.
It is one-sided on purpose: overlap looser than reality passes, and only
cleaner-than-real separation fails, which is the direction worth catching.

**Routine is excluded.** It is derived from reference ranges rather than fitted, and
including it let a modelling decision move the metric: swapping the two-patient MIMIC
Routine for reference ranges more than doubled the measured correlation, from 0.239
to 0.524. A gate that tracks a modelling choice is not measuring the data.

**This gate caught a real defect on its first run.** Drawing each vital independently
from a fitted Gaussian gave AUC 0.7319 against a bound of 0.7016 — our synthetic data
separated the categories more cleanly than real triage data does. Real vitals are
skewed, heavy-tailed, correlated within a patient, and pile up against physiological
ceilings such as SpO2 at 100 per cent. Fitting means and standard deviations
reproduces none of that.

The fix was to stop fitting a parametric distribution and resample the real rows
instead: a smoothed bootstrap over 190 screened MIMIC rows, jittered at 0.20 of each
column's SD. Generated AUC is now **0.6299**, inside MIMIC's own 95 per cent CI.

| approach | AUC | verdict |
|---|---|---|
| independent Gaussian draws, clipped | 0.7319 | fail |
| fitted covariance, rejection sampled | 0.7365 | fail |
| **smoothed bootstrap of real rows** | **0.6299** | **pass** |

### B. Within-category discriminability

A within-category ranker needs spread to order on. Thresholds were set from the
MIMIC-fitted distributions **before** any generated data was measured.

| category | fitted sd | fitted share `news2>=4` | asserted |
|---|---|---|---|
| Urgent | 1.81 | 26.9% | sd >= 1.5, share 0.10-0.45 |
| Semi-Urgent | 1.19 | 4.6% | sd >= 1.0, share 0.01-0.20 |

These are dataset-level properties. On the 609-referral sample a 4.6 per cent share
is about eight rows, so the checks require the full profile and skip otherwise rather
than being loosened until a slice passes.

The manual's requirement that at least 15 per cent of urgent referrals have
`news2 <= 2` is **kept unchanged**. It was always sound and is now empirically
supported: the measured figure is 69 per cent.

---

## 3. The Routine category has two patients in it

MIMIC-IV-ED Demo contains **2 stays at ESI 4-5** — two at acuity 4, none at acuity 5.
Both record a pain score of 8, so the fitted standard deviation for pain is exactly
0.0.

Two observations cannot parameterise a distribution, and no coupling adjustment
repairs it. Routine vitals are therefore derived from standard adult physiological
reference ranges and every Routine parameter is labelled `modelled`, not `fitted`.
This is the clinically correct choice in any case: a routine outpatient referral is
by definition someone with no acute physiological derangement.

`n_source_rows: 2` is recorded in the calibration file, alongside the two-patient
measurements, so the reason for the substitution is visible in the artefact and not
only here.

**Population mismatch, separately.** MIMIC-IV-ED is an emergency department cohort:
115 urgent, 90 semi-urgent, 2 routine. An outpatient referral list is close to the
inverse. Within-category vitals come from MIMIC; **category proportions never do**.
A test asserts the generated Urgent share stays below 40 per cent, against MIMIC's
own 55.6 per cent. It is currently 29.5 per cent.

---

## 4. Irish urgent referrals breach their timeframe almost always

The build manual expected fewer than 40 per cent of referrals to breach their
clinically recommended timeframe.

NTPF's own published wait bands imply **91.2 per cent** for the 28-day urgent target.
The arithmetic is not subtle: 28 days is under one month, and only 59.6 per cent of
the national list waits under six months.

The generator draws waits from those fitted bands and produces a measured breach rate
of **90.0 per cent**, within 1.1 points of what NTPF implies. The assertion is now
anchored to the NTPF-implied figure rather than to the original guess, so it fails if
the wait model drifts from the source rather than if reality is inconvenient.

An earlier version of the generator drew waits from a `gamma(2.2, 42)` that nothing
justified. That has been removed.

---

## 5. Three data-quality problems in the source

Found in the MIMIC triage table and excluded rather than silently absorbed. Each
screened variable keeps its as-measured value in a nested `unscreened_fitted` block,
so nothing is hidden.

| problem | n | effect if kept |
|---|---|---|
| `dbp` of 879 mmHg against `sbp` of 111 (stay 37298974) | 1 | inflates Urgent dbp SD from 16.22 to 79.72 |
| a Celsius value in the Fahrenheit column (stay 34992024) | 1 | converts to 2.5 C, violating our own CHECK, and inflates Semi-Urgent temp SD from 0.48 to 3.64 |
| free-text `pain` values (`Critical`, `UA`, `ett`, `unable`) and scores of 13 on a 0-10 scale | 19 | distorts the pain distribution |

A reviewer who downloads MIMIC and computes slightly different means can see why.

---

## 6. Provenance split

Every calibration parameter is labelled `fitted`, `modelled` or `assumed`. Nothing is
unlabelled.

| kind | count | share |
|---|---|---|
| fitted | 90 | 82.6% |
| modelled | 16 | 14.7% |
| assumed | 3 | 2.8% |

Well under the one-third threshold at which the grounding would be considered thin.

The three `assumed` parameters, none of which has any published source:

1. **Condition mix within each specialty.** HIPE covers it only partly; the rest is
   clinical judgement we do not have. The ICD-10-AM codes are real, the shares are not.
2. **The GP-priority versus triage-category disagreement rate**, at 0.18.
3. **The `latent_hazard` model.** Already documented as unvalidated in
   `DATASET_README.md` section 7.18. Its noise term is large on purpose and must not
   be reduced to make results look cleaner: if risk were a tidy function of the early
   warning score that the urgency agent also scores on, then "our ranking reduces
   deterioration" would be true by construction regardless of whether the system
   worked.

`coupling_coefficient` was reclassified from `modelled` to `fitted` at 1.0. It was
introduced to weaken MIMIC's vitals-to-acuity coupling, on the reasoning that Irish
CPC is assigned from a referral letter rather than at the bedside. The sweep showed no
weakening is needed: MIMIC's own coupling is already far below the level at which
circularity would be a concern.
