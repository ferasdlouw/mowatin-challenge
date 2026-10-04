"""
حساب الاتفاق بين المصحّحَين وعدّ الأخطاء حسب الفئات الخمس. يُشغَّل مرة لكل لغة.
"""
import argparse
import csv
import json
import statistics as st
from collections import Counter, defaultdict
from pathlib import Path

CODE2CAT = {"E1": "quran", "E2": "hadith", "E3": "term", "E4": "ruling", "E5": "referral"}
CATS = ["quran", "hadith", "term", "ruling", "referral"]
SYSTEMS = ["mt", "llm", "mowatin"]  # = معرّفات KEY.json و summary.json


def read(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return {r["id"]: r for r in csv.DictReader(f)}


def code(v):
    return (v or "").strip().upper() or "OK"


def num(v, where):
    v = (v or "").strip()
    if not v:
        return None
    try:
        x = float(v)
    except ValueError:
        raise SystemExit(f"{where}: درجة غير رقمية '{v}'")
    if not 1 <= x <= 5:
        raise SystemExit(f"{where}: الدرجة {x} خارج 1..5")
    return x


def kappa(x, y):
    n = len(x)
    po = sum(a == b for a, b in zip(x, y)) / n
    cx, cy = Counter(x), Counter(y)
    pe = sum(cx[k] * cy[k] for k in set(cx) | set(cy)) / (n * n)
    return po, (1.0 if pe == 1 else (po - pe) / (1 - pe))


def validate(rows, name):
    bad = []
    for i, r in rows.items():
        for L in "ABC":
            c = code(r[f"{L}_error"])
            if c != "OK" and c not in CODE2CAT:
                bad.append(f"{name} {i} {L}: '{c}'")
            for k in ("meaning", "clarity"):
                num(r.get(f"{L}_{k}"), f"{name} {i} {L}_{k}")
    return bad


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--lang", default="en")
    p.add_argument("--r1-shared", required=True)
    p.add_argument("--r2-shared", required=True)
    p.add_argument("--r1-rest")
    p.add_argument("--key")
    p.add_argument("--test")
    p.add_argument("--outdir", default="eval/results")
    a = p.parse_args()

    key = json.loads(Path(a.key or f"eval/blind/{a.lang}/KEY.json").read_text(encoding="utf-8"))["key"]
    r1, r2 = read(a.r1_shared), read(a.r2_shared)
    rest = read(a.r1_rest) if a.r1_rest else {}
    bad = validate(r1, "r1") + validate(r2, "r2") + validate(rest, "rest")
    if bad:
        raise SystemExit("رموز أخطاء غير معروفة (المسموح E1..E5 أو فارغ):\n  " + "\n  ".join(bad[:15]))
    ids = sorted(set(r1) & set(r2))
    if not ids:
        raise SystemExit("ما في مقاطع مشتركة بين الملفين")

    # ---- الاتفاق: وحدة التقييم = مقطع × نظام ----
    pairs = [(code(r1[i][f"{L}_error"]), code(r2[i][f"{L}_error"]), key[i][L], i, L) for i in ids for L in "ABC"]
    po_b, k_b = kappa(["OK" if x == "OK" else "ERR" for x, *_ in pairs], ["OK" if y == "OK" else "ERR" for _, y, *_ in pairs])
    po_t, k_t = kappa([x for x, *_ in pairs], [y for _, y, *_ in pairs])
    lines = [f"اللغة: {a.lang} | عدد المقاطع المشتركة: {len(ids)} ({len(pairs)} حكمًا لكل مصحح)",
             f"اتفاق صحيح/خطأ: {po_b:.1%} | kappa = {k_b:.2f}",
             f"اتفاق نوع الخطأ: {po_t:.1%} | kappa = {k_t:.2f}"]

    # ---- العدّ: المشترك بحكم المصحح 1 (بعد حسم الخلافات)، ثم باقي المقاطع ----
    final = dict(r1)
    for i, r in rest.items():
        final.setdefault(i, r)
    seg, errs = Counter(), defaultdict(Counter)
    sums = {k: defaultdict(lambda: [0.0, 0]) for k in ("meaning", "clarity")}
    for i, r in final.items():
        for L in "ABC":
            s = key[i][L]
            seg[s] += 1
            c = code(r[f"{L}_error"])
            if c != "OK":
                errs[s][CODE2CAT[c]] += 1
            for k in ("meaning", "clarity"):
                vals = [num(r.get(f"{L}_{k}"), "")]
                if i in r2:
                    vals.append(num(r2[i].get(f"{L}_{k}"), ""))
                vals = [v for v in vals if v is not None]
                if vals:
                    sums[k][s][0] += st.mean(vals)
                    sums[k][s][1] += 1

    out = Path(a.outdir) / a.lang
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "error_table.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["system", "segments", "errors", "errors_per_100"] + CATS)
        for s in SYSTEMS:
            e = sum(errs[s].values())
            w.writerow([s, seg[s], e, f"{100 * e / seg[s]:.1f}" if seg[s] else ""] + [errs[s][c] for c in CATS])
    with open(out / "disagreements.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "label", "rater1", "rater2"])
        w.writerows([i, L, x, y] for x, y, s, i, L in pairs if x != y)
    if a.test:
        cats = {}
        for l in Path(a.test).read_text(encoding="utf-8").splitlines():
            if l.strip():
                r = json.loads(l)
                cats[r["id"]] = r["category"]
        agg = defaultdict(lambda: [0, 0])
        for i, r in final.items():
            for L in "ABC":
                k = (cats.get(i, "?"), key[i][L])
                agg[k][1] += 1
                agg[k][0] += code(r[f"{L}_error"]) != "OK"
        with open(out / "error_by_category.csv", "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(["category", "system", "segments", "errors", "error_rate"])
            w.writerows([c, s, n, e, f"{e / n:.3f}"] for (c, s), (e, n) in sorted(agg.items()))
    (out / "agreement.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (out / "scores.json").write_text(json.dumps({
        "lang": a.lang, "shared_n": len(ids),
        "kappa_type": k_t, "kappa_binary": k_b, "agree_type": po_t, "agree_binary": po_b,
        "type_pairs": [[x, y] for x, y, *_ in pairs],
        "systems": {s: {"segments": seg[s], "errors": {c: errs[s][c] for c in CATS},
                        **{f"{k}_sum": sums[k][s][0] for k in sums}, **{f"{k}_n": sums[k][s][1] for k in sums}}
                    for s in SYSTEMS}}, ensure_ascii=False, indent=1), encoding="utf-8")

    print("\n".join(lines))
    print(f"عدد الخلافات: {sum(x != y for x, y, *_ in pairs)} (راجعيها في {out}/disagreements.csv)")
    for s in SYSTEMS:
        e = sum(errs[s].values())
        print(f"{s:<8} أخطاء {e}/{seg[s]}  " + " ".join(f"{c}={errs[s][c]}" for c in CATS))


if __name__ == "__main__":
    main()
