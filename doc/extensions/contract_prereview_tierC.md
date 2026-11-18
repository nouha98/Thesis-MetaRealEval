# Contract pre-review: tier C (15 tasks, 3 or more weak parameter types)

Prepared by Claude as a proposal. **You are the reviewer of record**: nothing here is in `contracts_v1/reviewed/`
until you confirm a verdict. No detection result was looked at (blindness, rule R6).

Tier definition: supported draft, not yet reviewed, 3 or more generated parameters whose type comes from
`p_literals`, `default` or `none` (weak evidence). Of the 166 unreviewed supported drafts: tier A 120 (no weak
parameter), tier B 31 (1–2), tier C 15.

## Rules applied (so later tiers are decided the same way)

| # | Rule | Why |
|---|---|---|
| R1 | Reject when every generated callable's reference raises `NotImplementedError` (abstract interface). | The reference has no behaviour to specify. A solution that implements the method is "detected" only for disagreeing with a stub. Without a documented-raises edit these tasks drop out anyway (undocumented exception makes the domain uncertain); adding the edit would create junk tests, so reject explicitly. |
| R2 | Reject when a needed input is a framework or non-stdlib object the generator cannot build (framebuffer, XML `Element`, request objects), unless the reference never touches it. | Generated `bool`/`None` inputs are not contract-valid. Type evidence from P literals fits only the reference's accessor, not the documented type. |
| R3 | Reject when the docstring states no behaviour (template text such as "Summary", "Description"). | Nothing to hold a solution to except the reference (D7 only). |
| R4 | Reject classes whose behaviour is background concurrency (worker pools, threads, timeouts). | Nondeterministic, so detections are masked or noise. |
| R5 | When the docstring states a type ("should be a dictionary"), edit the contract to generate it instead of leaving the method ungenerated. | A stateful class tested only through query methods on an empty store has no informative generated scenarios. |
| R6 | Verdicts never use detection results. | Keeps C1b blind to the LLM-vs-operator effect. |

## Verdicts

| # | task | class | proposed | edits / reason |
|---|---|---|---|---|
| 1 | RCE_csn_snippet_142 | ProjectTemplate | **accept with edits** | `get_project_template`: `name` str, `output_type` str, `debugger` str or None, `build_dir` str (the `float` option comes from one P literal and contradicts the class doc: "Build output path"). `debugger` str or None is an inference: the doc says only "Debugger" and the reference just stores it. Returns a dict, so comparison is by value. Only 1 P scenario. |
| 2 | RCE_csn_snippet_157 | HashMixin | **accept with edits** | `get_placeholder`: `value` str or None (docstring: "the `value` string is checked"), with a hint value starting with `\x` so the keep branch is reached; `compiler` and `connection` None (docstring: ignored). `get_encrypt_sql` and `pre_save` stay ungenerated (need a DB connection and a model instance). *Corrected 2026-11-18:* the class defines `encrypt_sql = None`, so no `AttributeError`; the reference returns `'%s'` for None or `\x…` and `None` otherwise. The docstring states that decision, so the tests are meaningful. |
| 3 | RCE_csn_snippet_171 | RunDAO | **reject** (R1) | Every method raises `NotImplementedError`. |
| 4 | RCE_csn_snippet_186 | TnsFilter | **reject** (R2) | `match(root, ns)`: `root` is documented as an XML `Element`; the P test passes a `dict` only because the reference calls `root.get(...)`. A solution written for `Element` could use another accessor and be flagged as faulty by construction. |
| 5 | RCE_csn_snippet_250 | MHMSBFormat | **reject** (R2) | `framebuf` is a framebuffer object (the draft typed it `bool`). |
| 6 | RCE_csn_snippet_251 | MVLSBFormat | **reject** (R2) | Same. |
| 7 | RCE_csn_snippet_252 | RGB888Format | **reject** (R2) | Same. |
| 8 | RCE_csn_snippet_274 | BasePermission | **accept with edits** | `request`, `view`, `obj` are opaque (type any, hint None; the draft's `tuple`/`bool` come from P literals). The reference returns the constant `True`; the docstring does not say the default is True, so detections are disagreement with the reference (D7). Probably no near-miss fault, in which case it excludes itself; that is not a reason to reject (R6). |
| 9 | RCE_csn_snippet_275 | Signer | **reject** (R1) | `sign` and `verify` only raise `NotImplementedError`. |
| 10 | RCE_csn_snippet_30 | LazyOpResult | **reject** (R3, R2) | `evaluate` docstring is "Summary ... Description". The constructor's `expr` is documented as `WeldObject` / numpy array (the draft typed it `int` from one P literal). `WeldObject` is neither imported nor defined in the reference, so every `evaluate` call raises an undocumented `NameError`. |
| 11 | RCE_csn_snippet_45 | TokenStoreBase | **reject** (R1) | All three methods raise `NotImplementedError`. |
| 12 | RCE_csn_snippet_85 | SessionListener | **reject** (R1) | `callback` and `errback` only raise `NotImplementedError`. |
| 13 | RCE_csn_snippet_98 | LCModel | **reject** (R1, R2) | `fit` and `predict_unseen` raise `NotImplementedError`; `extend_partial` takes numpy arrays. |
| 14 | RCE_post_snippet_268 | IndexManager | **accept with edits** (R5) | The draft leaves `index`, `remove`, `reindex` ungenerated, so generated scenarios only query an empty store. Docstrings say the document "should be a dictionary". Edit: `index(doc)`, `remove(doc)`, `reindex(old_doc, new_doc)` take `dict[str, int or str]`; `query(field: str, value: int or str)`; `query_in(field: str, values: list[int or str])`. This is the one change in the batch that adds real tests. |
| 15 | RCE_post_snippet_280 | BoundWorkerMethod | **reject** (R4) | Worker pool and background execution; `*args/**kwargs` are forwarded to an arbitrary wrapped function; `run_and_wait` documents the base `Exception`, which would make any exception valid. |

**Totals:** 4 accept with edits, 11 reject. If you agree, the evaluation population loses 11 of 166 supported
drafts here.

## Decision (user, 2026-11-18)
- All 15 verdicts confirmed: 4 accept with edits, 11 reject. Row 2 (csn_157) is "Changed": same verdict, corrected reasoning.
- R1–R6 are the standing rules for tiers A and B. **No R7**: an undocumented constant reference behaviour (csn_274) limits interpretation but is not a rejection reason. Its detections are reported as disagreement with the reference, not as specification violations.
- Written to `reviewed/` on 2026-11-18 (see the tier A sheet).
