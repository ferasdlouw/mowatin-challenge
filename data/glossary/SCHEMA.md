# صيغة المسرد (glossary)

ملف لكل مجموعة: `data/glossary/*.json` — مصفوفة من العناصر:

```json
{
  "id": "tawhid",
  "ar": "التوحيد",
  "variants_ar": ["توحيد", "وحدانية الله"],
  "en": {"preferred": "tawhid", "gloss": "the Oneness of God", "avoid": ["unity", "monotheism"]},
  "fr": {"preferred": "tawhîd", "gloss": "l'unicité de Dieu", "avoid": ["unité"]},
  "usage_note_ar": "يُبقى المصطلح مع شرح معناه...",
  "strategy": "keep_and_gloss",
  "source": {"name": "…", "ref": "…", "retrieved": "YYYY-MM-DD"},
  "status": {"en": "verified", "fr": "draft"},
  "reviewed_by": {"name": "…", "date": "YYYY-MM-DD"}
}
```

`strategy`:
- `keep_and_gloss` — يُبقى المصطلح العربي مُرَوْمَنًا + شرح أول مرة (Tawhid, Sunnah…)
- `translate` — يُترجم بالمقابل المعتمد (Revelation, Prophethood…)
- `context` — يُختار المقابل حسب السياق مع قائمة `avoid`

`status`: `verified` (من مصدر معتمد/مراجَع) | `draft` (يحتاج تحقق) — **لا يُستخدم `draft` في النسخة النهائية دون مراجعة.**

**قواعد إضافية** (يفحصها `python3 scripts/validate_glossary.py`، والتفاصيل في [`docs/SOURCES.md`](../../docs/SOURCES.md#5-قواعد-كتابة-المصطلح)):
- `verified` يتطلب `reviewed_by` فيه اسم المراجع وتاريخ المراجعة.
- `avoid` كلمات بلا أقواس، وسبب التجنب في `usage_note_ar`.
- `preferred` بحرف صغير وبلا أداة تعريف، إلا أسماء العلم (Allah، Islam، Ramadan…).
- `variants_ar` بلا أسماء الله الحسنى ولا ضد المصطلح، ولا تتكرر بين مصطلحين.
