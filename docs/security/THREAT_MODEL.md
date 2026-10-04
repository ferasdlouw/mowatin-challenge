# Threat model: Muwattin (one page)

Method: data flow with trust boundaries, then STRIDE per boundary, plus LLM-specific threats mapped to MITRE ATLAS. Updated in Phase SEC (2026-10-03). Evidence for every control: `docs/security/AUDIT.md`, tests in `backend/tests/security/`.

## Data flow
```
Browser (anyone, no account)
  │ ① HTTPS, CORS: mowatin.pages.dev + *.mowatin.pages.dev previews only
  ▼
Cloudflare Pages: static React app (_headers: CSP self-only, frame-ancestors none)
  │   files (.pdf/.docx) parsed in the browser; nothing uploaded
  ▼ ② fetch POST /v1/translate · GET /v1/glossary · GET /health
Render: one free FastAPI instance (512 MB), in-memory rate limit + cache
  │   middleware: request log (no query) → headers → CORS → error guard → rate limit → body cap
  ▼ pipeline: segment (≤ MAX_SEGMENTS) → classify on canonical text → handler
  │   trusted: data/** (glossary, Tanzil, approved translations, hadith, policy), prompts/
  │   untrusted: request text, every LLM output
  ▼ ③ HTTPS, keys in headers only, ≤ LLM_CALL_BUDGET calls/request, ≤ LLM_DAILY_CALL_BUDGET/day
LLM providers: Gemini (primary, judge), OpenRouter :free (fallback); free tiers may use text (D-033)
  │ ④ JSON reply → Pydantic schema → post-checks → response (output may be null → review)
```

## STRIDE per boundary
| Boundary | Threat | Control | Residual |
|---|---|---|---|
| ① browser ↔ site | Tampering: XSS via LLM output or file text | React text rendering only; no `dangerouslySetInnerHTML`; CSP `script-src 'self'`; `highlight()` escapes | Low |
| ① | Spoofing: site framed (clickjacking) | `frame-ancestors 'none'` + XFO DENY (site and API) | Low |
| ② site ↔ API | Spoofing: other origins using the API from browsers | CORS exact allowlist + preview regex (fullmatch), no credentials | Non-browser clients can call the API (public by design) |
| ② | DoS: request flood | per-IP 30/min on `/v1/*` (right-most XFF, IPv6 /64) plus 4× that per IPv6 /48 (D-042), body cap 413 | Many /48s or a botnet; bounded by the daily breaker |
| ② | DoS: one request, huge work (F1, NEW-1, NEW-2) | `MAX_SEGMENTS`, call budget, deadline, daily breaker (D-034); Quran near-match CPU bound (D-035); cache 64 MB, no degraded entries (D-039) | ~0.15 s CPU worst per Quran segment |
| ② | Information disclosure: errors, docs | generic Arabic errors, no stack; docs 404 in production | Low |
| ② | Repudiation / privacy | JSON logs with length + keyed hash prefix only (HMAC, random key per process, D-042); uvicorn access log off | Low |
| ③ API ↔ LLM | Information disclosure: keys | env only; header auth; errors never echo keys/URLs | Provider-side key restrictions are a human task |
| ③ | Information disclosure: user text to free tiers | disclosed in `docs/AI_APPROACH.md` (D-033) and in the UI (under the text box, FAQ, landing, tour) | Low |
| ④ LLM ↔ API | Tampering: prompt injection (direct + via LLM output), judge manipulation | data tags + `neutralize_tags()`; rule restated after data; output post-checks → review (D-037); judge on a different model | A clever paraphrase without markers can still lower quality; human review is the backstop |
| ④ | Elevation of trust: scripture or fatwa reaching the LLM | Quran from approved files only; fatwa/attribution matched on canonical text (D-036); unbracketed attributed verse matched word for word in Tanzil (D-041); unsure → `output: null` + review | A bare verse is caught when it is the whole segment (4+ words) or a 7+ word run (D-043); a shorter bare fragment inside a sentence is still translated as text |
| Repo / CI | Elevation: code exec on teammates via `.claude/` hooks, poisoned actions or packages | CODEOWNERS on sensitive paths; launchers run only an engine whose SHA-256 is committed (D-042); actions SHA-pinned; runtime packages hash-locked; Dependabot; gates without `\|\| true` | A binary a teammate installed on PATH or in `~/.impeccable` is trusted as before; CODEOWNERS binds only with a `main` ruleset (human task) |

## LLM threats (MITRE ATLAS)
| ATLAS | Threat here | Control |
|---|---|---|
| AML.T0051.000 LLM Prompt Injection: Direct | instructions in the Arabic text | data tags, neutraliser, restated rule, override-phrase check |
| AML.T0051.001 Indirect | localizer output steering the judge / back-translation | output neutralised before the judge; judge scores steering 0; post-check |
| AML.T0054 LLM Jailbreak | making the localizer answer a fatwa | fatwa path translates the question only; judge penalises added rulings; warn flag keeps review |
| AML.T0034 Cost Harvesting | burning the free quota | D-034 budgets + daily breaker; raw mode budgeted (D-038) |
| AML.T0048 External Harms | a fluent machine-translated verse or fabricated hadith shown as authoritative | approved translations only; unsourced hadith null; raw output confidence 0 + warn |
| AML.T0010 ML Supply Chain Compromise | third-party binary via agent hooks; actions; packages | CODEOWNERS, SHA pins, pinned engine hash, `requirements.lock` with hashes |
