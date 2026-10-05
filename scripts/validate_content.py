"""Validate the content slots owned by the reliability lead (see data/CONTENT_SLOTS.md).

Usage: python3 scripts/validate_content.py            # all slots
       python3 scripts/validate_content.py --strict   # also fail on placeholder/draft status
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATUSES = {"placeholder", "draft", "verified"}
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
REF = re.compile(r"^(\d{1,3}):(\d{1,3})$")
AYAH_COUNTS = [7, 286, 200, 176, 120, 165, 206, 75, 129, 109, 123, 111, 43, 52, 99, 128, 111, 110, 98, 135, 112, 78, 118, 64, 77, 227, 93, 88, 69, 60, 34, 30, 73, 54, 45, 83, 182, 88, 75, 85, 54, 53, 89, 59, 37, 35, 38, 29, 18, 45, 60, 49, 62, 55, 78, 96, 29, 22, 24, 13, 14, 11, 11, 18, 12, 12, 30, 52, 52, 44, 28, 28, 20, 56, 40, 31, 50, 40, 46, 42, 29, 19, 36, 25, 22, 17, 19, 26, 30, 20, 15, 21, 11, 8, 8, 19, 5, 8, 8, 11, 11, 8, 3, 9, 5, 4, 7, 3, 6, 3, 5, 4, 5, 6]
COLLECTIONS = {"bukhari", "muslim", "abudawud", "tirmidhi", "nasai", "ibnmajah", "ahmad", "malik", "darimi", "other"}
KINDS = {"personal_ruling", "personal_context"}
MESSAGE_KEYS = {
    "quran_from_approved", "quran_mismatch", "quran_not_found", "quran_ambiguous", "quran_translation_pending",
    "quran_diacritized", "quran_tashkeel_mismatch", "hadith_identified", "hadith_partial",
    "hadith_sourced", "hadith_unsourced", "hadith_fabricated", "fatwa_referral", "low_confidence",
    "term_check_failed", "avoid_word_found", "provider_fallback", "compare_why_term", "compare_why_quran",
    "compare_why_hadith", "glossary_source", "text_too_long", "rate_limited", "validation_error",
    "general_error", "limit_reached", "injection_suspected", "raw_unprotected", "translation_unavailable",
}
PLACEHOLDERS = {
    "quran_mismatch": {"{correct_text}", "{ref}"}, "quran_ambiguous": {"{refs}", "{ref}"},
    "quran_diacritized": {"{verse}", "{ref}"}, "quran_tashkeel_mismatch": {"{verse}", "{ref}"}, "hadith_identified": {"{hadith}", "{ref}"},
    "hadith_fabricated": {"{ruling}"}, "term_check_failed": {"{term}"},
    "avoid_word_found": {"{term}", "{word}"}, "compare_why_term": {"{term}", "{word}"},
    "glossary_source": {"{term}"}, "text_too_long": {"{max_chars}"}, "rate_limited": {"{retry_after}"},
}


def load(rel, errors):
    try:
        return json.loads((ROOT / rel).read_text(encoding="utf-8"))
    except FileNotFoundError:
        errors.append(f"{rel}: الملف غير موجود")
    except json.JSONDecodeError as e:
        errors.append(f"{rel}: JSON غير صالح (سطر {e.lineno}، عمود {e.colno}): {e.msg}")
    return None


def check_header(rel, d, errors, strict):
    st = d.get("status")
    if st not in STATUSES:
        errors.append(f"{rel}: status يجب أن يكون placeholder أو draft أو verified")
    if strict and st != "verified":
        errors.append(f"{rel}: status = {st} (المطلوب verified قبل التسليم النهائي)")
    if st == "verified":
        rb = d.get("reviewed_by") or {}
        if not rb.get("name") or not DATE.match(rb.get("date", "")):
            errors.append(f"{rel}: verified يتطلب reviewed_by.name و reviewed_by.date بصيغة YYYY-MM-DD")
    return st


def check_quran(lang, errors, strict):
    rel = f"data/quran/translations/{lang}.json"
    d = load(rel, errors)
    if d is None:
        return
    st = check_header(rel, d, errors, strict)
    if st != "placeholder":
        for k in ("edition", "translator", "publisher", "source_url", "license", "retrieved"):
            if not d.get(k):
                errors.append(f"{rel}: الحقل {k} فارغ")
        if d.get("retrieved") and not DATE.match(d["retrieved"]):
            errors.append(f"{rel}: retrieved بصيغة YYYY-MM-DD")
    verses = d.get("verses", {})
    if not isinstance(verses, dict):
        errors.append(f"{rel}: verses يجب أن يكون كائنًا {{\"سورة:آية\": \"النص\"}}")
        return
    for ref, text in verses.items():
        m = REF.match(ref)
        if not m:
            errors.append(f"{rel}: مفتاح غير صالح «{ref}» (الصيغة 2:153)")
            continue
        s, a = int(m.group(1)), int(m.group(2))
        if not (1 <= s <= 114 and 1 <= a <= AYAH_COUNTS[s - 1]):
            errors.append(f"{rel}: «{ref}» خارج النطاق (السورة {s} عدد آياتها {AYAH_COUNTS[s - 1] if 1 <= s <= 114 else '?'})")
        if not isinstance(text, str) or not text.strip():
            errors.append(f"{rel}: نص فارغ للآية {ref}")
        elif re.search(r"\(\s*\d+\s*:\s*\d+\s*\)|^\s*\d+[.)]", text):
            errors.append(f"{rel}: {ref} يحتوي رقم الآية داخل النص؛ احذفه (الرقم في المفتاح)")
    if st != "placeholder" and not verses:
        errors.append(f"{rel}: لا توجد آيات")
    print(f"  {rel}: {len(verses)} آية · status={st}")


def check_items(rel, required, errors, strict, extra=None):
    d = load(rel, errors)
    if d is None:
        return
    st = check_header(rel, d, errors, strict)
    items = d.get("items", [])
    ids = set()
    for i, it in enumerate(items, 1):
        where = f"{rel} [عنصر {i}{' ' + it.get('id', '') if isinstance(it, dict) else ''}]"
        if not isinstance(it, dict):
            errors.append(f"{where}: يجب أن يكون كائنًا")
            continue
        for k in required:
            if not it.get(k):
                errors.append(f"{where}: الحقل {k} مطلوب")
        if it.get("id") in ids:
            errors.append(f"{where}: id مكرر")
        ids.add(it.get("id"))
        if "variants_ar" in it and not isinstance(it["variants_ar"], list):
            errors.append(f"{where}: variants_ar يجب أن تكون قائمة")
        if extra:
            extra(where, it, errors)
    if st != "placeholder" and not items:
        errors.append(f"{rel}: لا توجد عناصر")
    print(f"  {rel}: {len(items)} عنصر · status={st}")


def hadith_extra(where, it, errors):
    if it.get("collection") and it["collection"] not in COLLECTIONS:
        errors.append(f"{where}: collection يجب أن يكون واحدًا من {sorted(COLLECTIONS)}")
    url = it.get("source_url", "")
    if url and not url.startswith("https://dorar.net/"):
        errors.append(f"{where}: source_url يجب أن يكون رابطًا من dorar.net")


def check_policy(errors, strict):
    rel = "data/policy/fatwa_signals.json"
    d = load(rel, errors)
    if d is not None:
        st = check_header(rel, d, errors, strict)
        for i, p in enumerate(d.get("phrases", []), 1):
            if not p.get("text_ar") or p.get("kind") not in KINDS:
                errors.append(f"{rel} [عبارة {i}]: text_ar مطلوب و kind من {sorted(KINDS)}")
        for i, x in enumerate(d.get("exclusions", []), 1):
            if not x.get("text_ar"):
                errors.append(f"{rel} [استثناء {i}]: text_ar مطلوب")
        print(f"  {rel}: {len(d.get('phrases', []))} عبارة، {len(d.get('exclusions', []))} استثناء · status={st}")
    rel = "data/policy/referral.json"
    d = load(rel, errors)
    if d is not None:
        st = check_header(rel, d, errors, strict)
        msg = d.get("message", {})
        if st != "placeholder":
            for lang in ("ar", "en", "fr"):
                if not msg.get(lang):
                    errors.append(f"{rel}: message.{lang} فارغة")
        for lang in ("en", "fr"):
            for i, b in enumerate(d.get("bodies", {}).get(lang, []), 1):
                if not b.get("name") or not str(b.get("url", "")).startswith("https://"):
                    errors.append(f"{rel} bodies.{lang}[{i}]: name و url (https) مطلوبان")
        print(f"  {rel}: status={st}")


def check_messages(errors, strict):
    rel = "data/messages/flags.ar.json"
    d = load(rel, errors)
    if d is None:
        return
    st = check_header(rel, d, errors, strict)
    msgs = d.get("messages", {})
    missing, unknown = MESSAGE_KEYS - set(msgs), set(msgs) - MESSAGE_KEYS
    if missing:
        errors.append(f"{rel}: مفاتيح ناقصة: {sorted(missing)} (لا تحذفي أي مفتاح)")
    if unknown:
        errors.append(f"{rel}: مفاتيح غير معروفة: {sorted(unknown)} (لا تضيفي مفاتيح جديدة دون تنسيق مع م. محمد)")
    for k, needed in PLACEHOLDERS.items():
        for ph in needed:
            if k in msgs and ph not in msgs[k]:
                errors.append(f"{rel}: الرسالة {k} يجب أن تحتوي {ph} كما هو")
    print(f"  {rel}: {len(msgs)} رسالة · status={st}")


def demo_extra(where, it, errors):
    exp = it.get("expected", {})
    if not exp.get("en") and not exp.get("fr"):
        errors.append(f"{where}: expected.en أو expected.fr مطلوبة")
    if len(it.get("text_ar", "")) > 4000:
        errors.append(f"{where}: text_ar أطول من 4000 حرف")


def main():
    strict = "--strict" in sys.argv
    errors = []
    print("فحص ملفات المحتوى:")
    check_quran("en", errors, strict)
    check_quran("fr", errors, strict)
    check_items("data/hadith/hadith.json", ["id", "text_ar", "collection", "number", "grade", "source_url"], errors, strict, hadith_extra)
    check_items("data/hadith/fabricated.json", ["id", "text_ar", "ruling", "source_url"], errors, strict)
    check_policy(errors, strict)
    check_messages(errors, strict)
    check_items("data/demo/examples.json", ["id", "label_ar", "text_ar", "shows"], errors, strict, demo_extra)
    if errors:
        print("\n❌ أخطاء:")
        print("\n".join(f"- {e}" for e in errors))
        sys.exit(1)
    print("\n✅ لا أخطاء")


if __name__ == "__main__":
    main()
