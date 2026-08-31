# How the Data Was Made

Where every number came from, what was measured and what was chosen, and three things the
real data disproved along the way.

Companion documents: [`DATASET_README.md`](../DATASET_README.md) for what the tables mean,
[`GETTING_THE_DATA.md`](GETTING_THE_DATA.md) for how to get them.

---

## 1. The sources

Four public sources, none requiring an account or an application. **Only one gives
row-level data; the rest are aggregates.**

| Source | Granularity | What it gives |
|---|---|---|
| **MIMIC-IV-ED Demo v2.2** (ODbL) | **Row-level, 207 stays** | Vitals distributions by triage acuity |
| NTPF open data | Aggregate | Specialty mix, waiting-time bands |
| ESRI report RS213 | Aggregate | Bed occupancy, length of stay |
| NTPF Outpatient MDS v2.6 | Specification | Field names, code values, rules |

**No Irish source publishes patient-level waiting list data.** It does not exist publicly.
So there are no Irish rows to copy, only Irish *shapes* to match. MIMIC matters because
it is the only place the real relationship between nurse-assigned urgency and observed
vitals can be measured, including how often the two disagree.

`make calibrate` re-downloads MIMIC and checks the committed figures still reproduce. It
does not overwrite them: the calibration determines the data, and the data is published
under a tag, so re-fitting silently would change one while the other kept claiming
otherwise. All twelve statistics reproduce exactly, n values included.

## 2. Every parameter is labelled

Nothing is unlabelled. Each of the 109 calibration parameters is one of three kinds:

| Kind | Count | Meaning |
|---|---|---|
| `fitted` | 90 | Measured directly from a source |
| `modelled` | 16 | A deliberate choice, with a stated reason |
| `assumed` | 3 | No published source exists |

**2.8% assumed.** The three, none of which has any source: the condition mix within each
specialty (the ICD-10-AM codes are real, the shares are not), the rate at which GP priority
and triage category disagree, and the `latent_hazard` model.

Three data-quality problems in MIMIC were excluded rather than absorbed, each scoped to the
column it affects, with the as-measured value kept alongside: a diastolic pressure of 879
mmHg, a Celsius reading sitting in the Fahrenheit column, and free-text entries in a 0 to 10
pain field.

## 3. How it is generated

Twelve steps, in dependency order. Hospitals and wards, then people, then referrals, then
triage, conditions and observations, then beds, clinics and events, then the daily
snapshots, then the held-out answer key.

Two decisions carry the whole design.

**Vitals are resampled from real MIMIC rows, not drawn from a fitted Gaussian.** Fitting
means and standard deviations throws away skew, heavy tails, within-patient correlation and
the ceiling where oxygen saturation piles up at 100%. Measured: a Gaussian gave an AUC of
0.732 against real MIMIC's own 0.651. Our synthetic data separated the categories *more
cleanly than reality*. Resampling 190 real rows with a small jitter gives 0.630, inside
MIMIC's own confidence interval. The distribution is right because it *is* the
distribution.

**`latent_hazard` never touches `news2`.** It is the answer key: which patients
deteriorate while waiting. If risk were a function of what the ranking agent reads, then
"our ranking reduces deterioration" would be true by construction whether or not the system
worked. Its noise term is large on purpose and must not be reduced to make results look
cleaner.

Waiting times are drawn from NTPF's published band distribution. Determinism is enforced:
same seed, byte-identical output, checked at both profiles.

## 4. Three things the data disproved

Each was an assumption in the original build specification. Each was checked and failed.

### An early warning score does not identify referral urgency

The specification required the correlation between `news2` and `severity_rank` to land in
0.35 to 0.65. A sweep across the one free parameter never exceeded **0.253**, at any value,
including values that would amplify beyond MIMIC's own measured separation.

The best possible rule based on `news2` alone recovers the triage category only **17.5
percentage points** better than guessing the most common one, and **54 to 59%** of the
highest-acuity patients score `news2 ≤ 2`.

This is a property of the instruments, not a defect in the fit. NEWS2 detects
deterioration in admitted ward patients over time; triage acuity reflects predicted
resource use and presenting complaint. Different things.

**It supports the project.** `DATASET_README.md` §7.6 already asserted that vitals alone do
not identify urgency. That was a design claim; it now has measured backing. It is also why
an urgency agent must read condition, pathway, referral source and the high-needs flag, not
just physiology.

The band was replaced by a check anchored in the source rather than chosen: the generated
AUC must not exceed MIMIC's own by more than 0.05. One-sided on purpose: overlap looser
than reality passes, and only cleaner-than-real separation fails. That gate caught a real
defect on its first run, which is how the resampling decision in §3 was found.

### Irish urgent referrals breach their timeframe almost always

The specification expected fewer than 40% to breach. NTPF's own published bands imply
**91.2%** for the 28-day urgent target. 28 days is under a month, and only 59.6% of the
national list waits under six. The generator produces 90.0%, within 1.1 points. The
assertion is now anchored to the NTPF figure rather than the original guess.

### The Routine category cannot be fitted

MIMIC's demo contains **2 stays** at the lowest acuities, both recording a pain score of 8,
so the fitted standard deviation is exactly 0.0. Two observations are not a distribution.
Routine vitals come from standard adult physiological reference ranges instead, and every
Routine parameter is labelled `modelled`, not `fitted`. It is the clinically correct choice
anyway: a routine outpatient referral is by definition someone with no acute derangement.

**Population caveat.** MIMIC is an emergency department cohort, 55.6% urgent. An
outpatient waiting list is close to the inverse. Within-category vitals come from MIMIC;
category proportions never do, and a test asserts the generated urgent share stays below
40%.

## 5. Known limitations

Each changes generated data, so none can be quietly edited into code that a published tag
already pins. **5.4 is fixed in v1.1; the rest are open.**

**5.1 Cross-hospital linkage is not demonstrated.** No person appears at two hospitals:
3,412 patients carry a national identifier and zero occur at more than one. So
`PW-DEMO-06` and `PW-DEMO-07` exist with the right shape but do not show multi-list
visibility. `cross_hospital_share` in the config is read by nothing.

**5.2 The `planted_cases` config block is decorative.** No code reads it. Only
`PW-DEMO-01`, `03` and `05` are actually shaped; the rest are ordinary referrals wearing
demo names.

**5.3 `latent_hazard` does not depend on the condition.** Despite the parameter name, the
base is a uniform draw that never reads the diagnosis. Age and noise are real. The
non-circularity guarantee is unaffected: it still never touches `news2`.

**5.4 Planted wait clocks contradicted their dates, fixed in v1.1.** Two demo referrals
shipped in `v1.0` recording waits their own dates could not support: one claimed 58 days
since receipt against a received date equal to the snapshot date. `plant()` had written the
counts directly and left the dates behind. Migration 008 now makes that combination
unloadable.

**The common thread in 5.1, 5.2 and 5.4 is worth naming.** In each case a test asserted
what the demo case *advertises*, that it breaches its timeframe or has waited 60
days, rather than whether the row could exist. Asserting the advertised property is not
the same as asserting the thing is real.
