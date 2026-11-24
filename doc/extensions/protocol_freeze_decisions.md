# Protocol decisions before freezing (plan rev. 9.1)

*2026-11-12, updated 2026-11-22. Sections 1–8 were written before any confirmatory run. Section 9 (coupling) has since been frozen, run and analysed; its status is in 9.8.*

## 1. Stage 1: remaining execution protections (done)

All generated code runs through one of three paths: `sandbox.execute` (Tier 1 / HumanEval and the HumanEval+ pilot), `sandbox.execute_pytest` (Tier 2 suites, hidden-suite grading) and the forkserver (scenarios, witnesses). Each path is covered by the opt-in policy (`core/exec_policy.py`). Without a policy, every call is the historical `subprocess.run`.

| Protection | Mechanism | Verified by |
|---|---|---|
| Credential separation | Child environment drops credential-like variables. | Canary on all three paths, plus fixtures. |
| Descendant cleanup | The child gets its own session (POSIX) or process group (Windows). On timeout the tree is killed; on POSIX, leftover group members are also killed after exit. | Canary grandchild check. On POSIX it is required on all three paths. |
| Isolated home (generated inputs only) | HOME, temp and XDG variables point to the scenario directory. | Used by the witness runner; grading leaves it off. |
| Protected grading inputs | `core/artifacts.protected_inputs`: inputs are read-only and sha256-checked before and after; `assert_absent` keeps agent working directories free of hidden files. | Tamper fixtures. |
| Runtime canary | `core/canary.require_canary` runs before every extension run and is recorded in `run_manifest.json`. The run aborts on any leak, and on POSIX on any surviving grandchild. | Tests, plus the dev-pilot manifest. |

**Windows result** (local canary):
- Without a policy, all three paths exposed the planted key and a real session token, and all grandchildren survived.
- With the policy, nothing was visible on any path, and `execute` / `execute_pytest` killed the grandchild.
- In forkserver *single* mode (Windows only), a grandchild orphaned by the per-scenario watchdog survives. A job object would fix this; that is out of scope. The canary reports it. freia runs fork mode, where the canary requires tree-kill.

## 2. 157/27 versus 164/34 (saturation report)

The leaderboard compares original, control and paraphrase scores on the same tasks, so every task needs a usable paraphrase score under the RQ2 family-coverage rule.
- Seven Tier 1 tasks fail that rule: HumanEval 32, 93, 113, 116, 130, 132 and 160.
- All seven are discriminating, which gives 164→157 and 34→27.

On the original prompt alone every task can be used:
- the Tier 1 margin is 0.026 on all 164 tasks against 0.124 on the 34 discriminating tasks;
- that is again exactly the discriminating share, 34/164;
- the excluded tasks change the size of the margin, not the mechanism.

Tier 2 drops 3 tasks, 2 of them discriminating. Details are in `doc/saturation/reporting_checks.md`, and the report text now says this.

## 3. Frozen artifacts (`config/extensions_protocol/`)

All were frozen locally without the gate manifest (`gated: false`). `--check` on freia must reproduce them exactly before any Stage 2 result is reported.

| Artifact | Content | sha256 (canonical JSON) |
|---|---|---|
| `cohorts_v1.json` | 24 development tasks; frozen audit order over the 351 others (stratified 173 csn / 178 post_cut-off); evaluation-cohort rule | `21f7b9a5…ffe7d0` |
| `rq3_population_v1.json` | τ_div held-out split, recomputed with the calibration function: 187 / 188, all development tasks in the calibration half. Stored task scores, task- and solution-level definitions, the G4 completion rule | `ba653f0d…f2af2b9` |
| `fault_split_v1.json` | 5,720 stored mutant records in 5,357 fault groups, with their frozen side (detail below) | `bdabf3cb…ad8713` |

**Re-freeze on freia (2026-11-18).** `freeze_protocol.py --check` on freia (gated, Python 3.11) did not reproduce the locally frozen files (Windows, ungated, Python 3.12), for two reasons. Neither consulted any outcome.
1. `rq3_population_v1.json` differed only in the `calibration_record_check` metadata. Locally the calibration record was not available; on freia it is found and the held-out split matches (188 tasks). The population itself was identical.
2. `fault_split_v1.json` differed in the group ids of tasks whose code has f-strings with quotes inside the braces (first case: `RCE_post_snippet_128`). `ast.unparse` writes these differently in 3.11 and 3.12 (PEP 701), so the normalised programs, and with them the group ids, depend on the interpreter.

The artifacts were therefore re-frozen **on freia, gated, Python 3.11**, the environment of every authoritative run. They are reproducible there with `--check`; a local 3.12 `--check` is expected to differ for those tasks. Stage 2b solution groups use the same normalisation, so `freeze_coupling.py` and all coupling runs also run on freia. The sha256 values in the table above are those of the local freeze and are superseded by `protocol_manifest.json`.

**Fault split.**
- It is decided from programs only, before any Stage 2 outcome.
- Groups are balanced within each (task, source) stratum, and a keyed coin sets the starting side.
- Counts: LLM 1,192 / 1,192; operator 1,462 / 1,487; mixed 14 / 10.
- Later site mutants are placed by `place_site_mutant`. A mutant identical to a discovery group is excluded from held-out evaluation; one identical to a held-out group joins it; a new program becomes a held-out site group. **The boundary can never move.**

**RQ3 scoring population (frozen).**
- **Task level.** Unit: the task. Score: the stored `pairwise_disagreement_rate`. Primary label: ≥1 RQ3-scored solution passes P and fails canonical H (operational disagreement). Population: held-out tasks, minus audit-reserved tasks, H-ready only. AUC uses the continuous score; sensitivity / specificity / J are computed only at the frozen τ_div = 0.1667.
- **Solution level** (separate analysis). Unit: P-passing RQ3-scored solutions. Score: that solution's disagreement with the other solutions, recomputed from re-executed traces. Metric: AUC with task-cluster bootstrap. τ_div is never applied.

## 4. Scope consequence to state now

Hidden-suite construction (A2) needs a supported contract:
- stdlib-only imports;
- typed or hinted parameters;
- no side-effect imports;
- a specified constructor.

**166 of the 351 evaluation tasks (47%) are supported by the draft contracts**; development tasks: 7 of 24. Runtime checks (reference self-consistency, a P scenario that runs) will lower this further.

So the H-ready cohort for Stage 5 and RQ5 is likely about **100–145 tasks**, and the RQ3 task-level population is likely about **80–90 tasks**, not 188. Unsupported tasks are reported with their reasons:
- 82 import non-stdlib modules;
- 72 have no generatable public method;
- 35 are dataclasses whose skeleton omits the fields;
- 27 have constructor parameters that cannot be generated;
- 25 import side-effect modules.

The coverage limitation goes into the thesis.

*Update 2026-11-22.* The contract review (rules R1–R6, `contract_prereview_tier{A,B,C}.md`) and the usability check leave **98 evaluation tasks with a reviewed, usable contract** (68 rejected), so the H-ready cohort can be at most about 98 tasks and the estimates above are too high.

## 5. Compatibility check before reusing historical RQ2 samples: cost and feasibility

**Statistical feasibility.** The original and control arms of RQ2 are two independent 10-sample draws from the same prompt and serving period. They are an exact no-drift benchmark for "fresh 10 vs historical 10" (`results_tier2_ext/compat_check_feasibility.json`; 300 random task subsets each).

Probability that the 95% task-cluster CI lies within ±0.03, with zero drift:

| Tasks × 10 fresh samples / model | gemma | qwen38 | qwen36 | pooled | all four pass |
|---|---|---|---|---|---|
| 60 (rev. 9 spec) | 0.96 | 0.67 | 0.42 | 0.99 | **0.30** |
| 120 | 1.00 | 0.97 | 0.88 | 1.00 | **0.85** |
| 200 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |

The rev. 9 design (60 tasks) would fail without any drift 70% of the time, so it is underpowered.

**Cost.** Per-completion tokens are from RQ2 v4 metadata: gemma ≈ 480, qwen36 ≈ 4.5k, qwen38 ≈ 16.8k. Throughput is about 2,800 tok/s for qwen38 on 2×H200 and about 2,000 tok/s for qwen36 on 1×A100.

| Option | Completions | qwen38 (2×H200) | qwen36 (1×A100) | gemma (gateway) | Total wall |
|---|---|---|---|---|---|
| Check, 60 tasks | 1,800 | ≈ 1.0 h | ≈ 0.4 h | ≈ 5 min | ≈ 1.5 h + 2 cold starts |
| Check, 120 tasks | 3,600 | ≈ 2.0 h | ≈ 0.8 h | ≈ 10 min | ≈ 3 h + 2 cold starts |
| Fresh pool for the whole RQ5 cohort (≈ 146 tasks × 20 samples × 3 models) | 8,760 | ≈ 4.9 h | ≈ 1.8 h | ≈ 25 min | ≈ 7 h |

**Recommendation: skip reuse and sample fresh.**
- A powered check costs about 40% of fresh sampling for a cohort this small.
- It passes only 85% of the time even with no drift.
- Reuse would mix serving periods inside the repair arm: a historical first candidate followed by fresh repair turns.

The plan keeps the gate as written only if you prefer reuse. In that case it uses **120 tasks** (not 60), with the deterministic checks first.

## 6. Audit sampling design (exact)

- **Population.** The audit-reserved tasks are the **first 20 H-ready tasks in the frozen `audit_order`**: whole tasks, stratified csn / post_cut-off. They are excluded from the Stage 5 and RQ5 confirmatory cohorts.
- **Q1, test validity.** Per audit task, a seeded simple random sample of min(5, admitted) H tests, seed = sha256(seed|audit|task). The reviewer judges each against the docstring and contract: *valid* / *over-specified* / *invalid*.
- **Q2, erroneous rejection.** Per audit task, all RQ2 completions that pass P and fail H. Sample min(5, n) (implementation, first failing H test) pairs, round-robin over models. The reviewer judges each: *true fault* / *erroneous rejection* / *unclear*. Also run every validated reference control on H; any failure is counted.
- **Estimation.**
  - Ratio estimators with inverse-sampling-fraction weights per task (so tasks with many tests are not under-represented).
  - 95% CIs by task-cluster bootstrap, 2,000 replicates.
  - Report n tasks and n items. Wilson intervals are not used, because items within a task are not independent.
  - "Unclear" is bounded both ways (counted as erroneous / as fault).
- **Acceptance (pre-registered).** H is frozen only if both hold:
  - invalid tests: point estimate ≤ 5% and upper bound ≤ 15%;
  - erroneous rejections among audited P-pass/H-fail pairs: point estimate ≤ 10% and upper bound ≤ 25%.

  Otherwise: revise the admission rules **once**, on development tasks only; rebuild; audit the **next 20** H-ready tasks of the frozen order (the first 20 stay excluded). Both rounds are reported.
- **Expected precision.** At most 100 items per question; the cluster-bootstrap half-width will be about ±0.05–0.08. This audit validates the oracle; it is not an estimate of benchmark correctness.

## 7. A3 inclusion rule (exact; A2 stays the default hidden oracle)

The rule is evaluated once, on the **development tasks only**, after the bounded A3 development pilot and before any evaluation-task H construction. The decision is recorded in `config/extensions_protocol/canonical_h_decision.json`.

D = development tasks with ≥1 admitted A2 test. **H = A2 ∪ A3 only if all four hold; otherwise H = A2**, and A3 is reported only as an RQ4c arm.
1. **Validity non-inferiority.** v_A3 ≥ v_A2 − 0.05, where v_X is the audited *valid* share of X's admitted tests on D. All A3 tests are audited; A2 tests are sampled at min(5, n) per task; both use weighted ratio estimates.
2. **No added erroneous rejection.** No validated reference control fails an A3 test. Also, among development RQ2 completions that pass P and all A2 tests but fail ≥1 A3 test (min(5, n) per task audited), there are **0** erroneous rejections, with *unclear* counted as erroneous.
3. **Incremental detection.** A3 detects ≥1 primary-confirmed held-out development group that no A2 test detects, on **≥3 distinct development tasks**.
4. **Feasibility.** The projected evaluation-task A3 cost (development tokens per targeted group × number of targeted evaluation groups, ≤3 per task) is within the ceiling fixed before the A3 pilot. Proposed ceiling: **≤20 H200-GPU-hours** for qwen38 + qwen36, plus ≤5M gateway tokens for gemma.

If A3 joins H, per-model Stage 5 and RQ5 results add the leave-one-model-out H sensitivity.

## 8. Engineering decisions recorded in the plan

- **Engine location.** The witness engine lives in `benchmarks/witness.py`, not `stage0/`: it is class-specific, and the architecture rule keeps that out of RQ code. The new `oracles/` package is added to the architecture-guarded directories.
- **Generation and shrinking.** Hypothesis generates contract-valid scenarios (seeded per task, version pinned). Shrinking is deterministic (step deletion, then argument simplification inside the contract, strictly smaller each round). Replay uses fresh processes: reference twice, mutant twice.
- **Contract drafting.**
  - Parameter types come from the annotation, then the docstring, then literals from P tests the reference passes (strict-xfail tests are ignored), then the default value.
  - Side-effect imports (network, processes, threads, shutil, …) and dataclasses without skeleton fields are unsupported.
  - Generated strings use a path-safe alphabet.
  - Floats are compared with rel 1e-9 / abs 1e-12 by default. Own-class return values are opaque unless documented properties exist (drafted as accessors, for review).
- **Witnesses from P scenarios.** A witness found on a gate-valid P scenario through the API serializer is the D3b "attributed suite kill", so no separate per-test P re-run is needed.

## 9. Stage 2b: mutant–fault coupling (D8). Frozen 2026-11-19; endpoints computed 2026-11-22 (9.8)

*Added 2026-11-17 for supervisor note 2. Order as carried out: this draft → technical pilot (blind to the LLM-vs-operator effect) → our own decisions, recorded here → freeze `coupling_v1.json` on freia (2026-11-19, commit 06eb6a8, spec 7bafb448185f; the SPEC and its sha256 plus the per-task solution-group digests; there is no separate solution-groups file) → full run C2 (job 5371174) → technical report and decisions (9.6, commit 0fa4983) → endpoints (2026-11-22) → review by Gordon together with the results (changes after his feedback are recorded deviations, and both versions are reported).*

**Question.** Are mutants coupled to the incorrect solutions the panel actually wrote, and are LLM mutants more strongly coupled than operator mutants? We follow the research question of Petrovic et al. (ICSE'21, RQ3), not their procedure, because LLM solutions are not historical buggy/fixed pairs. The measure is Chen et al.'s probabilistic coupling (ASE'20). Behavioural deduplication, size equalisation and the null-adjusted lift are **our** extensions.

### 9.1 Test pools (one name each)

| Pool | Content | Observation | Role |
|---|---|---|---|
| **Primary** | P scenarios plus **N = 120** new contract-valid generated scenarios (seed = extension seed + 1; the Stage 2 pool of 40 stays frozen). Stage-2-supported tasks only; every test keeps its source (p / gen). | API-visible only (D1), valid domain only (D2): `witness._level_of(compare(...))` ∈ {(api_visible, valid), (nontermination, valid)} | primary and secondary endpoints |
| **Perturbed-P** | Stage 0 / RQ3 pool (P scenarios plus literal perturbations), all tasks | step results of `observe` / `raises` steps with builtin values or exception types only; **never** `end:<var>` snapshots, `exec`-step tokens, or own-class / opaque values | sensitivity, kept only if it passes the false-detection gate (9.6) |
| **P per-test** | pytest D1 outcomes from `run_suite`, all tasks | gate-valid tests | descriptive; defines *P-pass* and *P-live* |
| **Pool-size check** | primary pool with only the first 40 of the 120 generated scenarios | as primary | robustness |

Why the observation rule matters: the historical full trace stores end-of-scenario state snapshots and object tokens (`forkserver._run_scenario`). Independently written solutions structure their state differently, so a full-trace comparison would flag almost every solution on almost every test, while mutants, which share the reference's internals, would not.

**Validity:** every test needs a reference that is consistent across two runs, and (primary) a `valid` domain. **Weighting:** equal per valid test, so generated scenarios dominate. P-only and generated-only values are reported descriptively. **Detection matrices run twice;** cells that disagree are masked and counted.

### 9.2 Populations

- **Mutants:** the groups of `fault_split_v1.json` (both sides; coupling does not use H). Pure *operator* and pure *llm_whole* groups form the two sources. **Mixed groups (24) are excluded** from the comparison and reported descriptively. K(m) = valid tests that detect m. K = ∅ means *undetected on the pool*.
- **Faults:** all 56,250 RQ2 completions → `build_solution` → per-task solution groups (normalised program), with provenance. D(f) = valid tests that detect f. Categories:
  - near-miss 0 < |D| < |T| (primary);
  - total failure;
  - invalid artifact;
  - *undetected-on-pool* (D = ∅; this does not mean correct).
- **Behavioural deduplication:** near-miss solution groups with the same D form one *fault class*. Within a source, mutant groups with the same K form one *goal*. Redundancy is reported (cf. Petrovic RQ4).
- **Cross-model rule:** an LLM goal is eligible for a fault class only if none of its models produced a member of that class. The rule is applied before deduplication.

### 9.3 Measures

- pc(m, f) = |K ∩ D| / |K|;
- strict ⇔ pc = 1;
- coverage FC(f) = |D ∩ ⋃K| / |D|;
- descriptive: mean pc;
- **Equalisation:** k = min(#operator goals, #eligible LLM goals); PC = the **exact expectation over all size-k subsets** of a source's goals of the max pc (order statistics: Σᵢ v₍ᵢ₎·C(i−1, k−1)/C(n, k)). This is the limit of random size-k draws: deterministic, and no draw seed is needed. Strict share and FC use the same exact expectation.
- **Null:** D's labels permuted **within the p / gen strata**, B = 200. lift = PC − E_null[PC]. The unadjusted PC is always reported.
- Seeds come from sha256(seed | task | class | purpose).

### 9.4 Endpoints

- **Availability** (share of groups with K ≠ ∅, per source) is descriptive here. Its confirmatory test is the E13 / RQ1-robustness row.
- **Conditional population:** supported *evaluation* tasks with ≥ 1 contributing fault class (a near-miss class with ≥1 operator goal and ≥1 eligible LLM goal). Each excluded task gets exactly one reason, in this order:
  1. no_valid_pool
  2. no_near_miss_fault
  3. no_detected_operator
  4. no_detected_llm
  5. no_cross_model_llm
- **Power rule** (fixed now, applied before any outcome): if the conditional population has fewer than **30** tasks, the row is reported as exploratory. *Wording fixed 2026-11-18:* the count is of conditional (contributing) evaluation tasks, read from `--technical` before any endpoint is computed. Below 30, the primary and the three secondary comparisons are reported as estimates with CIs, without confirmatory claims. In either case a non-significant result is not evidence that the sources are equivalent or that coupling is absent. The threshold is a reporting rule, not a power guarantee.

| | |
|---|---|
| **Primary** (confirmatory) | Per-task Δ = lift_LLM − lift_operator (mean over contributing classes). Paired Wilcoxon (the RQ1 helper; zero Δ reported), plus task-cluster bootstrap CI. Two-sided, α = 0.05. |
| **Secondary** (Holm, 3) | (a) strict-coupling share; (b) FC; (c) Petrovic-inspired: among *hidden faults* (all gate-valid P tests pass, D ≠ ∅), the share with a strictly coupled **P-live** mutant. Each compares LLM against operator. |
| **Descriptive** | unadjusted PC; mean pc; P-only and generated-only PC; availability; redundancy; mixed groups; per model; same-model vs cross-model coupling; per operator; by severity; P-pass vs P-fail; csn / post; saturation strata; site mutants (after Stage 3) |
| **Sensitivity** | perturbed-P pool; pool-size check; total failures included; **P-fail faults only** (faults that also fail a gate-valid P test, i.e. confirmed by a benchmark assertion); unstratified null; no behavioural deduplication; un-equalised max. The list is `SPEC["sensitivity"]` and is frozen with it. *Removed 2026-11-18, before the freeze:* "domain_uncertain included". The detection matrix runs valid-domain scenarios only, and on a domain-uncertain scenario the reference's own behaviour is undocumented, so a difference there has no oracle. |

*P-pass* and *P-live* use the pytest outcomes. A P **scenario** can detect a difference that the P test's assertions never check, so it is stronger than the test.

### 9.5 Qualitative review

Sample: 50 contributing fault classes with max pc < 1 for both sources, seeded and stratified by model.

The guide is frozen before the review: weak operator / missing operator / no applicable operator / unclear.

Evidence kept: the diff against the reference, a detecting scenario, and the nearest goal with its pc.

Procedure: the user classifies all 50; a blind second classification of 15 gives Cohen's κ; disagreements are resolved and recorded.

**Guide FROZEN 2026-11-22 (decided by the user before any sampling; not changed once sampling starts).** It supersedes the guide above.
- **Categories:**
  1. reference-specific / not a real fault: the detected difference is on an output that the docstring or contract leaves unspecified, or where the reference contradicts the docstring (e.g. csn_142 returns `''` where the docstring says `None`);
  2. no applicable operator;
  3. missing operator;
  4. weak operator;
  5. unclear.
- **Tie-break** when two categories could apply: take the first in the order above (reference-specific → no applicable operator → missing operator → weak operator → unclear).
- **Population ("uncoupled"):** contributing fault classes with no strictly coupled goal from either source (un-equalised max pc < 1 for operator goals and for cross-model-eligible LLM goals): 98 of 215.
- **Sample:** 50 classes. Strata = provenance pattern (one per single model; one for classes written by several models); proportional allocation (largest remainder); within a stratum, ordered by sha256(extension seed | "qualitative" | task | class id). `scripts/coupling_review_sheet.py`.
- **Sample drawn 2026-11-22** (`results_tier2_ext/coupling/full/qualitative/`): 98 uncoupled classes of 215 contributing; strata gemma4-31b-it 6 of 11, multi-model 6 of 12, qwen36-35b 16 of 31, qwen38-27b 22 of 44; 50 cases from **13 tasks**, 24 of them (48%) from two tasks (post_295: 14, csn_162: 10). Kept as `qualitative_v1/`, never classified.
- **Amendment 2026-11-22 (before any case was classified; decided on the sample's composition only, not its content): per-task cap.** Cases within one task share the reference and the operator set, so they are near-duplicates for this question, and a sample dominated by two tasks answers a narrower question than the task-weighted primary. Rule: the smallest per-task cap that still yields 50 classes; within a task the first classes in the hash order above are kept; the model strata are then applied to the capped pool. Each case carries its inclusion probability and design weight (`weight` in `classification.csv`). **Analysis:** category shares are reported (a) unweighted and (b) re-weighted to the 98-class population with the design weights, both with task-cluster bootstrap intervals.
  *Outcome:* the 98 uncoupled classes sit in 20 tasks (post_295: 24, csn_162: 20, post_185: 9, post_154: 8, the rest ≤ 6). Cap = **5** → capped pool 55 → **50 cases from 18 tasks**, at most 5 per task; the two largest tasks now give 10 of 50 cases (20%, was 48%). Two single-class tasks (csn_51, post_281) fall out in the model allocation from 55 to 50.
- **Raters:** the user classifies all 50 first. Only afterwards is it decided whether a human second rater (Gordon or a colleague) blind-rates 15; the fallback is a fresh AI session that receives only the sheet and this guide, reported as an AI rater. The Claude session that built the sheet is not a rater (it has seen every result).

### 9.6 Technical pilot gate GC (all 24 development tasks; 5 are supported after the dev contract review, which rejected csn_110 and post_309 — the draft contracts had 6; no coupling estimate is computed)

- ≥ 99% of cells agree across the two runs;
- reference rows are clean (the reference runs as a program in every task: no detection and no masked cell in either pool, and it passes P);
- per-test P reproduces the historical `is_killed` and `per_completion` (timeouts excepted);
- median number of valid tests per task ≥ 20;
- **false detection:**
  - perturbed-P rule: ≤ 5% of unperturbed P scenarios flagged on solutions that pass every P test; otherwise the pool is dropped and reported as infeasible;
  - primary pool: 10 P-scenario detections on P-passing solutions are inspected by hand, and all must be genuine behavioural differences;
- runtime is measured;
- the projected conditional population is computed.

Adjustments (N, filters) may use only these technical metrics and are recorded before the freeze.

**Adjustments recorded from the freia pilot (2026-11-18, `dev_pilot_freia_v2`):**
- **Reference-unstable tests are dropped.** On RCE_post_snippet_25 the reference row flagged 31 perturbed tests: the reference formats `datetime.now()` to the second, so the two back-to-back baseline runs agreed while every later run differed. Rule: a test on which the reference, run again as a program, detects or is masked is dropped for the whole task, like a masked test, in both pools (counted as `unstable_tests_dropped`). The perturbed false-detection rate is computed after this filter.
- **The cross-model rule is applied before deduplication**, as written in 9.2; the pilot code had applied it to deduplicated goals. Fixed before any coupling value was computed.
- **Endpoints refuse a supported task whose contract is not reviewed.**

**Decisions recorded before the freeze (2026-11-18):**
- **Genuine behavioural difference (spot-check criterion).** A detection is genuine when (1) the scenario is contract-valid, (2) both reference and candidate produce a stable, reproducible outcome (a returned value or an exception), (3) the externally observable outcomes differ, and (4) the difference is not a timeout, infrastructure error or invalid generated input. The pilot's 86 P-scenario detections on P-passing solutions (74 on post_24, 12 on post_64) meet this; all are return values that the P tests do not assert. **Gate GC passed.**
- **Detections are reference-relative.** D(f) and K(m) use the same oracle, the reference (D7), as in Chen'20 and Just'14. A detection is a deviation from the reference, not a proven specification violation. Splitting detections into "documented" and "underdetermined" cannot be done automatically (contracts describe valid inputs, not correct outputs), so the primary measure stays reference-relative and the P-fail-only sensitivity (9.4) is the assertion-confirmed check.
- **Contract review.** Rules R1–R6 (`doc/extensions/contract_prereview_tierC.md`) apply to every evaluation task. No verdict uses a detection result.

**Technical report of the full run C2 (freia, job 5371174, 8 shards, 2026-11-22; no coupling value computed):**

| Gate GC criterion | Full-run result |
|---|---|
| cell agreement ≥ 99% | primary 1.0; perturbed 0.99998 |
| reference rows clean | 370 of 375; the 5 others are unsupported tasks (csn_263, csn_36, post_358, post_4 fail P; csn_137: 69 unstable perturbed tests, dropped by the filter) |
| P reproduces history | mutants 2327/2327; solutions 54672/54680. All 8 mismatches have a per-test `timeout` outcome (csn_271, post_158, post_293, post_47: unsupported tasks), so they are timeouts excepted by the gate and do not touch the primary analysis |
| median valid tests ≥ 20 | 122 (103 supported tasks: 98 evaluation + 5 development, all `reviewed`) |
| runner errors, unavailable pools | none |
| primary pool, 10 P-scenario detections inspected | all 10 genuine (see the decisions); 1530 such detections in 22 tasks |
| perturbed false detection ≤ 5% | **10.7%** (1025/9605); pilot value was 1.29% |
| runtime | 60,226 task-seconds; each shard 1h52–2h16 |
| conditional population | **36** evaluation tasks (38 with the 2 contributing development tasks post_24 and post_64) of 98 supported evaluation tasks; excluded: no_valid_pool 253, no_near_miss_fault 23, no_detected_llm 17, no_cross_model_llm 18, no_detected_operator 4 |

**Decisions recorded before any endpoint is computed (2026-11-22):**
- **Power rule:** 36 ≥ 30, so the primary and the three secondary comparisons are confirmatory. The margin is thin: the thesis states n = 36.
- **Spot check:** all 10 sampled detections are genuine under the criterion above (valid input, stable outcome, observable difference, not a timeout or infrastructure error). Several are reference-specific details the P tests do not assert: e.g. csn_142 returns `linker_file: ''` where the class docstring says `None`, so a solution that follows the documentation is "detected". This is the limitation recorded in 9.7, and the reason for the P-fail-only sensitivity.
- **Perturbed-P pool: dropped as infeasible.** 9.1 keeps the pool "only if it passes the false-detection gate". The pilot passed that gate (1.29%), but the pool is defined for all tasks, so the gate is re-evaluated on the full run, and it fails (10.7% > 5%). `analyze_coupling.py` reports `perturbed_pool` as infeasible (threshold `PERTURBED_MAX_FALSE_DETECTION`, outside the frozen SPEC). Descriptive diagnosis only, not used to rescue the pool: 16 of 182 tasks with perturbed data have any flagged cell, and 3 unsupported tasks (post_111, csn_227, post_189) hold 79% of the flagged cells (2.4% without them). No task is filtered.
- **P-pass classification:** the 8 solutions above are classed P-fail because of a timeout; they belong to unsupported tasks.

### 9.7 Limitations to state

- supported subset only, and the conditional population only;
- LLM solutions are not historical bugs;
- coverage is not controlled (the null controls detection-set size, which is a different confounder);
- tests are non-uniform scenarios, dominated by generated ones;
- same-panel circularity is handled only through the cross-model rule;
- detections are reference-relative: on outputs the docstring leaves open, a "fault" deviates from the reference without being shown to violate the specification (P-fail-only sensitivity in 9.4);
- the contract population is shaped by review rules R1–R6 (abstract interfaces, framework inputs, template docstrings and concurrency classes are excluded);
- Tier 1 is out of scope, because HumanEval has a single `check()`;
- strict share and coverage are not null-adjusted: a goal with a small detection set fits inside D more easily (strict) and covers less of D (coverage), so these two secondaries partly reflect how hard each source's mutants are to kill (post-hoc descriptive `kill_share`); only the primary lift controls detection-set size;
- secondary (c) rests on 4 tasks: with n = 4 a two-sided Wilcoxon cannot reach p < 0.125, so it is uninformative by construction;
- the perturbed-P sensitivity is infeasible (9.6), so robustness to the pool rests on the pool-size check and the P-fail-only analysis;
- faults made by every model are excluded: after deduplication such a class has no eligible cross-model LLM goal (no_cross_model_llm). This is why the no-deduplication sensitivity has 53 tasks instead of 36; it gives the same answer;
- the same-model vs cross-model comparison is biased (unequal numbers of goals) and is not used as evidence against circularity;
- the pooled class-level descriptives (coupling rate, hidden classes, the qualitative review) are dominated by a few tasks: post_226 and post_295 hold 62 of the 215 contributing classes (29%). The per-task analyses (primary, secondaries) give each task the same weight and are not affected.

### 9.8 Results status (endpoints computed 2026-11-22, `results_tier2_ext/coupling/full/endpoints.json`)

Confirmatory (n = 36, power rule met):
- **Primary, null-adjusted lift:** LLM 0.117, operator 0.091; Δ = +0.026, 95% CI [−0.018, 0.073], Wilcoxon p = 0.23. No evidence that LLM mutants are more strongly coupled once detection-set size is controlled; this is not evidence of equivalence (9.4).
- **Secondary (Holm, 3):** strict-coupling share LLM 0.45 vs operator 0.30, Δ = +0.15 [0.06, 0.24], p_Holm = 0.001; fault coverage LLM 0.51 vs operator 0.77, Δ = −0.26 [−0.35, −0.17], p_Holm < 0.001; (c) hidden faults n = 4, p = 0.5.
- **Sensitivities:** every lift Δ stays within ±0.05 and non-significant (pool-size 40, total failures, P-fail only, unstratified null, no deduplication, unequalised max); perturbed pool infeasible.
- **Descriptive:** same-model vs cross-model max pc 0.79 vs 0.81 (135 classes). *Not* evidence about circularity: the cross-model maximum is taken over more goals, so it is biased upward (corrected 2026-11-22 after review).

**Exploratory, added after the endpoints (2026-11-22; outside the Holm family, not in the frozen SPEC; `exploratory_post_hoc` in `endpoints.json`):** null-adjusted strict share and coverage (`strict_share_lift`, `fault_coverage_lift`, each minus its null over the same permutations as the primary; the primary null is bit-identical, regression-tested), goal detection-set size (`kill_share`), one-sample tests of lift > 0 per source (`lift_above_null`), the Petrovic RQ3(a) coupling rate (`fault_coupling_rate_unequalised`), and pooled hidden-fault classes. Every comparison also reports a paired rank-biserial effect size (the Cliff's delta in `wilcoxon` treats the lists as independent) and `below_power_rule`. **Wording rule for the thesis:** the strict-share and coverage differences are interpreted only together with their null-adjusted versions.

*Exploratory results (re-run 2026-11-22; every confirmatory number reproduced exactly):*
- **Both sources are coupled above chance:** mean lift operator 0.091 (31/36 tasks positive, one-sample p < 0.001), LLM 0.117 (24/36 positive, p < 0.001).
- **LLM mutants are harder to kill:** a goal is detected by 42% of the valid tests for LLM vs 63% for operators (Δ −0.20 [−0.26, −0.15], paired r = −0.95).
- **That explains the secondaries.** Fault coverage adjusted for chance: Δ +0.006 [−0.042, 0.056], p = 0.88, so the raw −0.26 gap is a detection-set-size effect. Strict share adjusted for chance: Δ +0.073 [−0.030, 0.173], p = 0.07, half the raw +0.15 and no longer significant.
- **Petrovic RQ3(a):** of 215 contributing fault classes, 45% are strictly coupled to ≥1 operator goal, 46% to ≥1 LLM goal, 54% to either. These rates are *unequalised* (not matched for the number of mutants), and operators have more goals (284 vs 201), so LLM mutants reach the same rate with fewer goals. Descriptive only.
- **Availability on tasks with a pool:** operator 453/734 groups detected (62%), LLM 301/627 (48%).
- **Hidden faults:** 11 classes in 4 tasks (LLM 10, operator 3 strictly coupled); too few to interpret.

**Thesis statement supported by these results:** both mutant sources are coupled to the panel's real faults above chance, and LLM mutants are not more strongly coupled than operator mutants once detection-set size is controlled (primary, n = 36). The two Holm-significant secondaries are reported as found, but they largely reflect that LLM mutants are killed by fewer tests: the coverage gap vanishes and the strict-share gap halves when each is compared with its chance level.

**Coupling × saturation (Note 3 table, `doc/saturation/rq_table.md`, 2026-11-22; exploratory; 20/20 table checks OK, all 36 contributing tasks have a stratum):** LLM − operator lift is +0.026 [−0.019, 0.074] on all 36 tasks (same mean as the primary; the CI differs slightly because the table uses its own bootstrap), −0.022 [−0.079, 0.042] on the 16 non-extreme tasks and −0.035 [−0.105, 0.037] on the 14 baseline-discriminating tasks (graded score). Under pass@1 the subsets shrink to 8 tasks (−0.066 [−0.147, −0.003], Wilcoxon p = 0.08). Composition (graded; produced by `saturation_rq_table.py` as `coupling_population.composition` and printed in `rq_table.md`): the 20 extreme tasks are **16 floor** (mean +0.069) and **4 saturated** (+0.050); under pass@1, 24 floor and 4 saturated. The 4 saturated tasks are csn_53, post_173, post_255 and post_346. **Thesis wording:** *"No saturation stratum shows an LLM advantage (n = 8–16 per stratum, exploratory)."* The only interval that excludes zero is the n = 8 pass@1 subset; with 8 tasks a percentile bootstrap is unreliable (Wilcoxon p = 0.08), so it is not interpreted, and no stratum direction is interpreted.

**Hidden-fault tasks vs saturated tasks (secondary (c), n = 4):** the 4 hidden-fault tasks are csn_53, csn_82, post_255 and post_351; only two of them (csn_53 and post_255) are among the 4 saturated tasks, the other two (csn_82, post_351) are non-extreme. They are not the same tasks: a hidden fault needs a P-passing solution, which exists on saturated tasks (all models pass) and on non-extreme ones, but not on floor tasks.

**Why this split is not neutral for coupling.** The strata come from the same RQ2 solutions that supply the faults. On a floor task the original-prompt solutions all fail P, so its faults are mostly P-fail; on a saturated task they all pass P, so its faults are mostly P-pass (hidden). The split is therefore close to a P-fail vs P-pass split of the faults. It is not exact, because faults come from all three prompt relations (original, control, paraphrase) while the strata use the original prompt only. This matches the P-fail-only sensitivity (Δ +0.043, the most positive), and the P-pass vs P-fail breakdown (9.4) is reported next to this row.

Still to do before the results are final (all descriptive or qualitative; none changes the confirmatory numbers):
1. the rest of the 9.4 descriptives (per model, per operator, by severity, P-pass vs P-fail, csn / post, P-only vs generated-only PC, redundancy);
2. ~~the coupling row of the Note 3 table~~ done 2026-11-22 (above);
3. the **qualitative review (9.5)** of 50 uncoupled fault classes: the Petrovic RQ3 part Gordon pointed to (guide frozen; sheet built by `scripts/coupling_review_sheet.py`);
4. ~~the independent recompute of pc, lift and Δ on 3 tasks~~ **done 2026-11-22, passed** (`scripts/coupling_recompute.py`: no project imports; tasks chosen by a fixed structural rule before any value was computed): post_351 (fewest goals), post_226 (most faults written by several models: 7), post_295 (most P tests together with generated tests). All 39 recomputed values (n_tests, n_contributing, and pc, strict share, FC, null and lift per source, plus Δ) equal `endpoints.json` to 1e-9, with exact subset enumeration and the specified permutation null for every class. This verifies the data handling (masked and unstable tests, near-miss faults, deduplication, the cross-model rule before deduplication) and the formulas on these 3 tasks, not the other 33; it is a check of the implementation, not of the stored detections;
5. the thesis section and the package for Gordon.

## 10. Stage 2 (E13) witnesses: gate G2 and the full run (freia, 2026-11-24)

**Changes before the authoritative pilot (plan rev. 9.3).** Only reviewed contracts count: a supported draft is treated as unsupported (the earlier local pilot had used the draft of csn_110, which the dev review rejected). The pilot job no longer re-drafts contracts (the frozen `contracts_v1/` stays untouched). The canary uses the suite timeout and a warm-up, as the coupling runs do. The full run needs a passed G2 record with identical witness settings (`run_witness.py --g2`).

**Gate G2: PASSED** (`results_tier2_ext/witness/dev_pilot_reviewed/G2.json`; authoritative, gate manifest). All checks hold: fixtures, authoritative, all 24 development tasks, reviewed contracts, outcome taxonomy, canary, stored replay, and an **independent replay** of all 38 witnesses in fresh processes from the stored witness and the hash-checked frozen mutant code. Scale: 5/24 development tasks supported; 35 primary confirmed groups of 72 on supported tasks (yield 0.49); of 38 historically "equivalent" groups on supported tasks, 5 have a primary witness.

**Provenance note.** The freia checkout is recorded as `-dirty` only because of untracked, unrelated files under `config/` (old pilot configs); no tracked file differs from the commit, and none of these files is read by the runs (inputs are pinned).

**Full run** (8 array shards, job 5385664, about 4 min each; merge job 5385665; `results_tier2_ext/witness/full/`): 351 evaluation tasks, **98 supported** (= the accepted contracts), 4,993 fault groups (1,365 on supported tasks).
- **Primary confirmed groups (D3): 735** (origin: generated 673, P scenario 62). Witness replay 881/881.
- Outcomes: api_value 487, api_exception 248 (valid), api_exception domain-uncertain 37, private-state-only 109, unresolved 479, invalid artifact 5, unsupported 3,628.
- **L3 evidence:** of 560 historically "equivalent" groups on supported tasks, **119 (21%) have a primary witness**; 407 stay unresolved (never counted as equivalent).

**RQ1 robustness** (`rq1_robustness.md/json`, group level; LLM − operator kill-rate gap):

| population | operator | LLM | gap | paired tasks |
|---|---|---|---|---|
| historical | 919/1,387 = 0.663 | 409/809 = 0.506 | −0.157 | 203 |
| supported, historical | 357/497 = 0.718 | 160/310 = 0.516 | −0.202 | 73 |
| **primary confirmed (D3)** | 294/392 = 0.750 | 128/225 = 0.569 | **−0.181** | 64 |
| full trace (sensitivity) | 352/457 = 0.770 | 160/273 = 0.586 | −0.184 | 71 |
| unresolved counted as survived | 294/605 = 0.486 | 128/493 = 0.260 | −0.226 | 94 |

**Reading:** the RQ1 finding (LLM mutants are killed less often than operator mutants) is not an artefact of the historical equivalence filter: the gap persists, at a similar size, when only replayed, API-visible, valid-domain faults count, and in every sensitivity population. Wilcoxon p-values on paired per-task rates are in `rq1_robustness.json` (`wilcoxon_paired_task_rates`). The support restriction (98 of 351 tasks) is a stated limitation.

**Pre-registered RQ1 robustness primary (confirmatory hierarchy):** on primary confirmed groups the LLM − operator kill-rate gap is **−0.181, paired per-task Wilcoxon p = 0.001 (64 tasks)**; every population gives p ≤ 0.001 (historical −0.157, p < 0.001, 203 tasks). Effect sizes in the thesis use the paired rank-biserial (`rank_biserial_paired` in `rq1_robustness.json`, added 2026-11-24); the helper's Cliff's delta treats the lists as independent (−0.146 on the primary row) and is not used.

### 10.1 A2 tuning on development tasks: `cover_k` (2026-11-24)

**Rule, stated before the dev numbers were read:** choose the `cover_k` ∈ {1, 3, 5} with the highest held-out *P or H* detection on the development primary population; the smaller k on ties; at most 20 tests per task (a separate cap, enforced by `max_tests`).

**Dev results** (`results_tier2_ext/a2/dev_k{1,3,5}`; 5 H-ready tasks, 14 held-out primary groups on 4 tasks; admission rejected 0, over-specified 0, control defects 0 at every k):

| k | tests (5 tasks) | P | H | P or H | H only | P only |
|---|---|---|---|---|---|---|
| 1 | 6 | 8 | 8 | 10 | 2 | 2 |
| 3 | 19 | 8 | 10 | 11 | 3 | 1 |
| 5 | 34 | 8 | 11 | 12 | 4 | 1 |

The rule selects **k = 5**. The margin over k = 3 is one group: the only held-out group confirmed on a P scenario (independent of our generator), on one task. This is a configuration choice on a small sample, not evidence that k = 5 is best in general.

**Safety condition (added before the check is run; the rule above measures detection only):** larger H means more assertions and therefore more chances to assert reference-specific behaviour (24% of the uncoupled faults in the 9.5 review were of that kind). Before k = 5 is frozen, the stored RQ2 completions of the development tasks are graded on both suites (`scripts/grade_hidden.py`; dev completions are allowed for tuning, D5), and every program that passes P and the k = 3 suite but fails the k = 5 suite is judged by the researcher (true fault / erroneous rejection / unclear). **If any is an erroneous rejection, k = 3 is chosen instead**, and the same check is applied to k = 3 against k = 1. The decision and the judged cases are recorded here.

**Safety check result (freia, 2026-11-24; `results_tier2_ext/a2/dev_k{1,3,5}/grading.json`):** 750 stored RQ2 completions of the 5 H-ready development tasks graded on P (stored) and H. `k3_vs_k5.md` and `k1_vs_k3.md` list **0 extra rejections**: k = 5 rejects nothing that k = 3 accepts. **`cover_k` = 5 is final** (development-stage policy).

| k | P pass | H pass | P∧H | P-pass/H-fail |
|---|---|---|---|---|
| 1 | 148 | 145 | 84 | 64 |
| 3 | 148 | 152 | 85 | 63 |
| 5 | 148 | 152 | 85 | 63 |

(k = 1 is not a subset of k = 3: its second greedy pick differs, and that test rejects one P-passing csn_12 program the larger suites accept.)

**Finding that blocks A2 on evaluation tasks: erroneous rejection on unspecified outputs.** P-pass/H-fail is concentrated on two tasks: post_24 (56 of 57 P-passing completions) and post_64 (7 of 7), at every k. Inspection:
- post_24 (`LocalPathExtractor`): the whole specification is "判断是否为本地路径" / "从文本中提取本地文件路径" (decide whether a string is a local path; extract local file paths from text). The A2 tests assert the reference's own regex heuristics (e.g. `'VIUP6o^Ygo3f97.4a'` is extracted from `'VIUP6o^Ygo3f97.4a m'`; `'kZzr%3 DTlykU[J-97z'` is not a local path). Nothing in the docstring determines these values.
- post_64 (`BaseTool`): `get_metadata()` is documented only as "a dictionary containing the tool's metadata"; the tests assert the reference's exact key set (including `require_llm_engine`, excluding `user_metadata`).

**Why Stage 2 is not affected but H is.** A mutant is derived from the reference, so any behavioural difference from the reference is a change of the program under test: witnesses and RQ1 robustness stay valid. An RQ2 completion is an independent implementation written from the skeleton docstrings only; it can only be held to what those docstrings specify. A reference-differential oracle therefore needs to know which outputs are specified. The contracts (D1/D2) fix inputs and comparison rules but not that.

**Confirmed on the stored data (freia, 2026-11-24).** The recomputed differences of the P-pass/H-fail programs: on post_24 the reference extracts one "path" from a random string where the completions extract none (`length 1 != 0`) and disagrees on `is_local_path`; on post_64 the completions return another metadata key set (no `require_llm_engine`, or extra keys: 7 vs 9 entries). These are erroneous rejections on unspecified outputs.

### 10.2 Rule R7: output specification for hidden assertions (2026-11-24, before any evaluation-task H)

Decided on development evidence (10.1) and applied before A2 runs on any evaluation task. Stored separately in `config/extensions_protocol/output_spec_v1.json`, so the Stage 2 contracts and their hashes stay unchanged.

- **Levels**, per public callable, judged from the **skeleton docstrings only** (what the coding models saw), never from the reference body or any outcome:
  - `value`: the docstring determines the returned value for every contract-valid input (a rule, a formula, an example, a mathematical definition);
  - `type`: only the kind of value is promised (e.g. "a dictionary containing metadata", "a list of paths");
  - `none`: no return value is promised (no Returns section, setters).
- **What H asserts:** `value` the API token (as before); `type` the type family of the returned value (numbers form one family, containers by kind, objects by class); `none` only that the call returns normally. **Exception tokens are always asserted** (valid-domain exceptions are the documented ones, D2), so a completion that raises where the reference returns is detected at every level. Constructors are always `value`.
- **Same restriction for selection and assertion:** the A2 kill matrix uses the restricted comparison, so a test is kept only if it kills a discovery group *under what the specification allows*. Witness search and Stage 2 results are unchanged (a mutant is derived from the reference, so every difference is a change of that program).
- **Review:** Claude drafts the levels with a one-line reason each; the researcher reviews. Development tasks may run on drafts (tuning); evaluation tasks need `status: reviewed` (`build_a2.py` refuses otherwise). A callable missing from an entry defaults to `type` and is recorded (`levels_defaulted`).
- **Expected consequence, stated in advance:** on weakly specified tasks H shrinks to type and exception checks, or the task is not H-ready (no discovery group is killable under the specification). **The strength of a hidden oracle is bounded by the strength of the specification**; the share of tasks and callables at each level is reported.
- Development drafts: csn_12 (gcd value, factorize type), csn_52 (`__call__` type), csn_54 (`__call__` type), post_24 (both type), post_64 (get_metadata type, the setters and execute none).

**R7 made explicit (2026-11-24, before the dev re-check):**
- **`none` is not "no assertion".** It asserts that the call returns normally. A step is only asserted on the reviewed valid domain (D2): contract-valid inputs on which the reference completes, or raises an exception the docstring documents.
- **Exception rule.** (a) A documented exception the reference raises is asserted by type (`isinstance`, never the message). (b) A completion that raises where the reference returns normally on a contract-valid input fails H, at every level. Rule (b) is the completion counterpart of D2's `api_exception` witness for mutants, and it rests on the contract review having fixed the valid domain. It is a judgement, so it is **measured separately**: `grade_hidden.py` classifies every P-pass/H-fail program by failure kind (`value`, `type`, `unexpected_exception`, `missing_documented_exception`, `other_exception_type`) and counts the programs that fail *only* by an unexpected exception (`exception_only`). If, on development tasks, those cases are erroneous rejections (the docstring arguably allows the input to be refused), rule (b) is relaxed to the `value` level only, before any evaluation-task H.
- **Type match** (`oracles/spec.py`, `type_family`), fixed:
  - `None` is its own family (a method that returns `None` where a value is promised, or the reverse, mismatches);
  - `bool` is its own family;
  - `int`, `float`, `Decimal`, `Fraction` form one numeric family; `complex` is separate;
  - `str` and `bytes` are separate families;
  - `list`, `tuple`, `deque` and `range` are one sequence family;
  - `set` and `frozenset` are one family;
  - every `dict`, subclasses included, is the mapping family;
  - an instance of any other class (including the task's own class), an enum member, or a value with an exact representation (e.g. `datetime`) matches **by class name only**: a subclass does not match its base. In this benchmark completions re-implement the skeleton's class, so the name is the stable identity;
  - a class object (a returned type) matches any class object;
  - a value too large to tokenise (digest) gets no type check, only "returns normally".

**R7 development check (freia, 2026-11-24; `results_tier2_ext/a2/dev_k5_r7`, k = 5, the dev drafts):**

| | before R7 (k = 5) | with R7 |
|---|---|---|
| H-ready development tasks | 5 / 5 | 5 / 5 |
| tests kept | 34 | 28 |
| discovery groups covered | 18 / 18 | 13 / 18 |
| held-out primary groups detected by P / H / P or H (of 14) | 8 / 11 / 12 | 8 / 9 / 11 |
| held-out detected only by H | 4 | 3 |
| mean per-task held-out detection rate, H | 0.69 | 0.38 |
| P-passing completions failing H (of 148) | 63 | **0** |

**Reading.**
- R7 removes every P-pass/H-fail case on the development completions (63 → 0), including the 56 on post_24 and 7 on post_64 traced to unspecified outputs.
- H still adds detection on held-out faults (P or H 11 vs P alone 8), but less than before: 5 discovery groups are only killable through unspecified outputs, and the mean per-task H rate halves. This is the cost of asserting only what the docstrings promise, and it is the expected consequence stated in 10.2.
- **Limits of this check:** (a) the exception rule (b) is not exercised: no P-passing development completion fails H, so there is no exception-only case to judge; it is measured again in the audit. (b) With 0 P-pass/H-fail on 148, the development completions give no evidence yet that H finds real hidden faults; that question is Stage 5's, on the evaluation cohort. (c) n is small: 5 tasks, 14 held-out groups.
- `H pass` (491 of 750) exceeds `P pass` (148): H is not a superset of P and is graded separately (P∧H is the combined criterion).

**Status:** R7 is adopted. The development levels become `reviewed` once the researcher confirms them. Next comes the R7 review of the 98 evaluation contracts (233 callables; sheet `doc/extensions/output_spec_review_eval.md`): Claude drafts, the researcher reviews. Then A2 runs on the evaluation tasks.

**R7 addition (2026-11-24, from the development review).** A `type` level asserts the type family the *reference* returns. It may therefore be used only where the reference's return type agrees with the docstring. Where the reference contradicts the docstring, the level is `none`. Case: csn_52 `BitField.__call__` promises "a list", but the reference returns `None` for 0 and a bare string for one set bit (contract review note); its draft changed from `type` to `none`.

**R7 development rerun after the csn_52 revision (freia, 2026-11-24; `results_tier2_ext/a2/dev_k5_r7b`; the first R7 run `dev_k5_r7` is kept unchanged).** Between the runs, only csn_52's level changed (`type` → `none`); witness input, code and the other four tasks' levels are identical.

| | R7 first run (`dev_k5_r7`) | R7 rerun (`dev_k5_r7b`) |
|---|---|---|
| tests kept | 28 | 25 (csn_52: 8 → 5) |
| discovery groups covered | 13 / 18 | 9 / 18 |
| held-out primary groups (4 tasks, 14 groups): P / H / P or H | 8 / 9 / 11 | 8 / 3 / 8 |
| held-out detected only by H | 3 | **0** |
| P-passing completions failing H (of 148) | 0 | 0 |

**Reading.**
- The 3 H-only detections of the first R7 run all came from csn_52's type check, which asserted the reference's docstring-contradicting return types (`None` / a bare string where "a list" is promised). Under the corrected rule they are not valid assertions, so they are gone.
- **On the development tasks, the specification-faithful A2 adds no held-out detection beyond P, and it rejects no P-passing completion.** It is sound, but here it is not stronger than P. The development tasks are mostly one-line docstrings (post_24, csn_52, csn_54), so this is the bound stated in 10.2 at work. Whether H adds detection on the evaluation cohort is an open empirical question for RQ4c and Stage 5. It is not assumed.
- Five tasks are A2-ready, but only four have held-out primary groups; the fifth contributes no held-out population.

**Protocol wording (R7), made explicit.**
- The **docstring defines what is promised**; the reference is used only as a **consistency check**. `type` asserts the type family the reference returns, and may be used only where that family agrees with the docstring's promise; where the reference contradicts it, the level is `none`.
- **Constructors** are not classified by level. A constructor step asserts only that construction succeeds and yields an instance of the class, or raises the same documented exception; it promises no ordinary return value.
