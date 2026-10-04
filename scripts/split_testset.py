#!/usr/bin/env python3
"""
أداة مجموعة اختبار مُوطِّن: التحقق من الصيغة، والتقسيم إلى dev (~30%) و test (~70%) لكل فئة على حدة.

    python3 scripts/split_testset.py validate data/testset/testset.jsonl
    python3 scripts/split_testset.py split --input data/testset/testset.jsonl \\
        --input data/testset/official_scenarios.jsonl --force
    python3 scripts/split_testset.py add data/testset/official_scenarios.jsonl

split يعيد التقسيم كله، فلا يُستعمل بعد بدء التطوير على dev، ولا يكتب فوق test.jsonl إلا مع --force
(ولا يُستعمل --force بعد تجميد المجموعة بوسم testset-v1).
add يضيف حالات جديدة دون المساس بالتقسيم الموجود: حالات dev التي طُوِّر عليها تبقى في dev (D-040)،
وتُقسَم الحالات الجديدة وحدها لكل فئة بالنسبة والبذرة نفسيهما. يتحقق أولًا أن test.jsonl يطابق test.sha256.
الأمران يكتبان testset.jsonl (الكل) و dev.jsonl و test.jsonl و split.json و test.sha256 في --out.
التقييم الأعمى في scripts/blind_eval.py، والدرجات في scripts/score_eval.py.
"""
import argparse
import hashlib
import json
import random
import re
from collections import Counter, defaultdict
from pathlib import Path

SEED = 20261004  # مطابقة لـ split.json
DEV_RATIO = 0.3
CATEGORIES = {
    "term_critical", "quran_quote", "quran_misquote", "hadith_quote",
    "hadith_unsourced", "cultural", "level_d", "mixed",
}
REQUIRED = ["id", "category", "level", "text_ar", "targets", "expect", "source", "notes"]
EXPECT_KEYS = ["terms", "quran_refs", "hadith_refs", "must_flag", "must_refer"]
SOURCE_TYPES = {"team_authored", "verified_quran", "verified_hadith", "synthetic_benchmark", "scientific_reference"}
QURAN_REF = re.compile(r"^(\d{1,3}):(\d{1,3})(?:-(\d{1,3}))?$")  # 2:153 أو 65:2-3
# عدد آيات كل سورة (114 سورة، المجموع 6236)
AYAH_COUNTS = [7, 286, 200, 176, 120, 165, 206, 75, 129, 109, 123, 111, 43, 52, 99, 128, 111, 110, 98, 135, 112, 78, 118, 64, 77, 227, 93, 88, 69, 60, 34, 30, 73, 54, 45, 83, 182, 88, 75, 85, 54, 53, 89, 59, 37, 35, 38, 29, 18, 45, 60, 49, 62, 55, 78, 96, 29, 22, 24, 13, 14, 11, 11, 18, 12, 12, 30, 52, 52, 44, 28, 28, 20, 56, 40, 31, 50, 40, 46, 42, 29, 19, 36, 25, 22, 17, 19, 26, 30, 20, 15, 21, 11, 8, 8, 19, 5, 8, 8, 11, 11, 8, 3, 9, 5, 4, 7, 3, 6, 3, 5, 4, 5, 6]
HADITH_COLLECTIONS = {"bukhari", "muslim", "abudawud", "tirmidhi", "nasai", "ibnmajah", "ahmad", "malik"}


def load(path):
    """JSONL -> list of dicts (blank lines skipped)."""
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def dump(rows):
    """list of dicts -> JSONL text (one object per line, ending with a newline)."""
    return "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)


def _quran_ref_problem(ref):
    m = QURAN_REF.match(str(ref))
    if not m:
        return f"مرجع قرآني بصيغة غير صالحة «{ref}» (الصيغة 2:153 أو 65:2-3)"
    s, a = int(m.group(1)), int(m.group(2))
    b = int(m.group(3)) if m.group(3) else a
    if not (1 <= s <= 114 and 1 <= a <= b <= AYAH_COUNTS[s - 1]):
        return f"المرجع «{ref}» خارج النطاق"
    return None


def problems(rows):
    """قائمة بمشكلات الصيغة؛ فارغة = سليمة."""
    bad = []
    ids = Counter(r.get("id") for r in rows)
    for r in rows:
        i = r.get("id")
        missing = [k for k in REQUIRED if k not in r]
        if missing:
            bad.append(f"{i}: حقول ناقصة {missing}")
            continue
        if ids[i] > 1:
            bad.append(f"{i}: id مكرر")
        if r["category"] not in CATEGORIES:
            bad.append(f"{i}: فئة غير معروفة {r['category']}")
        if r["level"] not in ("A", "B", "C", "D"):
            bad.append(f"{i}: level يجب أن يكون A أو B أو C أو D")
        if not str(r["text_ar"]).strip():
            bad.append(f"{i}: text_ar فارغ")
        if not r["targets"] or not set(r["targets"]) <= {"en", "fr"}:
            bad.append(f"{i}: targets يجب أن تكون en و/أو fr")
        src = r["source"]
        if not isinstance(src, dict) or not src.get("name") or not src.get("ref"):
            bad.append(f"{i}: source يحتاج name و ref")
        elif "source_type" in src and src["source_type"] not in SOURCE_TYPES:
            # اختياري: الحالات القديمة (testset.seed) لا تحمله، ويُفحص متى وُجد
            bad.append(f"{i}: source.source_type يجب أن يكون واحدًا من {sorted(SOURCE_TYPES)}")
        ex = r["expect"]
        if not isinstance(ex, dict) or any(k not in ex for k in EXPECT_KEYS):
            bad.append(f"{i}: expect يجب أن يحتوي {EXPECT_KEYS}")
            continue
        for k in ("terms", "quran_refs", "hadith_refs"):
            if not isinstance(ex[k], list):
                bad.append(f"{i}: expect.{k} يجب أن تكون قائمة")
        if not (isinstance(ex["must_flag"], bool) and isinstance(ex["must_refer"], bool)):
            bad.append(f"{i}: must_flag و must_refer يجب أن تكون true/false")
            continue
        for q in ex["quran_refs"] if isinstance(ex["quran_refs"], list) else []:
            if (msg := _quran_ref_problem(q)):
                bad.append(f"{i}: {msg}")
        for h in ex["hadith_refs"] if isinstance(ex["hadith_refs"], list) else []:
            coll, _, num = str(h).partition(":")
            if coll not in HADITH_COLLECTIONS or not num:
                bad.append(f"{i}: مرجع حديث غير صالح «{h}» (الصيغة bukhari:1234)")
        if r["category"] == "level_d" and not ex["must_refer"]:
            bad.append(f"{i}: level_d يجب أن تكون must_refer=true")
        if r["category"] in ("quran_misquote", "hadith_unsourced") and not ex["must_flag"]:
            bad.append(f"{i}: {r['category']} يجب أن تكون must_flag=true")
    return bad


def cmd_validate(a):
    rows = load(a.testset)
    bad = problems(rows)
    counts = Counter(r.get("category") for r in rows)
    print(f"{len(rows)} حالة")
    for cat in sorted(counts, key=str):
        print(f"  {cat!s:<20}{counts[cat]:>4}")
    if bad:
        print("PROBLEMS:\n  " + "\n  ".join(bad))  # الاختبارات تبحث عن PROBLEMS
        raise SystemExit(1)
    print("OK")


def assign(rows, field="category"):
    """id -> "dev"/"test", per category, with the fixed seed and ratio (prints the table)."""
    by_cat = defaultdict(list)
    for r in rows:
        by_cat[r[field]].append(r)
    rng = random.Random(SEED)
    split = {}
    print(f"{'الفئة':<20}{'الكل':>6}{'dev':>6}{'test':>6}")
    for cat in sorted(by_cat):
        items = sorted(by_cat[cat], key=lambda r: r["id"])  # ترتيب ثابت قبل الخلط
        rng.shuffle(items)
        n = len(items)
        n_dev = round(n * DEV_RATIO)
        if n >= 2:
            n_dev = max(1, min(n_dev, n - 1))  # واحد على الأقل في كل جهة
        else:
            n_dev = 0
            print(f"تنبيه: الفئة {cat} فيها مقطع واحد فقط، ذهب إلى test")
        for i, r in enumerate(items):
            split[r["id"]] = "dev" if i < n_dev else "test"
        print(f"{cat:<20}{n:>6}{n_dev:>6}{n - n_dev:>6}")
    return split


def write(out, rows, split):
    """testset/dev/test in the input order, split.json and the checksum of test."""
    out.mkdir(parents=True, exist_ok=True)
    # نحافظ على ترتيب الملف الأصلي في المخرجات
    dev = [r for r in rows if split[r["id"]] == "dev"]
    test = [r for r in rows if split[r["id"]] == "test"]
    (out / "testset.jsonl").write_text(dump(rows), encoding="utf-8")
    (out / "dev.jsonl").write_text(dump(dev), encoding="utf-8")
    (out / "test.jsonl").write_text(dump(test), encoding="utf-8")
    (out / "split.json").write_text(
        json.dumps({"seed": SEED, "dev_ratio": DEV_RATIO, "split": split}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    digest = hashlib.sha256((out / "test.jsonl").read_bytes()).hexdigest()
    (out / "test.sha256").write_text(digest + "  test.jsonl\n", encoding="utf-8")

    print(f"\nالمجموع: {len(rows)} | dev={len(dev)} | test={len(test)}")
    print(f"sha256 لملف test: {digest}")


def cmd_add(a):
    out = Path(a.out)
    test_path = out / "test.jsonl"
    expected = (out / "test.sha256").read_text(encoding="utf-8").split()[0]
    if hashlib.sha256(test_path.read_bytes()).hexdigest() != expected:
        raise SystemExit("test.jsonl لا يطابق test.sha256؛ توقفت دون تغيير.")
    old_rows = load(out / "testset.jsonl")
    dev_ids = {r["id"] for r in load(out / "dev.jsonl")}
    test_ids = {r["id"] for r in load(test_path)}
    if dev_ids & test_ids or dev_ids | test_ids != {r["id"] for r in old_rows}:
        raise SystemExit("testset.jsonl لا يساوي dev + test؛ توقفت دون تغيير.")
    new_rows = load(a.new)
    bad = problems(old_rows + new_rows)
    if bad:
        raise SystemExit("خطأ في الصيغة، لم يُضَف شيء:\n  " + "\n  ".join(bad[:20]))
    split = {r["id"]: ("dev" if r["id"] in dev_ids else "test") for r in old_rows}
    print("الحالات الجديدة فقط:")
    new_split = assign(new_rows, a.field)
    # Existing files keep their bytes; the new cases are appended, so the diff shows only them.
    for name, rows in (
        ("testset.jsonl", new_rows),
        ("dev.jsonl", [r for r in new_rows if new_split[r["id"]] == "dev"]),
        ("test.jsonl", [r for r in new_rows if new_split[r["id"]] == "test"]),
    ):
        path = out / name
        text = path.read_text(encoding="utf-8")
        path.write_text(text + ("" if not text or text.endswith("\n") else "\n") + dump(rows), encoding="utf-8")
    split |= new_split
    (out / "split.json").write_text(
        json.dumps({"seed": SEED, "dev_ratio": DEV_RATIO, "split": split}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    digest = hashlib.sha256(test_path.read_bytes()).hexdigest()
    (out / "test.sha256").write_text(digest + "  test.jsonl\n", encoding="utf-8")
    n_dev = sum(v == "dev" for v in split.values())
    print(f"\nالمجموع: {len(split)} | dev={n_dev} | test={len(split) - n_dev}")
    print(f"sha256 لملف test: {digest}")
    print("التالي: أنشئي الإصدار testset-v1 بعد تأكيد الفريق، ثم لا تعيدي التقسيم.")


def cmd_split(a):
    out = Path(a.out)
    if (out / "test.jsonl").exists() and not a.force:
        raise SystemExit("test.jsonl موجود (مجمّد؟). استعملي --force فقط قبل التجميد.")
    rows = [r for path in a.input for r in load(path)]
    bad = problems(rows)
    if bad:
        raise SystemExit("خطأ في الصيغة، لم يُقسَّم شيء:\n  " + "\n  ".join(bad[:20]))

    write(out, rows, assign(rows, a.field))
    print("التالي: أنشئي الإصدار testset-v1 بعد تأكيد الفريق، ثم لا تعيدي التقسيم.")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    s = p.add_subparsers(dest="cmd", required=True)
    v = s.add_parser("validate", help="تحقق من صيغة ملف JSONL")
    v.add_argument("testset")
    v.set_defaults(f=cmd_validate)
    sp = s.add_parser("split", help="قسّم إلى dev و test")
    sp.add_argument("--input", action="append", help="ملف JSONL؛ كرّريه لدمج أكثر من ملف (الافتراضي testset.jsonl)")
    sp.add_argument("--field", default="category", help="اسم حقل الفئة في JSONL")
    sp.add_argument("--out", default="data/testset")
    sp.add_argument("--force", action="store_true", help="اكتبي فوق test.jsonl الموجود (قبل التجميد فقط)")
    sp.set_defaults(f=cmd_split)
    ad = s.add_parser("add", help="أضيفي حالات جديدة دون إعادة تقسيم الموجود")
    ad.add_argument("new")
    ad.add_argument("--field", default="category", help="اسم حقل الفئة في JSONL")
    ad.add_argument("--out", default="data/testset")
    ad.set_defaults(f=cmd_add)
    a = p.parse_args()
    if a.cmd == "split" and not a.input:
        a.input = ["data/testset/testset.jsonl"]
    a.f(a)


if __name__ == "__main__":
    main()
