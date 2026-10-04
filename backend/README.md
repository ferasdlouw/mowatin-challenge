# Mowatin backend

FastAPI service behind `POST /v1/translate`. The design is in [`docs/ARCHITECTURE.md`](../docs/ARCHITECTURE.md): the pipeline is in §2, the binding rules in §3 and the frozen API contract in §4. Decisions are in [`docs/DECISIONS.md`](../docs/DECISIONS.md).

Run, test and evaluate from the repository root: see the root [`README.md`](../README.md).

## Module map

| ARCHITECTURE.md §2 step | Module | What it does |
|---|---|---|
| Input | `app/main.py` | `create_app()` factory, routes `/health`, `/v1/translate`, `/v1/glossary`. Start: `uvicorn --factory app.main:create_app --app-dir backend` |
| Input | `app/schemas.py` | Request and response models, exactly as §4 (D-014) |
| Input | `app/config.py` | Every environment variable (names in `.env.example`) |
| [1] Segmenter | `app/pipeline/segmenter.py` | Sentences, then clauses at «، ؛»; ﴿…﴾ and «…» spans intact; a sentence with a fatwa signal stays whole (D-024) |
| [2] Classifier | `app/pipeline/classifier.py` | `quran / hadith / term_heavy / general / fatwa_like` + level; fatwa first (D-018), signals from `data/policy/fatwa_signals.json` |
| [3] Router | `app/pipeline/orchestrator.py` | Sends each segment to its handler; `mode` `localize`, `raw` or `compare` (baseline + `wrong`/`why`); cache; one `request_cost` log line |
| [3] Quran resolver | `app/pipeline/quran.py` | Matches the verse against the Tanzil text and inserts the approved translation from `data/quran/translations/`; a misquote gets the correct verse + block flag (D-007). No LLM |
| [3] Hadith handler | `app/pipeline/hadith.py` | Every «…» quote checked: fabricated first, then exact match in `data/hadith/hadith.json` (source + grade). The orchestrator translates the meaning only when all quotes are sourced (D-023) |
| [3] Level-D guard | `app/pipeline/fatwa_guard.py` | Level D, warn flag, referral text and bodies from `data/policy/referral.json`; the output is the literal question + referral, never an answer (D-022) |
| [3] Term lock | `app/pipeline/glossary.py`, `app/pipeline/normalize.py` | Detects glossary terms (Arabic normalized) in `data/glossary/` |
| [3] Localizer | `app/pipeline/localizer.py` | LLM translation with term lock per strategy and audience; `raw_translate()` for the baseline and level-D question |
| [4] Verifier | `app/pipeline/verifier.py` | Term check (deterministic), back-translation (character-trigram Dice), judge LLM; D-004 weights, missing check = 0 (D-021) |
| [5] Report | `app/pipeline/report.py` | Flag text from `data/messages/flags.ar.json`, `review_queue` (same rule as the frontend's `needsReview()`), summary, disclosure |
| Support | `app/pipeline/cache.py` | In-memory LRU 1,000 + TTL 1 h |
| LLM providers (§5) | `app/llm/` | Gemini and OpenRouter clients, router with retry and failover (D-011), prices with actual and list cost (D-031), smoke CLI `python -m app.llm.smoke --env-file ../.env` (primary, fallback and judge) |
| Prompts | `app/prompts/*.txt` | Versioned templates; user text inside delimiters |
| Security | `app/security/`, `app/errors.py` | CORS, rate limit, body cap, headers, request log without user text, error replies (D-016) |

## Tests

`tests/` mirrors `app/`; LLMs are faked through the provider interface, so there is no network. `cd backend && pytest -q`. Coverage of `app/pipeline` stays at 85% or more (`pytest --cov=app/pipeline`).
