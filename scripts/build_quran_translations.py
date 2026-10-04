#!/usr/bin/env python3
"""يبني data/quran/translations/{en,fr}.json من ملفات QuranEnc الرسمية (CSV) في data/quran/translations/source/.

- النص يُنقل حرفيًا. يُحذف فقط رقم الآية في أول النص (مثل «186. ») وعلامات الحواشي ([1])
  لأن الرقم في المفتاح، والحواشي محفوظة كاملة في الحقل footnotes.
- الملف الأصلي يبقى في source/ بمعلومات الإصدار كما هي (شرط QuranEnc).
الاستخدام: python3 scripts/build_quran_translations.py
"""
import csv, io, json, re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "quran" / "translations" / "source"
LICENSE = ("QuranEnc.com: «Contents of the translations can be downloaded and re-published, with the following terms and conditions»: "
           "1) No modification, addition, or deletion of the content. 2) Clearly referring to the publisher and the source (QuranEnc.com). "
           "3) Mentioning the version number. 4) Keeping the transcript information in the document. "
           "5) Notifying the source (QuranEnc.com) of any notes on the translation. 6) Updating the translation according to the latest version issued by the source. "
           "7) Avoiding inappropriate advertisements when displaying the translations.")
EDITIONS = {
    "en": {"file": "english_saheeh_v1.1.2-csv.1.csv", "edition": "Saheeh International",
           "translator": "Saheeh International — issued by Noor International Center",
           "publisher": "Noor International Center — via QuranEnc.com (Encyclopedia of the Noble Qur'an)",
           "source_url": "https://quranenc.com/en/browse/english_saheeh"},
    "fr": {"file": "french_rashid_v1.0.3-csv.1.csv", "edition": "Rachid Maach",
           "translator": "Rachid Maach (Rashid Ma'ash)",
           "publisher": "QuranEnc.com (Encyclopedia of the Noble Qur'an)",
           "source_url": "https://quranenc.com/en/browse/french_rashid"},
}


def build(lang, meta, retrieved="2026-10-02"):
    raw = (SRC / meta["file"]).read_text(encoding="utf-8-sig")
    rows = list(csv.reader(io.StringIO(raw)))
    info = rows[0][0]
    version = re.search(r"\((v[\d.]+-csv\.\d+)\)", info).group(1)
    start = next(i for i, r in enumerate(rows) if r[:3] == ["id", "sura", "aya"]) + 1
    verses, notes = {}, {}
    for r in rows[start:]:
        s, a, text, fn = r[1], r[2], r[3], r[4]
        ref = f"{int(s)}:{int(a)}"
        text = re.sub(rf"^\s*{int(a)}\.\s*", "", text)          # رقم الآية في أول النص
        text = re.sub(r"\s?\[\d+\]", "", text).strip()            # علامات الحواشي
        verses[ref] = text
        if fn.strip():
            notes[ref] = fn.strip()
    out = {"status": "draft", "language": lang, "edition": meta["edition"], "translator": meta["translator"],
           "publisher": meta["publisher"], "source_url": meta["source_url"], "version": version,
           "license": LICENSE, "retrieved": retrieved, "transcript_info": info,
           "reviewed_by": {"name": "", "date": ""}, "verses": verses, "footnotes": notes}
    (ROOT / "data" / "quran" / "translations" / f"{lang}.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(lang, meta["edition"], version, len(verses), "آية", len(notes), "حاشية")


if __name__ == "__main__":
    for lang, meta in EDITIONS.items():
        build(lang, meta)
