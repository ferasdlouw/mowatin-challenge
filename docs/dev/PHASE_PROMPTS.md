# Phase prompts (paste one per NEW Antigravity conversation)

> Before each prompt: open a NEW conversation, select the model, and make sure the previous phase is pushed to `main` and its CI run is green.
> Rules load automatically from `.agent/rules/muwattin.md`. Spec: `docs/dev/PLAN.md`. State: `docs/dev/PROGRESS.md`.

---

## Phase 0 — Plan (no code)
```
You are the lead engineer for Muwattin's backend. Read .agent/rules/muwattin.md, docs/dev/PROGRESS.md, docs/dev/PLAN.md (all of it), then the "Must-read files" listed in PLAN.md.

Task: Phase 0 only. Produce the Phase 0 artifact exactly as PLAN.md specifies: file tree for all phases, data-slot JSON schemas with examples, provider/fallback/judge proposal with free-quota arithmetic, confidence formula, partial-verse policy, review-flow decision, risks, and questions for me.

Constraints: write no code, edit no files, run no git commands except `git status` and `git log -5`. Base every claim on files you actually read; if something is unclear, list it as a question instead of assuming.

Stop after the artifact and wait for "approved".
```

## Phase 1 — Skeleton + CI
```
Run Phase 1 from docs/dev/PLAN.md. Work directly on main (no branch, no PR).
Follow the Phase protocol in .agent/rules/muwattin.md exactly (Start checks, record PHASE_BASE → plan artifact → wait for "go" → build → Close-out → push to main).
Approved Phase 0 decisions: [PASTE THE APPROVED DECISIONS HERE]. Record them in docs/DECISIONS.md and docs/dev/PROGRESS.md in this phase's commit.

Allowed paths: backend/**, render.yaml, .github/workflows/**, .env.example, docs/dev/PROGRESS.md, docs/DECISIONS.md.
Done when: PLAN.md Phase 1 "Done when" is met AND the Close-out passes:
1) local suite green, output shown;
2) `git diff --name-only PHASE_BASE` and `git status --porcelain` show only allowed paths;
3) deliverables table with evidence;
4) PROGRESS.md updated;
5) pushed to main and the CI run for that push is green (`gh run watch … --exit-status`); since this phase creates CI, prove the new workflow actually ran on the push.
Loop guard applies. Stop after the final report.
```

## Phase 2a — Normalize + glossary detection
```
Run Phase 2a from docs/dev/PLAN.md. Work directly on main (no branch, no PR).
Follow the Phase protocol in .agent/rules/muwattin.md (Start checks: main up to date, latest main CI green, PHASE_BASE recorded → plan artifact → wait for "go" → build → Close-out).

Allowed paths: backend/app/pipeline/normalize.py, backend/app/pipeline/glossary.py, backend/app/pipeline/__init__.py, backend/tests/**, docs/dev/PROGRESS.md, docs/DECISIONS.md.
Use only data/testset/dev.jsonl. Inspect glossary files with code/jq; never print them whole.

Done when: detection recall on dev expect.terms ≥95% (print the number and every miss), zero false locks of «المسلم/المسلمين/المسلمون» to islam, and the Close-out passes:
local suite green · diff only in allowed paths · deliverables table · PROGRESS.md updated · pushed to main only after all of that, and the CI run for that push watched to green (red = fix forward or revert per the rules; never leave main red).
Loop guard applies. Stop after the final report.
```

## Phase 2b — Segmenter + classifier
```
Run Phase 2b from docs/dev/PLAN.md. Work directly on main (no branch, no PR).
Follow the Phase protocol in .agent/rules/muwattin.md (Start checks, record PHASE_BASE → plan → "go" → build → Close-out → push to main).

Allowed paths: backend/app/pipeline/segmenter.py, backend/app/pipeline/classifier.py, backend/tests/**, docs/dev/PROGRESS.md, docs/DECISIONS.md.
Match levels to the conventions in frontend/src/data/examples.js (read only).

Done when: 100% correct type on dev quran_quote, quran_misquote, hadith_quote, hadith_unsourced and level_d cases; T097, T100, T148 NOT classified fatwa_like (print a per-category table), and the Close-out passes:
local suite green · diff only in allowed paths · deliverables table · PROGRESS.md updated · pushed to main only after all of that, and the CI run for that push watched to green (red = fix forward or revert per the rules; never leave main red).
Loop guard applies. Stop after the final report.
```

## Phase 2c — Quran resolver
```
Run Phase 2c from docs/dev/PLAN.md. Work directly on main (no branch, no PR).
Follow the Phase protocol in .agent/rules/muwattin.md (Start checks, record PHASE_BASE → plan → "go" → build → Close-out → push to main).
Ask me before downloading the Tanzil text; show the exact URL and file you will fetch. Store it unmodified; add CC BY 3.0 attribution.
The LLM is never called in this module. Never edit data/quran/translations/** (Rudaina's slot); tests use a small fixture translation.

Allowed paths: backend/app/pipeline/quran.py, data/quran/tanzil/** (Arabic text only; never data/quran/translations/**), THIRD_PARTY_NOTICES.md, backend/tests/**, docs/dev/PROGRESS.md, docs/DECISIONS.md.

Done when: 100% correct refs on dev quran_quote; 100% of dev quran_misquote blocked with the correct verse + ref named (print each case: input → decision → ref); ambiguous-match and partial-verse behaviour tested; and the Close-out passes:
local suite green · diff only in allowed paths · deliverables table · PROGRESS.md updated · pushed to main only after all of that, and the CI run for that push watched to green (red = fix forward or revert per the rules; never leave main red).
Loop guard applies. Stop after the final report.
```

## Phase 2d — Hadith + fatwa guard + report
```
Run Phase 2d from docs/dev/PLAN.md. Work directly on main (no branch, no PR).
Follow the Phase protocol in .agent/rules/muwattin.md (Start checks, record PHASE_BASE → plan → "go" → build → Close-out → push to main).
Content slots already exist with fixed schemas (data/CONTENT_SLOTS.md); load them as they are, never edit them, never invent content. All user-facing text comes from data/messages/flags.ar.json by key.
review_queue logic must be identical to needsReview() in frontend/src/lib/api.js; add a test that states that rule.

Allowed paths: backend/app/pipeline/{hadith,fatwa_guard,report,orchestrator}.py, backend/app/main.py (wiring only), backend/tests/**, docs/dev/PROGRESS.md, docs/DECISIONS.md.

Done when: 100% of dev hadith_unsourced and level_d cases end in review with correct flags; every must_refer=false dev case is not referred by the guard (print counts); /v1/translate returns a full contract-valid response for deterministic paths; and the Close-out passes:
local suite green · diff only in allowed paths · deliverables table · PROGRESS.md updated · pushed to main only after all of that, and the CI run for that push watched to green (red = fix forward or revert per the rules; never leave main red).
Loop guard applies. Stop after the final report.
```

## Phase 3a — LLM provider layer
```
Run Phase 3a from docs/dev/PLAN.md. Work directly on main (no branch, no PR).
Follow the Phase protocol in .agent/rules/muwattin.md (Start checks, record PHASE_BASE → plan → "go" → build → Close-out → push to main).
Use the providers approved in docs/DECISIONS.md. Tests must use respx mocks; no network in tests. Keys come only from env; never print env values. Ask before adding any dependency outside PLAN.md's approved list.

Allowed paths: backend/app/llm/**, backend/app/config.py, .env.example, backend/requirements*.txt, backend/tests/**, docs/dev/PROGRESS.md, docs/DECISIONS.md.

Done when: tests cover success, timeout, 429, 5xx, invalid JSON, retry and failover; usage/cost accounting is logged without user text; you give me ONE command to run a manual smoke call with my local .env (you do not run it with real keys unless I say so); and the Close-out passes:
local suite green · diff only in allowed paths · deliverables table · PROGRESS.md updated · pushed to main only after all of that, and the CI run for that push watched to green (red = fix forward or revert per the rules; never leave main red).
Loop guard applies. Stop after the final report.
```

## Phase 3b — Localizer + term lock + raw
```
Run Phase 3b from docs/dev/PLAN.md. Work directly on main (no branch, no PR).
Follow the Phase protocol in .agent/rules/muwattin.md (Start checks, record PHASE_BASE → plan → "go" → build → Close-out → push to main).
User text is always delimited and treated as data. Prompts live in backend/app/prompts/ as versioned files. raw mode = same model, no glossary, no verse/hadith handling, no verification (it is the fair baseline; do not weaken or strengthen it).

Allowed paths: backend/app/pipeline/{localizer,orchestrator}.py, backend/app/prompts/**, backend/app/main.py (wiring only), backend/tests/**, docs/dev/PROGRESS.md, docs/DECISIONS.md.

Done when: fake-LLM tests prove each strategy (keep_and_gloss / translate / context) puts the right instruction in the prompt and that an injected instruction inside user text is ignored; I run the smoke command you give me on 5 dev cases and they return contract-valid responses; and the Close-out passes:
local suite green · diff only in allowed paths · deliverables table · PROGRESS.md updated · pushed to main only after all of that, and the CI run for that push watched to green (red = fix forward or revert per the rules; never leave main red).
Loop guard applies. Stop after the final report.
```

## Phase 3c — Verifier + compare + cost
```
Run Phase 3c from docs/dev/PLAN.md. Work directly on main (no branch, no PR).
Follow the Phase protocol in .agent/rules/muwattin.md (Start checks, record PHASE_BASE → plan → "go" → build → Close-out → push to main).
Use the confidence formula approved in docs/DECISIONS.md. baseline.wrong and baseline.why are built deterministically (no extra LLM call). Judge must use a different model/provider than the localizer.

Allowed paths: backend/app/pipeline/{verifier,orchestrator,report,cache}.py, backend/app/prompts/**, backend/tests/**, docs/dev/PROGRESS.md, docs/DECISIONS.md.

Done when: tests prove a deterministic term failure caps confidence < 0.75, marks contain the exact rendered strings, and compare returns baseline per segment; the local frontend (VITE_API_URL=http://localhost:8000) renders «الترجمة» and «قبل وبعد» correctly for 3 dev cases (browser agent, zero console errors; screenshots described in the report, not committed); and the Close-out passes:
local suite green · diff only in allowed paths · deliverables table · PROGRESS.md updated · pushed to main only after all of that, and the CI run for that push watched to green (red = fix forward or revert per the rules; never leave main red).
Loop guard applies. Stop after the final report.
```

## Phase 4 — Security + resilience + deploy config
```
Run Phase 4 from docs/dev/PLAN.md. Work directly on main (no branch, no PR).
Follow the Phase protocol in .agent/rules/muwattin.md (Start checks, record PHASE_BASE → plan → "go" → build → Close-out → push to main).
Do not touch Render, Cloudflare or any account; write docs/dev/DEPLOY.md with the manual steps for me instead.

Allowed paths: backend/app/security/**, backend/app/{main,config,errors}.py, render.yaml, docs/dev/DEPLOY.md, backend/tests/**, docs/dev/PROGRESS.md, docs/DECISIONS.md.

Done when: tests prove CORS rejects a foreign origin and accepts mowatin.pages.dev + a preview subdomain, 429 with Retry-After, 413, 400 on extra fields, no user text in logs, /docs hidden when ENV=production; bandit, pip-audit and gitleaks are clean; and the Close-out passes:
local suite green · diff only in allowed paths · deliverables table · PROGRESS.md updated · pushed to main only after all of that, and the CI run for that push watched to green (red = fix forward or revert per the rules; never leave main red).
Loop guard applies. Stop after the final report.
```

## Phase 5 — Frontend crash + hardening (can run in parallel; share the commit hashes with Eng. Feras)
```
Run Phase 5 from docs/dev/PLAN.md. Work on main. When done, list the commit hashes for Eng. Feras.
Follow the Phase protocol in .agent/rules/muwattin.md (Start checks, record PHASE_BASE → plan → "go" → build → Close-out → push to main).
This is NOT a redesign: change only what Phase 5 lists. Keep the existing style and oxlint rules.

Allowed paths: frontend/src/app/TranslateView.jsx, frontend/src/components/ErrorBoundary.jsx, frontend/src/main.jsx, frontend/public/_headers, files containing console.log (removal only), docs/dev/screenshots/p5/**, docs/dev/PROGRESS.md.

Done when: repro (run an example, then submit other text) no longer crashes; ErrorBoundary shows the Arabic fallback when a render error is forced in dev; with `npm run build && npm run preview` the browser agent checks /, /app (3 tabs, EN+FR, all examples, free text twice in a row), /results, /developers at 375px and 1440px with zero console errors/warnings and zero CSP violations (screenshots saved in docs/dev/screenshots/p5/); and the Close-out passes:
lint+build+audit green · diff only in allowed paths · deliverables table · PROGRESS.md updated · pushed to main only after all of that, and the CI run for that push watched to green (red = fix forward or revert per the rules; never leave main red).
Loop guard applies. Stop after the final report.
```

## Phase 6 — Evaluation runner
```
Run Phase 6 from docs/dev/PLAN.md. Work directly on main (no branch, no PR).
Follow the Phase protocol in .agent/rules/muwattin.md (Start checks, record PHASE_BASE → plan → "go" → build → Close-out → push to main).
NEVER read data/testset/test.jsonl in this phase; test-split code paths are exercised with a fixture only. Do not commit generated runs or summary.json values.

Allowed paths: scripts/run_eval.py, scripts/eval_metrics.py, scripts/build_summary.py, backend/tests/**, docs/dev/PROGRESS.md, docs/DECISIONS.md.

Done when: metric functions have unit tests; `--split test` refuses without --i-confirm-frozen (tested); output files are readable by `python3 scripts/split_testset.py blind` (tested on fixture runs); you give me the dev command and I run `--split dev --runs 1` and it prints term accuracy, scripture integrity, referral recall/precision and over-referral; and the Close-out passes:
local suite green · diff only in allowed paths · deliverables table · PROGRESS.md updated · pushed to main only after all of that, and the CI run for that push watched to green (red = fix forward or revert per the rules; never leave main red).
Loop guard applies. Stop after the final report.
```

## Phase 7 — Docs for judges
```
Run Phase 7 from docs/dev/PLAN.md. Work directly on main (no branch, no PR).
Follow the Phase protocol in .agent/rules/muwattin.md (Start checks, record PHASE_BASE → plan → "go" → build → Close-out → push to main).
Write Arabic-first where the file is Arabic (README.md). Every command you document must be one you actually ran in this conversation, with its output.

Allowed paths: README.md, backend/README.md, THIRD_PARTY_NOTICES.md, docs/DECISIONS.md, .env.example, docs/dev/PROGRESS.md.

Done when: in a fresh clone in a temp dir, the README steps install, run tests and start the server without edits (show output); THIRD_PARTY_NOTICES lists every new dependency with its license; and the Close-out passes:
diff only in allowed paths · deliverables table · PROGRESS.md updated · pushed to main only after all of that, and the CI run for that push watched to green (red = fix forward or revert per the rules; never leave main red).
Loop guard applies. Stop after the final report.
```

## Phase R — Rudaina data drop-in (use once per file she delivers)

Pick the ONE line for the file that arrived and paste it into the prompt below where it says `[ITEM]`:

| Item | File (slot) | Schema | What it unlocks |
|---|---|---|---|
| `quran-en` | `data/quran/translations/en.json` | `data/CONTENT_SLOTS.md` §1 | English verse translations (Phase 2c) |
| `quran-fr` | `data/quran/translations/fr.json` | §1 | French verse translations (Phase 2c) |
| `hadith` | `data/hadith/hadith.json` | §2 | Sourced hadith matching (Phase 2d) |
| `fabricated` | `data/hadith/fabricated.json` | §2 | Fabricated-saying detection (Phase 2d) |
| `fatwa-signals` | `data/policy/fatwa_signals.json` | §3 | Fatwa detection + exclusions (Phase 2b/2d) |
| `referral` | `data/policy/referral.json` | §3 | Referral message + bodies (Phase 2d) |
| `messages` | `data/messages/flags.ar.json` | §4 | Final user-facing Arabic texts (all phases) |
| `demo` | `data/demo/examples.json` | §5 | Demo examples (cache + Eng. Feras's UI) |

```
Run Phase R from docs/dev/PLAN.md for item: [ITEM] (look up its slot file and schema section in the table in docs/dev/PHASE_PROMPTS.md, Phase R). Work directly on main (no branch, no PR).
Follow the Phase protocol in .agent/rules/muwattin.md (Start checks, record PHASE_BASE → plan → "go" → build → Close-out → push to main).

Steps:
1) Locate the file. Normally Eng. Rudaina has already pushed it to its slot on main. If instead I attached it, copy it to its slot path unchanged (byte-for-byte; no reformatting).
2) Run `python3 scripts/validate_content.py`. If it fails: do NOT edit her file. List every problem (file, key/line, what is expected per data/CONTENT_SLOTS.md) as a short Arabic list I can forward to her, and STOP.
3) If status is not "verified", say so and ask me whether to continue with a draft.
4) Run the full backend suite and a dev smoke eval (`python3 scripts/run_eval.py --split dev --runs 1` if it exists) and print before/after metrics relevant to this item (e.g. quran-*: dev quran_quote cases now returning approved translations; fatwa-signals: level_d recall + over-referral on T097/T100/T148; messages: no missing keys or {placeholders}).
5) If a loader change is genuinely required because the schema in data/CONTENT_SLOTS.md was not followed by the code, fix the CODE, not her file, and keep the change minimal.

Allowed paths: the one slot file for [ITEM] (only in case 1, copying an attached file unchanged), backend/app/** (only for a minimal loader fix in step 5), backend/tests/**, docs/dev/PROGRESS.md (tick the item in "Waiting on humans").
Never edit any other slot file, data/glossary/**, or data/testset/**.

Done when: validator passes; full suite green; before/after metrics printed; and the Close-out passes:
diff only in allowed paths · deliverables table · PROGRESS.md updated · pushed to main only after all of that, and the CI run for that push watched to green (red = fix forward or revert per the rules; never leave main red).
Loop guard applies. Stop after the final report.
```

## If something goes wrong mid-phase (recovery prompt)
```
Stop working. Do not edit anything else.
1) Show `git status`, `git log --oneline origin/main..HEAD` (unpushed commits) and `git diff --stat PHASE_BASE` (use the hash from PROGRESS.md or this conversation).
2) Compare the changed files against this phase's Allowed paths in docs/dev/PLAN.md and list any out-of-scope file.
3) List the phase deliverables with done / not done and evidence.
4) If you were retrying the same fix, state the error, what you tried, and 2 hypotheses.
5) Do NOT push unverified work. If main is red because of this phase, revert the phase commits and push the revert. Write the state into docs/dev/PROGRESS.md (commit it only if the suite is green; otherwise paste the text in your reply), and stop. I will continue in a fresh conversation.
```
