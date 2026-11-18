# Protocol decisions before freezing (plan rev. 9.1)

*2026-11-12. For review by you and Gordon before any confirmatory run. No model was called and no full evaluation was run.*

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

## 9. Stage 2b: mutant–fault coupling (D8). DRAFT for discussion with Gordon; nothing frozen

*Added 2026-11-17 for supervisor note 2. No coupling code has run and no coupling value has been computed. The order is: this draft → discussion → technical pilot (blind to the LLM-vs-operator effect) → approval of the final text → freeze `coupling_v1.json` (the SPEC and its sha256, plus the per-task solution-group digests; there is no separate solution-groups file) → confirmatory run.*

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

### 9.7 Limitations to state

- supported subset only, and the conditional population only;
- LLM solutions are not historical bugs;
- coverage is not controlled (the null controls detection-set size, which is a different confounder);
- tests are non-uniform scenarios, dominated by generated ones;
- same-panel circularity is handled only through the cross-model rule;
- detections are reference-relative: on outputs the docstring leaves open, a "fault" deviates from the reference without being shown to violate the specification (P-fail-only sensitivity in 9.4);
- the contract population is shaped by review rules R1–R6 (abstract interfaces, framework inputs, template docstrings and concurrency classes are excluded);
- Tier 1 is out of scope, because HumanEval has a single `check()`.
