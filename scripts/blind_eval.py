#!/usr/bin/env python3
"""
إخفاء أسماء الأنظمة (A/B/C) وتوليد أوراق التقييم الأعمى. يُشغَّل مرة لكل لغة.

التشغيل (من جذر المشروع)، بملفات run_eval.py:
    python scripts/blind_eval.py --lang en --i-confirm-frozen \
        --mt      eval/results/runs/gt_run1.jsonl \
        --llm     eval/results/runs/raw_run1.jsonl \
        --mowatin eval/results/runs/mowatten_run1.jsonl
    python scripts/blind_eval.py --lang fr --i-confirm-frozen  (بنفس الملفات)

معرّفات الأنظمة مطابقة لـ summary.json: mt (Google) وllm (النموذج بلا مُوطِّن) وmowatin.
الإدخال: JSONL من run_eval.py، صف لكل (id, target): {id, target, output, segments}.
يُقيَّم فقط ما في data/testset/test.jsonl وهدفه يشمل --lang؛ أي مقطع من dev يُتجاهل مع تنبيه.
مجموعة test مختومة: لا تُقرأ إلا مع --i-confirm-frozen وبعد مطابقة test.sha256 (كما في run_eval.py).

المخرجات في eval/blind/<lang>/:
    shared_sample.csv : العينة المشتركة (30 مقطعًا) يقيّمها الشخصان معًا
    rest.csv          : باقي مقاطع test
    KEY.json          : مفتاح فك الإخفاء، لا يراه المصححون ولا يُرفع إلى git

أعمدة التقييم لكل نظام X من A/B/C:
    X_error   : فارغ = صحيحة، وإلا E1..E5 (انظري ERROR_TAXONOMY.md)
    X_meaning : الحفاظ على الجوهر من 1 إلى 5
    X_clarity : الوضوح والملاءمة الثقافية من 1 إلى 5
"""
import argparse
import csv
import json
import random
from pathlib import Path

from run_eval import resolve_split

TESTSET_DIR = Path(__file__).resolve().parent.parent / "data" / "testset"
SEED = 20261005
SHARED_N = 30
SYSTEMS = ["mt", "llm", "mowatin"]  # = eval/results/summary.json system ids
# نص محايد عمدًا: لا يذكر "إحالة" ولا "إيقاف" حتى لا يوحي بنوع النظام ولا يوجّه حكم المصحح.
NO_OUTPUT = "(لا يوجد ناتج)"


def load(path, field, lang, name):
    """id -> output in ``lang``. run_eval writes one row per (id, target): rows of the other
    language are skipped, so an EN sheet never shows a FR answer.

    Empty output is ambiguous, so it is split by ``segments``:
      - segments present  -> the system withheld the answer (referral/block): a real result, shown.
      - no segments at all -> the API call failed (run_eval turns failures into empty rows):
        not a result. Stop and make the caller re-run those units.
    """
    out, failed, dup = {}, [], []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if r.get("target", lang) != lang:
            continue
        v = r[field]
        v = v.get(lang) if isinstance(v, dict) else v
        if (v or "").strip():
            text = v
        elif r.get("segments"):
            text = NO_OUTPUT
        else:
            failed.append(r["id"])
            continue
        if r["id"] in out:
            dup.append(r["id"])
        out[r["id"]] = text
    if dup:
        raise SystemExit(f"خطأ: {name} فيه id مكرر ({len(dup)}), مثل {dup[:3]}. هل دمجتِ ملفي تشغيلين؟")
    if failed:
        raise SystemExit(f"خطأ: {name} فيه {len(failed)} استدعاء فاشل (ناتج فارغ بلا segments): {failed[:5]}. "
                         "أعيدي تشغيل هذه المقاطع قبل التقييم.")
    return out


def source_path(test_arg, confirmed):
    """The sealed test set only with consent and a matching checksum, checked before it is read;
    any other file (a fixture, dev) as given."""
    path = Path(test_arg)
    if path.resolve() != (TESTSET_DIR / "test.jsonl").resolve():
        return path
    return resolve_split("test", confirmed, TESTSET_DIR)


def main(argv=None):
    p = argparse.ArgumentParser()
    for s in SYSTEMS:
        p.add_argument(f"--{s}", required=True)
    p.add_argument("--test", default=str(TESTSET_DIR / "test.jsonl"))
    p.add_argument("--i-confirm-frozen", action="store_true",
                   help="مطلوب لقراءة مجموعة test المختومة (التقييم الرسمي فقط)")
    p.add_argument("--field", default="output")
    p.add_argument("--source-field", default="text_ar", help="حقل النص العربي في test.jsonl")
    p.add_argument("--lang", default="en", help="اللغة الهدف المقيَّمة: en أو fr")
    p.add_argument("--outdir", help="الافتراضي eval/blind/<lang>")
    a = p.parse_args(argv)
    outdir = a.outdir or f"eval/blind/{a.lang}"
    test_path = source_path(a.test, a.i_confirm_frozen)

    outs = {s: load(getattr(a, s), a.field, a.lang, s) for s in SYSTEMS}
    test = [json.loads(l) for l in test_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    skipped = [r["id"] for r in test if a.lang not in r["targets"]]
    test = [r for r in test if a.lang in r["targets"]]
    ids = sorted(r["id"] for r in test)
    src = {r["id"]: r[a.source_field] for r in test}
    if skipped:
        print(f"تنبيه: استبعدت {len(skipped)} مقطعًا هدفه ليس {a.lang}: {skipped}")
    for s in SYSTEMS:
        extra = sorted(set(outs[s]) - set(ids) - set(skipped))
        if extra:
            print(f"تنبيه: النظام {s} فيه {len(extra)} مقطع ليس من test (تجاهلته)، مثل {extra[:3]}")
        missing = [i for i in ids if i not in outs[s]]
        if missing:
            raise SystemExit(f"خطأ: النظام {s} ناقص {len(missing)} مقطع ({a.lang})، مثل {missing[:3]}")

    rng = random.Random(SEED)
    key, rows = {}, {}
    for i in ids:
        perm = SYSTEMS[:]
        rng.shuffle(perm)  # ترتيب مختلف لكل مقطع
        key[i] = dict(zip("ABC", perm))
        rows[i] = {"id": i, "source_ar": src[i], **{L: outs[key[i][L]][i] for L in "ABC"},
                   **{f"{L}_{k}": "" for k in ("error", "meaning", "clarity") for L in "ABC"}, "notes": ""}

    shared = sorted(rng.sample(ids, min(SHARED_N, len(ids))))
    shared_set = set(shared)
    rest = [i for i in ids if i not in shared_set]
    rng.shuffle(shared)  # نخلط ترتيب العرض حتى لا يتبع ترتيب الفئات
    rng.shuffle(rest)

    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    cols = ["id", "source_ar", "A", "B", "C"] + [f"{L}_{k}" for k in ("error", "meaning", "clarity") for L in "ABC"] + ["notes"]
    for name, group in (("shared_sample", shared), ("rest", rest)):
        with open(out / f"{name}.csv", "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            w.writerows(rows[i] for i in group)
    (out / "KEY.json").write_text(
        json.dumps({"seed": SEED, "lang": a.lang, "shared": shared, "key": key}, ensure_ascii=False, indent=2),
        encoding="utf-8")

    print(f"تم ({a.lang}): shared={len(shared)} rest={len(rest)} في {out}/")
    print("تذكير: لا ترفعين KEY.json إلى git ولا ترسلينه للمصححين.")


if __name__ == "__main__":
    main()
