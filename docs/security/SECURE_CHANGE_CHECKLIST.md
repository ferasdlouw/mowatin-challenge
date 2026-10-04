# Secure change checklist

Run the group(s) that match your change before you commit. Every line is yes/no and names what proves it. `pytest` means `cd backend && pytest -q`; the security suite is `backend/tests/security/`.

## Any change
1. No secret, key or `.env` content added anywhere — `gitleaks detect --no-banner`.
2. `backend/tests/security/` green, pipeline coverage ≥ 85% — `pytest --cov=app/pipeline --cov-fail-under=85`.

## New or changed endpoint
3. Path starts with `/v1/` (rate-limited) or is `/health` — `test_invariants.py::test_every_v1_route_is_rate_limited`.
4. Request model sets `extra="forbid"` — `test_invariants.py::test_every_request_body_model_forbids_extra_fields`.
5. Response matches `docs/ARCHITECTURE.md` §4 exactly (or §4 and `frontend/src/lib/api.js` change together with approval) — `tests/test_translate.py`.
6. Errors go through `app/errors.py` (Arabic text, no stack) — `tests/security/test_degradation.py`.

## New or changed prompt
7. New version file; the old one stays unchanged — `tests/pipeline/test_prompt_json_shapes.py`.
8. Untrusted fields sit in data tags, are filled through `neutralize_tags()`, and the rule is restated after the block — `test_invariants.py::test_untrusted_prompt_fields_pass_the_tag_neutraliser`, `::test_live_prompts_restate_the_rule_after_the_data_block`.
9. Prompt names every required JSON key — `test_prompt_json_shapes.py`.

## New LLM call
10. Goes through the request's `_MeteredRouter` (budget + cost log); no new `LLMRouter(...)` — `test_invariants.py::test_every_llm_path_is_inside_the_request_budget`, `::test_llm_routers_are_built_only_in_known_places`.
11. A failed or refused call fails safe to `output: null` + review — `tests/security/test_consumption.py`.
12. Its output is post-checked (`looks_steered`) before it counts as a translation — `tests/security/test_prompt_injection.py`.

## Safety matching (fatwa, Quran, hadith, glossary)
13. Matches use `canonicalize_for_matching()` (or `normalize_text` for data lookups) — `tests/security/test_canonical_guards.py`.
14. Dev categories unchanged — `test_canonical_guards.py::test_dev_categories_unchanged`.
15. No unbounded loop over all verses/terms per request — `test_consumption.py::test_quran_near_match_is_cpu_bounded`.

## Logging
16. New log lines carry counters and `fingerprint()` only, never text, prompts or outputs — `test_invariants.py::test_no_log_line_carries_user_text_or_llm_output`.

## New dependency or data file
17. Approved in `docs/dev/PLAN.md` and pinned; a runtime package also regenerates `backend/requirements.lock` (command in its header) — `test_deploy_config.py::test_lock_matches_the_direct_pins`; `pip-audit` / `npm audit --omit=dev` clean (CI).
18. Data files are read from fixed paths, never from request input (review the diff).
19. New user-facing Arabic text lives in `data/messages/flags.ar.json` (Rudaina), not in code.

## Frontend sink
20. No `dangerouslySetInnerHTML`, `innerHTML`, `eval`, `new Function` or unescaped `new RegExp(data)` — `grep -rnE "dangerouslySetInnerHTML|innerHTML|eval\(|new Function" frontend/src` is empty.
21. Built site loads with zero CSP violations under `frontend/public/_headers` (Pages preview console).

## CI edit
22. No `|| true` / `continue-on-error`; every `uses:` pinned to a 40-char SHA — `test_invariants.py::test_ci_*`; `uvx zizmor@1.16.0 --offline .github/workflows/ci.yml` clean.
23. Triggers and permissions unchanged unless the human approved it.

## Agent-config edit (`.claude/`, `.agent/`, `CLAUDE.md`)
24. Human's explicit OK; no new hook that downloads or executes code — review the diff with CODEOWNERS.
25. After deploy: `scripts/security_smoke.sh $API` passes (docs/dev/DEPLOY.md §3).
