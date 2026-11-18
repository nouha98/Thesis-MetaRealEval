# Contract pre-review: tier B (31 tasks, 1–2 weakly typed parameters)

Prepared by Claude as a proposal; **you are the reviewer of record**. Rules R1–R6 are in
`contract_prereview_tierC.md`. No detection result was looked at (R6). Evidence: the reference body and
docstrings of every generated method (scratchpad digests), 2026-11-18.

## R1 clarifications (confirmed by the user 2026-11-18; not new rules)
R1's reason is "the reference has no behaviour to specify". Two cases follow from that reason and are applied
below:
- **R1a. Empty stubs count as abstract.** A method whose body is only `pass` or a docstring, in a class
  documented as an interface or base to override, is treated like `NotImplementedError`. Tasks that depend on
  this: 113, 141, 216, 279, 302, post_252.
  It does **not** apply when the no-op *is* the documented behaviour (csn_147, "No-op hash function").
- **R1b. Mixed classes.** When only some methods are abstract, those methods are set to `generate=false` and
  the rest are kept (csn_46, csn_82).

## Parameter-level consequences of R5 (applied from row 29 on; also used in tier A)
- **R5a. Ignored parameter, no stated effect:** opaque (type any, hint None), and no invented type. Applies to
  csn_33 `exc`, post_194 `error` and csn_147 `data`.
- **R5b. Ignored parameter whose name or docstring states an effect** (e.g. `max_length`): `generate=false`, so
  the default is used. Otherwise a solution that honours the parameter would be flagged only because the
  reference ignores it. Applies to post_227.

## Verdicts

| # | task | class | proposed | edits / reason |
|---|---|---|---|---|
| 1 | csn_109 | HistoryManager | **reject** (R2) | Core input `operation` is a callable (docstring and annotation); the draft typed it `bytes`. Without it only `size()`/`reset()` on an empty stack remain. |
| 2 | csn_113 | FileLikeIO | **reject** (R1a) | `exists`/`remove` are docstring-only interface stubs ("For normal files, the implementation is …"). `remove` would also touch the file system. |
| 3 | csn_125 | FenwickMin | **accept with edits** | ctor `size`: int, min 0 (draft: bool or int). `update.val`: int (draft: bool or int; docstring "a value", the reference compares it with `min`). `prefixMin.a`: int (docstring); negative `a` → infinity is documented. **Added when writing the file:** `update.a` min 0. The docstring says "index in t", and in the reference a negative index never terminates (`i = a + 1 <= 0`, `i += i & -i` stays 0), so generated scenarios would time out. |
| 4 | csn_141 | Api | **reject** (R1a) | `call_action` is `pass`; the class doc says implementations must provide it. |
| 5 | csn_147 | NoHashContext | **accept with edits** | Documented no-op hash: `update` does nothing, `digest`/`hexdigest` return None. `update.data` and ctor `data`: opaque (R5a). The reference never reads them and no docstring types them, so no type is imposed. Detections will be disagreement with the reference (a solution returning `b''`). |
| 6 | csn_149 | TorConfigType | **accept with edits** | `parse.s`: str (docstring "Given the string s"; draft: float from one P literal). The reference returns `s` unchanged. `validate` stays ungenerated (needs an instance). Low value. |
| 7 | csn_151 | AdaptiveCardComponent | **accept as drafted** | The only weak parameter is `to_json(**kwargs)`, which is not generated anyway. Ctor lists come from the docstring. |
| 8 | csn_170 | MetricsDAO | **reject** (R1) | `get`/`delete` raise `NotImplementedError` ("The MetricsDAO class is abstract"). |
| 9 | csn_172 | MultipleThings | **accept with edits** | `get_thing.idx`: int (docstring "the index"; draft: bytes, float or bool). ctor `things`: list (class doc "container for multiple things"; draft: bytes or set of bool). `name`: str ("mDNS server name"; draft: bytes). |
| 10 | csn_173 | SingleThing | **reject** (R2) | `get_name` returns `self.thing.title`: `thing` is a framework Thing object (draft: bool, so every `get_name` raises). |
| 11 | csn_184 | Encoder | **accept with edits** (R5) | `encode` was left ungenerated, yet its docstring says `@type s: str`. Edit: generate `encode`, `decode`, `needsEncoding` with `s`: str (docstring), plus hints containing XML specials (`a&b<c>"d'e`, `&amp;&lt;x&gt;`) so encoding paths are reached. Adds real tests. |
| 12 | csn_205 | ArgFilterBase | **reject** (R1) | Both methods raise `NotImplementedError` (documented). |
| 13 | csn_207 | IJavaStreamParser | **reject** (R1) | Both methods raise `NotImplementedError`. |
| 14 | csn_216 | PowerManagementObserver | **reject** (R1a, R2) | `pass` observer callbacks on an ABC; the input is a PowerManagement instance. |
| 15 | csn_222 | Transport | **reject** (R2, R4) | Needs a gateway, a connect coroutine and a protocol with a transport; asyncio I/O. |
| 16 | csn_273 | BasePagination | **reject** (R1) | `NotImplementedError`; inputs are an SQLAlchemy query and a request. |
| 17 | csn_278 | Dumper | **reject** (R1, R2) | `load` raises `NotImplementedError`; `dump` needs a record object. |
| 18 | csn_279 | SearchDumperExt | **reject** (R1a, R2) | `load` is docstring-only; `record_cls` is a class and `record` a record object. |
| 19 | csn_302 | ErrorHandler | **reject** (R1a) | `handle` is `pass` on an ABC. |
| 20 | csn_33 | ExceptionHandler | **accept with edits** | `wants` is documented: "This base class returns True for all exceptions by default". The reference never touches `exc` (`del exc`), so the R2 exception applies: `exc` opaque (hint None). `handle` stays ungenerated (documented "must be overridden"). Contrast with csn_274: here the constant is documented. |
| 21 | csn_46 | ShareClass | **accept with edits** (R1b) | Only `magic()` has behaviour (a documented dict). Set `canonical_uri`, `extract`, `service_number` to `generate=false` (they raise `NotImplementedError`). Low value. |
| 22 | csn_51 | Array | **accept with edits** | ctor `fmt`: str, the struct format (draft: bytes); hints of valid formats (`<I`, `>2H`, `4B`). `buf`: bytes, with hints of matching lengths (`b'\x01\x00\x00\x00'`, `b'\x00\x01\x00\x02'`). Random formats raise `struct.error` and drop out as domain-uncertain; expect few valid tests. |
| 23 | csn_53 | Bits | **accept with edits** | ctor `num_bits`: int, min 0 (draft: int or bool). `val`: int (class doc "Breaks an integer"). |
| 24 | csn_63 | StreamingFile | **reject** (R2) | `data_stream` is an iterator (`next(...)`); the generator has no iterator type, and lists raise `TypeError`. |
| 25 | csn_82 | Completer | **accept with edits** (R1b) | `complete` is `pass` on an ABC → `generate=false`. `relevant_part`: `original` str, `pos` int, min 0 (docstring of `complete` types them; draft had `pos` bool). |
| 26 | post_129 | TranscriptionBuffer | **accept with edits** | `partial_segments`, `completed_segments`: list[str] or None (draft: str/tuple). **Assumption recorded:** the string element type is inferred from the reference implementation (it stores and concatenates the lists), not stated by the docstring, which says only "segments". ctor `client_uid`: str (draft: list). |
| 27 | post_189 | RateLimiter | **reject** (R4, R2) | Real sleeping and timing; `env.sim.render()` needs a simulator object. |
| 28 | post_194 | ConstantDelayRetryPolicy | **accept with edits** | Documented: "Return the fixed delay while attempts remain; otherwise None". `error` is never touched → opaque (hint None; draft: float). ctor from annotations. |
| 29 | post_227 | ConversationTurn | **accept with edits** | ctor `user_message`: str or dict[str, str], with hint `{"content": "…60 chars…"}` so the dict path and truncation are reached. `message_index`: int. `get_preview.max_length`: **`generate=false`** (R5b). The reference ignores it and always truncates at 50; its docstring ("Get a preview of the user message for display in completions") promises nothing about it, so `get_preview` stays generated with the default. |
| 30 | post_252 | BasePlugin | **reject** (R1a, R2) | `register_frontend` is `pass`; the class doc says plugins must implement it; the input is a callable. |
| 31 | post_374 | ChannelIterator | **accept with edits** | ctor `num_channels`: int, min 0 (draft: bool or int). `get_channel.index`: int, min 0 ("Index of the channel"; draft: int or bool). |

**Totals:** 15 accepted (14 with edits, 1 as drafted), 16 rejected. 6 rejections depend on R1a.

**R5 sweep:** besides csn_184, the only other documented-type method left ungenerated is in rejected tasks
(113 `open`, 149 `validate`, which needs an instance).

## Decision (user, 2026-11-18)
- R1a and R1b confirmed. All 31 verdicts confirmed: 15 accept, 16 reject.
- Qualifications incorporated: row 5 `data` is opaque (R5a); row 26 assumption recorded; row 29 `max_length`
  is not generated (R5b).
- Written to `reviewed/` on 2026-11-18 (see the tier A sheet). Before the freeze, every accepted contract is
  checked to be usable: it loads, is still supported, and yields valid generated tests.
