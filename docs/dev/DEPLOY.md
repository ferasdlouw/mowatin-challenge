# Deploying the Muwattin API (manual steps)

> For Mohammed, done by hand. The coding agent never touches Render, Cloudflare or any account.
> Service definition: `render.yaml` (names only, no values). Security policy: `docs/DECISIONS.md` D-016.

## 1. Create the Render service (once)
1. Sign in to <https://dashboard.render.com> with the account that should own the service.
2. **New → Blueprint**, connect the GitHub repo `ferasdlouw/mowatin-challenge`, branch `main`. Render reads `render.yaml` and proposes one free web service, `muwattin-api`.
3. Render asks for every variable marked `sync: false`. Fill them from the table in §2, then **Apply**.
4. Wait for the first deploy to go **Live**. The URL looks like `https://muwattin-api.onrender.com` (Render may add a suffix if the name is taken). Use it as `API` below.

`render.yaml` already sets:
- `ENV=production`, which hides `/docs`, `/redoc` and `/openapi.json`.
- `PYTHON_VERSION=3.11.12`.
- Health check on `/health`.
- Start command: `uvicorn --factory app.main:create_app --app-dir backend … --no-access-log`. The uvicorn access log is off because it would print `/v1/glossary?q=…` (what the user typed). The app writes its own request line with no query string.
- No `rootDir`: Render hides files outside `rootDir`, and the API needs `data/`. A build filter redeploys only on changes to `backend/**`, `data/**` or `render.yaml`.

## 2. Environment variables (Render → muwattin-api → Environment)
Never paste a key anywhere else: not in git, chat, issues or screenshots.

| Name | Value | Required |
|---|---|---|
| `ALLOWED_ORIGINS` | `https://mowatin.pages.dev` (comma-separated exact origins; no `*`, no trailing `/`). Preview URLs `https://<id>.mowatin.pages.dev` are already allowed by code. | yes |
| `TRUSTED_PROXY_HOPS` | `1` (Render's proxy appends the client IP to `X-Forwarded-For`; see §4) | yes |
| `RATE_LIMIT_PER_MIN` | `30` | optional (default 30) |
| `MAX_TEXT_CHARS` | `4000` (the frontend says "4000 حرف"; keep them equal) | optional (default 4000) |
| `LLM_TIMEOUT_S` | `20` | optional (default 20) |
| `LLM_PROVIDER` / `LLM_API_KEY` / `LLM_MODEL` | `gemini` / your AI Studio key / `gemini-3.5-flash-lite` (D-028) | yes for real output |
| `FALLBACK_PROVIDER` / `FALLBACK_API_KEY` / `FALLBACK_MODEL` | `openrouter` / your OpenRouter key / `qwen/qwen3.8-27b:free` (D-029) | recommended |
| `JUDGE_PROVIDER` / `JUDGE_API_KEY` / `JUDGE_MODEL` | `gemini` / your AI Studio key / `gemini-3.1-flash-lite` (D-030) | recommended |
| `LLM_BILLING` | `free` while the keys are on free tiers; `paid` once billing is on (D-031) | optional (default `paid`) |

Set all three variables of a slot or none. The app still starts without fallback or judge; the startup log line `llm_slots` shows each slot as `configured`, `unset` or `incomplete`, never the values. Fix any `incomplete` slot.

## 3. Checks after each deploy
Run these from your own machine, with `API=https://muwattin-api.onrender.com`:

**Security smoke test (Phase SEC; run it first, once per deploy):**
```bash
scripts/security_smoke.sh $API https://mowatin.pages.dev
```
It checks health, docs hidden, security headers, CORS allowed/refused, 400 on an extra field, 413 on 4001 chars, a 2000-segment input capped and answered quickly with the rest in review, and 429 + `Retry-After` on `/v1/*` (via `/v1/glossary`, no LLM call). It spends at most `LLM_CALL_BUDGET` LLM calls and uses up your per-minute limit for about a minute. Every line must say `PASS`. The limits it checks come from `MAX_SEGMENTS`, `LLM_CALL_BUDGET`, `REQUEST_DEADLINE_S` and `LLM_DAILY_CALL_BUDGET` (defaults in `backend/app/config.py`, D-034); Render asks for them because `render.yaml` lists them with `sync: false` (leave them empty to keep the defaults). A `limit_hit` line in Logs means a request hit one of them.

The individual checks, if you want to run them by hand:

```bash
# health: expect {"status":"ok",...}
curl -s $API/health

# docs hidden in production: expect 404 for all three
for p in docs redoc openapi.json; do curl -s -o /dev/null -w "$p %{http_code}\n" $API/$p; done

# CORS allowed: expect "access-control-allow-origin: https://mowatin.pages.dev"
curl -s -D - -o /dev/null -X OPTIONS $API/v1/translate \
  -H "Origin: https://mowatin.pages.dev" -H "Access-Control-Request-Method: POST" \
  -H "Access-Control-Request-Headers: content-type"

# CORS refused: expect 400 and no access-control-allow-origin header
curl -s -D - -o /dev/null -X OPTIONS $API/v1/translate \
  -H "Origin: https://evil.example.com" -H "Access-Control-Request-Method: POST"

# extra field: expect 400
curl -s -o /dev/null -w "%{http_code}\n" -X POST $API/v1/translate \
  -H "Content-Type: application/json" -d '{"text":"نص","debug":true}'
```

In **Logs**, check that you see `llm_slots`, `http_request` and `translate_request` lines, and that none of them contains the text you sent. `translate_request` shows only `chars` and a `sha256` prefix.

## 4. Rate-limit and proxy check (do this once)
The limiter counts per client IP and takes the IP from the **right-hand** end of `X-Forwarded-For`, because a client can forge entries on the left. If the right-hand entry on Render turns out to be a shared edge address, every user would share one bucket of 30 requests per minute.

1. From your laptop, send 31 requests within a minute:
   ```bash
   for i in $(seq 31); do curl -s -o /dev/null -w "%{http_code} " -X POST $API/v1/translate \
     -H "Content-Type: application/json" -d '{"text":"اختبار"}'; done; echo
   ```
   Expect thirty `200` (or `5xx` until the LLM keys are set) and then `429`. The 429 reply carries `Retry-After: <seconds>`.
2. **Right away**, open the live frontend on a phone using mobile data (not your Wi-Fi) and translate one text.
   - It works: IPs are counted per client. Done.
   - The phone also gets "طلبات كثيرة في وقت قصير": the limiter is seeing a shared proxy address. Set `TRUSTED_PROXY_HOPS=2`, redeploy, and repeat. If it still fails, set it back to `1`, raise `RATE_LIMIT_PER_MIN` to `120` as a stopgap, and tell the coding agent.

Notes:
- The limiter lives in memory, so it resets when the instance restarts or sleeps. That's acceptable for one free instance. With more than one instance each would count separately.
- `/health` is never rate-limited.

## 5. Keep-alive (cron-job.org)
Free Render services sleep after 15 minutes without traffic, and the first request then takes 30–60 s. Keep the API awake through the judging window (Oct 7–22):

1. Sign up at <https://cron-job.org> (free).
2. **Create cronjob**:
   - Title: `muwattin-api keep-alive`
   - URL: `$API/health` (the full https URL)
   - Schedule: every **10 minutes**
   - Request method: GET; timeout: 30 s
   - Notifications: email on failure (after 2 consecutive failures)
3. Save, then use **Test run**: expect HTTP 200.

Budget: the free plan gives 750 instance hours a month, and one always-awake service uses about 744 in a 31-day month. Don't keep a second free service awake on the same account.

## 6. Connect the frontend (Feras)
After §3 passes, send Feras the API URL (it's not a secret). In Cloudflare Pages → `mowatin` → Settings → Environment variables, he sets `VITE_API_URL=$API` for **Production** (and **Preview** if previews should be live too), then redeploys. The site switches from DEMO to live mode.

If the API moves to another domain, or a custom frontend domain is added, add that origin to `ALLOWED_ORIGINS` and redeploy the API.

## 7. Rollback
- **Fast:** Render → muwattin-api → Events/Deploys → pick the last good deploy → **Rollback**.
- **Proper:** the coding agent runs `git revert <commit>` on `main` and pushes; Render redeploys automatically.
- **Frontend only:** Feras removes `VITE_API_URL` and redeploys Pages. The site falls back to DEMO mode.

## 8. Run with an open-source or local model
Any slot (`LLM_*`, `FALLBACK_*`, `JUDGE_*`) can point at an OpenAI-compatible endpoint with provider `openai_compat` (D-026). The defaults above do not change; this is opt-in per slot. Code: `backend/app/llm/openai_compat.py`, `backend/app/llm/factory.py`.

| Variable | Value |
|---|---|
| `<SLOT>_PROVIDER` | `openai_compat` |
| `<SLOT>_BASE_URL` | the endpoint root that serves `/chat/completions` (required for this provider only) |
| `<SLOT>_MODEL` | the model name the server expects |
| `<SLOT>_API_KEY` | the server's key; may be empty only when the base URL is `localhost` or `127.0.0.1` |

Rules enforced at startup (an invalid slot fails with a message naming the variable, never its value):
- `https://` is allowed for any host; `http://` only for `localhost` or `127.0.0.1`.
- No credentials, query or fragment in the base URL.
- Models missing from `backend/app/llm/pricing.py` cost $0 in the logs, with `"price_unknown": true` on each `llm_call` line. Prices are never guessed.

Local model on your machine (Ollama or LM Studio, backend run locally as in the README):
```bash
# Ollama: `ollama pull <model>` first; it serves on port 11434 by default
LLM_PROVIDER=openai_compat
LLM_BASE_URL=http://localhost:11434/v1
LLM_MODEL=<model>
LLM_API_KEY=

# LM Studio: start its local server; it serves on port 1234 by default
JUDGE_PROVIDER=openai_compat
JUDGE_BASE_URL=http://127.0.0.1:1234/v1
JUDGE_MODEL=<model>
JUDGE_API_KEY=
```

Any OpenAI-compatible host (works on Render too, because it is https):
```bash
FALLBACK_PROVIDER=openai_compat
FALLBACK_BASE_URL=https://<host>/v1
FALLBACK_MODEL=<model>
FALLBACK_API_KEY=<key>
```

Notes:
- `localhost` means the machine running the API. On Render it is the Render container, so a local model works only when you run the backend yourself.
- Requests ask for JSON output (`response_format: {"type": "json_object"}`). A server that rejects this returns HTTP 400; the call is logged with outcome `client` and the router fails over (D-011). Pick a model and server that support JSON output.
- A slot with an empty key still shows as `incomplete` in the startup `llm_slots` line (that check lives in `backend/app/main.py` and only reads the three original variables). The slot still works if the rules above pass.
- Compare models with `docs/MODELS.md`.

## Known limits
- `POST /v1/translate` still returns the stub response until the orchestrator phases (2c–3c) land.
