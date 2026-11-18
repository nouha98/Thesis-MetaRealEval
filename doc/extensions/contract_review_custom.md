# Contract review sheet: custom

375 tasks drafted; 173 supported by the draft. For each **supported** task, check and mark a verdict: `accept`, `edit` (say what) or `reject` (task leaves the supported subset).

Check in particular:
1. **Types** whose source is `p_literals`, `default` or `none` (weak evidence) against the docstring.
2. **Constraints** the docstring states (ranges, non-empty, allowed values); none are drafted automatically.
3. **Documented exceptions**: an exception the docstring describes but the draft misses would wrongly make inputs domain-uncertain.
4. **Own-class comparison**: `opaque` (returned instances never asserted) or `accessors` (the listed documented properties/attributes); never private state.
5. Methods the draft does not generate (and why).

| # | task | supported | reasons | verdict | note |
|---|---|---|---|---|---|
| 1 | RCE_csn_snippet_10 | no | no public method or property can be generated | | |
| 2 | RCE_csn_snippet_101 | yes | - | | |
| 3 | RCE_csn_snippet_103 | no | no public method or property can be generated | | |
| 4 | RCE_csn_snippet_104 | yes | - | | |
| 5 | RCE_csn_snippet_105 | yes | - | | |
| 6 | RCE_csn_snippet_106 | no | no public method or property can be generated | | |
| 7 | RCE_csn_snippet_108 | yes | - | | |
| 8 | RCE_csn_snippet_109 | yes | - | | |
| 9 | RCE_csn_snippet_11 | no | imports non-stdlib modules | | |
| 10 | RCE_csn_snippet_110 | yes | - | | |
| 11 | RCE_csn_snippet_111 | no | imports non-stdlib modules | | |
| 12 | RCE_csn_snippet_113 | yes | - | | |
| 13 | RCE_csn_snippet_115 | yes | - | | |
| 14 | RCE_csn_snippet_116 | yes | - | | |
| 15 | RCE_csn_snippet_117 | no | imports non-stdlib modules; constructor parameters cannot be generated | | |
| 16 | RCE_csn_snippet_119 | yes | - | | |
| 17 | RCE_csn_snippet_12 | yes | - | | |
| 18 | RCE_csn_snippet_120 | yes | - | | |
| 19 | RCE_csn_snippet_121 | no | imports non-stdlib modules | | |
| 20 | RCE_csn_snippet_123 | no | imports side-effect modules ['multiprocessing'] | | |
| 21 | RCE_csn_snippet_125 | yes | - | | |
| 22 | RCE_csn_snippet_127 | no | constructor parameters cannot be generated; no public method or property can be generated | | |
| 23 | RCE_csn_snippet_128 | no | constructor parameters cannot be generated | | |
| 24 | RCE_csn_snippet_129 | no | constructor parameters cannot be generated | | |
| 25 | RCE_csn_snippet_13 | no | imports non-stdlib modules | | |
| 26 | RCE_csn_snippet_131 | no | imports non-stdlib modules | | |
| 27 | RCE_csn_snippet_132 | no | no public method or property can be generated | | |
| 28 | RCE_csn_snippet_133 | no | constructor parameters cannot be generated; no public method or property can be generated | | |
| 29 | RCE_csn_snippet_135 | yes | - | | |
| 30 | RCE_csn_snippet_137 | no | imports side-effect modules ['threading'] | | |
| 31 | RCE_csn_snippet_139 | yes | - | | |
| 32 | RCE_csn_snippet_140 | no | no public method or property can be generated | | |
| 33 | RCE_csn_snippet_141 | yes | - | | |
| 34 | RCE_csn_snippet_142 | yes | - | | |
| 35 | RCE_csn_snippet_144 | no | no public method or property can be generated | | |
| 36 | RCE_csn_snippet_145 | no | no public method or property can be generated | | |
| 37 | RCE_csn_snippet_147 | yes | - | | |
| 38 | RCE_csn_snippet_149 | yes | - | | |
| 39 | RCE_csn_snippet_150 | no | imports non-stdlib modules | | |
| 40 | RCE_csn_snippet_151 | yes | - | | |
| 41 | RCE_csn_snippet_152 | no | imports non-stdlib modules; constructor parameters cannot be generated | | |
| 42 | RCE_csn_snippet_153 | yes | - | | |
| 43 | RCE_csn_snippet_154 | no | imports side-effect modules ['urllib']; constructor parameters cannot be generated | | |
| 44 | RCE_csn_snippet_156 | no | constructor parameters cannot be generated | | |
| 45 | RCE_csn_snippet_157 | yes | - | | |
| 46 | RCE_csn_snippet_159 | yes | - | | |
| 47 | RCE_csn_snippet_160 | yes | - | | |
| 48 | RCE_csn_snippet_161 | yes | - | | |
| 49 | RCE_csn_snippet_162 | yes | - | | |
| 50 | RCE_csn_snippet_163 | yes | - | | |
| 51 | RCE_csn_snippet_164 | no | imports side-effect modules ['urllib'] | | |
| 52 | RCE_csn_snippet_168 | yes | - | | |
| 53 | RCE_csn_snippet_169 | yes | - | | |
| 54 | RCE_csn_snippet_17 | yes | - | | |
| 55 | RCE_csn_snippet_170 | yes | - | | |
| 56 | RCE_csn_snippet_171 | yes | - | | |
| 57 | RCE_csn_snippet_172 | yes | - | | |
| 58 | RCE_csn_snippet_173 | yes | - | | |
| 59 | RCE_csn_snippet_174 | no | no public method or property can be generated | | |
| 60 | RCE_csn_snippet_175 | yes | - | | |
| 61 | RCE_csn_snippet_177 | no | constructor parameters cannot be generated | | |
| 62 | RCE_csn_snippet_178 | yes | - | | |
| 63 | RCE_csn_snippet_180 | no | no public method or property can be generated | | |
| 64 | RCE_csn_snippet_182 | no | imports non-stdlib modules; no public method or property can be generated | | |
| 65 | RCE_csn_snippet_184 | yes | - | | |
| 66 | RCE_csn_snippet_186 | yes | - | | |
| 67 | RCE_csn_snippet_187 | no | no public method or property can be generated | | |
| 68 | RCE_csn_snippet_193 | yes | - | | |
| 69 | RCE_csn_snippet_199 | yes | - | | |
| 70 | RCE_csn_snippet_2 | yes | - | | |
| 71 | RCE_csn_snippet_200 | no | no public method or property can be generated | | |
| 72 | RCE_csn_snippet_201 | no | imports non-stdlib modules | | |
| 73 | RCE_csn_snippet_203 | no | imports non-stdlib modules; constructor parameters cannot be generated; no public method or property can be generated | | |
| 74 | RCE_csn_snippet_204 | yes | - | | |
| 75 | RCE_csn_snippet_205 | yes | - | | |
| 76 | RCE_csn_snippet_206 | no | no public method or property can be generated | | |
| 77 | RCE_csn_snippet_207 | yes | - | | |
| 78 | RCE_csn_snippet_208 | no | no public method or property can be generated | | |
| 79 | RCE_csn_snippet_209 | no | no public method or property can be generated | | |
| 80 | RCE_csn_snippet_210 | no | no public method or property can be generated | | |
| 81 | RCE_csn_snippet_211 | no | no public method or property can be generated | | |
| 82 | RCE_csn_snippet_213 | no | no public method or property can be generated | | |
| 83 | RCE_csn_snippet_216 | yes | - | | |
| 84 | RCE_csn_snippet_217 | yes | - | | |
| 85 | RCE_csn_snippet_218 | yes | - | | |
| 86 | RCE_csn_snippet_22 | no | no public method or property can be generated | | |
| 87 | RCE_csn_snippet_220 | yes | - | | |
| 88 | RCE_csn_snippet_221 | no | dataclass whose fields are not in the skeleton (constructor unspecified) | | |
| 89 | RCE_csn_snippet_222 | yes | - | | |
| 90 | RCE_csn_snippet_223 | no | no public method or property can be generated | | |
| 91 | RCE_csn_snippet_227 | no | dataclass whose fields are not in the skeleton (constructor unspecified); imports non-stdlib modules | | |
| 92 | RCE_csn_snippet_229 | no | no public method or property can be generated | | |
| 93 | RCE_csn_snippet_23 | no | no public method or property can be generated | | |
| 94 | RCE_csn_snippet_230 | no | no public method or property can be generated | | |
| 95 | RCE_csn_snippet_231 | yes | - | | |
| 96 | RCE_csn_snippet_232 | no | imports non-stdlib modules; constructor parameters cannot be generated; no public method or property can be generated | | |
| 97 | RCE_csn_snippet_233 | yes | - | | |
| 98 | RCE_csn_snippet_235 | no | no public method or property can be generated | | |
| 99 | RCE_csn_snippet_240 | yes | - | | |
| 100 | RCE_csn_snippet_241 | yes | - | | |
| 101 | RCE_csn_snippet_245 | yes | - | | |
| 102 | RCE_csn_snippet_248 | no | imports non-stdlib modules | | |
| 103 | RCE_csn_snippet_249 | no | imports side-effect modules ['shutil']; no public method or property can be generated | | |
| 104 | RCE_csn_snippet_250 | yes | - | | |
| 105 | RCE_csn_snippet_251 | yes | - | | |
| 106 | RCE_csn_snippet_252 | yes | - | | |
| 107 | RCE_csn_snippet_257 | yes | - | | |
| 108 | RCE_csn_snippet_258 | no | imports non-stdlib modules; no public method or property can be generated | | |
| 109 | RCE_csn_snippet_259 | no | imports non-stdlib modules | | |
| 110 | RCE_csn_snippet_26 | no | imports side-effect modules ['subprocess'] | | |
| 111 | RCE_csn_snippet_260 | no | constructor parameters cannot be generated | | |
| 112 | RCE_csn_snippet_261 | no | imports non-stdlib modules | | |
| 113 | RCE_csn_snippet_262 | no | imports non-stdlib modules; no public method or property can be generated | | |
| 114 | RCE_csn_snippet_263 | no | imports non-stdlib modules | | |
| 115 | RCE_csn_snippet_264 | no | imports non-stdlib modules; no public method or property can be generated | | |
| 116 | RCE_csn_snippet_269 | no | imports non-stdlib modules | | |
| 117 | RCE_csn_snippet_271 | no | imports non-stdlib modules; constructor parameters cannot be generated; no public method or property can be generated | | |
| 118 | RCE_csn_snippet_272 | yes | - | | |
| 119 | RCE_csn_snippet_273 | yes | - | | |
| 120 | RCE_csn_snippet_274 | yes | - | | |
| 121 | RCE_csn_snippet_275 | yes | - | | |
| 122 | RCE_csn_snippet_276 | yes | - | | |
| 123 | RCE_csn_snippet_277 | no | no public method or property can be generated | | |
| 124 | RCE_csn_snippet_278 | yes | - | | |
| 125 | RCE_csn_snippet_279 | yes | - | | |
| 126 | RCE_csn_snippet_28 | no | constructor parameters cannot be generated | | |
| 127 | RCE_csn_snippet_280 | yes | - | | |
| 128 | RCE_csn_snippet_283 | no | constructor parameters cannot be generated | | |
| 129 | RCE_csn_snippet_284 | no | imports non-stdlib modules | | |
| 130 | RCE_csn_snippet_285 | no | constructor parameters cannot be generated | | |
| 131 | RCE_csn_snippet_286 | yes | - | | |
| 132 | RCE_csn_snippet_287 | no | dataclass whose fields are not in the skeleton (constructor unspecified) | | |
| 133 | RCE_csn_snippet_288 | yes | - | | |
| 134 | RCE_csn_snippet_29 | no | imports non-stdlib modules; constructor parameters cannot be generated | | |
| 135 | RCE_csn_snippet_292 | no | imports side-effect modules ['socket']; constructor parameters cannot be generated | | |
| 136 | RCE_csn_snippet_293 | no | constructor parameters cannot be generated | | |
| 137 | RCE_csn_snippet_294 | no | imports side-effect modules ['threading'] | | |
| 138 | RCE_csn_snippet_297 | no | constructor parameters cannot be generated; no public method or property can be generated | | |
| 139 | RCE_csn_snippet_3 | no | no public method or property can be generated | | |
| 140 | RCE_csn_snippet_30 | yes | - | | |
| 141 | RCE_csn_snippet_302 | yes | - | | |
| 142 | RCE_csn_snippet_303 | no | no public method or property can be generated | | |
| 143 | RCE_csn_snippet_304 | yes | - | | |
| 144 | RCE_csn_snippet_305 | yes | - | | |
| 145 | RCE_csn_snippet_33 | yes | - | | |
| 146 | RCE_csn_snippet_35 | no | imports non-stdlib modules | | |
| 147 | RCE_csn_snippet_36 | no | dataclass whose fields are not in the skeleton (constructor unspecified); imports non-stdlib modules | | |
| 148 | RCE_csn_snippet_40 | no | imports non-stdlib modules; no public method or property can be generated | | |
| 149 | RCE_csn_snippet_41 | no | constructor parameters cannot be generated; no public method or property can be generated | | |
| 150 | RCE_csn_snippet_42 | yes | - | | |
| 151 | RCE_csn_snippet_44 | no | imports non-stdlib modules | | |
| 152 | RCE_csn_snippet_45 | yes | - | | |
| 153 | RCE_csn_snippet_46 | yes | - | | |
| 154 | RCE_csn_snippet_48 | yes | - | | |
| 155 | RCE_csn_snippet_49 | yes | - | | |
| 156 | RCE_csn_snippet_50 | yes | - | | |
| 157 | RCE_csn_snippet_51 | yes | - | | |
| 158 | RCE_csn_snippet_52 | yes | - | | |
| 159 | RCE_csn_snippet_53 | yes | - | | |
| 160 | RCE_csn_snippet_54 | yes | - | | |
| 161 | RCE_csn_snippet_55 | no | no public method or property can be generated | | |
| 162 | RCE_csn_snippet_56 | yes | - | | |
| 163 | RCE_csn_snippet_57 | no | imports non-stdlib modules; no public method or property can be generated | | |
| 164 | RCE_csn_snippet_58 | no | imports non-stdlib modules | | |
| 165 | RCE_csn_snippet_59 | no | dataclass whose fields are not in the skeleton (constructor unspecified) | | |
| 166 | RCE_csn_snippet_6 | yes | - | | |
| 167 | RCE_csn_snippet_60 | yes | - | | |
| 168 | RCE_csn_snippet_62 | no | imports side-effect modules ['threading'] | | |
| 169 | RCE_csn_snippet_63 | yes | - | | |
| 170 | RCE_csn_snippet_66 | no | constructor parameters cannot be generated; no public method or property can be generated | | |
| 171 | RCE_csn_snippet_69 | yes | - | | |
| 172 | RCE_csn_snippet_7 | yes | - | | |
| 173 | RCE_csn_snippet_75 | yes | - | | |
| 174 | RCE_csn_snippet_8 | yes | - | | |
| 175 | RCE_csn_snippet_81 | no | no public method or property can be generated | | |
| 176 | RCE_csn_snippet_82 | yes | - | | |
| 177 | RCE_csn_snippet_83 | no | no public method or property can be generated | | |
| 178 | RCE_csn_snippet_84 | yes | - | | |
| 179 | RCE_csn_snippet_85 | yes | - | | |
| 180 | RCE_csn_snippet_86 | no | constructor parameters cannot be generated | | |
| 181 | RCE_csn_snippet_87 | no | no public method or property can be generated | | |
| 182 | RCE_csn_snippet_9 | yes | - | | |
| 183 | RCE_csn_snippet_92 | no | no public method or property can be generated | | |
| 184 | RCE_csn_snippet_93 | no | no public method or property can be generated | | |
| 185 | RCE_csn_snippet_98 | yes | - | | |
| 186 | RCE_post_snippet_101 | no | imports non-stdlib modules; no public method or property can be generated | | |
| 187 | RCE_post_snippet_103 | no | imports non-stdlib modules; imports side-effect modules ['urllib'] | | |
| 188 | RCE_post_snippet_107 | no | dataclass whose fields are not in the skeleton (constructor unspecified) | | |
| 189 | RCE_post_snippet_109 | no | dataclass whose fields are not in the skeleton (constructor unspecified) | | |
| 190 | RCE_post_snippet_111 | no | imports side-effect modules ['subprocess'] | | |
| 191 | RCE_post_snippet_112 | yes | - | | |
| 192 | RCE_post_snippet_113 | no | dataclass whose fields are not in the skeleton (constructor unspecified) | | |
| 193 | RCE_post_snippet_119 | no | dataclass whose fields are not in the skeleton (constructor unspecified) | | |
| 194 | RCE_post_snippet_120 | no | imports non-stdlib modules | | |
| 195 | RCE_post_snippet_128 | no | imports side-effect modules ['shutil', 'subprocess'] | | |
| 196 | RCE_post_snippet_129 | yes | - | | |
| 197 | RCE_post_snippet_130 | no | imports non-stdlib modules | | |
| 198 | RCE_post_snippet_132 | yes | - | | |
| 199 | RCE_post_snippet_134 | yes | - | | |
| 200 | RCE_post_snippet_135 | no | imports non-stdlib modules | | |
| 201 | RCE_post_snippet_136 | no | dataclass whose fields are not in the skeleton (constructor unspecified) | | |
| 202 | RCE_post_snippet_14 | yes | - | | |
| 203 | RCE_post_snippet_141 | yes | - | | |
| 204 | RCE_post_snippet_142 | yes | - | | |
| 205 | RCE_post_snippet_149 | no | imports non-stdlib modules | | |
| 206 | RCE_post_snippet_150 | no | dataclass whose fields are not in the skeleton (constructor unspecified); no public method or property can be generated | | |
| 207 | RCE_post_snippet_151 | no | imports non-stdlib modules; constructor parameters cannot be generated; no public method or property can be generated | | |
| 208 | RCE_post_snippet_152 | yes | - | | |
| 209 | RCE_post_snippet_153 | yes | - | | |
| 210 | RCE_post_snippet_154 | yes | - | | |
| 211 | RCE_post_snippet_155 | yes | - | | |
| 212 | RCE_post_snippet_156 | no | dataclass whose fields are not in the skeleton (constructor unspecified) | | |
| 213 | RCE_post_snippet_158 | no | imports non-stdlib modules | | |
| 214 | RCE_post_snippet_159 | yes | - | | |
| 215 | RCE_post_snippet_16 | yes | - | | |
| 216 | RCE_post_snippet_161 | no | no public method or property can be generated | | |
| 217 | RCE_post_snippet_165 | yes | - | | |
| 218 | RCE_post_snippet_166 | no | constructor parameters cannot be generated | | |
| 219 | RCE_post_snippet_167 | yes | - | | |
| 220 | RCE_post_snippet_172 | no | dataclass whose fields are not in the skeleton (constructor unspecified) | | |
| 221 | RCE_post_snippet_173 | yes | - | | |
| 222 | RCE_post_snippet_174 | no | imports non-stdlib modules | | |
| 223 | RCE_post_snippet_176 | no | imports non-stdlib modules | | |
| 224 | RCE_post_snippet_18 | no | imports non-stdlib modules; constructor parameters cannot be generated | | |
| 225 | RCE_post_snippet_182 | yes | - | | |
| 226 | RCE_post_snippet_183 | no | dataclass whose fields are not in the skeleton (constructor unspecified); imports non-stdlib modules | | |
| 227 | RCE_post_snippet_185 | yes | - | | |
| 228 | RCE_post_snippet_188 | no | imports side-effect modules ['threading'] | | |
| 229 | RCE_post_snippet_189 | yes | - | | |
| 230 | RCE_post_snippet_19 | yes | - | | |
| 231 | RCE_post_snippet_190 | no | constructor parameters cannot be generated | | |
| 232 | RCE_post_snippet_194 | yes | - | | |
| 233 | RCE_post_snippet_20 | no | dataclass whose fields are not in the skeleton (constructor unspecified) | | |
| 234 | RCE_post_snippet_201 | no | dataclass whose fields are not in the skeleton (constructor unspecified); imports non-stdlib modules | | |
| 235 | RCE_post_snippet_206 | no | imports non-stdlib modules | | |
| 236 | RCE_post_snippet_208 | no | imports side-effect modules ['subprocess'] | | |
| 237 | RCE_post_snippet_209 | yes | - | | |
| 238 | RCE_post_snippet_21 | no | dataclass whose fields are not in the skeleton (constructor unspecified) | | |
| 239 | RCE_post_snippet_210 | no | imports side-effect modules ['subprocess'] | | |
| 240 | RCE_post_snippet_211 | no | no public method or property can be generated | | |
| 241 | RCE_post_snippet_212 | no | imports side-effect modules ['subprocess'] | | |
| 242 | RCE_post_snippet_213 | no | imports non-stdlib modules | | |
| 243 | RCE_post_snippet_216 | no | no public method or property can be generated | | |
| 244 | RCE_post_snippet_218 | yes | - | | |
| 245 | RCE_post_snippet_219 | yes | - | | |
| 246 | RCE_post_snippet_22 | yes | - | | |
| 247 | RCE_post_snippet_221 | yes | - | | |
| 248 | RCE_post_snippet_222 | yes | - | | |
| 249 | RCE_post_snippet_223 | yes | - | | |
| 250 | RCE_post_snippet_225 | yes | - | | |
| 251 | RCE_post_snippet_226 | yes | - | | |
| 252 | RCE_post_snippet_227 | yes | - | | |
| 253 | RCE_post_snippet_228 | no | imports non-stdlib modules | | |
| 254 | RCE_post_snippet_23 | yes | - | | |
| 255 | RCE_post_snippet_230 | no | imports non-stdlib modules | | |
| 256 | RCE_post_snippet_232 | yes | - | | |
| 257 | RCE_post_snippet_234 | no | imports side-effect modules ['shutil'] | | |
| 258 | RCE_post_snippet_237 | no | dataclass whose fields are not in the skeleton (constructor unspecified) | | |
| 259 | RCE_post_snippet_239 | no | dataclass whose fields are not in the skeleton (constructor unspecified) | | |
| 260 | RCE_post_snippet_24 | yes | - | | |
| 261 | RCE_post_snippet_241 | no | imports non-stdlib modules | | |
| 262 | RCE_post_snippet_242 | yes | - | | |
| 263 | RCE_post_snippet_243 | yes | - | | |
| 264 | RCE_post_snippet_245 | yes | - | | |
| 265 | RCE_post_snippet_246 | no | imports non-stdlib modules; no public method or property can be generated | | |
| 266 | RCE_post_snippet_249 | yes | - | | |
| 267 | RCE_post_snippet_25 | no | imports side-effect modules ['urllib'] | | |
| 268 | RCE_post_snippet_252 | yes | - | | |
| 269 | RCE_post_snippet_253 | yes | - | | |
| 270 | RCE_post_snippet_254 | yes | - | | |
| 271 | RCE_post_snippet_255 | yes | - | | |
| 272 | RCE_post_snippet_256 | yes | - | | |
| 273 | RCE_post_snippet_262 | no | imports non-stdlib modules | | |
| 274 | RCE_post_snippet_264 | yes | - | | |
| 275 | RCE_post_snippet_268 | yes | - | | |
| 276 | RCE_post_snippet_280 | yes | - | | |
| 277 | RCE_post_snippet_281 | yes | - | | |
| 278 | RCE_post_snippet_283 | no | dataclass whose fields are not in the skeleton (constructor unspecified) | | |
| 279 | RCE_post_snippet_284 | no | dataclass whose fields are not in the skeleton (constructor unspecified) | | |
| 280 | RCE_post_snippet_285 | yes | - | | |
| 281 | RCE_post_snippet_286 | yes | - | | |
| 282 | RCE_post_snippet_287 | no | dataclass whose fields are not in the skeleton (constructor unspecified) | | |
| 283 | RCE_post_snippet_288 | no | dataclass whose fields are not in the skeleton (constructor unspecified) | | |
| 284 | RCE_post_snippet_289 | no | dataclass whose fields are not in the skeleton (constructor unspecified) | | |
| 285 | RCE_post_snippet_29 | yes | - | | |
| 286 | RCE_post_snippet_291 | no | constructor parameters cannot be generated | | |
| 287 | RCE_post_snippet_292 | no | constructor parameters cannot be generated | | |
| 288 | RCE_post_snippet_293 | no | imports non-stdlib modules | | |
| 289 | RCE_post_snippet_294 | yes | - | | |
| 290 | RCE_post_snippet_295 | yes | - | | |
| 291 | RCE_post_snippet_296 | no | imports side-effect modules ['webbrowser']; no public method or property can be generated | | |
| 292 | RCE_post_snippet_297 | no | imports side-effect modules ['webbrowser']; no public method or property can be generated | | |
| 293 | RCE_post_snippet_298 | no | imports non-stdlib modules | | |
| 294 | RCE_post_snippet_3 | no | dataclass whose fields are not in the skeleton (constructor unspecified) | | |
| 295 | RCE_post_snippet_301 | no | imports non-stdlib modules | | |
| 296 | RCE_post_snippet_302 | no | imports non-stdlib modules | | |
| 297 | RCE_post_snippet_305 | yes | - | | |
| 298 | RCE_post_snippet_306 | no | imports non-stdlib modules | | |
| 299 | RCE_post_snippet_307 | yes | - | | |
| 300 | RCE_post_snippet_308 | yes | - | | |
| 301 | RCE_post_snippet_309 | yes | - | | |
| 302 | RCE_post_snippet_312 | yes | - | | |
| 303 | RCE_post_snippet_316 | no | imports side-effect modules ['shutil'] | | |
| 304 | RCE_post_snippet_318 | no | constructor parameters cannot be generated | | |
| 305 | RCE_post_snippet_319 | no | imports side-effect modules ['concurrent'] | | |
| 306 | RCE_post_snippet_320 | no | dataclass whose fields are not in the skeleton (constructor unspecified) | | |
| 307 | RCE_post_snippet_321 | no | dataclass whose fields are not in the skeleton (constructor unspecified) | | |
| 308 | RCE_post_snippet_322 | no | dataclass whose fields are not in the skeleton (constructor unspecified) | | |
| 309 | RCE_post_snippet_324 | yes | - | | |
| 310 | RCE_post_snippet_325 | yes | - | | |
| 311 | RCE_post_snippet_338 | no | imports side-effect modules ['threading'] | | |
| 312 | RCE_post_snippet_339 | yes | - | | |
| 313 | RCE_post_snippet_340 | yes | - | | |
| 314 | RCE_post_snippet_341 | yes | - | | |
| 315 | RCE_post_snippet_342 | yes | - | | |
| 316 | RCE_post_snippet_343 | yes | - | | |
| 317 | RCE_post_snippet_345 | no | dataclass whose fields are not in the skeleton (constructor unspecified) | | |
| 318 | RCE_post_snippet_346 | yes | - | | |
| 319 | RCE_post_snippet_347 | yes | - | | |
| 320 | RCE_post_snippet_351 | yes | - | | |
| 321 | RCE_post_snippet_353 | no | imports non-stdlib modules | | |
| 322 | RCE_post_snippet_358 | no | imports non-stdlib modules; no public method or property can be generated | | |
| 323 | RCE_post_snippet_359 | no | imports non-stdlib modules | | |
| 324 | RCE_post_snippet_360 | no | dataclass whose fields are not in the skeleton (constructor unspecified) | | |
| 325 | RCE_post_snippet_361 | no | imports non-stdlib modules | | |
| 326 | RCE_post_snippet_362 | no | imports non-stdlib modules; imports side-effect modules ['subprocess'] | | |
| 327 | RCE_post_snippet_363 | no | imports non-stdlib modules | | |
| 328 | RCE_post_snippet_364 | no | dataclass whose fields are not in the skeleton (constructor unspecified) | | |
| 329 | RCE_post_snippet_368 | yes | - | | |
| 330 | RCE_post_snippet_369 | no | imports non-stdlib modules; imports side-effect modules ['subprocess'] | | |
| 331 | RCE_post_snippet_370 | no | imports non-stdlib modules | | |
| 332 | RCE_post_snippet_371 | yes | - | | |
| 333 | RCE_post_snippet_373 | no | imports non-stdlib modules | | |
| 334 | RCE_post_snippet_374 | yes | - | | |
| 335 | RCE_post_snippet_38 | no | imports non-stdlib modules | | |
| 336 | RCE_post_snippet_39 | no | imports non-stdlib modules | | |
| 337 | RCE_post_snippet_4 | no | imports non-stdlib modules | | |
| 338 | RCE_post_snippet_41 | yes | - | | |
| 339 | RCE_post_snippet_42 | yes | - | | |
| 340 | RCE_post_snippet_43 | no | imports side-effect modules ['subprocess'] | | |
| 341 | RCE_post_snippet_45 | yes | - | | |
| 342 | RCE_post_snippet_46 | no | imports non-stdlib modules; no public method or property can be generated | | |
| 343 | RCE_post_snippet_47 | no | imports non-stdlib modules; no public method or property can be generated | | |
| 344 | RCE_post_snippet_48 | no | imports non-stdlib modules; no public method or property can be generated | | |
| 345 | RCE_post_snippet_49 | no | imports non-stdlib modules; no public method or property can be generated | | |
| 346 | RCE_post_snippet_5 | no | imports side-effect modules ['subprocess'] | | |
| 347 | RCE_post_snippet_50 | no | imports non-stdlib modules; no public method or property can be generated | | |
| 348 | RCE_post_snippet_51 | no | imports non-stdlib modules; no public method or property can be generated | | |
| 349 | RCE_post_snippet_52 | no | imports non-stdlib modules; no public method or property can be generated | | |
| 350 | RCE_post_snippet_53 | no | imports non-stdlib modules; no public method or property can be generated | | |
| 351 | RCE_post_snippet_54 | no | imports non-stdlib modules; no public method or property can be generated | | |
| 352 | RCE_post_snippet_55 | no | imports non-stdlib modules; no public method or property can be generated | | |
| 353 | RCE_post_snippet_56 | no | imports non-stdlib modules; no public method or property can be generated | | |
| 354 | RCE_post_snippet_57 | no | imports non-stdlib modules; no public method or property can be generated | | |
| 355 | RCE_post_snippet_58 | no | imports non-stdlib modules; no public method or property can be generated | | |
| 356 | RCE_post_snippet_59 | no | imports non-stdlib modules; no public method or property can be generated | | |
| 357 | RCE_post_snippet_60 | no | imports non-stdlib modules; no public method or property can be generated | | |
| 358 | RCE_post_snippet_62 | no | dataclass whose fields are not in the skeleton (constructor unspecified) | | |
| 359 | RCE_post_snippet_63 | no | dataclass whose fields are not in the skeleton (constructor unspecified) | | |
| 360 | RCE_post_snippet_64 | yes | - | | |
| 361 | RCE_post_snippet_67 | no | dataclass whose fields are not in the skeleton (constructor unspecified) | | |
| 362 | RCE_post_snippet_68 | yes | - | | |
| 363 | RCE_post_snippet_69 | yes | - | | |
| 364 | RCE_post_snippet_70 | yes | - | | |
| 365 | RCE_post_snippet_71 | no | dataclass whose fields are not in the skeleton (constructor unspecified) | | |
| 366 | RCE_post_snippet_72 | no | dataclass whose fields are not in the skeleton (constructor unspecified) | | |
| 367 | RCE_post_snippet_73 | no | imports non-stdlib modules | | |
| 368 | RCE_post_snippet_75 | no | imports non-stdlib modules | | |
| 369 | RCE_post_snippet_77 | no | imports non-stdlib modules | | |
| 370 | RCE_post_snippet_83 | no | imports non-stdlib modules; no public method or property can be generated | | |
| 371 | RCE_post_snippet_84 | no | imports non-stdlib modules; no public method or property can be generated | | |
| 372 | RCE_post_snippet_86 | no | imports non-stdlib modules | | |
| 373 | RCE_post_snippet_88 | no | imports non-stdlib modules; no public method or property can be generated | | |
| 374 | RCE_post_snippet_90 | no | imports non-stdlib modules; constructor parameters cannot be generated | | |
| 375 | RCE_post_snippet_97 | no | imports non-stdlib modules; imports side-effect modules ['concurrent'] | | |

## RCE_csn_snippet_101 (`ClosableNamedTemporaryFile`)

Own-class comparison: `{"ClosableNamedTemporaryFile": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | - | - | - | - | - | - |
| close | True | - | - | - | - | - | - |
| write | False | buf | positional | any | none **(weak)** |  | - |

## RCE_csn_snippet_104 (`BufferSegment`)

Own-class comparison: `{"BufferSegment": {"kind": "accessors", "attributes": ["offset"], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: ['offset'].

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | - | - | - | - | - | - |
| __len__ | True | - | - | - | - | - | - |
| tobytes | True | - | - | - | - | - | - |

## RCE_csn_snippet_105 (`BufferWithSegmentsCollection`)

Own-class comparison: `{"BufferWithSegmentsCollection": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | - | - | - | - | - | - |
| __len__ | True | - | - | - | - | - | - |

## RCE_csn_snippet_108 (`Details`)

Own-class comparison: `{"Details": {"kind": "accessors", "attributes": ["all"], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: ['all'].

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | details | positional | bool | p_literals **(weak)** | False | - |

## RCE_csn_snippet_109 (`HistoryManager`)

Own-class comparison: `{"HistoryManager": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | kwargs | varkw | any | none **(weak)** |  | - |
| __call__ | True | operation | positional | bytes | p_literals **(weak)** |  | - |
| reset | True | - | - | - | - | - | - |
| size | True | - | - | - | - | - | - |

## RCE_csn_snippet_110 (`Enum`)

Own-class comparison: `{"Enum": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | - | - | - | - | - | - |
| __repr__ | True | - | - | - | - | - | - |
| iteritems | True | - | - | - | - | - | - |

## RCE_csn_snippet_113 (`FileLikeIO`)

Own-class comparison: `{"FileLikeIO": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | - | - | - | - | - | - |
| exists | True | path | positional | bool | p_literals **(weak)** | False | - |
| open | False | path | positional | any | none **(weak)** |  | - |
| open | False | mode | positional | str | default **(weak)** | 'r' | - |
| remove | True | path | positional | bool | p_literals **(weak)** | None, False | - |

## RCE_csn_snippet_115 (`Variable`)

Own-class comparison: `{"Variable": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | name | positional | str | docstring | False | - |
| __repr__ | True | - | - | - | - | - | - |

## RCE_csn_snippet_116 (`Solver`)

Own-class comparison: `{"Solver": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | - | - | - | - | - | - |
| getSolution | True | domains | positional | dict[any, any] | annotation | None | - |
| getSolution | True | constraints | positional | list[tuple[any, ...]] | annotation | None | - |
| getSolution | True | vconstraints | positional | dict[any, any] | annotation |  | - |
| getSolutionIter | True | domains | positional | dict[any, any] | annotation |  | - |
| getSolutionIter | True | constraints | positional | list[tuple[any, ...]] | annotation | [('.:0:`m)@Oa!3XEF',), ('.:0:`m)@Oa!3XEF',), ('.:0:`m)@Oa!3X | - |
| getSolutionIter | True | vconstraints | positional | dict[any, any] | annotation |  | - |
| getSolutions | True | domains | positional | dict[any, any] | annotation |  | - |
| getSolutions | True | constraints | positional | list[tuple[any, ...]] | annotation |  | - |
| getSolutions | True | vconstraints | positional | dict[any, any] | annotation |  | - |

## RCE_csn_snippet_119 (`DummyClass`)

Own-class comparison: `{"DummyClass": {"kind": "accessors", "attributes": ["prop"], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: ['prop'].

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | - | - | - | - | - | - |
| run | True | - | - | - | - | - | - |

## RCE_csn_snippet_12 (`Factorization`)

Own-class comparison: `{"Factorization": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | - | - | - | - | - | - |
| factorize | False | pq | positional | any | none **(weak)** |  | - |
| gcd | True | a | positional | int | p_literals **(weak)** | -3165 | - |
| gcd | True | b | positional | int | p_literals **(weak)** | None, -3165 | - |

## RCE_csn_snippet_120 (`NestedDummyClass`)

Own-class comparison: `{"NestedDummyClass": {"kind": "accessors", "attributes": ["prop"], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: ['prop'].

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | - | - | - | - | - | - |
| run | True | - | - | - | - | - | - |

## RCE_csn_snippet_125 (`FenwickMin`)

Own-class comparison: `{"FenwickMin": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | size | positional | bool | int | p_literals **(weak)** | True, 846 | - |
| prefixMin | True | a | positional | int | docstring | False, -2429.0 | - |
| update | True | a | positional | int | docstring | True, False | - |
| update | True | val | positional | bool | int | p_literals **(weak)** | False, 846 | - |

## RCE_csn_snippet_135 (`NoOpTraceId`)

Own-class comparison: `{"NoOpTraceId": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | - | - | - | - | - | - |
| to_id | True | - | - | - | - | - | - |

## RCE_csn_snippet_139 (`LazyField`)

Own-class comparison: `{"LazyField": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | klass | positional | bytes | p_literals **(weak)** | None | - |
| __call__ | True | args | varargs | any | annotation |  | - |
| __call__ | True | kwargs | varkw | any | annotation |  | - |
| create | True | - | - | - | - | - | - |
| update | True | kwargs | varkw | any | annotation |  | - |

## RCE_csn_snippet_141 (`Api`)

Own-class comparison: `{"Api": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | - | - | - | - | - | - |
| call_action | True | action | positional | str | annotation | True | - |
| call_action | True | params | varkw | any | none **(weak)** |  | - |

## RCE_csn_snippet_142 (`ProjectTemplate`)

Own-class comparison: `{"ProjectTemplate": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | - | - | - | - | - | - |
| get_project_template | True | name | positional | str | default **(weak)** | 'Default' | - |
| get_project_template | True | output_type | positional | str | default **(weak)** | 'exe' | - |
| get_project_template | True | debugger | positional | none | default **(weak)** | None | - |
| get_project_template | True | build_dir | positional | float | str | p_literals **(weak)** | 1081.5533, 'build' | - |

## RCE_csn_snippet_147 (`NoHashContext`)

Own-class comparison: `{"NoHashContext": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | data | positional | none | p_literals **(weak)** | None | - |
| digest | True | - | - | - | - | - | - |
| hexdigest | True | - | - | - | - | - | - |
| update | True | data | positional | any | none **(weak)** | None | - |

## RCE_csn_snippet_149 (`TorConfigType`)

Own-class comparison: `{"TorConfigType": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | - | - | - | - | - | - |
| parse | True | s | positional | float | p_literals **(weak)** | 3353.4 | - |
| validate | False | s | positional | any | none **(weak)** |  | - |
| validate | False | instance | positional | any | none **(weak)** |  | - |
| validate | False | name | positional | any | none **(weak)** |  | - |

## RCE_csn_snippet_151 (`AdaptiveCardComponent`)

Own-class comparison: `{"AdaptiveCardComponent": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | serializable_properties | positional | list[any] | docstring | 'QO', -618 | - |
| __init__ | True | simple_properties | positional | list[any] | docstring | 'QO', -618 | - |
| to_dict | True | - | - | - | - | - | - |
| to_json | True | kwargs | varkw | any | none **(weak)** |  | - |

## RCE_csn_snippet_153 (`SelectorPattern`)

Own-class comparison: `{"SelectorPattern": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | name | positional | str | annotation | 'dPYnfOZhA]T2' | - |
| __init__ | True | pattern | positional | str | annotation | 'dPYnfOZhA]T2' | - |
| get_name | True | - | - | - | - | - | - |
| match | True | selector | positional | str | annotation | '*' | - |
| match | True | index | positional | int | annotation | 1596 | - |
| match | True | flags | positional | int | annotation | 1596 | - |

## RCE_csn_snippet_157 (`HashMixin`)

Own-class comparison: `{"HashMixin": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | original | positional | none | default **(weak)** | None | - |
| __init__ | True | args | varargs | any | none **(weak)** |  | - |
| __init__ | True | kwargs | varkw | any | none **(weak)** |  | - |
| get_encrypt_sql | False | connection | positional | any | none **(weak)** |  | - |
| get_placeholder | True | value | positional | none | default **(weak)** | None | - |
| get_placeholder | True | compiler | positional | none | default **(weak)** | None | - |
| get_placeholder | True | connection | positional | none | default **(weak)** | None | - |
| pre_save | False | model_instance | positional | any | none **(weak)** |  | - |
| pre_save | False | add | positional | any | none **(weak)** |  | - |

## RCE_csn_snippet_159 (`Style`)

Own-class comparison: `{"Style": {"kind": "accessors", "attributes": ["text"], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: ['text'].

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | text | positional | str | list[str] | annotation | '\rTmtROD~FL"GR1IiN>M*', -3249 | - |

## RCE_csn_snippet_160 (`SBVCueBlock`)

Own-class comparison: `{"SBVCueBlock": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | start | positional | str | annotation | "U'\x0c_i*$v/nEjKI'" | - |
| __init__ | True | end | positional | str | annotation | "U'\x0c_i*$v/nEjKI'" | - |
| __init__ | True | payload | positional | list[str] | annotation | "U'\x0c_i*$v/nEjKI'" | - |
| from_lines | True | lines | positional | list[str] | annotation |  | - |
| is_valid | True | lines | positional | list[str] | annotation |  | - |

## RCE_csn_snippet_161 (`SRTCueBlock`)

Own-class comparison: `{"SRTCueBlock": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | index | positional | str | annotation | None | - |
| __init__ | True | start | positional | str | annotation | None | - |
| __init__ | True | end | positional | str | annotation | None | - |
| __init__ | True | payload | positional | list[str] | annotation | None | - |
| from_lines | True | lines | positional | list[str] | annotation |  | - |
| is_valid | True | lines | positional | list[str] | annotation |  | - |

## RCE_csn_snippet_162 (`WebVTTCommentBlock`)

Own-class comparison: `{"WebVTTCommentBlock": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | text | positional | str | annotation | 'lP;m2)g@Nl6', None, '(`\n' | - |
| format_lines | True | lines | positional | str | annotation | 'lOa&CrcEb_H=D!73s', '%\n' | - |
| from_lines | True | lines | positional | list[str] | annotation |  | - |
| is_valid | True | lines | positional | list[str] | annotation |  | - |

## RCE_csn_snippet_163 (`WebVTTStyleBlock`)

Own-class comparison: `{"WebVTTStyleBlock": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | text | positional | str | annotation | 'c4kW-8L-&\r|zND+/', '\ts\tYrWzE}Tw.d:F\n!p+Q' | - |
| format_lines | True | lines | positional | list[str] | annotation | ["X8'}Zgv;)", 'KT&sK2u;p', 'U*yP_5d6y\n}]dj{', '\ts\tYrWzE}T | - |
| from_lines | True | lines | positional | list[str] | annotation |  | - |
| is_valid | True | lines | positional | list[str] | annotation |  | - |

## RCE_csn_snippet_168 (`Gateway`)

Own-class comparison: `{"Gateway": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | req | positional | bool | p_literals **(weak)** | False | - |
| respond | True | - | - | - | - | - | - |

## RCE_csn_snippet_169 (`Cursor`)

Own-class comparison: `{"Cursor": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | - | - | - | - | - | - |
| count | True | - | - | - | - | - | - |

## RCE_csn_snippet_17 (`Variable`)

Own-class comparison: `{"Variable": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | val | positional | dict[any, any] | p_literals **(weak)** | None, {} | - |
| __init__ | True | _type | positional | dict[any, any] | p_literals **(weak)** | None, {} | - |
| __str__ | True | - | - | - | - | - | - |

## RCE_csn_snippet_170 (`MetricsDAO`)

Own-class comparison: `{"MetricsDAO": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | - | - | - | - | - | - |
| delete | False | run_id | positional | any | none **(weak)** |  | - |
| get | True | run_id | positional | int | p_literals **(weak)** | 1613 | - |
| get | True | metric_id | positional | int | p_literals **(weak)** | 1613 | - |

## RCE_csn_snippet_171 (`RunDAO`)

Own-class comparison: `{"RunDAO": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | - | - | - | - | - | - |
| delete | True | run_id | positional | bool | p_literals **(weak)** | True | - |
| get | True | run_id | positional | bool | p_literals **(weak)** | True | - |
| get_runs | True | sort_by | positional | none | default **(weak)** | None | - |
| get_runs | True | sort_direction | positional | none | default **(weak)** | None | - |
| get_runs | True | start | positional | int | default **(weak)** | 0 | - |
| get_runs | True | limit | positional | none | p_literals **(weak)** | None | - |
| get_runs | True | query | positional | dict[str, str | list[any]] | default **(weak)** | {'type': 'and', 'filters': []} | - |

## RCE_csn_snippet_172 (`MultipleThings`)

Own-class comparison: `{"MultipleThings": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | things | positional | bytes | set[bool] | p_literals **(weak)** | None | - |
| __init__ | True | name | positional | bytes | p_literals **(weak)** | None | - |
| get_name | True | - | - | - | - | - | - |
| get_thing | True | idx | positional | bytes | float | bool | p_literals **(weak)** | -98.093463, True | - |
| get_things | True | - | - | - | - | - | - |

## RCE_csn_snippet_173 (`SingleThing`)

Own-class comparison: `{"SingleThing": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | thing | positional | bool | p_literals **(weak)** | True | - |
| get_name | True | - | - | - | - | - | - |
| get_thing | True | _ | positional | none | default **(weak)** | None | - |
| get_things | True | - | - | - | - | - | - |

## RCE_csn_snippet_175 (`S2Image`)

Own-class comparison: `{"S2Image": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | - | - | - | - | - | - |
| extend | False | source | positional | any | none **(weak)** |  | - |
| extend | False | new_image_name | positional | any | none **(weak)** |  | - |
| extend | False | s2i_args | positional | none | default **(weak)** | None | - |
| usage | True | - | - | - | - | - | - |

## RCE_csn_snippet_178 (`TableCell`)

Own-class comparison: `{"TableCell": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | kind | positional | str | annotation | 'K=nB', None, 'oAgDUE' | - |
| __init__ | True | value | positional | any | annotation | None, 'oAgDUE' | - |
| __init__ | True | alignment | keyword_only | str | p_literals **(weak)** | 'oAgDUE', '<' | - |
| __repr__ | True | - | - | - | - | - | - |
| __str__ | True | - | - | - | - | - | - |

## RCE_csn_snippet_184 (`Encoder`)

Own-class comparison: `{"Encoder": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | - | - | - | - | - | - |
| decode | True | s | positional | str | p_literals **(weak)** | ':g]`~0|H4\\xO]O^0/', '>PqYLuHl[9c.-|k,&', '|pCZ5k' | - |
| encode | False | s | positional | any | none **(weak)** |  | - |
| needsEncoding | True | s | positional | str | p_literals **(weak)** | 'fj5gQbOH$)', '>PqYLuHl[9c.-|k,&' | - |

## RCE_csn_snippet_186 (`TnsFilter`)

Own-class comparison: `{"TnsFilter": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | tns | varargs | any | none **(weak)** |  | - |
| add | True | tns | varargs | any | none **(weak)** |  | - |
| match | True | root | positional | dict[bool, bool] | p_literals **(weak)** | {False: False} | - |
| match | True | ns | positional | any | none **(weak)** | None | - |

## RCE_csn_snippet_193 (`CkClass`)

Own-class comparison: `{"CkClass": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | - | - | - | - | - | - |
| __str__ | True | - | - | - | - | - | - |
| flags2text | True | - | - | - | - | - | - |
| state2text | True | - | - | - | - | - | - |
| to_dict | True | - | - | - | - | - | - |

## RCE_csn_snippet_199 (`UriParam`)

Own-class comparison: `{"UriParam": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | uri | positional | bool | p_literals **(weak)** | False | - |
| __repr__ | True | - | - | - | - | - | - |

## RCE_csn_snippet_2 (`OcrQualityDictionary`)

Own-class comparison: `{"OcrQualityDictionary": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | wordlist | keyword_only | list[str] | annotation | 'RkE0|i+v>h)f0lYa!AV', 'RkE0|i+v>hcf0lYa!AV' | - |
| measure_words_matched | True | ocr_text | positional | str | annotation | 'RkE0|i+v>h)f0lYa!AV', 'RkE0|i+v>hcf0lYa!AV' | - |

## RCE_csn_snippet_204 (`AuthenticationBase`)

Own-class comparison: `{"AuthenticationBase": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | - | - | - | - | - | - |
| authenticate_request | True | - | - | - | - | - | - |
| get_request_credentials | True | - | - | - | - | - | - |

## RCE_csn_snippet_205 (`ArgFilterBase`)

Own-class comparison: `{"ArgFilterBase": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | - | - | - | - | - | - |
| filter_query | True | query | positional | int | p_literals **(weak)** | 580 | - |
| filter_query | True | view | positional | int | p_literals **(weak)** | 580 | - |
| filter_query | True | arg_value | positional | str | docstring | 168 | - |
| maybe_set_arg_name | True | arg_name | positional | str | docstring | [False, False] | - |

## RCE_csn_snippet_207 (`IJavaStreamParser`)

Own-class comparison: `{"IJavaStreamParser": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | - | - | - | - | - | - |
| dump | True | content | positional | any | none **(weak)** | None | - |
| run | True | - | - | - | - | - | - |

## RCE_csn_snippet_216 (`PowerManagementObserver`)

Own-class comparison: `{"PowerManagementObserver": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | - | - | - | - | - | - |
| on_power_sources_change | False | power_management | positional | any | none **(weak)** |  | - |
| on_time_remaining_change | True | power_management | positional | bool | p_literals **(weak)** | False | - |

## RCE_csn_snippet_217 (`FilteredValueIndicator`)

Own-class comparison: `{"FilteredValueIndicator": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | - | - | - | - | - | - |
| __repr__ | True | - | - | - | - | - | - |
| __str__ | True | - | - | - | - | - | - |

## RCE_csn_snippet_218 (`RepeatValueIndicator`)

Own-class comparison: `{"RepeatValueIndicator": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | key | positional | str | annotation | ';Os.pK(99\rm', '!\tbF8GB8ICrq(\r^Nh>' | - |
| __repr__ | True | - | - | - | - | - | - |

## RCE_csn_snippet_220 (`RateLimitsInfo`)

Own-class comparison: `{"RateLimitsInfo": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | - | - | - | - | - | - |
| __str__ | True | - | - | - | - | - | - |
| from_dict | False | data | positional | any | none **(weak)** |  | - |
| from_headers | False | headers | positional | any | none **(weak)** |  | - |

## RCE_csn_snippet_222 (`Transport`)

Own-class comparison: `{"Transport": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | gateway | positional | any | none **(weak)** | None | - |
| __init__ | True | connect | positional | any | none **(weak)** | None | - |
| __init__ | True | timeout | positional | float | default **(weak)** | 1.0 | - |
| __init__ | True | reconnect_timeout | positional | none | float | p_literals **(weak)** | None, 10.0 | - |
| __init__ | True | kwargs | varkw | any | none **(weak)** |  | - |
| disconnect | True | - | - | - | - | - | - |
| send | True | message | positional | any | none **(weak)** | None | - |

## RCE_csn_snippet_231 (`WordArray`)

Own-class comparison: `{"WordArray": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | bytes | positional | bytes | p_literals **(weak)** | None | - |
| __len__ | True | - | - | - | - | - | - |

## RCE_csn_snippet_233 (`Template`)

Own-class comparison: `{"Template": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: ['name']; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | name | positional | str | docstring | None | - |
| __init__ | True | versions | positional | any | none **(weak)** | None | - |
| get_latest_version | True | - | - | - | - | - | - |
| get_version | True | ver_name | positional | str | none | docstring | None | - |

## RCE_csn_snippet_240 (`ExternalIssue`)

Own-class comparison: `{"ExternalIssue": {"kind": "accessors", "attributes": ["payload"], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: ['payload'].

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | bts_url | positional | none | default **(weak)** | None | - |
| __init__ | True | bts_project | positional | none | default **(weak)** | None | - |
| __init__ | True | submit_date | positional | none | default **(weak)** | None | - |
| __init__ | True | ticket_id | positional | none | default **(weak)** | None | - |
| __init__ | True | url | positional | none | default **(weak)** | None | - |

## RCE_csn_snippet_241 (`Issue`)

Own-class comparison: `{"Issue": {"kind": "accessors", "attributes": ["payload"], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: ['payload'].

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | issue_type | positional | bool | p_literals **(weak)** | True | - |
| __init__ | True | comment | positional | bool | none | p_literals **(weak)** | True, None | - |
| __init__ | True | auto_analyzed | positional | bool | default **(weak)** | False | - |
| __init__ | True | ignore_analyzer | positional | bool | default **(weak)** | True | - |
| external_issue_add | False | issue | positional | any | none **(weak)** |  | - |

## RCE_csn_snippet_245 (`Sampleable`)

Own-class comparison: `{"Sampleable": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | - | - | - | - | - | - |
| get_default_sample | True | - | - | - | - | - | - |
| get_sample | True | - | - | - | - | - | - |

## RCE_csn_snippet_250 (`MHMSBFormat`)

Own-class comparison: `{"MHMSBFormat": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | - | - | - | - | - | - |
| fill | False | framebuf | positional | any | none **(weak)** |  | - |
| fill | False | color | positional | any | none **(weak)** |  | - |
| fill_rect | True | framebuf | positional | bool | p_literals **(weak)** | False | - |
| fill_rect | True | x | positional | bool | p_literals **(weak)** | False | - |
| fill_rect | True | y | positional | tuple[bool, ...] | p_literals **(weak)** |  | - |
| fill_rect | True | width | positional | bool | p_literals **(weak)** | False | - |
| fill_rect | True | height | positional | bool | p_literals **(weak)** | False | - |
| fill_rect | True | color | positional | bool | p_literals **(weak)** | False | - |
| get_pixel | False | framebuf | positional | any | none **(weak)** |  | - |
| get_pixel | False | x | positional | any | none **(weak)** |  | - |
| get_pixel | False | y | positional | any | none **(weak)** |  | - |
| set_pixel | False | framebuf | positional | any | none **(weak)** |  | - |
| set_pixel | False | x | positional | any | none **(weak)** |  | - |
| set_pixel | False | y | positional | any | none **(weak)** |  | - |
| set_pixel | False | color | positional | any | none **(weak)** |  | - |

## RCE_csn_snippet_251 (`MVLSBFormat`)

Own-class comparison: `{"MVLSBFormat": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | - | - | - | - | - | - |
| fill | False | framebuf | positional | any | none **(weak)** |  | - |
| fill | False | color | positional | any | none **(weak)** |  | - |
| fill_rect | True | framebuf | positional | any | none **(weak)** | None | - |
| fill_rect | True | x | positional | bool | p_literals **(weak)** | False | - |
| fill_rect | True | y | positional | any | none **(weak)** | None | - |
| fill_rect | True | width | positional | any | none **(weak)** | None | - |
| fill_rect | True | height | positional | bool | p_literals **(weak)** | False | - |
| fill_rect | True | color | positional | any | none **(weak)** | None | - |
| get_pixel | False | framebuf | positional | any | none **(weak)** |  | - |
| get_pixel | False | x | positional | any | none **(weak)** |  | - |
| get_pixel | False | y | positional | any | none **(weak)** |  | - |
| set_pixel | False | framebuf | positional | any | none **(weak)** |  | - |
| set_pixel | False | x | positional | any | none **(weak)** |  | - |
| set_pixel | False | y | positional | any | none **(weak)** |  | - |
| set_pixel | False | color | positional | any | none **(weak)** |  | - |

## RCE_csn_snippet_252 (`RGB888Format`)

Own-class comparison: `{"RGB888Format": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | - | - | - | - | - | - |
| fill | False | framebuf | positional | any | none **(weak)** |  | - |
| fill | False | color | positional | any | none **(weak)** |  | - |
| fill_rect | True | framebuf | positional | bool | p_literals **(weak)** | False, True | - |
| fill_rect | True | x | positional | bool | p_literals **(weak)** | False, True | - |
| fill_rect | True | y | positional | bool | p_literals **(weak)** | False, True | - |
| fill_rect | True | width | positional | bool | p_literals **(weak)** | False, True | - |
| fill_rect | True | height | positional | bool | p_literals **(weak)** | False | - |
| fill_rect | True | color | positional | bool | p_literals **(weak)** | False | - |
| get_pixel | False | framebuf | positional | any | none **(weak)** |  | - |
| get_pixel | False | x | positional | any | none **(weak)** |  | - |
| get_pixel | False | y | positional | any | none **(weak)** |  | - |
| set_pixel | False | framebuf | positional | any | none **(weak)** |  | - |
| set_pixel | False | x | positional | any | none **(weak)** |  | - |
| set_pixel | False | y | positional | any | none **(weak)** |  | - |
| set_pixel | False | color | positional | any | none **(weak)** |  | - |

## RCE_csn_snippet_257 (`UserProfileService`)

Own-class comparison: `{"UserProfileService": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | - | - | - | - | - | - |
| lookup | True | user_id | positional | str | annotation |  | - |
| save | True | user_profile | positional | dict[str, any] | annotation | [True, True, True, True] | - |

## RCE_csn_snippet_272 (`UserContextFormViewMixin`)

Own-class comparison: `{"UserContextFormViewMixin": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | - | - | - | - | - | - |
| get_agnocomplete_context | True | - | - | - | - | - | - |
| get_form_kwargs | True | - | - | - | - | - | - |

## RCE_csn_snippet_273 (`BasePagination`)

Own-class comparison: `{"BasePagination": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | - | - | - | - | - | - |
| get_paginated_response | False | data | positional | any | none **(weak)** |  | - |
| paginate_query | True | query | positional | int | p_literals **(weak)** | 1613 | - |
| paginate_query | True | request | positional | int | p_literals **(weak)** | 1613 | - |

## RCE_csn_snippet_274 (`BasePermission`)

Own-class comparison: `{"BasePermission": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | - | - | - | - | - | - |
| has_object_permission | True | request | positional | tuple[any, ...] | p_literals **(weak)** |  | - |
| has_object_permission | True | view | positional | tuple[any, ...] | p_literals **(weak)** |  | - |
| has_object_permission | True | obj | positional | tuple[any, ...] | p_literals **(weak)** |  | - |
| has_permission | True | request | positional | bool | p_literals **(weak)** | False | - |
| has_permission | True | view | positional | bool | p_literals **(weak)** | False | - |

## RCE_csn_snippet_275 (`Signer`)

Own-class comparison: `{"Signer": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | - | - | - | - | - | - |
| sign | True | msg | positional | bool | p_literals **(weak)** | False | - |
| sign | True | key | positional | bool | p_literals **(weak)** | False | - |
| verify | True | msg | positional | bool | p_literals **(weak)** | False | - |
| verify | True | sig | positional | bool | p_literals **(weak)** | False | - |
| verify | True | key | positional | bool | p_literals **(weak)** | False | - |

## RCE_csn_snippet_276 (`QuerySingle`)

Own-class comparison: `{"QuerySingle": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | connection | positional | dict[bool, bool] | bool | p_literals **(weak)** | {True: True}, True | - |
| __init__ | True | object_type | positional | set[bool] | bool | p_literals **(weak)** | None, True | - |
| __init__ | True | url_params | positional | set[bool] | none | p_literals **(weak)** | None | - |
| __init__ | True | query_params | positional | dict[bool, bool] | none | p_literals **(weak)** | {True: True}, None | - |
| reload | True | - | - | - | - | - | - |
| result | True | - | - | - | - | - | - |

## RCE_csn_snippet_278 (`Dumper`)

Own-class comparison: `{"Dumper": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | - | - | - | - | - | - |
| dump | False | record | positional | any | none **(weak)** |  | - |
| dump | False | data | positional | any | none **(weak)** |  | - |
| load | True | data | positional | int | p_literals **(weak)** | -2270 | - |
| load | True | record_cls | positional | int | p_literals **(weak)** | -2270 | - |

## RCE_csn_snippet_279 (`SearchDumperExt`)

Own-class comparison: `{"SearchDumperExt": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | - | - | - | - | - | - |
| dump | False | record | positional | any | none **(weak)** |  | - |
| dump | False | data | positional | any | none **(weak)** |  | - |
| load | True | data | positional | int | p_literals **(weak)** | -2270 | - |
| load | True | record_cls | positional | int | p_literals **(weak)** | -2270 | - |

## RCE_csn_snippet_280 (`SystemFieldContext`)

Own-class comparison: `{"SystemFieldContext": {"kind": "accessors", "attributes": ["field", "record_cls"], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: ['field', 'record_cls'].

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | field | positional | str | p_literals **(weak)** | "Oo'.@Ha&uMmc,;~W\rudy" | - |
| __init__ | True | record_cls | positional | str | p_literals **(weak)** | "Oo'.@Ha&uMmc,;~W\rudy" | - |

## RCE_csn_snippet_286 (`AccessEnumMixin`)

Own-class comparison: `{"AccessEnumMixin": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | - | - | - | - | - | - |
| __str__ | True | - | - | - | - | - | - |
| validate | False | level | positional | any | none **(weak)** |  | - |

## RCE_csn_snippet_288 (`Aspect`)

Own-class comparison: `{"Aspect": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | - | - | - | - | - | - |
| clone | True | - | - | - | - | - | - |
| getId | True | - | - | - | - | - | - |

## RCE_csn_snippet_30 (`LazyOpResult`)

Own-class comparison: `{"LazyOpResult": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: ['dim', 'expr', 'weld_type']; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | expr | positional | int | p_literals **(weak)** | 891 | - |
| __init__ | True | weld_type | positional | int | p_literals **(weak)** | 891 | - |
| __init__ | True | dim | positional | int | p_literals **(weak)** | 891 | - |
| evaluate | True | verbose | positional | bool | docstring | True | - |
| evaluate | True | decode | positional | bool | docstring | True | - |
| evaluate | True | passes | positional | none | default **(weak)** | None | - |
| evaluate | True | num_threads | positional | int | default **(weak)** | 1 | - |
| evaluate | True | apply_experimental_transforms | positional | bool | default **(weak)** | False | - |

## RCE_csn_snippet_302 (`ErrorHandler`)

Own-class comparison: `{"ErrorHandler": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | - | - | - | - | - | - |
| can_handle | False | e | positional | any | none **(weak)** |  | - |
| handle | True | e | positional | bool | p_literals **(weak)** | False | - |

## RCE_csn_snippet_304 (`CommandDispatcher`)

Own-class comparison: `{"CommandDispatcher": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | - | - | - | - | - | - |
| bound | False | instance | positional | any | docstring |  | - |
| command | False | fn | positional | UNSUPPORTED (docstring type 'function') | docstring |  | - |
| execute_command | True | command | positional | str | docstring |  | KeyError |
| execute_command | True | args | positional | dict[any, any] | docstring | None | KeyError |

## RCE_csn_snippet_305 (`QuotaBase`)

Own-class comparison: `{"QuotaBase": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | - | - | - | - | - | - |
| get_quota_usage | True | - | - | - | - | - | - |

## RCE_csn_snippet_33 (`ExceptionHandler`)

Own-class comparison: `{"ExceptionHandler": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | - | - | - | - | - | - |
| handle | False | exc | positional | any | none **(weak)** |  | - |
| wants | True | exc | positional | bool | p_literals **(weak)** | False | - |

## RCE_csn_snippet_42 (`WifiManager`)

Own-class comparison: `{"WifiManager": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | device | positional | str | p_literals **(weak)** | 'D16^?' | - |
| getWifiState | True | - | - | - | - | - | - |

## RCE_csn_snippet_45 (`TokenStoreBase`)

Own-class comparison: `{"TokenStoreBase": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | token_collection | positional | str | docstring | True, 'default' | - |
| has_token | False | music_service_id | positional | any | none **(weak)** |  | - |
| has_token | False | household_id | positional | any | none **(weak)** | None | - |
| load_token_pair | False | music_service_id | positional | any | none **(weak)** |  | - |
| load_token_pair | False | household_id | positional | any | none **(weak)** |  | - |
| save_token_pair | True | music_service_id | positional | bool | p_literals **(weak)** | True | - |
| save_token_pair | True | household_id | positional | bool | p_literals **(weak)** | True | - |
| save_token_pair | True | token_pair | positional | bool | p_literals **(weak)** | True | - |

## RCE_csn_snippet_46 (`ShareClass`)

Own-class comparison: `{"ShareClass": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | - | - | - | - | - | - |
| canonical_uri | True | uri | positional | str | docstring |  | - |
| extract | True | uri | positional | float | p_literals **(weak)** | -434.91 | - |
| magic | True | - | - | - | - | - | - |
| service_number | True | - | - | - | - | - | - |

## RCE_csn_snippet_48 (`Datetime`)

Own-class comparison: `{"Datetime": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | - | - | - | - | - | - |
| now | True | - | - | - | - | - | - |
| pack | False | datetime | positional | UNSUPPORTED (annotation dt.datetime) | annotation |  | - |
| unpack | True | data | positional | bytes | annotation |  | - |

## RCE_csn_snippet_49 (`QuilAtom`)

Own-class comparison: `{"QuilAtom": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | - | - | - | - | - | - |
| __str__ | True | - | - | - | - | - | - |
| out | True | - | - | - | - | - | - |

## RCE_csn_snippet_50 (`MetPyChecker`)

Own-class comparison: `{"MetPyChecker": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | tree | positional | any | none **(weak)** | None | - |
| error | False | err | positional | any | none **(weak)** |  | - |
| run | True | - | - | - | - | - | - |

## RCE_csn_snippet_51 (`Array`)

Own-class comparison: `{"Array": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | fmt | positional | bytes | p_literals **(weak)** |  | - |
| __call__ | True | buf | positional | bytes | p_literals **(weak)** |  | - |

## RCE_csn_snippet_52 (`BitField`)

Own-class comparison: `{"BitField": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | names | varargs | int | p_literals **(weak)** | 594 | - |
| __call__ | True | val | positional | list[int] | int | p_literals **(weak)** | None, [594, 594, 594], 594, 2 | - |

## RCE_csn_snippet_53 (`Bits`)

Own-class comparison: `{"Bits": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | num_bits | positional | int | bool | p_literals **(weak)** | 1409, False, True | - |
| __call__ | True | val | positional | int | p_literals **(weak)** | 1409, None | - |

## RCE_csn_snippet_54 (`Enum`)

Own-class comparison: `{"Enum": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | args | varargs | any | none **(weak)** |  | - |
| __init__ | True | kwargs | varkw | any | none **(weak)** |  | - |
| __call__ | True | val | positional | any | none **(weak)** | None | - |

## RCE_csn_snippet_56 (`Collection`)

Own-class comparison: `{"Collection": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | - | - | - | - | - | - |
| __len__ | True | - | - | - | - | - | - |

## RCE_csn_snippet_6 (`RecordFile`)

Own-class comparison: `{"RecordFile": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: ['name', 'path']; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | name | positional | str | docstring | -4170, -3323 | - |
| __init__ | True | path | positional | str | docstring | None, -3323 | - |
| __repr__ | True | - | - | - | - | - | - |

## RCE_csn_snippet_60 (`CodePageManager`)

Own-class comparison: `{"CodePageManager": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | data | positional | int | p_literals **(weak)** | -1077 | - |
| get_encoding_name | True | - | - | - | - | - | - |

## RCE_csn_snippet_63 (`StreamingFile`)

Own-class comparison: `{"StreamingFile": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | data_stream | positional | int | str | p_literals **(weak)** | -3426, '+na}_<' | - |
| read | True | size | positional | int | none | p_literals **(weak)** | -3426, None | - |

## RCE_csn_snippet_69 (`BaseStorage`)

Own-class comparison: `{"BaseStorage": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | - | - | - | - | - | - |
| exists | True | id | positional | str | docstring | 282.6 | - |
| max_file_idx | True | - | - | - | - | - | - |
| write | True | id | positional | str | docstring | False | - |
| write | True | data | positional | bytes | str | docstring | None | - |

## RCE_csn_snippet_7 (`RecordLevel`)

Own-class comparison: `{"RecordLevel": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: ['icon', 'name', 'no']; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | name | positional | str | docstring | None, False | - |
| __init__ | True | no | positional | int | docstring | None, False | - |
| __init__ | True | icon | positional | str | docstring | None, False | - |
| __repr__ | True | - | - | - | - | - | - |

## RCE_csn_snippet_75 (`Geometry`)

Own-class comparison: `{"Geometry": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | - | - | - | - | - | - |
| geojson | True | - | - | - | - | - | - |
| to_dict | True | - | - | - | - | - | - |

## RCE_csn_snippet_8 (`RecordProcess`)

Own-class comparison: `{"RecordProcess": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: ['id', 'name']; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | id_ | positional | int | docstring | -4170, -3323 | - |
| __init__ | True | name | positional | str | docstring | None, -3323 | - |
| __repr__ | True | - | - | - | - | - | - |

## RCE_csn_snippet_82 (`Completer`)

Own-class comparison: `{"Completer": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | - | - | - | - | - | - |
| complete | True | original | positional | str | docstring | False | - |
| complete | True | pos | positional | int | docstring | ' ' | - |
| relevant_part | True | original | positional | str | p_literals **(weak)** | '', ' ' | - |
| relevant_part | True | pos | positional | bool | p_literals **(weak)** | False | - |

## RCE_csn_snippet_84 (`Scheme`)

Own-class comparison: `{"Scheme": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | title | positional | any | none **(weak)** | None | - |
| add_argument | False | arg | positional | any | none **(weak)** |  | - |
| to_xml | True | - | - | - | - | - | - |

## RCE_csn_snippet_85 (`SessionListener`)

Own-class comparison: `{"SessionListener": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | - | - | - | - | - | - |
| callback | True | root | positional | str | p_literals **(weak)** | "W.'" | - |
| callback | True | raw | positional | int | p_literals **(weak)** | 4915 | - |
| errback | True | ex | positional | str | p_literals **(weak)** | '[F7.f].-Js@' | - |

## RCE_csn_snippet_9 (`RecordThread`)

Own-class comparison: `{"RecordThread": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: ['id', 'name']; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | id_ | positional | int | docstring | -4170, -3323 | - |
| __init__ | True | name | positional | str | docstring | None, -3323 | - |
| __repr__ | True | - | - | - | - | - | - |

## RCE_csn_snippet_98 (`LCModel`)

Own-class comparison: `{"LCModel": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | - | - | - | - | - | - |
| extend_partial | True | times | positional | int | p_literals **(weak)** | -1679 | - |
| extend_partial | True | obs_times | positional | int | p_literals **(weak)** | -1679 | - |
| extend_partial | True | obs_losses | positional | int | p_literals **(weak)** | -1679 | - |
| extend_partial | True | config | positional | none | default **(weak)** | None | - |
| fit | True | times | positional | list[any] | docstring | True | - |
| fit | True | losses | positional | list[any] | docstring | True | - |
| fit | True | configs | positional | list[any] | none | docstring | None | - |
| predict_unseen | True | times | positional | str | p_literals **(weak)** | '' | - |
| predict_unseen | True | config | positional | str | p_literals **(weak)** | '' | - |

## RCE_post_snippet_112 (`SessionResetHandler`)

Own-class comparison: `{"SessionResetHandler": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | log_func | positional | float | none | tuple[str | float, ...] | p_literals **(weak)** | -3660.6, None | - |
| check_for_reset_command | True | command | positional | str | annotation | ';~W\rudy;\\8=P$/0&D$' | - |
| clear_reset_state | True | - | - | - | - | - | - |
| find_reset_session_file | False | project_dir | positional | UNSUPPORTED (annotation Path) | annotation | None | - |
| find_reset_session_file | False | current_file | positional | UNSUPPORTED (annotation Path) | annotation | None | - |
| find_reset_session_file | False | max_wait | positional | float | annotation | -1192.88686, 10.0 | - |
| get_reset_info | True | - | - | - | - | - | - |
| is_reset_pending | True | - | - | - | - | - | - |
| mark_reset_detected | True | command | positional | str | annotation | None, "'x(\x0c30cs<IDfpe(`\n" | - |

## RCE_post_snippet_129 (`TranscriptionBuffer`)

Own-class comparison: `{"TranscriptionBuffer": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | client_uid | positional | list[str] | p_literals **(weak)** | None, ['Nf9\x0c\tcb\n', 'Nf9\x0c\tcb\n', 'Nf9\x0c\tcb\n'] | - |
| add_segments | True | partial_segments | positional | str | tuple[str | list[str], ...] | p_literals **(weak)** | '%R', None | - |
| add_segments | True | completed_segments | positional | str | p_literals **(weak)** | '%R', None, 'Nf9\x0c\tcb\n' | - |
| get_segments_for_response | True | - | - | - | - | - | - |

## RCE_post_snippet_132 (`Text_background`)

Own-class comparison: `{"Text_background": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | color | keyword_only | str | annotation | 'gMe:' | - |
| __init__ | True | style | keyword_only | int | default **(weak)** | 1 | - |
| __init__ | True | alpha | keyword_only | float | annotation | True | - |
| __init__ | True | round_radius | keyword_only | float | annotation | 0.0 | - |
| __init__ | True | height | keyword_only | float | annotation | True, 0.14 | - |
| __init__ | True | width | keyword_only | float | annotation | False, 0.14 | - |
| __init__ | True | horizontal_offset | keyword_only | float | annotation | 0.5 | - |
| __init__ | True | vertical_offset | keyword_only | float | annotation | False, 0.5 | - |
| export_json | True | - | - | - | - | - | - |

## RCE_post_snippet_134 (`Text_shadow`)

Own-class comparison: `{"Text_shadow": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | has_shadow | keyword_only | bool | annotation | False | - |
| __init__ | True | alpha | keyword_only | float | annotation | 0.9 | - |
| __init__ | True | angle | keyword_only | float | annotation | -45.0 | - |
| __init__ | True | color | keyword_only | str | annotation | ']%DKW+]', '#000000' | - |
| __init__ | True | distance | keyword_only | float | annotation | ']%DKW+]', 5.0 | - |
| __init__ | True | smoothing | keyword_only | float | annotation | ']%DKW+]', 0.45 | - |
| export_json | True | - | - | - | - | - | - |

## RCE_post_snippet_14 (`templater`)

Own-class comparison: `{"templater": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | q_dict | positional | dict[any, any] | annotation |  | - |
| __init__ | True | a_dict | positional | dict[any, any] | annotation |  | - |
| __init__ | True | user_name | positional | str | annotation | '' | - |
| __init__ | True | global_bio | positional | str | annotation | '' | - |
| __init__ | True | is_cot | positional | bool | annotation | True | - |
| get_A_template | True | question_type | positional | str | annotation |  | - |
| get_Q_template | True | question_type_prompt | positional | str | annotation |  | - |

## RCE_post_snippet_141 (`GoalRedirectionTemplate`)

Own-class comparison: `{"GoalRedirectionTemplate": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | - | - | - | - | - | - |
| enhance_ambiguous_framing | True | attack | positional | str | annotation | 'j5g', 'Izn:^VmBJqm7%(h', '[fG\\i"U' | - |
| enhance_constraint_confusion | True | attack | positional | str | annotation | 'unRaJ4\x0cioNK', None | - |
| enhance_goal_drift | True | attack | positional | str | annotation |  | - |
| enhance_operational_alignment | True | attack | positional | str | annotation |  | - |
| enhance_priority_shifting | True | attack | positional | str | annotation | 'Izn:^VmBJqm7%(h' | - |
| enhance_scope_expansion | True | attack | positional | str | annotation | 'Y\x0cx#a@z5\x0b$b6' | - |

## RCE_post_snippet_142 (`SystemOverrideTemplate`)

Own-class comparison: `{"SystemOverrideTemplate": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | - | - | - | - | - | - |
| enhance_api_admin_call | True | attack | positional | str | annotation | 'Izn:^VmBJqm7%(h', 'j5g', '[fG\\i"U' | - |
| enhance_emergency_protocol | True | attack | positional | str | annotation | 'unRaJ4\x0cioNK', None | - |
| enhance_machine_identity | True | attack | positional | str | annotation |  | - |
| enhance_maintenance_mode | True | attack | positional | str | annotation |  | - |
| enhance_system_override | True | attack | positional | str | annotation | 'Izn:^VmBJqm7%(h' | - |
| enhance_trusted_integration | True | attack | positional | str | annotation | 'Y\x0cx#a@z5\x0b$b6' | - |

## RCE_post_snippet_152 (`Trie`)

Own-class comparison: `{"Trie": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | - | - | - | - | - | - |
| insert | True | word | positional | str | annotation |  | - |
| is_prefix | True | prefix | positional | str | annotation |  | - |
| is_word | True | word | positional | str | annotation |  | - |

## RCE_post_snippet_153 (`ConditionalTracker`)

Own-class comparison: `{"ConditionalTracker": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | - | - | - | - | - | - |
| are_mutually_exclusive | True | context1 | positional | tuple[any, ...] | annotation | None | - |
| are_mutually_exclusive | True | context2 | positional | tuple[any, ...] | annotation |  | - |
| process_line | True | line | positional | str | annotation | '}Lz6_UE[L1\x0by^!"\x0bnu' | - |
| process_line | True | line_index | positional | int | annotation | '}Lz6_UE[L1\x0by^!"\x0bnu' | - |
| reset | True | - | - | - | - | - | - |

## RCE_post_snippet_154 (`ShellUtils`)

Own-class comparison: `{"ShellUtils": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | - | - | - | - | - | - |
| contains_shell_operators | True | line | positional | str | annotation | '\nL/9:=' | - |
| is_shell_control_end | True | line | positional | str | annotation | '6g0l9j*Bz\r<ej,' | - |
| is_shell_control_start | True | line | positional | str | annotation |  | - |

## RCE_post_snippet_155 (`PatternUtils`)

Own-class comparison: `{"PatternUtils": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | - | - | - | - | - | - |
| apply_assignment_spacing | True | line | positional | str | annotation | 'q6\x0cq]j]B-q^.rp&HK~z', 'Q;H&/5', '[K\x0c$9QvI)oz7qJXm}FS. | - |
| apply_assignment_spacing | True | use_spaces | positional | bool | annotation | False, True | - |
| contains_assignment | True | line | positional | str | annotation | 'H*ts4.kx}>T5tP#8X)L_', 'r\'n"\trJ:p', '|l8F%\\lPL' | - |
| format_pattern_rule | True | line | positional | str | annotation | '?H]dx$7K{i_', 'Z0&#j', "%T3\x0cr`FxL(s:'V", '&WOmP>J\n6B9@& | - |
| format_pattern_rule | True | space_after_colon | positional | bool | annotation | True | - |
| format_target_colon | True | line | positional | str | annotation | '?H]dx$7K{i_', 'r+=n\tJ:', '[K\x0c$9QvI)oz7qJXm}FS.', 'r\'n" | - |
| format_target_colon | True | space_before | positional | bool | annotation | 'Q;H&/5', False | - |
| format_target_colon | True | space_after | positional | bool | annotation | 'KBO?a;;Mv#sa[\\@B[3WV', True | - |
| get_conditional_indent_level | True | line | positional | str | annotation | '^)d6 h', '?H]dx$7K{i_', 'Q;H&/5', '|l8F%\\lPL' | - |
| is_conditional_directive | True | line | positional | str | annotation |  | - |

## RCE_post_snippet_159 (`MemoryFormatter`)

Own-class comparison: `{"MemoryFormatter": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | - | - | - | - | - | - |
| format_delete_response | True | status | positional | str | annotation | '$dmJRs' | - |
| format_delete_response | True | doc_id | positional | str | annotation | '$dmJRs' | - |
| format_delete_response | True | kb_id | positional | str | annotation | '$dmJRs' | - |
| format_get_response | True | document_id | positional | str | annotation |  | - |
| format_get_response | True | kb_id | positional | str | annotation |  | - |
| format_get_response | True | content_data | positional | dict[any, any] | annotation |  | - |
| format_list_response | True | response | positional | dict[any, any] | annotation |  | - |
| format_retrieve_response | True | response | positional | dict[any, any] | annotation |  | - |
| format_retrieve_response | True | min_score | positional | float | annotation | 768.80272, 0.0 | - |
| format_store_response | True | doc_id | positional | str | annotation | 'uG~|@BO;Dv\r' | - |
| format_store_response | True | kb_id | positional | str | annotation | 'BV\\T*F{UDsh!_B71?' | - |
| format_store_response | True | title | positional | str | annotation | 'uG~|@BO;Dv\r', 'BV\\T*F{UDsh!_B71?' | - |

## RCE_post_snippet_16 (`ObservabilityManager`)

Own-class comparison: `{"ObservabilityManager": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | custom_callbacks | positional | list[any] | none | annotation | {}, None | - |
| __repr__ | True | - | - | - | - | - | - |
| add_callback | False | callback | positional | any | none **(weak)** |  | - |
| clear_callbacks | True | - | - | - | - | - | - |
| get_callbacks | True | - | - | - | - | - | - |
| get_handler_names | True | - | - | - | - | - | - |
| has_callbacks | True | - | - | - | - | - | - |

## RCE_post_snippet_165 (`ToolHistory`)

Own-class comparison: `{"ToolHistory": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | - | - | - | - | - | - |
| add_searched_queries | True | queries | positional | list[str] | annotation | ['Tcw7b3XU8Cc=}i7J~Cz', 'f9H_\t#b\nW_+E', 'Tcw7b3XU8Cc=}i7J~ | - |
| add_visited_urls | True | urls | positional | list[str] | annotation | ['u0?<Kb<A-|:^!0', 'Fh=^f.P_`4I*', 'u0?<Kb<A-|:^!0'], ['q(\r | - |
| get_searched_queries | True | - | - | - | - | - | - |
| get_visited_urls | True | - | - | - | - | - | - |

## RCE_post_snippet_167 (`PackingMetrics`)

Own-class comparison: `{"PackingMetrics": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | - | - | - | - | - | - |
| calculate_stats_only | True | sequence_lengths | positional | list[int] | annotation | [False] | - |
| calculate_stats_only | True | bins | positional | list[list[int]] | annotation | [[False]] | - |
| calculate_stats_only | True | bin_capacity | positional | int | annotation | -689 | - |
| get_aggregated_stats | True | - | - | - | - | - | - |
| print_aggregated_stats | True | - | - | - | - | - | - |
| reset | True | - | - | - | - | - | - |
| update | True | sequence_lengths | positional | list[int] | annotation | [True, 482, 482, 482, 482], [], [True, False, False, False] | - |
| update | True | bins | positional | list[list[int]] | annotation | [], [[True, False, False, False], [True, False, False, False | - |
| update | True | bin_capacity | positional | int | annotation | True, False, -654 | - |
| update | True | packing_time | positional | float | none | annotation | None | - |

## RCE_post_snippet_173 (`Clock`)

Own-class comparison: `{"Clock": {"kind": "accessors", "attributes": ["now_ns", "now_s"], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: ['now_ns', 'now_s'].

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | - | - | - | - | - | - |
| update | True | ns | positional | int | annotation | True, -2505.065008 | ValueError |

## RCE_post_snippet_182 (`OutputSink`)

Own-class comparison: `{"OutputSink": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | - | - | - | - | - | - |
| finalize | True | - | - | - | - | - | - |
| write | True | text | positional | str | annotation |  | - |

## RCE_post_snippet_185 (`TopKStringTracker`)

Own-class comparison: `{"TopKStringTracker": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | m | positional | int | annotation | True, 277 | - |
| add_string_dict | True | string_counts | positional | dict[any, any] | annotation |  | - |
| add_strings | True | strings | positional | list[str] | annotation | '}L:Q|[\x0cm9TT9$.\\0y*p', ':{g+4' | - |
| get_count | True | string | positional | str | annotation |  | - |
| get_top_k | True | k | positional | int | annotation | -2248, -3328, True, False | - |
| size | True | - | - | - | - | - | - |
| trim_to_m | True | - | - | - | - | - | - |

## RCE_post_snippet_189 (`RateLimiter`)

Own-class comparison: `{"RateLimiter": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | hz | positional | int | docstring | 2035, 3652 | - |
| sleep | True | env | positional | int | p_literals **(weak)** | 2035, None, 870 | - |

## RCE_post_snippet_19 (`MarkdownCleaner`)

Own-class comparison: `{"MarkdownCleaner": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | - | - | - | - | - | - |
| clean_markdown | True | text | positional | str | annotation | 'X|\njs}dPppS\x0c(', '|\njs}dPppS\x0c(', "eY.2F'Uij<$p~7q\\_ | - |

## RCE_post_snippet_194 (`ConstantDelayRetryPolicy`)

Own-class comparison: `{"ConstantDelayRetryPolicy": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | maximum_attempts | positional | int | annotation | 3 | - |
| __init__ | True | delay | positional | float | annotation | 5 | - |
| next | True | elapsed_time | positional | float | annotation | -572.39 | - |
| next | True | attempts | positional | int | annotation | 1722, -572.39 | - |
| next | True | error | positional | float | p_literals **(weak)** | -572.39 | - |

## RCE_post_snippet_209 (`DriverAnalyzer`)

Own-class comparison: `{"DriverAnalyzer": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | file_contents | positional | dict[UNSUPPORTED (annotation pathlib.Path), str] | annotation | {'7': '7'} | - |
| analyze_access_sequences | True | reg_name | positional | str | none | annotation | None | - |
| analyze_function_context | True | reg_name | positional | str | annotation | '7', '' | - |
| analyze_timing_constraints | True | reg_name | positional | str | none | annotation | None | - |

## RCE_post_snippet_218 (`CBlock`)

Own-class comparison: `{"CBlock": {"kind": "accessors", "attributes": ["value"], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: ['value'].

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | value | positional | str | none | annotation | '{', None, 'ga{nab<\\]LW`vb', True, '(o\ttk[' | - |
| __init__ | True | meta | positional | dict[str, any] | none | annotation | {'(o\ttk[': '(o\ttk[', ']@i_1eEmY>': '(o\ttk[', '\t\t^\rX':  | - |
| __repr__ | True | - | - | - | - | - | - |
| __str__ | True | - | - | - | - | - | - |

## RCE_post_snippet_219 (`TokenUsageTracker`)

Own-class comparison: `{"TokenUsageTracker": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | - | - | - | - | - | - |
| get_stats | True | - | - | - | - | - | - |
| reset | True | - | - | - | - | - | - |
| update | True | success | positional | bool | annotation |  | - |
| update | True | token_usage | positional | dict[str, int] | annotation | {'G': False, ",W[\rO'L\x0bLkQ>\\9;": 1219} | - |
| update | True | turn_count | positional | int | annotation | False | - |
| update | True | execution_time | positional | float | annotation | True | - |

## RCE_post_snippet_22 (`DocumentAnalyzer`)

Own-class comparison: `{"DocumentAnalyzer": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | - | - | - | - | - | - |
| analyze_document_type | True | content | positional | str | annotation | 'eyT4"`' | - |
| detect_segmentation_strategy | True | content | positional | str | annotation | '>`Oye(zX?"O\x0ckLdq_6~' | - |
| detect_segmentation_strategy | True | doc_type | positional | str | annotation |  | - |

## RCE_post_snippet_221 (`GitHubTokenPool`)

Own-class comparison: `{"GitHubTokenPool": {"kind": "accessors", "attributes": ["pool_size"], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: ['pool_size'].

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | tokens | positional | list[str] | annotation | [] | - |
| get_current_token | True | - | - | - | - | - | - |
| get_next_token | True | - | - | - | - | - | - |

## RCE_post_snippet_222 (`ModelConfig`)

Own-class comparison: `{"ModelConfig": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | model_name | positional | str | annotation |  | ValueError |
| get_supported_models | True | - | - | - | - | - | - |

## RCE_post_snippet_223 (`BedrockAgentCoreContext`)

Own-class comparison: `{"BedrockAgentCoreContext": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | - | - | - | - | - | - |
| get_request_id | True | - | - | - | - | - | - |
| get_session_id | True | - | - | - | - | - | - |
| get_workload_access_token | True | - | - | - | - | - | - |
| set_request_context | True | request_id | positional | str | annotation |  | - |
| set_request_context | True | session_id | positional | str | none | annotation | None | - |
| set_workload_access_token | True | token | positional | str | annotation |  | - |

## RCE_post_snippet_225 (`PrecisionPreservingDataHandler`)

Own-class comparison: `{"PrecisionPreservingDataHandler": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | - | - | - | - | - | - |
| preserve_calculation_precision | True | result | positional | float | annotation | None, 1504 | - |
| preserve_calculation_precision | True | operation | positional | str | annotation | 'LcA?lNH\t1B,z_*', '3?d"\taH\nU `[#!vvL23w' | - |
| retrieve_price_data | True | data | positional | any | annotation | None | - |
| store_price_data | True | data | positional | any | annotation | None, True | - |
| validate_system_precision | True | - | - | - | - | - | - |

## RCE_post_snippet_226 (`PriceFormatter`)

Own-class comparison: `{"PriceFormatter": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | - | - | - | - | - | - |
| format_currency | True | price | positional | float | int | none | annotation | 1327, -2025, None, -2136, 1566.7264 | - |
| format_currency | True | currency | positional | str | annotation | '', '[Y!CrxTp%/#*', 824, 'USD' | - |
| format_percentage | True | percentage | positional | float | int | none | annotation | 2660, None, -2136, False, {True: True} | - |
| format_price_for_display | True | price | positional | float | int | none | annotation | None, True, -1939, -197, False | - |
| format_price_for_logging | True | price | positional | float | int | none | annotation | None, 1327, -2653, -2354.04, False | - |
| format_quantity | True | quantity | positional | float | int | none | annotation | -334, None, -2354.04, -2653, False | - |

## RCE_post_snippet_227 (`ConversationTurn`)

Own-class comparison: `{"ConversationTurn": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | user_message | positional | dict[any, any] | bool | float | p_literals **(weak)** | {}, True, -2266.63672, None | - |
| __init__ | True | message_index | positional | bool | float | str | p_literals **(weak)** | None, True, -2266.63672, 'z' | - |
| get_preview | True | max_length | positional | set[str] | int | p_literals **(weak)** | 50 | - |

## RCE_post_snippet_23 (`GitHubURLExtractor`)

Own-class comparison: `{"GitHubURLExtractor": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | - | - | - | - | - | - |
| extract_github_urls | True | text | positional | str | annotation | 'HyU', 'M/Cq', '_/Cq' | - |
| extract_target_path | True | text | positional | str | annotation | 'KN{~7>', 'M/Cq' | - |
| infer_repo_name | True | url | positional | str | annotation | '>5j\\6.3;{:R"', '5N +lXPgK+Iw^CP;&O+', '71HoLcHmq,\\O=fhf' | - |

## RCE_post_snippet_232 (`Stopwatch`)

Own-class comparison: `{"Stopwatch": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: ['elapsed', 'is_running']; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | - | - | - | - | - | - |
| reset | True | - | - | - | - | - | - |
| start | True | - | - | - | - | - | - |
| stop | True | - | - | - | - | - | - |

## RCE_post_snippet_24 (`LocalPathExtractor`)

Own-class comparison: `{"LocalPathExtractor": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | - | - | - | - | - | - |
| extract_local_paths | True | text | positional | str | annotation | 'VIUP6o^Ygo3f97.4a m', 'p~\\\'k\'(4~"', 'kZzr%3 DTlykU[J-97z | - |
| is_local_path | True | path | positional | str | annotation | "tqlFHixd'k Sig\t", 'kZzr%3 DTlykU[J-97z', '.' | - |

## RCE_post_snippet_242 (`ImmediateFlushSink`)

Own-class comparison: `{"ImmediateFlushSink": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | stream | positional | none | p_literals **(weak)** | None | - |
| flush | True | - | - | - | - | - | - |
| write | True | message | positional | str | docstring |  | - |

## RCE_post_snippet_243 (`PrintAndFlushSink`)

Own-class comparison: `{"PrintAndFlushSink": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | - | - | - | - | - | - |
| flush | True | - | - | - | - | - | - |
| write | True | message | positional | str | annotation | 'XFPz$.SPCcfqD;5Y_Q' | - |

## RCE_post_snippet_245 (`CallableRegistry`)

Own-class comparison: `{"CallableRegistry": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | - | - | - | - | - | - |
| contains | True | name | positional | str | annotation |  | - |
| get | True | name | positional | str | annotation |  | KeyError |
| register | False | name | positional | str | annotation |  | - |
| register | False | callable_obj | positional | UNSUPPORTED (annotation Callable) | annotation |  | - |

## RCE_post_snippet_249 (`Message`)

Own-class comparison: `{"Message": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | role | positional | str | annotation | 'SyA`M\x0cqL;IS}$LFZ1' | - |
| __init__ | True | content | positional | str | annotation | 'SyA`M\x0cqL;IS}$LFZ1' | - |
| from_dict | True | data | positional | dict[str, str] | annotation |  | - |
| to_dict | True | - | - | - | - | - | - |

## RCE_post_snippet_252 (`BasePlugin`)

Own-class comparison: `{"BasePlugin": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | - | - | - | - | - | - |
| register_backend | False | app | positional | any | none **(weak)** |  | - |
| register_frontend | True | register_func | positional | set[bytes] | p_literals **(weak)** |  | - |

## RCE_post_snippet_253 (`PromptLogger`)

Own-class comparison: `{"PromptLogger": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | log_file | positional | str | annotation | 'E8 0I=~U1%k)\t/6', 'y)(R3z%C{4L<rp\tk:', 'log.txt' | - |
| clear_logs | True | - | - | - | - | - | - |
| get_recent_logs | True | count | positional | int | annotation | 'y)(R3z%C{4L<rp\tk:', -1748, 10 | - |
| log_formatted_prompt | True | system_prompt | positional | str | annotation | 'Ap]ef\t7dxU', None, 'G1R(\tiN)', 'y)(R3z%C{4L<rp\tk:' | - |
| log_formatted_prompt | True | user_prompt | positional | str | annotation | None, '1\x0b+', 'S@b"kP,' | - |
| log_formatted_prompt | True | memory_context | positional | str | annotation | "M7^(mk3\x0c>\r'1w<M+U\\", '' | - |
| log_formatted_prompt | True | character_name | positional | str | annotation | None | - |
| log_formatted_prompt | True | user_query | positional | str | annotation | None | - |
| log_prompt | True | messages | positional | list[dict[str, str]] | annotation | [{}], 'y)(R3z%C{4L<rp\tk:' | - |
| log_prompt | True | character_name | positional | str | annotation | None | - |
| log_prompt | True | user_query | positional | str | annotation | None | - |

## RCE_post_snippet_254 (`TimeTracker`)

Own-class comparison: `{"TimeTracker": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | history_dir | positional | str | annotation | '@!-nM', '`\\eHtj*+6,-ZUN*', None | - |
| format_time_elapsed | False | last_time | positional | UNSUPPORTED (annotation datetime) | annotation |  | - |
| format_time_elapsed | False | current_time | positional | UNSUPPORTED (annotation datetime) | annotation |  | - |
| get_last_message_time | True | character_id | positional | str | annotation | '@!-nM' | - |
| get_time_elapsed_prefix | True | character_id | positional | str | annotation | '`\\eHtj*+6,-ZUN*' | - |

## RCE_post_snippet_255 (`CacheKeyBuilder`)

Own-class comparison: `{"CacheKeyBuilder": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | - | - | - | - | - | - |
| agent_health_key | True | agent_id | positional | str | annotation | 'pcT7%XIZ*B,' | - |
| alerts_key | True | agent_id | positional | str | none | annotation | None | - |
| alerts_key | True | time_range | positional | str | annotation | "VY*\\'}0", '24h' | - |
| alerts_key | True | level | positional | int | none | annotation | None | - |
| ports_key | True | agent_id | positional | str | annotation | ',*n1W`}pJ_Gk*;._.', '8yY}]rr4}=0q$iDii|' | - |
| ports_key | True | state | positional | list[str] | annotation | None | - |
| ports_key | True | protocol | positional | list[str] | annotation | '8yY}]rr4}=0q$iDii|', None | - |
| processes_key | True | agent_id | positional | str | annotation | ']6<', '&&@8Ph' | - |
| processes_key | True | include_children | positional | bool | annotation | True | - |
| vulnerabilities_key | True | agent_id | positional | str | none | annotation | None | - |
| vulnerabilities_key | True | severity | positional | str | none | annotation | None | - |

## RCE_post_snippet_256 (`PromptPatternMatcher`)

Own-class comparison: `{"PromptPatternMatcher": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | - | - | - | - | - | - |
| analyze_prompt | True | prompt | positional | str | annotation | ' eN\\\r', '', 'S\t]%(=fFe\\56v' | - |
| analyze_prompt | True | tool_name | positional | str | annotation | ' eN\\\r', '' | - |
| analyze_prompt | True | arguments | positional | dict[str, any] | annotation | ' eN\\\r', 'S\t]%(=fFe\\56v' | - |

## RCE_post_snippet_264 (`User`)

Own-class comparison: `{"User": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | id | positional | str | annotation | '2rKv7"m P*{h/', 't~BO 4u~j:Z\n', '_pJ]+7 ,"y"S' | - |
| __init__ | True | name | positional | str | annotation | 'Rm$tz2L0Q"]S.#Tve', 't~BO 4u~j:Z\n', '_pJ]+7 ,"y"S' | - |
| __init__ | True | roles | positional | list[str] | annotation | None | - |
| __repr__ | True | - | - | - | - | - | - |

## RCE_post_snippet_268 (`IndexManager`)

Own-class comparison: `{"IndexManager": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | - | - | - | - | - | - |
| clear | True | - | - | - | - | - | - |
| index | False | doc | positional | any | none **(weak)** |  | - |
| query | True | field | positional | any | none **(weak)** | None | - |
| query | True | value | positional | any | none **(weak)** | None | - |
| query_in | True | field | positional | str | p_literals **(weak)** | "Tow'KBs\tcZs,(\x0b" | - |
| query_in | True | values | positional | str | p_literals **(weak)** | "Tow'KBs\tcZs,(\x0b" | - |
| reindex | False | old_doc | positional | any | none **(weak)** |  | - |
| reindex | False | new_doc | positional | any | none **(weak)** |  | - |
| remove | False | doc | positional | any | none **(weak)** |  | - |

## RCE_post_snippet_280 (`BoundWorkerMethod`)

Own-class comparison: `{"BoundWorkerMethod": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | wrapper | positional | dict[bool, bool] | p_literals **(weak)** | {False: False} | - |
| __init__ | True | instance | positional | any | annotation | False | - |
| __call__ | True | args | varargs | any | none **(weak)** |  | - |
| __call__ | True | kwargs | varkw | any | none **(weak)** |  | - |
| async_call | True | args | varargs | any | none **(weak)** |  | - |
| async_call | True | kwargs | varkw | any | none **(weak)** |  | - |
| run_and_wait | True | args | varargs | any | none **(weak)** |  | Exception, RuntimeError |
| run_and_wait | True | timeout | keyword_only | float | none | annotation | None | Exception, RuntimeError |
| run_and_wait | True | kwargs | varkw | any | none **(weak)** |  | Exception, RuntimeError |
| set_pool | False | pool | positional | UNSUPPORTED (annotation WorkerPool) | annotation |  | - |
| shutdown_default_pool | True | - | - | - | - | - | - |
| submit | True | args | varargs | any | none **(weak)** |  | - |
| submit | True | kwargs | varkw | any | none **(weak)** |  | - |

## RCE_post_snippet_281 (`FewShotFormat`)

Own-class comparison: `{"FewShotFormat": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | - | - | - | - | - | - |
| convert | True | examples | positional | list[dict[str, any]] | annotation | [{",'": ",'"}, {",'": ",'"}, {",'": ",'"}], None, '3.}!B9Afy | - |
| validate | True | examples | positional | list[dict[str, any]] | annotation | [{'yc.GP': 'yc.GP', ",'": 'yc.GP'}, {'yc.GP': 'yc.GP', ",'": | - |

## RCE_post_snippet_285 (`Block`)

Own-class comparison: `{"Block": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | block_type | positional | str | annotation | '>L.is', 's4]hUi:~g#', 1190 | - |
| __init__ | True | content | positional | str | annotation | '>L.is', 'QLDM{@EpO,N`jRxt5W?', '{J.fP&e2m;EH*T9\t', 1190 | - |
| __init__ | True | title | positional | str | none | annotation | '>L.is', None | - |
| __repr__ | True | - | - | - | - | - | - |

## RCE_post_snippet_286 (`NavigationAction`)

Own-class comparison: `{"NavigationAction": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | target_uri | positional | str | annotation | ';Os.pK(99\rm', '!\tbF8GB8ICrq(\r^Nh>' | - |
| __repr__ | True | - | - | - | - | - | - |

## RCE_post_snippet_29 (`LastUsedParams`)

Own-class comparison: `{"LastUsedParams": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | config_dir | positional | none | default **(weak)** | None | - |
| clear | True | - | - | - | - | - | - |
| exists | True | - | - | - | - | - | - |
| load | True | - | - | - | - | - | - |
| save | False | settings | positional | UNSUPPORTED (annotation Settings) | annotation |  | - |

## RCE_post_snippet_294 (`CodeManager`)

Own-class comparison: `{"CodeManager": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | - | - | - | - | - | - |
| get_formatted_codes | True | - | - | - | - | - | - |
| get_raw_code | True | - | - | - | - | - | - |
| has_code | True | - | - | - | - | - | - |
| update_from_response | True | response | positional | str | annotation |  | - |

## RCE_post_snippet_295 (`ToolSelector`)

Own-class comparison: `{"ToolSelector": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | tools | positional | list[dict[str, any]] | annotation | [{'pL0JGu#': 'pL0JGu#', 'J3.f#]NOFY9p+g|v\x0b*&': 'J3.f#]NOF | - |
| filter_by_keywords | True | keywords | positional | list[str] | annotation | ['B]r&%_cx=b}4!1x ', 'B]r&%_cx=b}4!1x '], ['^\r+y&Y0)2iop?bo | - |
| filter_by_keywords | True | match_all | positional | bool | annotation | False, True | - |
| filter_by_roles | True | role_patterns | positional | dict[str, list[str]] | annotation | {'+"n?&9#': ['+"n?&9#', '\\zgEChhwQ>r4Ep1z-'], "%a#w-I'Y3etQ | - |
| select_by_names | True | tool_names | positional | list[str] | annotation | [], ['B]r&%_cx=b}4!1x ', 'B]r&%_cx=b}4!1x '], '^\r+y&Y0)2iop | - |
| select_tools | True | task_description | positional | str | annotation | ';c', '', '^\r+\ty& 2iop?boA\te', 'l@CB\r\r|*\rF^\x0c.nz', ' | - |
| select_tools | True | num_agents | positional | int | none | annotation | 603, True, 602, None | - |
| select_tools | True | overlap | positional | bool | annotation | True, {'^\r+\ty& 2iopboA\te': '^\r+\ty& 2iopboA\te'}, False | - |
| select_tools | True | limit | positional | int | annotation | 5 | - |

## RCE_post_snippet_305 (`ArazzoComponentsBuilder`)

Own-class comparison: `{"ArazzoComponentsBuilder": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | - | - | - | - | - | - |
| build_default_components | True | - | - | - | - | - | - |
| create_action | True | action_type | positional | str | annotation |  | - |
| create_action | True | name | positional | str | annotation |  | - |
| create_action | True | action_definition | positional | dict[str, any] | annotation |  | - |

## RCE_post_snippet_307 (`ReferenceValidator`)

Own-class comparison: `{"ReferenceValidator": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | - | - | - | - | - | - |
| validate_step_references | True | workflow | positional | dict[str, any] | annotation | False, {'V@qf3V': 'V@qf3V', 'NwF$W': 755} | - |

## RCE_post_snippet_308 (`InMemoryBlobStore`)

Own-class comparison: `{"InMemoryBlobStore": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | max_size | positional | int | annotation | 4119, 100 | - |
| delete | True | blob_id | positional | str | annotation | 'u6.vH?s;4P/%\x0b/U{', 'IWf;)' | - |
| info | True | blob_id | positional | str | annotation |  | - |
| load | True | blob_id | positional | str | annotation | 'v\tg', '6v:&Mg!8}g<wr1j', 'Sa\\+4u:JVEAsf>"=d' | - |
| save | True | data | positional | bytes | annotation | "k'-a^\n5{\t>9nRK-pS", 'MB' | - |
| save | True | meta | positional | dict[str, any] | annotation | {"k'-a^\n5{\t>9nRK-pS": 'MB', 'MB': 4119}, {"k'-a^\n5{\t>9nR | - |

## RCE_post_snippet_309 (`LocalFileBlobStore`)

Own-class comparison: `{"LocalFileBlobStore": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | root | positional | str | none | annotation | None | - |
| __init__ | True | janitor_after_h | positional | int | annotation | 24 | - |
| delete | True | blob_id | positional | str | annotation |  | - |
| info | True | blob_id | positional | str | annotation |  | FileNotFoundError |
| load | True | blob_id | positional | str | annotation |  | FileNotFoundError |
| purge_old | True | - | - | - | - | - | - |
| save | True | data | positional | bytes | annotation |  | - |
| save | True | meta | positional | dict[str, any] | annotation |  | - |

## RCE_post_snippet_312 (`NotesSearchController`)

Own-class comparison: `{"NotesSearchController": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | - | - | - | - | - | - |
| search_notes | True | notes | positional | list[dict[str, any]] | annotation | {}, [{}, {}], [] | - |
| search_notes | True | query | positional | str | annotation | ']NOFY9p+g|v\x0b*&?I', '/rnGxMZQLeJ=\n4', '' | - |

## RCE_post_snippet_324 (`CommandRateLimiter`)

Own-class comparison: `{"CommandRateLimiter": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | max_calls | positional | int | annotation | True, -1161, 5 | - |
| __init__ | True | period | positional | float | annotation | False, 60.0 | - |
| calls_remaining | True | - | - | - | - | - | - |
| can_call | True | - | - | - | - | - | - |
| time_to_next_call | True | - | - | - | - | - | - |

## RCE_post_snippet_325 (`AgentInfo`)

Own-class comparison: `{"AgentInfo": {"kind": "accessors", "attributes": ["kind", "path"], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: ['kind', 'path'].

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | name | positional | str | annotation |  | - |
| __init__ | True | description | positional | str | annotation |  | - |
| __init__ | True | file_path | positional | none | default **(weak)** | None | - |
| __init__ | True | module | positional | none | default **(weak)** | None | - |
| __init__ | True | yaml_document | positional | none | default **(weak)** | None | - |

## RCE_post_snippet_339 (`MCPConfigGenerator`)

Own-class comparison: `{"MCPConfigGenerator": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | base_dir | positional | str | none | annotation | None | - |
| generate_config | True | config | positional | dict[str, any] | annotation |  | - |
| write_config | True | config | positional | dict[str, any] | annotation |  | - |
| write_config | True | output_path | positional | str | annotation |  | - |

## RCE_post_snippet_340 (`Fix`)

Own-class comparison: `{"Fix": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: ['value']; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | value | positional | bool | p_literals **(weak)** | False | - |
| __repr__ | True | - | - | - | - | - | - |

## RCE_post_snippet_341 (`Free`)

Own-class comparison: `{"Free": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: ['guess']; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | guess | positional | bool | p_literals **(weak)** | False | - |
| __repr__ | True | - | - | - | - | - | - |

## RCE_post_snippet_342 (`Maximize`)

Own-class comparison: `{"Maximize": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: ['guess']; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | guess | positional | bool | p_literals **(weak)** | False | - |
| __repr__ | True | - | - | - | - | - | - |

## RCE_post_snippet_343 (`Minimize`)

Own-class comparison: `{"Minimize": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: ['guess']; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | guess | positional | bool | p_literals **(weak)** | False | - |
| __repr__ | True | - | - | - | - | - | - |

## RCE_post_snippet_346 (`EventDataNormalizer`)

Own-class comparison: `{"EventDataNormalizer": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | - | - | - | - | - | - |
| extract_target_info | True | event_data | positional | dict[str, any] | annotation | {'G@Zr4U': 'G@Zr4U'} | - |
| extract_user_id | True | event_data | positional | dict[str, any] | annotation | {} | - |
| normalize_event_data | True | event_type | positional | str | annotation | {} | - |
| normalize_event_data | True | event_data | positional | dict[str, any] | annotation | {} | - |

## RCE_post_snippet_347 (`MessageBuilder`)

Own-class comparison: `{"MessageBuilder": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | - | - | - | - | - | - |
| build_ark_message | True | ark | positional | dict[str, any] | annotation |  | - |
| build_file_message | True | file_info | positional | dict[str, any] | annotation |  | - |
| build_image_message | True | url | positional | str | annotation |  | - |
| build_keyboard_message | True | content | positional | str | annotation |  | - |
| build_keyboard_message | True | keyboard | positional | dict[str, any] | annotation |  | - |
| build_markdown_message | True | content | positional | str | annotation |  | - |
| build_markdown_message | True | markdown | positional | dict[str, any] | annotation |  | - |
| build_text_message | True | content | positional | str | annotation |  | - |

## RCE_post_snippet_351 (`AgentInfo`)

Own-class comparison: `{"AgentInfo": {"kind": "accessors", "attributes": ["kind", "path"], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: ['kind', 'path'].

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | name | positional | str | annotation |  | - |
| __init__ | True | description | positional | str | annotation |  | - |
| __init__ | True | file_path | positional | none | default **(weak)** | None | - |
| __init__ | True | module | positional | none | default **(weak)** | None | - |
| __init__ | True | yaml_document | positional | none | default **(weak)** | None | - |

## RCE_post_snippet_368 (`PromptCompiler`)

Own-class comparison: `{"PromptCompiler": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | - | - | - | - | - | - |
| compile | True | prompt_file | positional | str | annotation | 'w0a%\nj' | - |
| compile | True | params | positional | dict[str, str] | annotation | 'w0a%\nj' | - |

## RCE_post_snippet_371 (`WorkflowDefinition`)

Own-class comparison: `{"WorkflowDefinition": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | name | positional | str | docstring | {} | - |
| __init__ | True | file_path | positional | str | docstring | {} | - |
| __init__ | True | metadata | positional | dict[any, any] | docstring | {} | - |
| __init__ | True | content | positional | str | docstring | {} | - |
| validate | True | - | - | - | - | - | - |

## RCE_post_snippet_374 (`ChannelIterator`)

Own-class comparison: `{"ChannelIterator": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | num_channels | positional | bool | int | p_literals **(weak)** | True, 0 | - |
| __len__ | True | - | - | - | - | - | - |
| get_channel | True | index | positional | int | bool | p_literals **(weak)** | 2318, True | - |

## RCE_post_snippet_41 (`HeaderManager`)

Own-class comparison: `{"HeaderManager": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | - | - | - | - | - | - |
| create_header | True | plan | positional | str | annotation | 'pro' | - |
| create_header | True | timezone | positional | str | annotation | 'Europe/Warsaw' | - |

## RCE_post_snippet_42 (`ScreenManager`)

Own-class comparison: `{"ScreenManager": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | - | - | - | - | - | - |
| create_full_screen_layout | True | content_sections | positional | list[list[str]] | annotation | '1(xop,nZV.9hzl`' | - |
| set_margins | True | left | positional | int | annotation | 0 | - |
| set_margins | True | right | positional | int | annotation | 0 | - |
| set_margins | True | top | positional | int | annotation | 0 | - |
| set_margins | True | bottom | positional | int | annotation | 0 | - |
| set_screen_dimensions | True | width | positional | int | annotation | 717 | - |
| set_screen_dimensions | True | height | positional | int | annotation | 717 | - |

## RCE_post_snippet_45 (`TokenBucketRateLimiter`)

Own-class comparison: `{"TokenBucketRateLimiter": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | tokens_per_second | positional | int | annotation | True | - |
| __init__ | True | bucket_capacity | positional | int | none | annotation | None | - |
| get_wait_time | True | - | - | - | - | - | - |
| try_consume_token | True | - | - | - | - | - | - |

## RCE_post_snippet_64 (`BaseTool`)

Own-class comparison: `{"BaseTool": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | tool_name | positional | str | docstring | None | - |
| __init__ | True | tool_description | positional | str | docstring | None | - |
| __init__ | True | tool_version | positional | str | docstring | False, None | - |
| __init__ | True | input_types | positional | dict[any, any] | docstring | None | - |
| __init__ | True | output_type | positional | str | docstring | None, False | - |
| __init__ | True | demo_commands | positional | list[any] | docstring | None, False, 4132 | - |
| __init__ | True | output_dir | positional | str | docstring | None, False | - |
| __init__ | True | user_metadata | positional | dict[any, any] | docstring | None, '3Dg=' | - |
| __init__ | True | model_string | positional | str | docstring | None | - |
| execute | True | args | varargs | any | none **(weak)** |  | NotImplementedError |
| execute | True | kwargs | varkw | any | none **(weak)** |  | NotImplementedError |
| get_metadata | True | - | - | - | - | - | - |
| set_custom_output_dir | True | output_dir | positional | str | docstring | None | - |
| set_llm_engine | True | model_string | positional | str | docstring |  | - |
| set_metadata | True | tool_name | positional | str | docstring | '3Dg=' | - |
| set_metadata | True | tool_description | positional | str | docstring | '3Dg=' | - |
| set_metadata | True | tool_version | positional | str | docstring | '3Dg=' | - |
| set_metadata | True | input_types | positional | dict[any, any] | docstring | '3Dg=' | - |
| set_metadata | True | output_type | positional | str | docstring | '3Dg=' | - |
| set_metadata | True | demo_commands | positional | list[any] | docstring | None | - |
| set_metadata | True | user_metadata | positional | dict[any, any] | docstring | None | - |

## RCE_post_snippet_68 (`AgentState`)

Own-class comparison: `{"AgentState": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | initial_state | positional | dict[str, any] | none | annotation | None | - |
| delete | True | key | positional | str | annotation | 'H0}\tO>]a&+vtG^\\', "W.'" | - |
| get | True | key | positional | str | none | annotation | None | - |
| set | False | key | positional | str | annotation |  | ValueError |
| set | False | value | positional | any | annotation |  | ValueError |

## RCE_post_snippet_69 (`CompositeCallbackHandler`)

Own-class comparison: `{"CompositeCallbackHandler": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | handlers | varargs | UNSUPPORTED (annotation Callable) | annotation |  | - |
| __call__ | True | kwargs | varkw | any | annotation |  | - |

## RCE_post_snippet_70 (`PrintingCallbackHandler`)

Own-class comparison: `{"PrintingCallbackHandler": {"kind": "opaque", "attributes": [], "accessors": []}}`; floats rel 1e-09, abs 1e-12; numeric `python_eq`. Documented attributes: -; properties: -.

| callable | generated | parameter | kind | type | source | hints | raises (documented) |
|---|---|---|---|---|---|---|---|
| __init__ | True | - | - | - | - | - | - |
| __call__ | True | kwargs | varkw | any | annotation |  | - |
