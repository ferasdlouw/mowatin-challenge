# Backend build plan (master spec)

> Read with `.agent/rules/muwattin.md` (rules + phase protocol) and `docs/dev/PROGRESS.md` (state).
> Each conversation implements ONE phase section below. Only the "Allowed paths" of that phase may change.

## Product in one paragraph
Muwattin is a protection layer on top of machine translation for Arabic Islamic (dawah) content → English and French: "translation tools translate words; Muwattin protects meaning". Per segment it:
- locks Sharia terms to the team glossary;
- inserts approved Quran translations instead of generating them;
- never presents an unsourced hadith as authentic;
- refuses personal rulings and refers them;
- verifies the output and scores confidence (from 0 to 1); anything doubtful enters the human `review_queue`.

## Judging weights (optimize for these)
| Weight | Criterion | What it means for the build |
|---|---|---|
| 25% | Technical quality / real use of AI | Clean pipeline; LLM where it adds value; deterministic checks where it does not |
| 20% | Benefit per track standard | Measured gain vs the SAME LLM without Muwattin |
| 15% | Scientific reliability and safety | Quran integrity, hadith attribution, fatwa referral, no hallucinated claims |
| 15% | Innovation | |
| 10% | UX and accessibility | |
| 10% | Operational realism | Cost per request, fallback provider, uptime through Oct 7–22 |
| 5% | Clarity / verifiability | A judge can rerun tests and the evaluation from the README |

## Must-read files
1. `docs/ARCHITECTURE.md` (pipeline, binding rules §3, contract §4)
2. `docs/EVALUATION.md`
3. `data/glossary/SCHEMA.md` and one glossary file (via `jq`)
4. `data/testset/SCHEMA.md` and `dev.jsonl`
5. `frontend/src/lib/api.js` (the client: `normalize()`, `needsReview()`, error messages)
6. `frontend/src/data/examples.js` (exact response shapes, levels, flag tone)
7. `eval/results/SCHEMA.md`
8. `scripts/split_testset.py`
9. `CONTRIBUTING.md`
10. `.env.example`

## Data slots awaiting Eng. Rudaina
The slots ALREADY EXIST with fixed schemas: see `data/CONTENT_SLOTS.md` (schemas + examples) and `scripts/validate_content.py` (validator). Do NOT change file names, keys or schemas; build loaders against them exactly, with a safe default while `status` is `placeholder`. Do NOT invent content. Tests use fixtures, never the placeholder files. Slots: `data/quran/translations/{en,fr}.json`, `data/hadith/{hadith,fabricated}.json`, `data/policy/{fatwa_signals,referral}.json`, `data/messages/flags.ar.json` (keys + `{placeholders}` are a contract), `data/demo/examples.json`.
1. Quran translations EN/FR
2. Hadith list + fabricated sayings
3. Fatwa phrases + referral text + referral bodies
4. Final Arabic flag messages
5. Demo examples

## Approved dependencies
- **Backend:** fastapi, uvicorn[standard], pydantic, pydantic-settings, httpx
- **Backend dev:** pytest, pytest-cov, pytest-asyncio, respx, ruff, bandit, pip-audit
- **CI:** gitleaks action

Anything else: ask first.

---

## Phase 0 — Plan and decisions (no code, no commit)
- **Deliver an artifact** with: the file tree for all phases; data-slot schemas (JSON examples); a provider proposal; the confidence formula; the partial-verse policy; the review-flow decision; risks; and questions for Mohammed.
- **Provider proposal:**
  - Primary: Gemini API via Google AI Studio free tier.
  - Fallback: a different company.
  - Judge: a different model from the localizer.
  - Check that the free quota covers dev + eval (~150 cases × 2 langs × 3 runs × 2 systems) + judging Oct 7–22. Show the arithmetic.
- **Env names:** `LLM_PROVIDER/LLM_API_KEY/LLM_MODEL`, `FALLBACK_*`, `JUDGE_*`, `ALLOWED_ORIGINS`, `RATE_LIMIT_PER_MIN`, `MAX_TEXT_CHARS`, `ENV`, `GT_API_KEY` (optional).
- **Allowed paths:** none (artifact only). PROGRESS.md is updated in Phase 1's commit with the approved decisions.
- **Done when:** Mohammed replies "approved" with any edits.

## Phase 1 — Backend skeleton + CI
- **Deliverables:**
  - `backend/` with:
    - `app/main.py` (app factory, routers)
    - `app/config.py` (pydantic-settings; fail fast on missing required vars)
    - `app/schemas.py` (mirrors contract §4 exactly)
    - `app/errors.py` (exception → HTTP mapping: 400, 413, 429, 5xx with a generic Arabic message, no stack traces or provider text)
  - Routes:
    - `POST /v1/translate`: for now returns a valid contract-shaped response built by a stub orchestrator, documented as a stub.
    - `GET /v1/glossary?q=`
    - `GET /health`: no LLM call; returns status + counts, no secrets.
  - Packaging: pinned `requirements.txt` + `requirements-dev.txt`, `pyproject.toml` (ruff, pytest config), `render.yaml`.
  - `.github/workflows/ci.yml` on push to `main` (and on pull_request, harmless if unused):
    - glossary validator, dev testset validate, `python3 scripts/validate_content.py`
    - ruff, pytest, bandit, pip-audit
    - frontend `npm ci/lint/build/audit`
    - gitleaks
    - least-privilege `permissions: contents: read`
  - `.env.example`: names only.
  - Contract tests: request validation (lengths, enums, extra fields rejected), 413 on more than 4000 chars, response schema round-trip against the example in `docs/ARCHITECTURE.md`.
- **Allowed paths:** `backend/**`, `render.yaml`, `.github/workflows/**`, `.env.example`, `docs/dev/PROGRESS.md`, `docs/DECISIONS.md` (append rows only).
- **Done when:** local suite and GitHub CI are green; `curl localhost:8000/health` works; a translate stub response passes the frontend's `normalize()` shape.

## Phase 2a — Normalization + glossary detection
- **Deliverables:**
  - `app/pipeline/normalize.py`: strip tashkeel and tatweel, unify أإآ→ا, ة→ه, ى→ي. Tokenize with attached-prefix handling (و ف ب ل ك ال and combinations, e.g. «والتقوى», «بالصبر»).
  - `app/pipeline/glossary.py`: load once, index `ar` + `variants_ar`. Longest match wins; no overlaps. Return glossary ids + spans.
  - Explicit, documented exclusion so «المسلم/المسلمين/المسلمون» are NOT locked to `islam` (data issue reported to Rudaina).
  - 25 or more detection tests drawn from dev cases (`expect.terms`).
- **Allowed paths:** `backend/app/pipeline/normalize.py`, `backend/app/pipeline/glossary.py`, `backend/app/pipeline/__init__.py`, `backend/tests/**`, `docs/dev/PROGRESS.md`, `docs/DECISIONS.md`.
- **Done when:** detection recall on dev `expect.terms` is 95% or more with zero false locks on the exclusion list. Report the number.

## Phase 2b — Segmenter + classifier
- **Deliverables:**
  - `segmenter.py`: sentence/clause split that keeps ﴿…﴾ and «…» spans intact.
  - `classifier.py` (rule-based):
    - `quran` if it contains ﴿…﴾
    - `hadith` if it contains «…» plus an attribution (قال رسول الله / النبي / ﷺ)
    - `fatwa_like` if it has personal-ruling signals (هل يجوز لي، ما حكم، هل يحل، هل علي، في حالتي، "أنا …" + question; extendable from the `data/policy/` slot)
    - `term_heavy` if glossary terms are present
    - `general` otherwise
  - Levels follow `frontend/src/data/examples.js`: A = established content, C = unverified hadith attribution, D = personal ruling.
- **Tests** cover every dev category, including the 3 over-referral cases (T097, T100, T148 must NOT be `fatwa_like`).
- **Allowed paths:** `backend/app/pipeline/segmenter.py`, `backend/app/pipeline/classifier.py`, `backend/tests/**`, `docs/dev/PROGRESS.md`, `docs/DECISIONS.md`.
- **Done when:** dev classification matches category for 100% of `quran*`, `hadith*` and `level_d` cases, and over-referral cases are not `fatwa_like`.

## Phase 2c — Quran resolver
- **Deliverables:**
  - Download the official Tanzil Arabic text once (ask before the download) into `data/quran/tanzil/`, unmodified, with attribution per CC BY 3.0. Add the attribution to `THIRD_PARTY_NOTICES.md`.
  - Translation slot `data/quran/translations/{en,fr}.json` already exists (schema in `data/CONTENT_SLOTS.md` §1): load it; while `status` is `placeholder` or the verse is missing, return `output: null` + the `quran_translation_pending` message.
  - `quran.py`:
    - normalized substring match against a verse or a consecutive range
    - exact match → `sources[{kind:"quran", ref, edition}]` + approved translation
    - placeholder translation → `output: null` + info flag
    - no exact match → near-match search (normalized edit distance over candidates):
      - close → `output: null` + block flag naming the correct verse and ref + review
      - nothing close → warn + review
    - ambiguous → deterministic pick + all refs listed + info flag
    - partial-verse policy from Phase 0
    - the LLM is never called here
- **Tests:** all dev `quran_quote` and `quran_misquote` cases, using a fixture translation file.
- **Allowed paths:** `backend/app/pipeline/quran.py`, `data/quran/tanzil/**` (never `data/quran/translations/**`), `THIRD_PARTY_NOTICES.md`, `backend/tests/**`, `docs/dev/PROGRESS.md`, `docs/DECISIONS.md`.
- **Done when:** 100% correct refs on dev `quran_quote`; 100% of dev `quran_misquote` blocked with the correct verse named.

## Phase 2d — Hadith handler + fatwa guard + report
- **Deliverables:**
  - Use the existing slots (`data/CONTENT_SLOTS.md` §2–§4) and messages from `data/messages/flags.ar.json` by key, filling `{placeholders}`.
  - `hadith.py`: matched → sources with collection, number and grade, and the LLM may translate the meaning. Unmatched or fabricated → `output: null` + warn/block + review. Empty slot → every hadith goes to review.
  - `fatwa_guard.py`: never a ruling. The question itself may be translated faithfully; level D; warn flag with the referral text; always in review.
  - `report.py`: `review_queue` = confidence below 0.75 OR any warn/block flag (identical to `needsReview` in `api.js`); `summary`; the fixed `disclosure` string.
  - Orchestrator wires 2a–2d deterministically (LLM paths stubbed until Phase 3).
- **Allowed paths:** `backend/app/pipeline/{hadith,fatwa_guard,report,orchestrator}.py`, `backend/app/main.py` (wiring only), `backend/tests/**`, `docs/dev/PROGRESS.md`, `docs/DECISIONS.md`.
- **Done when:** 100% of dev `hadith_unsourced` and `level_d` cases end in review with the correct flags; `must_refer=false` cases are not referred by the guard.

## Phase 3a — LLM provider layer
- **Deliverables:** `backend/app/llm/`:
  - `base.py`: protocol with a `complete_json(prompt, schema)` style API.
  - Providers via httpx: Gemini + the fallback provider chosen in Phase 0.
  - `router.py`: timeout, 1 retry with backoff, automatic failover recorded as an info flag and in a structured log.
  - Low temperature, fixed seed where supported. JSON output validated by Pydantic: invalid → retry once → fail safe (`output: null` + review), never crash.
  - Usage accounting: tokens and estimated cost per call, logged without user text.
- **Tests:** respx-mocked HTTP for success, timeout, 429, 5xx, invalid JSON and failover.
- **Allowed paths:** `backend/app/llm/**`, `backend/app/config.py`, `.env.example`, `backend/requirements*.txt` (approved deps only), `backend/tests/**`, `docs/dev/PROGRESS.md`, `docs/DECISIONS.md`.
- **Done when:** all provider tests pass with no network; one manual smoke call with Mohammed's local key succeeds (Mohammed runs it; the key never appears in output).

## Phase 3b — Localizer + term lock + raw mode
- **Deliverables:**
  - `localizer.py`: translate `general` and `term_heavy` segments with term lock per `strategy`:
    - `keep_and_gloss`: romanized term + short gloss on first use
    - `translate`: `preferred`
    - `context`: choose, with the `avoid` list enforced
  - Audience adaptation without changing meaning.
  - Prompt templates in `backend/app/prompts/` (versioned), with user text delimited as data.
  - `mode=raw`: same LLM, plain translation, no glossary, no verse or hadith handling, no verification. This is the fair baseline.
  - Orchestrator wires `localize` and `raw` end to end through `POST /v1/translate`.
- **Allowed paths:** `backend/app/pipeline/{localizer,orchestrator}.py`, `backend/app/prompts/**`, `backend/app/main.py` (wiring only), `backend/tests/**`, `docs/dev/PROGRESS.md`, `docs/DECISIONS.md`.
- **Done when:** fake-LLM tests prove locked renderings are requested in the prompt; a manual dev smoke run (5 cases, Mohammed's key) returns contract-valid responses.

## Phase 3c — Verifier + compare + cost
- **Deliverables:**
  - `verifier.py`, combined into `confidence` with the documented formula; a deterministic term failure caps confidence below 0.75. Three checks:
    - (a) deterministic term check: required rendering present, no `avoid` word; fills `marks` with the exact rendered strings
    - (b) back-translation + semantic comparison
    - (c) judge on a different model or provider (`JUDGE_*`) scoring meaning preservation and added claims from 0 to 1
  - `mode=compare`: localize + raw, with `baseline {output, wrong[], why}` built deterministically, with no extra LLM call:
    - `wrong` = `avoid` words found in raw + verse/hadith mishandled by raw
    - `why` = a short Arabic explanation from `flags.ar.json` templates
  - In-memory LRU cache with TTL keyed by hash(text, lang, audience, mode).
  - Cost per request aggregated, for docs/SUSTAINABILITY.md.
- **Allowed paths:** `backend/app/pipeline/{verifier,orchestrator,report,cache}.py`, `backend/app/prompts/**`, `backend/tests/**`, `docs/dev/PROGRESS.md`, `docs/DECISIONS.md`.
- **Done when:** compare responses render correctly in the local frontend «قبل وبعد» tab, and dev smoke shows `marks` highlighting correctly.

## Phase 4 — Security, resilience, deploy config
- **Deliverables:**
  - CORS: exact allowlist from `ALLOWED_ORIGINS` plus a strict regex for `*.mowatin.pages.dev` previews; no wildcard; GET and POST only.
  - Per-IP rate limit (in-memory) → 429 + `Retry-After`. Body size cap.
  - Security headers: `X-Content-Type-Options`, `Referrer-Policy`, `Cache-Control: no-store` on translate.
  - `/docs` and `/openapi.json` hidden when `ENV=production`.
  - No user text in logs (a test asserts this).
  - Graceful degradation when the fallback or judge is unconfigured.
  - `render.yaml` finalized (health check path, env var names, no values).
  - `docs/dev/DEPLOY.md`: Render steps + cron-job.org keep-alive on `/health` every 10 min, for Mohammed to do by hand.
- **Allowed paths:** `backend/app/security/**`, `backend/app/{main,config,errors}.py`, `render.yaml`, `docs/dev/DEPLOY.md`, `backend/tests/**`, `docs/dev/PROGRESS.md`, `docs/DECISIONS.md`.
- **Done when:** tests prove CORS rejection, 429, 413, the no-text-in-logs rule and hidden docs in production; bandit and pip-audit are clean.

## Phase 5 — Frontend crash + hardening (tell Eng. Feras the commit hashes; may run in parallel with backend phases)
- **Deliverables:**
  1. Fix the white screen: in `frontend/src/app/TranslateView.jsx`, `step` stays 3 from the previous run when status becomes `loading`, so `STEPS[Math.max(step,0)][1]` reads `STEPS[3]`. Clamp the index and reset correctly.
     - Repro: run an example, then submit any other text.
  2. Top-level React Error Boundary (new `frontend/src/components/ErrorBoundary.jsx`, wrapped in `main.jsx`) with a calm Arabic message and a retry button.
  3. `frontend/public/_headers`:
     - CSP: `default-src 'self'`; `connect-src 'self'` + the API origin; `img-src 'self' data: blob:`; `font-src 'self'`; `worker-src`/`script-src` that keep pdfjs and mammoth working; `frame-ancestors 'none'`
     - `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`, `Permissions-Policy`
  4. Remove any `console.log` in production code.
- **Allowed paths:** `frontend/src/app/TranslateView.jsx`, `frontend/src/components/ErrorBoundary.jsx`, `frontend/src/main.jsx`, `frontend/public/_headers`, files containing `console.log` (removal only), `docs/dev/screenshots/p5/**`, `docs/dev/PROGRESS.md`.
- **Done when:** the browser agent checks `/`, `/app` (3 tabs, EN and FR, all examples, free text twice in a row, file upload), `/results` and `/developers` at 375px and 1440px with zero console errors or warnings and no CSP violations. Screenshots are saved under `docs/dev/screenshots/p5/` and listed in the final report.

## Phase 6 — Evaluation runner (tooling only; the evaluation owner runs the official runs)
- **Deliverables:**
  - `scripts/run_eval.py`:
    - `--split dev` by default; `--split test` requires `--i-confirm-frozen`
    - `--runs 3`; systems `raw`, `localize`, and `gt` only if `GT_API_KEY` is set
    - writes `eval/results/runs/{system}_run{n}.jsonl` with `{id, target, output, segments}`, readable by `scripts/split_testset.py blind`
    - id mapping `gt↔mt`, `raw↔llm`, `mowatten↔mowatin` (a mapping, not a rename)
  - `scripts/eval_metrics.py`, scored against `expect`:
    - term accuracy
    - scripture integrity (correct ref and no LLM verse text)
    - referral recall and precision
    - over-referral rate
    - errors per 100 by category
  - `scripts/build_summary.py`: fills `eval/results/summary.json` (mean ± sd) per `eval/results/SCHEMA.md`, keeping `status: "pending"`.
- **Allowed paths:** `scripts/run_eval.py`, `scripts/eval_metrics.py`, `scripts/build_summary.py`, `backend/tests/**` (metric tests), `docs/dev/PROGRESS.md`, `docs/DECISIONS.md`. Do NOT commit generated run outputs or `summary.json` values in this phase.
- **Done when:** a dev run (`--runs 1`) completes and prints metrics, and metric functions have unit tests.

## Phase 7 — Docs for judges
- **Deliverables:**
  - README sections «التشغيل محليًا» and «إعادة القياس», each followable in under 5 minutes with a curl example.
  - `THIRD_PARTY_NOTICES.md` updated with all new deps and their licenses.
  - `docs/DECISIONS.md` rows complete.
  - `.env.example` final.
  - `backend/README.md` (architecture map of modules → ARCHITECTURE.md steps).
- **Allowed paths:** `README.md`, `backend/README.md`, `THIRD_PARTY_NOTICES.md`, `docs/DECISIONS.md`, `.env.example`, `docs/dev/PROGRESS.md`.
- **Done when:** a fresh clone following the README runs tests and a dev smoke eval.

## Phase R — Rudaina data drop-in (repeat per file)
- **Slots:** see the item table in `docs/dev/PHASE_PROMPTS.md` (Phase R) and the schemas in `data/CONTENT_SLOTS.md`.
- **Deliverables:** confirm her file is in its slot (copy an attached file unchanged if needed); run `scripts/validate_content.py`; never edit her content (report problems in Arabic and stop); re-run the suite + dev smoke eval and report before/after metrics; if needed, a minimal loader fix in code.
- **Allowed paths:** that one slot file (copy-in only), `backend/app/**` (minimal loader fix only), `backend/tests/**`, `docs/dev/PROGRESS.md`.
- **Done when:** validator and suite are green, CI is green, and metrics are reported.
