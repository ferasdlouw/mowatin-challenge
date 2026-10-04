# Security audit: Muwattin (مُوطِّن), Phase SEC, Stage A

> Read-only audit. No code was changed in Stage A. Every claim below comes from a command, test or file read in the audit session of 2026-10-03.
> Approver: the human running the session (a team engineer).

## 1. Scope, commit, tools

**Commit audited:** `4aea03d` (`PHASE_BASE`). After the audit started, `origin/main` moved to `0f87f8c` ("Update split_testset.py"). That commit changes only `scripts/split_testset.py`, has no secrets (gitleaks over `4aea03d..origin/main`: "no leaks found"), and **turns `main` red**: CI run 37118932966 fails `tests/evaluation/test_run_eval.py::test_id_mapping_matches_both_tools` and `::test_run_files_are_readable_by_split_testset_blind`, because the `blind` subcommand and `SYSTEMS` were removed. That file is not in this phase's allowed paths.

**In scope:** `backend/**`, `frontend/src/**` (sinks, file parsing, storage), `.github/**`, `.claude/**`, `.agent/**`, `render.yaml`, `.env.example`, `.gitignore`, the full git history, and docs where they make security or privacy claims. Out of scope: Render, Cloudflare and provider accounts (read nothing, changed nothing), and `data/testset/test.jsonl` (sealed, never opened).

| Tool | Version | How it ran | Result |
|---|---|---|---|
| gitleaks | 8.30.1 (release zip, scratch dir) | `detect --log-opts="--all"` (133 commits; the clone already holds the full history: `git fetch --unshallow` says "complete repository") and `--no-git` on the tree | history: 1 finding, a known false positive (see D1); tree: 3 hits, all in the git-ignored local `.env` |
| git log grep | n/a | `AIza…`, `sk-or-v1-…`, `sk-…`, `ghp_…`, `github_pat_`, `BEGIN … PRIVATE` over `git log --all -p` | 0 matches each |
| pytest + pytest-cov | 9.0.3 / 6.1.1 | full suite, `--cov=app/pipeline` | 475 passed, 1 xfailed (strict, data fix pending), pipeline coverage 97% |
| ruff | 0.11.12 | `check`, `format --check` | clean |
| bandit | 1.9.1 | `-r app -c pyproject.toml -q` | no issues |
| pip-audit | 2.9.0 | `-r requirements.txt` and `-r requirements-dev.txt` | "No known vulnerabilities found" (both) |
| npm audit | npm 11.16.0 | `--audit-level=high`, `--json` | 5 high, all build-time (see NEW-7) |
| npm audit signatures | npm 11.16.0 | after `npm ci` | exit 0; 34 packages with verified attestations |
| zizmor | 1.16.0 (`uvx`, ephemeral) | `--offline .github/workflows/ci.yml` | 1 high (`unpinned-uses`), 4 medium (`artipacked`), 6 suppressed |
| custom probes | n/a | scratch scripts on a fake LLM router and FastAPI `TestClient`, no network | timings and counts quoted below |
| semgrep | 1.97.0 | `uvx` on Windows | **NOT RUN**: the package fails to build on Windows, and the Docker daemon is not running |
| live LLM red-team | n/a | n/a | **NOT RUN**: no "live red-team go" was given |
| browser CSP check | n/a | n/a | **NOT RUN** in Stage A (planned for Batch 7) |

## 2. Findings

Severity: Critical = a single anonymous request can take the demo down or burn the free quota; High = a safety guard is bypassed or the instance can crash; Medium = a weakness with a realistic path but limited impact; Low = defence in depth or hygiene.

| ID | Sev | Domain | OWASP / ATLAS | Location | Evidence | Impact on Muwattin | Proposed fix | Contract / data / owner impact | Needs human? |
|---|---|---|---|---|---|---|---|---|---|
| F1 | Critical | D3/D2 consumption | API4:2023, LLM10:2025, AML.T0034 | `pipeline/segmenter.py:34`, `pipeline/orchestrator.py:345` | `segment("أ،"*2000)` returns 2000 segments. With a counting fake router, one request makes **4,000 routed calls in `localize` and 6,000 in `compare`**, with the judge unset. With `JUDGE_*` set, that is 3 and 4 calls per segment (6,000 / 8,000), and each call can make 4 HTTP attempts (2 tries × 2 providers). The handler keeps going after the client disconnects. | One 4 KB request can use up every free daily quota (OpenRouter: 50/day), and the live demo then shows "needs review" everywhere until the next day. The 30/min rate limit counts requests, not LLM calls. | Batch 2: `MAX_SEGMENTS`, a per-request LLM call budget, a per-request deadline, and a process-wide daily circuit breaker. Over a limit: no LLM call, `output: null` + a warn flag, one privacy-safe `limit_hit` log line. | Contract-legal (null + flag). New flag key for Rudaina. | Decision D1, D2 |
| NEW-1 | **Critical (not in the prompt)** | D3/D8 availability | API4:2023 | `pipeline/quran.py:116-150` (`find_near`), called from the `async` route `main.py:136` | Any `﴿…﴾` span with no exact match runs a pure-Python edit distance against the 6,236 verses. The prefilter `overlap < len(query_words) // 2` (L131) lets **every verse** through for a one-word query (`1 // 2 == 0`). Measured: `resolve_quran("﴿" + "ب"*L + "﴾")` takes **2.7 s at L=5, 11.4 s at L=10, 29.1 s at L=20**. It runs on the event loop, so all other requests and `/health` wait. | One anonymous request with a few junk "verses" freezes the only Render instance for minutes, with no LLM key involved. The health check fails and Render restarts the service, so the demo goes down while judges are looking. | Batch 2: skip the near-match (→ `quran_not_found`, review) when the query is shorter than a minimum or longer than the longest verse plus slack; require at least one shared word; cap the candidates (top-N by overlap); add a per-request CPU deadline. Prove that dev quran/misquote cases are unchanged. | No contract change. Behaviour change → DECISIONS row. | Decision D3 |
| NEW-2 | High | D3/D8 memory | API4:2023 | `pipeline/cache.py:47` (stores every response), `orchestrator.py:350` | A 2,000-segment `compare` response kept in the cache measured **~2.87 MB** (tracemalloc, 5 entries). The cache holds 1,000 entries, about 2.9 GB, while a Render free instance has 512 MB. | Roughly 150 distinct large requests (5 minutes from one IP at 30/min) can run the instance out of memory, and it then keeps crashing. | Batch 2/5: once F1 is fixed the response stays small (remainder merged, see D2), plus a byte cap on the cache, and nothing degraded is cached (F6). | None | Decision D2 |
| F2 | High | D2 safety integrity | LLM09:2025 (safety control bypass), AML.T0051 | `pipeline/classifier.py:24,28,35` (raw substring match) | Reproduced: `ما حُكم صلاتي؟` (one damma) and `ما حكـــم صلاتي؟` (tatweel) → `term_heavy`/A; `كم زك‍اة مالي؟` (ZWJ) → `general`/B; also `هل يجو​ز لي…؟` (ZWSP) and `ما ح‮كم…` (RLO) → `term_heavy`. Only the plain `ما حكم صلاتي؟` → `fatwa_like`/D. | An ordinary vocalised fatwa question (normal Arabic diacritics, no attacker needed) is translated as plain text: no referral, no level D, no review. This breaks hard rule 2. | Batch 3: one `canonicalize_for_matching()` (drop Unicode Cf chars, tatweel, tashkeel incl. U+0670; unify alef/ya/ta-marbuta), used by fatwa phrases + exclusions, hadith attribution, Quran markers and glossary detection; original spans stay intact. | No contract change. | No |
| F3 | High | D2 safety integrity | LLM09:2025 | `pipeline/classifier.py:51` (`﴿﴾` only), `:54-58` (`«»` + attribution only) | Reproduced: `قال الله تعالى: (وما أرسلناك إلا رحمة للعالمين)` → `term_heavy`/A; `قال رسول الله صلى الله عليه وسلم: النظافة من الإيمان` → `term_heavy`/A. | A verse in plain parentheses is machine-translated, and an unsourced saying is translated fluently with no «ليس بحديث موثق» flag. Both break hard rule 2. | Batch 3 minimum: an attribution formula (canonicalized) without recognised brackets → warn flag + review (segment stays in review even if the LLM translated it; or `output: null`, see D4). Stronger detection (unbracketed text matched against the Tanzil index in `quran.py`) proposed as a DECISIONS row. | New flag key for Rudaina. | Decision D4 |
| F4 | High | D2 prompt injection | LLM01:2025 (direct + indirect), AML.T0051.000/.001 | `localizer.py:87-92`, `verifier.py:185-186, 214, 243`; prompts `localize_v2.txt`, `raw_v2.txt`, `backtranslate_v1.txt`, `judge_v1.txt` | `str.format` inserts user text (and the localizer's output) verbatim. Nothing neutralises `</user_text>`, `</original>` or `</translation>`. The localizer output, which an attacker influences, sits inside the judge prompt's `<translation>`, and the back-translation the score depends on also comes from that output. | A crafted input can close the data tag, add instructions, and push the judge to 1.0 and the back-translation to the original text, so a manipulated translation reaches 1.0 confidence and skips human review. | Batch 4: new prompt versions plus one tag-neutraliser, the rule restated after the data block, and deterministic post-checks (data-block tag or override marker in the output, out-of-range length ratio → review). Tests use fake providers. | No contract change. Old prompt files kept. | No (dev eval re-run is for the human) |
| F5 | Medium | D3 business logic | API6:2023 (sensitive business flow), LLM09 | `orchestrator.py:207-209` | `mode=raw` returns the unprotected LLM translation (verses and fatwa questions included) with `confidence = 1.0` and no flags. | A free general-purpose LLM proxy on the team's keys, and a screenshot risk ("Muwattin translated a verse with AI at 100%"). | Options in D5 (contract-frozen). | `mode` semantics | Decision D5 |
| F6 | Medium | D7 privacy, D3 | — (PDPL: transparency, minimisation) | `cache.py:47`, `orchestrator.py:349-350`; UI `frontend/src/app/TranslateView.jsx:93`, `components/Sections.jsx:321,411`, `Tour.jsx:14`; DECISIONS D-005 | The cache keeps source + output for 1 h. It also caches **degraded** responses (every LLM call failed → `output: null`), so a quota blip serves "review" answers for an hour after recovery. `docs/AI_APPROACH.md` §4 discloses the 1 h cache and the free-tier data use (D-033). The UI says «لا نحفظ نصك» and does **not** say that text is sent to Google/OpenRouter free tiers, where it may be used and read by reviewers. D-005 says "stores nothing". | Users and judges are told something stricter than what happens. A failed quota looks like a broken product for up to an hour. | Batch 5: never cache a response where any LLM call failed or any limit hit; DECISIONS wording for the 1 h in-memory cache. UI disclosure goes to Feras/Rudaina. | UI copy is Feras's lane | Needs a human (UI copy) |
| F7 | Medium | D5 CI | CICD-SEC-4/-8 (OWASP CI/CD Top 10) | `.github/workflows/ci.yml` L30-35, 45, 48, 51, 77, 19/21/59/61/82/84/101/105 | "Validate glossary" (L30) and "Validate test set" (L34) both run `validate_content.py`, so `validate_glossary.py` never runs. No coverage threshold (L45, `--cov=app`). Bandit falls back to a config-less run (L48). `pip-audit … \|\| true` (L51) skips the dev requirements. `npm audit … \|\| true` (L77). Actions are pinned by tag; zizmor: 1 high `unpinned-uses`, 4 `artipacked`. No `concurrency`, no `timeout-minutes`, no `.github/dependabot.yml`. | A vulnerable dependency, a broken glossary or a coverage drop merges with a green tick. | Batch 6 (CI permissions/trigger-adjacent edits need explicit OK). | — | Decision D7 |
| F8 | Medium | D5 agent config | CICD-SEC-3 (dependency chain), AML.T0010 | `.claude/settings.json` (SessionStart / PostToolUse / Stop hooks), `.claude/skills/impeccable/scripts/impeccable:41-196`; `.github/CODEOWNERS` | The hooks run the launcher on every session start and every Edit/Write. The launcher execs `$IMPECCABLE_BIN`, a sibling binary, `~/.impeccable/bin/impeccable`, a cache, or `impeccable` on PATH, and as a last resort downloads `engine-v0.1.9` from `github.com/pbakaus/impeccable` releases. It checks a `.sha256` fetched **from the same release**, which catches corruption but not a compromised release. CODEOWNERS has only `* @ferasdlouw` plus a docs line, nothing for `/.claude/`, `/.agent/`, `/.github/`, `/backend/app/security/`, `/backend/app/prompts/`, `/render.yaml`. `gh api …/branches/main/protection` → 404 (no protection, or no rights to read it). | Once public, a merged PR that edits `.claude/**` runs code on every teammate's machine the next time they open Claude Code in the repo. | Batch 1: CODEOWNERS entries. Option for Feras: make the hooks opt-in (`settings.local.json`) and pin the engine hash in-repo. Do not delete. | Owner: Feras | Decision D8; needs a human (branch protection) |
| F9 | Medium | Process | — | repo root | No `CLAUDE.md`. Claude Code does not auto-load `.agent/rules/muwattin.md`. | Every security rule depends on someone pasting "read the rules first". | Batch 1: `CLAUDE.md` = `@.agent/rules/muwattin.md` + 5 security lines. | — | No |
| F10 | Low | D4 headers | API8:2023 | `security/headers.py:9-13`; `frontend/public/_headers` absent; `frontend/src/lib/extract.js:20` | API responses carry `nosniff`, `no-referrer`, `no-store` (translate) only; no HSTS, CSP, `frame-ancestors`, XFO, CORP. The Pages site has no headers file. pdfjs `getDocument` has no `isEvalSupported: false`. | Clickjacking/framing of the site; less defence in depth if an XSS ever lands. | Batch 7. | Frontend = Feras's lane (approval per file) | Decision D9 |
| F11 | Low | Process / config | — | repo root; `render.yaml:22-49` | No `SECURITY.md`. `render.yaml` lists neither `LLM_BILLING` nor `LLM_/FALLBACK_/JUDGE_BASE_URL`. | Researchers have no private channel once the repo is public; cost logs say "paid" on Render unless someone remembers the variable. | Batch 1 (`SECURITY.md`), Batch 2 (`render.yaml` names with the new limit vars). | — | Needs a human (enable private vulnerability reporting) |
| NEW-3 | Low | D3/D8 CPU | API4:2023 | `glossary.py:34-79`, `classifier.py:12-20,41-44` | `glossary.detect` on one 4,000-char segment of short tokens takes **546 ms**, `classify` 491 ms (several calls per segment, all on the event loop). `segment("أ."*2000)` takes 0.92 s, because `is_fatwa_like` re-reads `fatwa_signals.json` per sentence. All regexes pass the 200 ms ReDoS bound (worst `find_whole_word` 0 ms, Dice 2 ms). | Adds seconds of loop blocking per large request; secondary to NEW-1. | Batch 2: load signals once (cached); the per-request deadline covers the rest. | — | No |
| NEW-4 | Low | D3 rate limit | API4:2023 | `security/client_ip.py:31-38`, `rate_limit.py:51-58` | Forged left XFF entries are ignored (probe: `[200,200,200,429,429]`). One key per IPv6 /64, so a client holding a /48 rotates through 65k keys; when 10k keys are active, **new** clients get 429. | Only an attacker with IPv6 ranges; the limit is per request anyway (F1 is the real bound). | Accept; the F1 daily breaker bounds the damage. Document it in the threat model. | — | No |
| NEW-5 | Low | D1 public history | — | git metadata | 4 personal (non-noreply) author emails in 63 commits. | They become public with the repo. History must not be rewritten (rules). | None in code. Teammates may switch to GitHub noreply emails for future commits. | — | Needs a human (awareness) |
| NEW-6 | Low | D6/D7 | — | `security/privacy.py:10-13`, `llm/router.py:194-197` | Logs carry an unsalted 12-hex SHA-256 prefix of the text/prompt (correlation only, not used for security). A short common text ("ما حكم صلاتي؟") can be confirmed by hashing guesses. | Someone with log access could confirm a guessed short input. | Accept and document (logs are only on Render). | — | No |
| NEW-7 | Low | D5 deps | — | `frontend/package.json` (`tailwindcss ^3.4.19`) | `npm audit`: 5 high, all build-time (`braces` via `micromatch`/`chokidar`/`fast-glob` ← tailwindcss 3). None reach the browser bundle. The fix is tailwindcss 4 (major). | None at runtime; it blocks making `npm audit` a real gate. | Batch 6: gate on `npm audit --omit=dev --audit-level=high`, and record the dev-only advisory in `docs/security/SUPPRESSIONS.md`; tailwind 4 is a Feras decision. | Dependency change = Feras | Decision D7 |
| NEW-8 | Low | D5 deps | CICD-SEC-3 | `render.yaml:17`, `backend/requirements.txt` | Direct deps pinned with `==`, transitive deps resolved at build time, no `--require-hashes`. | A compromised transitive release would reach the next Render build. | Accept for the competition; Dependabot (Batch 6) shows drift. | — | No |

## 3. PASS list (checked and right)

**D1 secrets**
- Full-history gitleaks: one hit, `generic-api-key` in `docs/dev/PROGRESS.md` at `5353092` L139. That line is prose (a list of test names for the local keyless server and HTTP error cases), was reworded in `7ce3061`, and is not a secret.
- No key pattern in history (0 matches each for AIza, sk-or-v1, sk-, ghp_, github_pat_, private-key blocks).
- The only `.env*` file ever added is `.env.example`. `.env` / `.env.*` are git-ignored (`.gitignore:2`).
- `.env.example` holds only names, non-secret defaults and comments.
- Keys travel only in headers: Gemini `x-goog-api-key` (`gemini.py:35`), Bearer for OpenRouter/openai_compat (`openrouter.py`, `openai_compat.py`). `ProviderError` messages hold only kind + status (`llm/errors.py`). `openai_compat` rejects credentials/query in the base URL, and its config errors name the variable, never the value.

**D2 LLM**
- LLM07: prompt templates hold no secrets, keys or internal URLs (all 6 files read).
- LLM05: every LLM reply is validated against a Pydantic schema (`router._parse`). Output is rendered as React text (no `dangerouslySetInnerHTML` in `frontend/src`). `highlight()` regex-escapes every needle (`ui.jsx:62`). `find_whole_word` uses `re.escape`. LLM output never builds a path.
- `str.format` gets user text only as a field value, never as the format string, so `{…}` in user text is inert.
- Quran output in `localize` mode never comes from an LLM (`orchestrator._quran`); a fabricated hadith is never sent to the LLM (`_hadith`).

**D3 API**
- `TranslateRequest` has `extra="forbid"` (probe: extra field → 400). Responses match §4.
- `/docs`, `/redoc`, `/openapi.json`, `/DOCS` → 404 with `ENV=Production`.
- 404/405 bodies are the generic Arabic error with no stack or provider detail. An unhandled error logs only type + frames (`errors.py:133`).
- Body cap: declared 25,024+ bytes → 413; chunked → 413; text > 4000 → 413 (all with `no-store`).
- Rate-limit bypass attempts fail: forged left XFF, `/v1/translate/` (307, counted), `/v1/%74ranslate` (counted), `?x=1`, `/v1/./translate` (counted). `/V1/…`, `//v1/…`, `/v1//…` → 404 (no handler reached). OPTIONS is exempt but only answers CORS.
- 429 carries `Retry-After`, CORS and `no-store`.
- Cache key = SHA-256 over JSON of (text, lang, audience, mode), so no cross-user collision or poisoning.
- `/v1/glossary?q=` > 200 chars is rejected (validation).

**D4 web**
- CORS: allowed `https://mowatin.pages.dev` and `https://abc.mowatin.pages.dev`. Refused with 400 and no ACAO: `x.mowatin.pages.dev.evil.com`, `evil-mowatin.pages.dev`, `http://` scheme, uppercase host, `:8443`, `null`, `a.b.mowatin.pages.dev`. Credentials off.
- No `innerHTML`, `eval`, `postMessage` or `window.open` in `frontend/src`. The one external link uses `rel="noopener noreferrer"`.
- CSV export defuses formula injection (`ReviewView.jsx`, leading `= + - @`).
- `localStorage` holds UI prefs only (`mowatin.lang`, `mowatin.tour.v2`).
- File parsing is client-side: 10 MB cap, PDF ≤ 40 pages, mammoth `extractRawText` (no HTML).

**D5 supply chain**
- `pip-audit` clean on both requirement files.
- The npm lockfile resolves 183/183 packages from `registry.npmjs.org` with sha512 integrity; `npm audit signatures` exit 0.
- Workflow already has top-level `permissions: contents: read`, no `pull_request_target`, and no `${{ github.event.* }}` in `run:`.
- Direct-dependency names checked by hand against the canonical projects (fastapi, starlette, uvicorn, pydantic, pydantic-settings, httpx, pytest*, respx, ruff, bandit, pip-audit, react, react-dom, mammoth, pdfjs-dist, lucide-react, @fontsource/*, vite, @vitejs/plugin-react, tailwindcss, postcss, autoprefixer, oxlint): no typosquats, and no internal package names that could be confused with a public one.

**D6 code**
- bandit clean; ruff clean.
- ReDoS: every regex in `backend/app/**` stays under 200 ms on 4,000-char worst cases (the slow paths are algorithmic, NEW-1/NEW-3, not regex).
- Every file read uses a fixed path under `data/` or `prompts/`; none takes request input.
- SHA-256 prefixes are for correlation only (privacy.py, router.py, cache key), never for authentication.
- `openai_compat` base URL is env-only, so SSRF is not user-reachable.

**D7 privacy**
- Every log call in `backend/app` (11 sites) logs counters, fingerprints, path (no query), or slot status; none logs user text, LLM output, IP or keys. Tests: `backend/tests/security/test_privacy_logs.py`. The uvicorn access log is off (`render.yaml:20`).

**D8 operations**
- `request_cost` (`llm_failed`, `llm_completions`), `http_request` (status 429) and `llm_failover` lines are enough to see an attack without user text.
- Rollback: `git revert` + push works from the agent side (DEPLOY §7).

**D9 threat model**
- Done as a working model in this audit (summary below). It becomes `docs/security/THREAT_MODEL.md` in Stage C.
  Browser → Pages (static) → Render API (trust boundary 1: anonymous internet input) → pipeline (data files trusted, user text untrusted) → LLM providers (boundary 2: third-party processing; their output is untrusted on the way back, boundary 3).
  STRIDE:
  - Spoofing: n/a (no auth).
  - Tampering: F4 injection (AML.T0051).
  - Repudiation: logs without text.
  - Information disclosure: F6, provider data use.
  - DoS: F1, NEW-1, NEW-2, NEW-3 (AML.T0034 cost harvesting).
  - Elevation: F8 agent hooks.

## 4. Remediation plan (batches; each batch = failing test first, smallest fix, full suite green)

**Blocker before any Stage B commit:** `main` is red because of `0f87f8c` (`scripts/split_testset.py`). Rules §2 forbid starting on a red `main`, and the file is outside this phase's allowed paths. Its author must fix or revert it, or the human must allow me to revert it.

| Batch | Findings | Files | Tests (new) | Decisions |
|---|---|---|---|---|
| 1 — before public | D1 result, F9, F11, F8 (CODEOWNERS) | `CLAUDE.md`, `SECURITY.md`, `.github/CODEOWNERS` | — (docs) | D8 (hooks) |
| 2 — consumption | F1, NEW-1, NEW-2 (size), NEW-3, F11 (`render.yaml`) | `app/config.py`, `app/pipeline/orchestrator.py`, new `app/pipeline/budget.py`, `app/pipeline/quran.py`, `app/pipeline/classifier.py`, `.env.example`, `render.yaml`, `docs/DECISIONS.md` | `tests/security/test_consumption.py`: 2000-segment input ≤ budget calls (fake provider), deadline, daily breaker, `limit_hit` log has no text; `test_quran_near_cpu.py`: junk `﴿…﴾` < 200 ms, dev misquote cases unchanged | D1, D2, D3 |
| 3 — guard integrity | F2, F3 | `app/pipeline/normalize.py`, `classifier.py`, `hadith.py`, `quran.py` (marker check), `glossary.py`, `orchestrator.py`, `docs/DECISIONS.md` | `tests/security/test_canonical_guards.py`: tashkeel/tatweel/Cf variants → `fatwa_like`; unbracketed attribution → review flag; dev category counts before/after (now: term_heavy 30, general 8, quran 9, hadith 7, fatwa_like 2 over 56 segments) | D4 |
| 4 — injection | F4 | new `prompts/localize_v3.txt`, `raw_v3.txt`, `backtranslate_v2.txt`, `judge_v2.txt`; new `app/pipeline/injection.py`; `localizer.py`, `verifier.py` | `tests/security/test_prompt_injection.py`: tag breakout, AR+EN override, judge manipulation, zero-width smuggling; neutraliser unit tests; length-ratio bounds from dev (reported) | — |
| 5 — logic + privacy | F5, F6, NEW-2 (cache) | `orchestrator.py`, `cache.py`, `docs/DECISIONS.md`, `docs/AI_APPROACH.md` (wording only, approval) | degraded response not cached; cache byte cap; raw per D5 | D5, D6 |
| 6 — CI | F7, NEW-7 | `.github/workflows/ci.yml`, new `.github/dependabot.yml`, `docs/security/SUPPRESSIONS.md` | CI itself + invariant test `ci.yml` has no `\|\| true`, every `uses:` is a 40-char SHA | D7 |
| 7 — headers | F10 | `app/security/headers.py`; with approval `frontend/public/_headers`, `frontend/src/lib/extract.js` | `tests/security/test_headers_and_docs.py` additions; CORS still works; browser CSP check on built `dist/` | D9 |
| Stage C | prevention | `docs/security/THREAT_MODEL.md`, `SECURE_CHANGE_CHECKLIST.md`, `.agent/rules/muwattin.md` §6 (approval), `tests/security/test_invariants.py`, `scripts/security_smoke.sh`, DEPLOY §3, PR template | invariants | — |

### Decisions needed (my recommendation first)
- **D1, `MAX_SEGMENTS` default.** The prompt's rule (largest dev segment count × 2) gives **3 × 2 = 6**. Demo examples have at most 3 segments. A real 4,000-char khutbah has roughly 30–60 segments, so 6 would leave most of an uploaded document untranslated (in review).
  - (a) **Recommended: 6**, as the rule says, with the env var documented so the team can raise it on Render once the paid tier or quota allows.
  - (b) 30.

  Also: per-request LLM budget = `MAX_SEGMENTS × 4 + 4` (28 at 6); deadline 90 s; daily breaker `LLM_DAILY_CALL_BUDGET` = 1,000 routed calls (resets at 00:00 UTC, in memory).
- **D2, what happens to segments past the cap.**
  - (a) **Recommended:** the remainder becomes **one** final segment (`source` = the rest of the text, `output: null`, warn flag `limit_reached`, review). Contract-legal, keeps the response and cache entry small (fixes NEW-2), no LLM call.
  - (b) Each remaining segment is returned null + flag (2,000 objects, NEW-2 stays).
  - (c) 413 when over the cap (status-code semantics change → contract).
- **D3, Quran near-match bounds.** **Recommended:** run `find_near` only when the normalised query is 8 or more chars and at most 1.3 × the longest verse, the candidate verse shares at least 1 word and at least 50% of the query words (ceil), and candidates are capped at the 20 highest-overlap verses. Otherwise → `quran_not_found` + review. This is a DECISIONS row; dev misquote cases must stay `quran_mismatch`.
- **D4, F3 fail-safe.**
  - (a) **Recommended:** attribution formula (`قال الله`, `قال تعالى`, `قال رسول الله`, `قال النبي`, `صلى الله عليه وسلم`, `ﷺ`, canonicalized) without `﴿﴾`/`«»` → **no LLM call, `output: null`**, warn flag `scripture_unbracketed`, review. It matches how an unsourced hadith is treated today.
  - (b) Translate but add the warn flag.

  Separately, a DECISIONS proposal: match unbracketed spans against the Tanzil index (later phase).
- **D5, `mode=raw`.**
  - (a) **Recommended:** keep the LLM translation but `confidence = 0.0` and a warn flag `raw_unprotected` (so the segment is always in review), and count raw calls in the F1 budget. Contract-legal, and the eval baseline metric reads `output` only.
  - (b) `raw` only when `ENV != production` (400 in production; `mode` semantics change → contract).
  - (c) Leave as is.
- **D6, cache.** **Recommended:** keep LRU 1,000 × 1 h but never cache a response with any failed LLM call or limit hit, and cap the cache at 64 MB of response JSON. DECISIONS row amends D-005 wording to "stores nothing on disk; an in-memory 1 h response cache, lost on restart".
- **D7, CI gates.**
  - (a) **Recommended:** `npm audit --omit=dev --audit-level=high` as the gate, with the tailwind-3 dev advisory in `SUPPRESSIONS.md` (needs your OK), plus `pip-audit` on both requirement files with no `|| true`, bandit without fallback, `--cov=app/pipeline --cov-fail-under=85`, the real `validate_glossary.py --min-approved 100` step, SHA pins, `persist-credentials: false`, `concurrency`, `timeout-minutes`.
  - (b) Upgrade tailwind to 4 (Feras, dependency change).

  This needs explicit approval for CI edits (rules §1.7). Triggers stay unchanged.
- **D8, impeccable hooks (Feras).**
  - (a) **Recommended:** CODEOWNERS now, plus a branch ruleset (human); Feras decides later whether hooks move to `settings.local.json` (opt-in).
  - (b) Opt-in now (edit `.claude/**`, needs Feras's OK).
- **D9, frontend files.** Approve `frontend/public/_headers` (new) and `frontend/src/lib/extract.js` (`isEvalSupported: false` only), Feras's lane. Also approve the append to `.agent/rules/muwattin.md` (Stage C) and the wording fix in `docs/AI_APPROACH.md`.

### New Arabic message keys (for Eng. Rudaina, `data/messages/flags.ar.json`; code falls back to the generic flag text until added)
- `limit_reached`: «لم يُترجَم باقي النص لأنه تجاوز الحد المسموح للطلب الواحد؛ قسّمه وأعد الإرسال.»
- `scripture_unbracketed`: «يبدو أن المقطع ينسب نصًا إلى الله أو إلى النبي ﷺ دون علامات الاقتباس المعتمدة؛ لم يُترجَم آليًا ويحتاج مراجعة.»
- `injection_suspected`: «في الترجمة ما يشبه تعليمات أو وسومًا ليست من النص؛ تحتاج مراجعة.»
- `raw_unprotected`: «ترجمة آلية مباشرة بلا حماية مُوطِّن؛ للمقارنة فقط.»

## 5. Needs a human (accounts and settings; the agent never touches them)
1. **`main` is red** (`0f87f8c`): fix or revert before Stage B.
2. GitHub: enable secret scanning + push protection, private vulnerability reporting, Dependabot alerts; add a branch ruleset on `main` (require CI; CODEOWNERS review for the paths above if agents' direct pushes are moved to a bypass list).
3. AI Studio: restrict the key to the Generative Language API. OpenRouter: set the key's credit limit to $0.
4. Render: set the new env vars from Batch 2 (`MAX_SEGMENTS`, `LLM_CALL_BUDGET`, `REQUEST_DEADLINE_S`, `LLM_DAILY_CALL_BUDGET`) and `LLM_BILLING=free`.
5. Cloudflare Pages: deploy `_headers`, then verify the CSP on the preview URL if the local browser check cannot run.
6. After each deploy: run `scripts/security_smoke.sh $API`.
7. Re-run the dev eval with the v3 prompts (quota: `--delay 12`, team's day).
8. UI copy (Feras/Rudaina): «لا نحفظ نصك» → disclose the 1 h in-memory cache and that text goes to Google/OpenRouter free tiers (D-033).
9. Teammates: consider GitHub noreply emails for future commits (NEW-5).

## 6. Status after remediation (Phase SEC, 2026-10-03)
All decisions D1–D9 were approved by the session's human with the recommended options.

| ID | Status | Fix | Regression tests |
|---|---|---|---|
| F1 | Closed | D-034 budgets (`app/pipeline/budget.py`) | `tests/security/test_consumption.py` |
| NEW-1 | Closed | D-035 bounded `find_near` (29 s → ~0.15 s worst) | `test_consumption.py::test_quran_near_match_is_cpu_bounded` |
| NEW-2 | Closed | merged remainder (D-034) + 64 MB cache cap (D-039) | `test_consumption.py::test_large_response_stays_small_for_the_cache`, `test_raw_and_cache.py::test_cache_is_bounded_by_bytes` |
| F2 | Closed | D-036 `canonicalize_for_matching()` | `tests/security/test_canonical_guards.py` |
| F3 | Closed | D-036 unbracketed attribution → handler, no LLM; D-041 the attributed verse is matched word for word in Tanzil and gets the approved translation, anything else stays null + review | `test_canonical_guards.py::test_unbracketed_verse_gets_the_approved_translation`, `::test_unbracketed_match_respects_word_boundaries`, `::test_unbracketed_verse_is_never_sent_to_the_llm` |
| F4 | Closed | D-037 prompts v3/v2, `neutralize_tags()`, post-checks | `tests/security/test_prompt_injection.py` |
| F5 | Closed | D-038 raw confidence 0 + warn | `tests/security/test_raw_and_cache.py` |
| F6 | Closed | D-039 no degraded cache entries; AI_APPROACH wording; UI disclosure placed by Feras (`c664499`) | `test_raw_and_cache.py` |
| F7 | Closed | `ci.yml` gates, SHA pins, Dependabot | `tests/security/test_invariants.py::test_ci_*` |
| F8 | Closed in the repo; ruleset open | CODEOWNERS (multi-path line fixed); both Impeccable launchers refuse an engine download whose SHA-256 is not in the committed `engine-0.1.9.sha256` (D-042), so a replaced release asset never runs. Hooks stay on (Feras's workflow). The `main` ruleset that makes CODEOWNERS binding is a human task | launchers run against the real release: wrong pin → exit 127, nothing cached; right pin → runs (sh and cmd) |
| F9, F11 | Closed | `CLAUDE.md`, `SECURITY.md`, `render.yaml` names | `tests/security/test_deploy_config.py` |
| F10 | Closed | API headers, `_headers` (live on `mowatin.pages.dev`: CSP, HSTS, XFO checked with curl 2026-10-03), pdf.js `isEvalSupported: false`. `connect-src` narrows to the exact API origin once the API is deployed | `tests/security/test_headers_and_docs.py` |
| NEW-3 | Closed | fatwa signals read once (segmenter 0.92 s → 0.33 s on 2,000 sentences) | — |
| NEW-4 | Closed | an IPv6 /48 also has a limit, 4× the per-client one, checked first (D-042); a /48 adds at most 120 keys a minute | `test_rate_limit.py::test_one_ipv6_site_cannot_rotate_past_the_limit`, `::test_ipv4_clients_are_not_grouped` |
| NEW-6 | Closed | log hashes are HMAC-SHA-256 under a random per-process key (D-042) | `test_privacy_logs.py::test_fingerprint_cannot_be_confirmed_by_hashing_a_guess`, `tests/llm/test_usage_log.py` |
| NEW-8 | Closed | `backend/requirements.lock`: all 25 runtime packages pinned with hashes; Render and CI install it with `--require-hashes`; pip-audit reads it (D-042) | `test_deploy_config.py::test_render_installs_every_package_from_the_hash_lock`, `::test_lock_pins_and_hashes_every_package`, `::test_lock_matches_the_direct_pins` |
| NEW-5 | Accepted | history is never rewritten (rules); teammates can use GitHub noreply addresses for new commits | — |
| NEW-7 | Suppressed (dev-only) | `docs/security/SUPPRESSIONS.md`; Dependabot #57 (tailwindcss 4) breaks the build and is deferred by the team to after 2026-10-22 | CI `npm audit --omit=dev` |

Flag keys: `scripture_unbracketed` was not needed. The unbracketed case reuses `quran_not_found` / `hadith_unsourced`, whose texts already say what happened. `limit_reached`, `injection_suspected` and `raw_unprotected` are in `flags.ar.json` since `143914c`.

Still open, all outside the repository (§5): GitHub settings and the `main` ruleset, AI Studio / OpenRouter key limits, Render variables and the first deploy + `security_smoke.sh`, `connect-src` once the API URL exists, the dev eval re-run with the new prompts.

Bare verses (no formula, no brackets): D-043, tests `test_canonical_guards.py::test_bare_verse_*`, `::test_ordinary_sentence_is_not_taken_for_a_verse`.
