#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""فحص ملفات المسرد data/glossary/*.json وفق data/glossary/SCHEMA.md

الاستخدام:
    python3 scripts/validate_glossary.py [مجلد المسرد]
    python3 scripts/validate_glossary.py --require-approved        # يفشل إن قلّ المعتمد (en) عن 100
    python3 scripts/validate_glossary.py --require-approved --min-approved 120    # حدّ آخر
يخرج برمز 1 إن وُجدت أخطاء.

القواعد:
- الحقول بالضبط كما في SCHEMA.md.
- strategy: keep_and_gloss | translate | context
- status لكل لغة: verified | draft
- verified يتطلب: مصدرًا مكتوبًا (source.name و source.ref) + reviewed_by فيه اسم المراجع وتاريخ (YYYY-MM-DD).
- keep_and_gloss و context تتطلب gloss.
- context تتطلب قائمة avoid.
- لا يتكرر id ولا المصطلح العربي عبر كل الملفات.
قواعد مراجعة الفريق (2026-10-02):
- gloss غير فارغ في كل اللغات، لكل الاستراتيجيات.
- avoid كلمات فقط بلا أقواس؛ سبب التجنب يُكتب في usage_note_ar.
- preferred بحرف صغير إلا أسماء العلم (قائمة PROPER).
- المتغيرات بلا أقواس، ولا تتضمن أسماء الله الحسنى ولا أضداد المصطلح، ولا تتكرر بين مصطلحين، ولا تساوي مصطلحًا آخر.
- إذا اختلف en.preferred عن مقابل الجمهرة يجب ذكر «سبب الاختلاف عن الجمهرة» في usage_note_ar.
"""
import json, sys, re, glob, os
from collections import Counter

import argparse
ap = argparse.ArgumentParser(description="فحص ملفات المسرد وفق data/glossary/SCHEMA.md وقواعد المراجعة")
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ap.add_argument("dir", nargs="?", default=os.path.join(REPO, "data", "glossary"), help="مجلد المسرد (الافتراضي data/glossary في المستودع)")
ap.add_argument("--require-approved", action="store_true",
                help="يفشل الفحص إن قلّ عدد المصطلحات المعتمدة (status.en=verified بمراجع مسمّى وتاريخ) عن --min-approved")
ap.add_argument("--min-approved", type=int, default=100, metavar="N", help="الحد الأدنى للمعتمد مع --require-approved (الافتراضي 100)")
ARGS = ap.parse_args()
DIR = ARGS.dir
KEYS = ["id", "ar", "variants_ar", "en", "fr", "usage_note_ar", "strategy", "source", "status", "reviewed_by"]
LANG_KEYS = {"preferred", "gloss", "avoid"}
STRATEGIES = {"keep_and_gloss", "translate", "context"}
STATUSES = {"verified", "draft"}
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
ID = re.compile(r"^[a-z0-9_]+$")

errors, warnings, entries = [], [], []
PROPER = ("Allah", "Islam", "Ramadan", "Qur'an", "'Arafat", "Arafat", "Ka'bah", "Coran", "'Arafât", "Ka'ba", "Kaaba",
          # أعلام وأسماء أماكن وكتب وفرق (توسعة 500)
          "Khawarij", "Khawârij", "Mu'tazila", "Murji'ah", "Dajjal", "Dajjâl", "Gog", "Torah", "Gospel", "Évangile",
          "Psalms", "Psaumes", "Satan", "Kawthar", "Michael", "Michaël", "Friday", "Eid", "Dhuhr", "Makkan", "Uthmani",
          "Prophet's", "Ansar", "Ansâr", "Mothers of the Believers", "Mères des croyants", "Israelite", "Ha-Mim",
          "Night of Power", "Nuit du Destin", "Muzdalifah", "Sacred Mosque", "Mosquée", "Aqsa", "Zamzam", "Black Stone",
          "Station of Abraham")
TASH = re.compile(r"[\u064B-\u0652\u0670]")
def bare(s): return TASH.sub("", s or "")
DIVINE_NAMES = {"الحكيم", "الحي", "الحيي", "المتكبر", "المؤمن", "المحسن", "الجامع", "الملك", "ملك", "الرحمن", "الرحيم", "العليم",
                "السميع", "البصير", "القدوس", "السلام", "العزيز", "الجبار", "الخالق", "الرزاق", "الوهاب", "الغفور", "الودود",
                "الشهيد", "الحق", "الوكيل", "القوي", "الولي", "الحميد", "الكريم", "اللطيف", "الخبير", "الحليم", "العظيم",
                "الكبير", "العدل", "عدل", "البر", "الهادي", "النور", "التواب", "العفو", "الرؤوف", "الغني", "الواحد", "الأحد", "الصمد", "القيوم", "الأمين"}
def err(f, r, m): errors.append(f"{os.path.basename(f)} › {r.get('id', '?')}: {m}")
def warn(f, r, m): warnings.append(f"{os.path.basename(f)} › {r.get('id', '?')}: {m}")

def reviewers(rb):
    if rb is None: return []
    if isinstance(rb, dict): return [rb]
    if isinstance(rb, list): return [x for x in rb if isinstance(x, dict)]
    return [{"name": rb}] if isinstance(rb, str) else []

files = sorted(glob.glob(os.path.join(DIR, "*.json")))
if not files: sys.exit(f"لا توجد ملفات JSON في {DIR}")
for f in files:
    try:
        data = json.load(open(f, encoding="utf-8"))
    except Exception as e:
        errors.append(f"{f}: JSON غير صالح — {e}"); continue
    if not isinstance(data, list):
        errors.append(f"{f}: يجب أن يكون الملف مصفوفة"); continue
    for r in data:
        if not isinstance(r, dict):
            errors.append(f"{os.path.basename(f)}: عنصر ليس كائنًا JSON: {str(r)[:40]}"); continue
        if not isinstance(r.get("variants_ar"), list):
            err(f, r, "variants_ar يجب أن تكون قائمة"); r = {**r, "variants_ar": []}
        for lang in ("en", "fr"):
            L0 = r.get(lang)
            if isinstance(L0, dict) and set(L0) == LANG_KEYS and not (isinstance(L0["preferred"], str) and isinstance(L0["gloss"], str) and isinstance(L0["avoid"], list)):
                err(f, r, f"{lang}: preferred و gloss نصوص، و avoid قائمة")
                r = {**r, lang: None}
        entries.append((f, r))
        missing = [k for k in KEYS if k not in r]; extra = [k for k in r if k not in KEYS]
        if missing: err(f, r, f"حقول ناقصة: {missing}")
        if extra: warn(f, r, f"حقول غير موجودة في الصيغة: {extra}")
        if not ID.match(str(r.get("id", ""))): err(f, r, "id يجب أن يكون حروفًا إنجليزية صغيرة وأرقامًا و _")
        if not r.get("ar"): err(f, r, "ar فارغ")
        strat = r.get("strategy")
        if strat not in STRATEGIES: err(f, r, f"strategy غير صالحة: {strat}")
        src = r.get("source") or {}
        has_source = bool(src.get("name")) and bool(src.get("ref"))
        if not has_source: err(f, r, "بلا مصدر مكتوب (source.name / source.ref)")
        if src.get("retrieved") and not DATE.match(src["retrieved"]): err(f, r, "source.retrieved ليس بصيغة YYYY-MM-DD")
        revs = reviewers(r.get("reviewed_by"))
        named_dated = any(x.get("name") and DATE.match(str(x.get("date", ""))) for x in revs)
        for lang in ("en", "fr"):
            L = r.get(lang)
            if not isinstance(L, dict) or set(L) != LANG_KEYS:
                err(f, r, f"{lang} يجب أن يحتوي preferred و gloss و avoid فقط"); continue
            if not L["preferred"]: err(f, r, f"{lang}.preferred فارغ")
            if strat in ("keep_and_gloss", "context") and not L["gloss"]: err(f, r, f"{lang}.gloss مطلوب مع {strat}")
            if strat == "context" and not L["avoid"]: err(f, r, f"{lang}.avoid مطلوبة مع context")
            if not L["avoid"]: warn(f, r, f"{lang}.avoid فارغة — طبقة التحقق لن تكشف خطأ")
            if not L["gloss"].strip(): err(f, r, f"{lang}.gloss فارغ")
            elif len(L["gloss"].split()) < 3: err(f, r, f"{lang}.gloss قصير جدًا (نقل صوتي فقط؟): {L['gloss']}")
            if re.match(r"^(the |le |la |les |l'|al-|as-|an-|ar-|at-|ad-)", L["preferred"]): err(f, r, f"{lang}.preferred يبدأ بأداة تعريف: {L['preferred']}")
            for a in L["avoid"]:
                if "(" in a or ")" in a: err(f, r, f"{lang}.avoid فيها أقواس: {a} — انقلي الشرح إلى usage_note_ar")
            p0 = L["preferred"]
            body = re.sub(r"^(l'|le |la |les |the )", "", p0)
            if body[:1].isupper() and not body.startswith(PROPER): err(f, r, f"{lang}.preferred يجب أن يبدأ بحرف صغير: {p0}")
            pref = L["preferred"].strip().lower()
            for a in L["avoid"]:
                if re.sub(r"\s*\(.*?\)", "", a).strip().lower() == pref:
                    err(f, r, f"{lang}.avoid تحتوي الصيغة المفضلة نفسها: {a}")
            st = (r.get("status") or {}).get(lang)
            if st not in STATUSES: err(f, r, f"status.{lang} غير صالحة: {st}")
            if st == "verified":
                if not has_source: err(f, r, f"status.{lang}=verified بلا مصدر مكتوب — ممنوع")
                if not named_dated: err(f, r, f"status.{lang}=verified بلا مراجع مسمّى وتاريخ في reviewed_by — ممنوع")

ars_all = {r.get("ar") for _, r in entries}
for f, r in entries:
    for v in r.get("variants_ar", []):
        if "(" in v: err(f, r, f"متغير فيه أقواس: {v}")
        if bare(v) in DIVINE_NAMES: err(f, r, f"متغير من أسماء الله الحسنى أو ألقاب الأعلام: {v}")
        if v.startswith("عقوق") or "(ضده)" in v: err(f, r, f"متغير هو ضد المصطلح: {v}")
    m = re.search(r"في الجمهرة: EN «(.*?)»", str(r.get("usage_note_ar") or ""))
    if m:
        n = lambda z: re.sub(r"[^a-z]", "", z.lower().translate(str.maketrans("āīūḥṣḍṭẓʿʾ", "aiuhsdtz''")).replace("the ", "").replace("al-", "").replace("as-", ""))
        if not isinstance(r.get("en"), dict): continue
        j, p = n(m.group(1)), n(r["en"]["preferred"])
        if p != j and "سبب الاختلاف" not in r["usage_note_ar"]:
            err(f, r, f"المقابل «{r['en']['preferred']}» يختلف عن الجمهرة «{m.group(1)}» بلا سبب مكتوب")
var_owner = {}
for f, r in entries:
    seen_b = set()
    for v in r.get("variants_ar", []):
        if bare(v) in seen_b or bare(v) == bare(r.get("ar")): err(f, r, f"متغير مكرر داخل المصطلح نفسه أو يساويه: {v}")
        seen_b.add(bare(v)); var_owner.setdefault(bare(v), []).append(r.get("ar"))
for f, r in entries:
    for v in r.get("variants_ar", []):
        if len(var_owner[bare(v)]) > 1: err(f, r, f"المتغير «{v}» مكرر في: {var_owner[bare(v)]}")
        if bare(v) in {bare(a) for a in ars_all} and bare(v) != bare(r.get("ar")): err(f, r, f"المتغير «{v}» مصطلح مستقل في المسرد")

ids = Counter(r.get("id") for _, r in entries)
ars = Counter(r.get("ar") for _, r in entries)
for f, r in entries:
    if ids[r.get("id")] > 1: err(f, r, "id مكرر عبر الملفات")
    if ars[r.get("ar")] > 1: err(f, r, "المصطلح العربي مكرر عبر الملفات")

total = len(entries)
def approved(r, lang):
    ok = any(x.get("name") and DATE.match(str(x.get("date", ""))) for x in reviewers(r.get("reviewed_by")))
    return (r.get("status") or {}).get(lang) == "verified" and ok
ver_en = sum(approved(r, "en") for _, r in entries)
ver_fr = sum(approved(r, "fr") for _, r in entries)
print(f"الملفات: {len(files)} · المصطلحات: {total}")
for f in files:
    print(f"  {os.path.basename(f)}: {sum(1 for ff, _ in entries if ff == f)}")
print(f"معتمد (en): {ver_en} · معتمد (fr): {ver_fr} · المتبقي لهدف 100 (en): {max(0, 100 - ver_en)}")
for w in warnings: print("⚠️ ", w)
for e in errors: print("❌ ", e)
if ARGS.require_approved and ver_en < ARGS.min_approved:
    errors.append(f"--require-approved: المعتمد (en) {ver_en} أقل من {ARGS.min_approved}")
    print(f"❌  المعتمد (en) {ver_en} أقل من المطلوب {ARGS.min_approved}")
print("✅ لا أخطاء" if not errors else f"❌ {len(errors)} خطأ")
sys.exit(1 if errors else 0)
