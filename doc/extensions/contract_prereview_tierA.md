# Contract pre-review: tier A (120 tasks, no weakly typed method parameter)

Prepared by Claude as a proposal; **you are the reviewer of record**. Rules: R1–R6 (tier C sheet); R1a, R1b,
R5a and R5b (tier B sheet). No detection result was looked at (R6).

**Method.** An automatic flagger marked abstract stubs (R1/R1a), parameters the reference never reads
(R5a/R5b candidates), ungenerated methods (R5), and concurrency or I/O (R4). Then every task's reference body
was read. Tier A means the *method* parameters are well typed; constructor parameters can still be weak and are
reviewed too.

**Ignored parameters: three cases (safeguard confirmed by the user, 2026-11-18).** Each case needs evidence in
the task. "Ignored" means the reference body never reads the parameter.
- **R5a:** ignored, and neither the name nor the documentation promises an effect → pass None (opaque).
- **R5b:** ignored, and the *documentation* explicitly promises an effect → `generate=false`, so the default is
  used.
- **Neither:** ignored, and only the *name* suggests an effect while the documentation is silent → no automatic
  rule. Review the parameter individually and record the decision (csn_153 `flags`: kept as drafted).

**Drafter bug found:** csn_60 `get_encoding_name` is a `@staticmethod(encoding)`, but the draft has no
parameter, so every call would raise `TypeError`. I checked every static method in all supported drafts, and
this is the only case. It is fixed by the edit in row 48.

## Batch 1 (49 of 120)

| # | task | class | proposed | edits / reason |
|---|---|---|---|---|
| 1 | csn_101 | ClosableNamedTemporaryFile | **reject** (R4) | Creates a real temp file with a random name and deletes it in `__del__`; the only generated call is `close()`. |
| 2 | csn_104 | BufferSegment | **reject** (R1) | All methods raise `NotImplementedError`. |
| 3 | csn_105 | BufferWithSegmentsCollection | **reject** (R1) | Same. |
| 4 | csn_108 | Details | **accept with edits** | ctor `details`: dict[str, str or int] (draft: bool). Inferred from the reference (`self.details[attr]`) and the class doc ("data for single IP address"). Only the `all` property is observed. Low value. |
| 5 | csn_115 | Variable | **accept as drafted** | |
| 6 | csn_116 | Solver | **reject** (R1) | All three methods raise `NotImplementedError` (the message is built first, so the flagger missed it). |
| 7 | csn_119 | DummyClass | **accept as drafted** | `run` is `pass`, but the docstring says "Do nothing": the no-op is the documented behaviour (R1a exception). Low value. |
| 8 | csn_120 | NestedDummyClass | **accept as drafted** | Same. |
| 9 | csn_135 | NoOpTraceId | **accept as drafted** | Constant id string. Low value. |
| 10 | csn_139 | LazyField | **reject** (R2) | `klass` is a Field class (`signature(self.klass.__init__)`); the draft typed it `bytes`. |
| 11 | csn_153 | SelectorPattern | **accept as drafted** | `match` ignores `flags`, but only the name suggests an effect (no docstring statement), so R5b does not apply (safeguard). Returns an `re.Match`; random patterns raise `re.error` and drop out. |
| 12 | csn_159 | Style | **accept as drafted** | |
| 13 | csn_160 | SBVCueBlock | **accept with edits** | Hint for `lines`: `["0:00:01.000,0:00:02.500", "Hello"]`. Random lines never match the timing pattern, and `from_lines` then fails an `assert` (undocumented), so without a valid example only `is_valid → False` is tested. |
| 14 | csn_161 | SRTCueBlock | **accept with edits** | Hint `["1", "00:00:01,000 --> 00:00:02,500", "Hello"]`, same reason. |
| 15 | csn_162 | WebVTTCommentBlock | **accept with edits** | Hints `["NOTE a comment"]`, `["NOTE", "two", "lines"]`. |
| 16 | csn_163 | WebVTTStyleBlock | **accept with edits** | Hint `["STYLE", "::cue { color: red }"]`. |
| 17 | csn_168 | Gateway | **reject** (R1) | `respond` raises `NotImplementedError` ("Must be overridden"). |
| 18 | csn_169 | Cursor | **reject** (R1) | Same. |
| 19 | csn_17 | Variable | **accept with edits** | ctor `val`: int, str or list (draft: dict from one P literal); `_type`: str. Inferred from the class doc ("variable with value and type"). `__str__` returns `str(val)`. |
| 20 | csn_175 | S2Image | **reject** (R1) | Both methods raise `NotImplementedError`. |
| 21 | csn_178 | TableCell | **accept with edits** | `alignment` (keyword-only, type `Alignment`): str with hints `<`, `>`, `^` (draft: from a P literal). |
| 22 | csn_193 | CkClass | **accept as drafted** | Base class with empty `flags_dict`/`fields`, so outputs are `[]`, `''`, `{}`. Real code, not stubs. Low value. |
| 23 | csn_199 | UriParam | **accept with edits** | ctor `uri`: str (class doc "a URI value"; `__repr__` must return a str). Draft: bool. |
| 24 | csn_2 | OcrQualityDictionary | **accept as drafted** | |
| 25 | csn_204 | AuthenticationBase | **reject** (R1, R2) | `get_request_credentials` raises `NotImplementedError`; `authenticate_request` needs Flask's request context. |
| 26 | csn_217 | FilteredValueIndicator | **accept as drafted** | Constant `'[Filtered]'`. Low value. |
| 27 | csn_218 | RepeatValueIndicator | **accept as drafted** | |
| 28 | csn_220 | RateLimitsInfo | **accept with edits** (R5) | `from_dict(data)` ("Create … from a dictionary") and `from_headers(headers)` ("from HTTP headers") were left ungenerated. Generate both with dicts, hints `{"interval": 1.0, "limit": 10, "remaining": 5}` and `{"X-RateLimit-Interval": "1", "X-RateLimit-Limit": "10", "X-RateLimit-Remaining": "5", "X-RateLimit-Reset": "0"}`. Observe the returned object through attributes `interval`, `limit`, `remaining`, `throttled`. Without this, `__str__` on the class defaults (None) raises `TypeError` and nothing is valid. |
| 29 | csn_231 | WordArray | **accept as drafted, provisional** | `__len__` returns a float (`len/2`), so `len(x)` raises `TypeError`. It stays in only if the usability check finds valid tests. |
| 30 | csn_233 | Template | **reject** (R2) | `versions` maps names to TemplateVersion objects (`.timestamp()`). |
| 31 | csn_240 | ExternalIssue | **accept with edits** | All five ctor parameters are str or None (draft: None only). Evidence: the `__init__` docstring gives URLs, project, ticket ID and date; `submit_date` as str is an inference. |
| 32 | csn_241 | Issue | **accept with edits** | ctor `issue_type`: str, hints `pb001`, `ab001`, `si001`, `ti001`, `nd001` (docstring "Allowable values"); `comment`: str or None. `external_issue_add` stays ungenerated (needs an ExternalIssue object). |
| 33 | csn_245 | Sampleable | **reject** (R2) | Mixin: `get_default_sample` reads `self.name`, which only the host class defines, so every call raises. |
| 34 | csn_257 | UserProfileService | **accept with edits** (R1b) | `save` is a `pass` stub in an override-me service → `generate=false`. Keep `lookup` (`UserProfile` is defined in the module). |
| 35 | csn_272 | UserContextFormViewMixin | **reject** (R2) | Django view mixin (`self.request.user`, `super().get_form_kwargs()`). |
| 36 | csn_276 | QuerySingle | **reject** (R2) | Needs a connection object with `query_single`. |
| 37 | csn_280 | SystemFieldContext | **accept with edits** | `field` and `record_cls` are a field object and a record class, but the reference only stores and returns them, so the R2 exception applies: opaque (hint None). Low value. |
| 38 | csn_286 | AccessEnumMixin | **reject** (R2) | Enum mixin (`self.value`, `cls(level) in cls`). |
| 39 | csn_288 | Aspect | **reject** (R4) | `getId` returns `id(self)`, which differs between runs; `clone` returns an own-class copy. |
| 40 | csn_304 | CommandDispatcher | **reject** (R2) | Core input is a callable (`command(fn)`); without it `execute_command` only raises the documented `KeyError`. Same as csn_109. |
| 41 | csn_305 | QuotaBase | **reject** (R2) | Reads `self.resources` from the host and an undefined `QuotaHealth`. |
| 42 | csn_42 | WifiManager | **reject** (R2) | Needs a device object (`device.shell(...)`). |
| 43 | csn_48 | Datetime | **accept with edits** (R4, R1b-style) | `now()` → `generate=false` (current time, R4). Keep `unpack(data: bytes)`, with a valid 12-byte hint `b'\x00\x00\x00\x00\xe8\x07\x1e\x0c\x18\x01\x0f\x01'`. `pack` stays ungenerated: **technical limitation**, since the generator's type vocabulary is builtins only (`contracts._BASE`: int, float, str, bytes, containers, unions) and has no `datetime`; `pack` also needs a timezone-aware value (`utcoffset()`). Not worth new generator code for one method. |
| 44 | csn_49 | QuilAtom | **reject** (R1) | All methods raise `NotImplementedError`. |
| 45 | csn_50 | MetPyChecker | **reject** (R2) | `tree` is an AST and `MetPyVisitor` is external. |
| 46 | csn_56 | Collection | **reject** (R1a) | Docstring-only stubs in an interface ("Customized interface"). |
| 47 | csn_6 | RecordFile | **accept as drafted** | |
| 48 | csn_60 | CodePageManager | **accept with edits** | Drafter bug: add `encoding: str` to `get_encoding_name` (`return encoding.upper()`). ctor `data`: dict[str, str] (draft: int; `get_encoding` indexes it), inferred from the reference. |
| 49 | csn_69 | BaseStorage | **reject** (R1a) | `@abstractmethod` placeholders (`return`, `return False`, `return 0`); docstring "Abstract interface". |

**Batch 1 totals:** 27 accepted (12 as drafted, 15 with edits), 22 rejected.

**Pattern added from this batch:** hints for patterned string inputs (rows 13–16, 43). When a method's
documented input is a structured string or packet (cue timings, binary timestamp), random values never reach the
documented branch. One valid example is added as a hint, in the same way as csn_184's XML specials. This is not
a new rule: it is what R5 already asks, so that a documented method is actually exercised.

**Batch 1 decision (user, 2026-11-18):** approved: 27 accept (12 as drafted, 15 with edits), 22 reject.
- csn_231 is provisional on the usability check.
- csn_280 is accepted with the limitation "weak behavioural evidence".
- csn_48 `pack` is a recorded technical limitation.

**Usability check (applies to every accepted contract, all tiers).** Before the freeze, each reviewed contract
must load, still be supported, and yield at least one valid generated test. A contract that fails is removed
from the population, and the removal is recorded here.

## Batches 2 and 3 (71 of 120)

Two applications recorded here so that later readers see the same logic:
- **R5a replaces only invented types.** An ignored parameter with an *annotated* type keeps it (post_225
  `operation: str`, post_256 `tool_name: str`); the annotation is documentation.
- **Undefined dependency = R2.** A class whose module uses a name it never defines or imports cannot be built or
  called (csn_305 `QuotaHealth`, post_152 `TrieNode`, post_347 `MessageType`).
- **Parameter-level R4.** Where only one code path is nondeterministic, that path's trigger is not generated and
  the rest of the method is kept (post_295, post_112).

| # | task | class | proposed | edits / reason |
|---|---|---|---|---|
| 50 | csn_7 | RecordLevel | **accept as drafted** | |
| 51 | csn_75 | Geometry | **reject** (R1) | Both methods raise `NotImplementedError`. |
| 52 | csn_8 | RecordProcess | **accept as drafted** | |
| 53 | csn_84 | Scheme | **accept with edits** | ctor `title`: str (draft: any/none; written into an XML `title` element). `to_xml` returns an `ET.Element`, compared as opaque. `add_argument` stays ungenerated (needs an Argument object). |
| 54 | csn_9 | RecordThread | **accept as drafted** | |
| 55 | post_112 | SessionResetHandler | **accept with edits** (R4, parameter level) | ctor `log_func` `generate=false` (a callable; the default `print` is used). `get_reset_info` `generate=false`: it returns `time.time()` of the reset. Keep `check_for_reset_command`, `mark_reset_detected`, `is_reset_pending`, `clear_reset_state`. `find_reset_session_file` stays ungenerated (file system). |
| 56 | post_132 | Text_background | **accept with edits** | ctor `style` is `Literal[1, 2]`: int, min 1, hints 1, 2 (draft: from the default only). |
| 57 | post_134 | Text_shadow | **accept as drafted** | |
| 58 | post_14 | templater | **accept with edits** (R4) | `get_A_template` → `generate=false` (it uses `random.choice` / `random.sample`). Keep `get_Q_template`. Low value. |
| 59 | post_141 | GoalRedirectionTemplate | **accept as drafted** | Deterministic f-string templates. |
| 60 | post_142 | SystemOverrideTemplate | **accept with edits** (R4) | `enhance_emergency_protocol` → `generate=false`: it embeds `hash(attack)`, which is salted per process for str. Keep the other five methods. |
| 61 | post_152 | Trie | **reject** (R2) | Undefined dependency: `TrieNode` is used in `__init__` but not defined in the module, so the class cannot be constructed. |
| 62 | post_153 | ConditionalTracker | **accept with edits** | Hints for `process_line.line`: `ifeq ($(A),1)`, `else`, `endif`, `ifdef X` (the draft's only hint is random text, so the conditional branches are never reached). |
| 63 | post_154 | ShellUtils | **accept with edits** | Hints: `if [ -f x ]; then`, `for i in 1 2; do`, `fi`, `done;`, `a && b` (same reason). |
| 64 | post_155 | PatternUtils | **accept as drafted** | 17 P scenarios supply branch-reaching lines. |
| 65 | post_159 | MemoryFormatter | **accept as drafted** | |
| 66 | post_16 | ObservabilityManager | **accept as drafted** | `add_callback` stays ungenerated (callable). |
| 67 | post_165 | ToolHistory | **accept as drafted** | |
| 68 | post_167 | PackingMetrics | **accept as drafted** | `print_aggregated_stats` writes to stdout, which is not observed. |
| 69 | post_173 | Clock | **accept as drafted** | Documented `ValueError`. |
| 70 | post_182 | OutputSink | **reject** (R1) | `write` raises `NotImplementedError`; `finalize` is an empty stub. |
| 71 | post_185 | TopKStringTracker | **accept as drafted** | |
| 72 | post_19 | MarkdownCleaner | **accept as drafted** | |
| 73 | post_209 | DriverAnalyzer | **accept as drafted** | `file_contents` keys are documented as `Path`, but the reference uses only `.values()` (R2 exception). |
| 74 | post_218 | CBlock | **accept as drafted** | |
| 75 | post_219 | TokenUsageTracker | **accept as drafted** | |
| 76 | post_22 | DocumentAnalyzer | **accept as drafted** | |
| 77 | post_221 | GitHubTokenPool | **accept as drafted** | |
| 78 | post_222 | ModelConfig | **accept as drafted** | The ctor reads environment variables, but only `get_supported_models` (a constant list) is generated. Low value. |
| 79 | post_223 | BedrockAgentCoreContext | **accept as drafted** | Class-level `ContextVar`s. |
| 80 | post_225 | PrecisionPreservingDataHandler | **accept as drafted** | `operation` is ignored, but it is annotated `str`, so it is kept (see above). Identity functions. Low value. |
| 81 | post_226 | PriceFormatter | **accept as drafted** | |
| 82 | post_23 | GitHubURLExtractor | **accept as drafted** | |
| 83 | post_232 | Stopwatch | **reject** (R4) | `time.perf_counter()` elapsed times. |
| 84 | post_242 | ImmediateFlushSink | **reject** (R2) | Needs a stream object; all behaviour is writes to it (the default is stderr). |
| 85 | post_243 | PrintAndFlushSink | **accept as drafted** | Writes to stdout (not observed); `flush` is a documented no-op ("Already flushed on every write call"). Low value. |
| 86 | post_245 | CallableRegistry | **reject** (R2) | Core input is a callable (`register`); same as csn_109 / csn_304. |
| 87 | post_249 | Message | **accept with edits** | `from_dict` hint `{"role": "user", "content": "hi"}` (random dicts raise `KeyError`). Compare the returned `Message` by attributes `role`, `content` (draft: opaque). |
| 88 | post_253 | PromptLogger | **reject** (R4) | Log files, `os.makedirs`, `os.remove`, `datetime.now()`. |
| 89 | post_254 | TimeTracker | **reject** (R4) | Reads history files; `datetime.now()`. |
| 90 | post_255 | CacheKeyBuilder | **accept as drafted** | |
| 91 | post_256 | PromptPatternMatcher | **accept as drafted** | `tool_name` is ignored but annotated `str`, so it is kept. |
| 92 | post_264 | User | **accept as drafted** | |
| 93 | post_281 | FewShotFormat | **accept as drafted** | |
| 94 | post_285 | Block | **accept as drafted** | |
| 95 | post_286 | NavigationAction | **accept as drafted** | |
| 96 | post_29 | LastUsedParams | **reject** (R4) | Files under `Path.home()`. |
| 97 | post_294 | CodeManager | **accept as drafted** | |
| 98 | post_295 | ToolSelector | **accept with edits** (R4, parameter level) | `select_tools.num_agents` → `generate=false`: the default None keeps the single-agent path, because the multi-agent path uses `random.choice`. |
| 99 | post_305 | ArazzoComponentsBuilder | **accept as drafted** | |
| 100 | post_307 | ReferenceValidator | **accept as drafted** | |
| 101 | post_308 | InMemoryBlobStore | **reject** (R4) | `save` returns `uuid4()` ids and stamps `time.time()`; `load`/`info` need those ids. |
| 102 | post_312 | NotesSearchController | **accept as drafted** | |
| 103 | post_324 | CommandRateLimiter | **reject** (R4) | `time.time()` windows; `time_to_next_call` is timing-dependent. Same as post_189. |
| 104 | post_325 | AgentInfo | **accept with edits** | ctor `file_path`: str or None (the reference only applies `str()`; R2 exception), so `path` has a defined value. `module`/`yaml_document` stay None (R2). |
| 105 | post_339 | MCPConfigGenerator | **accept with edits** (R4) | `write_config` → `generate=false` (writes a file and prints). Keep `generate_config`. |
| 106 | post_340 | Fix | **accept with edits** | ctor `value`: float (draft: bool). Inferred from the class doc ("fixed state variable in the optimization problem"). |
| 107 | post_341 | Free | **accept with edits** | ctor `guess`: float (same reasoning). |
| 108 | post_342 | Maximize | **accept with edits** | Same. |
| 109 | post_343 | Minimize | **accept with edits** | Same. |
| 110 | post_346 | EventDataNormalizer | **accept as drafted** | |
| 111 | post_347 | MessageBuilder | **reject** (R2) | Undefined dependency: `MessageType` is not defined in the module, so every method raises `NameError`. |
| 112 | post_351 | AgentInfo | **accept with edits** | Same as row 104. |
| 113 | post_368 | PromptCompiler | **reject** (R4) | Reads prompt files and creates `.apm/compiled`. |
| 114 | post_371 | WorkflowDefinition | **accept as drafted** | |
| 115 | post_41 | HeaderManager | **accept as drafted** | |
| 116 | post_42 | ScreenManager | **accept as drafted** | |
| 117 | post_45 | TokenBucketRateLimiter | **reject** (R4) | Time-based refill. |
| 118 | post_68 | AgentState | **accept with edits** (R5) | `set(key, value)` was left ungenerated, but the docstring states the type: "must be JSON serializable". Generate `value`: int, str, list or dict. Without it only `get`/`delete` on the initial state are tested. |
| 119 | post_69 | CompositeCallbackHandler | **reject** (R2) | `*handlers` are callables. |
| 120 | post_70 | PrintingCallbackHandler | **accept as drafted** | Writes to stdout (not observed). Low value. Treated like post_243. |

**Batches 2–3 totals:** 56 accepted (39 as drafted, 17 with edits), 15 rejected.

## Tier A summary
| | as drafted | with edits | rejected |
|---|---|---|---|
| batch 1 (49) | 12 | 15 | 22 |
| batches 2–3 (71) | 39 | 17 | 15 |
| **tier A (120)** | **51** | **32** | **37** |

**All tiers (166 unreviewed evaluation drafts):** tier C 4 accept / 11 reject; tier B 15 / 16; tier A 83 / 37.
That is **102 accepted, 64 rejected**, before the usability check.

## Decision (user, 2026-11-18)
- Batches 2–3 confirmed: 56 accept (39 as drafted, 17 with edits), 15 reject. Tier A: 51 / 32 / 37.
- **Written to `contracts_v1/reviewed/` on 2026-11-18** by `scripts/apply_contract_review.py` from
  `contracts_v1/review_decisions.json` (all 166 tiers A, B and C; rule and evidence are in each file's
  `review.notes`). Result: 52 accept, 50 accept with edits, 64 reject.
- Limitation found while writing the edits: contract hints are JSON values, so **bytes hints cannot be stored**.
  The csn_48 `unpack` packet and the csn_51 `buf` bytes rely on random bytes, and the usability check decides them.
