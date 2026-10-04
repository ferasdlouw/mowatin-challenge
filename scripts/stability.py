#!/usr/bin/env python3
"""
قياس ثبات مُوطِّن عبر 3 تشغيلات.

    python scripts/stability.py --runs r1.jsonl r2.jsonl r3.jsonl [--rates 3.1 2.8 3.4]

المخرجات في eval/results/:
    stability.txt          : ملخص الثبات
    unstable_segments.csv  : المقاطع التي اختلف ناتجها بين التشغيلات (راجعيها يدويًا)
"""
import argparse
import csv
import json
import statistics as st
from difflib import SequenceMatcher
from itertools import combinations
from pathlib import Path


def load(path, field):
    d = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            # run_eval writes one row per (id, target); keying by id alone kept only one language.
            key = f"{r['id']}|{r['target']}" if "target" in r else r["id"]
            d[key] = r[field] or ""
    return d


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--runs", nargs=3, required=True)
    p.add_argument("--rates", nargs=3, type=float, help="نسبة الأخطاء لكل تشغيل")
    p.add_argument("--field", default="output")
    p.add_argument("--outdir", default="eval/results")
    a = p.parse_args()

    runs = [load(r, a.field) for r in a.runs]
    ids = sorted(set(runs[0]) & set(runs[1]) & set(runs[2]))
    if not ids:
        raise SystemExit("خطأ: لا توجد مقاطع مشتركة بين ملفات التشغيل الثلاثة")
    if len(ids) != len(runs[0]):
        print(f"تنبيه: المقاطع المشتركة {len(ids)} فقط، تأكدي أن الملفات الثلاثة كاملة")

    unstable, sims = [], []
    identical = 0
    for i in ids:
        outs = [r[i] for r in runs]
        if len(set(outs)) == 1:
            identical += 1
        else:
            s = min(SequenceMatcher(None, x, y).ratio() for x, y in combinations(outs, 2))
            unstable.append([i, f"{s:.2f}"] + outs)
        sims += [SequenceMatcher(None, x, y).ratio() for x, y in combinations([r[i] for r in runs], 2)]

    lines = [f"المقاطع: {len(ids)}",
             f"ناتج متطابق حرفيًا في التشغيلات الثلاثة: {identical} ({identical / len(ids):.1%})",
             f"متوسط التشابه النصي بين أي تشغيلين: {st.mean(sims):.3f}",
             f"مقاطع اختلف ناتجها: {len(unstable)}"]
    if a.rates:
        m, sd = st.mean(a.rates), st.stdev(a.rates)
        lines.append(f"نسبة الأخطاء: المتوسط {m:.3f} | الانحراف المعياري {sd:.3f}")

    out = Path(a.outdir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "stability.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    with open(out / "unstable_segments.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "min_similarity", "run1", "run2", "run3"])
        w.writerows(sorted(unstable, key=lambda r: float(r[1])))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
