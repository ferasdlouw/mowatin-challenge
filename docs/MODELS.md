# Model choice: quality, speed and cost

How we pick the localizer model on evidence: intelligence (dev-set quality), speed (latency, tokens/s) and cost. Every number in the table must come from a real run as described below. **Never fill a cell by estimate.**

> **Status (2026-10-03): partial run.** First keyed dev run, free tiers, `--delay 12`. Stopped on purpose at request 127 of 176 to leave the team's free quota for the day: the raw pass is complete (88 requests), the localize pass covered 39 of 88. Latency, speed and cost below come from those 127 requests; term accuracy and referral recall for Muwattin need the full run: `python scripts/run_eval.py --split dev --runs 1 --delay 12 2> eval/results/runs/eval.log`.

## Results (dev split, 1 run per model)

| model | provider | dev term accuracy | dev referral recall | median latency | tokens/s | cost per 1,000 segments | notes |
|---|---|---|---|---|---|---|---|
| `gemini-3.5-flash-lite` | `gemini` (primary, D-028) | pending full run | pending full run | 995 ms (187 ok calls) | 29.9 | localize: $0 actual, $0.30 at list price; raw: $0 actual, $0.11 at list price (2026-10-03 partial) | free tier: 15 requests/min (Google 429), daily cap not reached after ~260 calls; 2 invalid-JSON answers in 189 calls |
| `qwen/qwen3.8-27b:free` | `openrouter` (fallback, D-029) | not measured | not measured | not measured | not measured | $0 actual; list = `qwen/qwen3.8-27b` price | 1 failover in 127 requests, answered 429 twice (transient; 200 a minute later). Free: 20/min, 50/day |
| `gemini-3.1-flash-lite` | `gemini` (judge, D-030) | n/a (judge) | n/a | 1,074 ms (37 ok calls) | 7.4 | included in the localize cost | separate daily quota from the primary |
| _any model_ | `openai_compat` (open-source / local, D-026) | pending run | pending run | pending run | pending run | pending run | $0 in the logs if the model is not in `pricing.py` (`price_unknown`) |

Notes on the columns:
- **dev term accuracy / referral recall:** `systems.mowatin[0].term_accuracy` and `.referral_recall` in `eval/results/runs/metrics.json` (definitions: `scripts/eval_metrics.py`, D-015). Referral recall comes from deterministic rules, so it should not change between models; a change means a level-D segment lost its output.
- **median latency / tokens/s:** median of `latency_ms` and `output_tokens_per_s` over the `llm_call` log lines with `"outcome": "ok"` for that model (`backend/app/llm/router.py`).
- **cost per 1,000 segments:** `1000 × Σ cost_usd / Σ segments` over the `request_cost` lines with `"mode": "localize"` (`backend/app/pipeline/orchestrator.py`). Two figures (D-031): actual `cost_usd` ($0 on free tiers) and `list_cost_usd`, the same calls at the paid list prices in `backend/app/llm/pricing.py` (sources and check date in the file). The cost includes back-translation and, when the judge uses the same provider, the judge.

## How to fill a row

1. In the root `.env`, set the slot under test: `LLM_PROVIDER`, `LLM_MODEL`, `LLM_API_KEY` (plus `LLM_BASE_URL` for `openai_compat`, see `docs/dev/DEPLOY.md` §8). Leave `FALLBACK_PROVIDER` empty so every call goes to the model under test. Keep `JUDGE_*` the same for every row, so only the localizer changes.
2. Run the dev split once and keep the log (stderr). `eval/results/runs/` is git-ignored:

   ```bash
   python3 scripts/run_eval.py --split dev --runs 1 2> eval/results/runs/eval.log
   ```

3. Read the numbers. The logs carry no user text (only lengths and hash prefixes), so this is safe to run and share:

   ```bash
   python3 - <<'EOF'
   import json, statistics
   model = "gemini-3.5-flash-lite"  # the LLM_MODEL under test
   calls, costs = [], []
   for line in open("eval/results/runs/eval.log", encoding="utf-8"):
       if "{" not in line:
           continue
       try:
           r = json.loads(line[line.index("{"):])
       except ValueError:
           continue
       if r.get("event") == "llm_call" and r["model"] == model and r["outcome"] == "ok":
           calls.append(r)
       if r.get("event") == "request_cost" and r["mode"] == "localize":
           costs.append(r)
   m = json.load(open("eval/results/runs/metrics.json", encoding="utf-8"))["systems"]["mowatin"][0]
   tps = [c["output_tokens_per_s"] for c in calls if c["output_tokens_per_s"]]
   print("term accuracy  ", m["term_accuracy"])
   print("referral recall", m["referral_recall"])
   print("median latency ", statistics.median(c["latency_ms"] for c in calls), "ms")
   print("tokens/s       ", statistics.median(tps) if tps else "n/a")
   segs = max(1, sum(c["segments"] for c in costs))
   print("cost/1k segs   ", 1000 * sum(c["cost_usd"] for c in costs) / segs, "actual")
   print("cost/1k segs   ", 1000 * sum(c["list_cost_usd"] for c in costs) / segs, "at list price")
   print("price_unknown  ", any(c["price_unknown"] for c in calls))
   EOF
   ```

4. Copy the five values into the table, put the date and anything unusual (failed calls printed by `run_eval.py`, `price_unknown`, free tier) in **notes**, and commit.
5. Repeat for the next model. Use the dev split only; the test split is sealed (`docs/EVALUATION.md`).

## How to read it

Pick the cheapest, fastest model whose term accuracy is close to the best row. Term accuracy guards meaning; latency matters for the live demo; cost matters for the operational-realism score. Scripture integrity and referral do not depend on the model: Quran text, hadith grading and referral are deterministic (`docs/AI_APPROACH.md`).
