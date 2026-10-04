@.agent/rules/muwattin.md

## Security non-negotiables (details: `docs/security/`)
1. No secret in git, logs, prompts, tests or chat; never open `.env`. Logs carry `fingerprint()` (length + hash prefix), never user text or LLM output.
2. Every LLM call goes through the request budget (`app/pipeline/budget.py`); user text in prompts passes `neutralize_tags()` and every safety match uses `canonicalize_for_matching()`.
3. Scripture and fatwa guards fail safe: unsure → `output: null` + a warn flag (review), never a confident LLM answer.
4. Changes under `backend/app/security/`, `backend/app/prompts/`, `.github/`, `.claude/`, `.agent/` or `render.yaml` need the human's explicit OK.
5. Run `docs/security/SECURE_CHANGE_CHECKLIST.md` for every change; `backend/tests/security/` must stay green.
