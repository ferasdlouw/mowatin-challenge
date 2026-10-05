# معمارية مُوطِّن

> وثيقة تصميم أُعدّت قبل بدء التحدي (انظر `PRE_CHALLENGE.md`). التنفيذ يبدأ عند `v0-start`.

## 1. الفكرة في سطر
نص دعوي عربي ← نص موطَّن (EN / FR) يحافظ على الدلالة الشرعية، مع **تقرير تحقق** لكل مقطع.

## 2. الـ Pipeline

```
Input (AR text + target lang + audience)
   │
   ▼
[1] Segmenter        ─ يقطّع النص إلى مقاطع (جمل/فقرات)
   │
   ▼
[2] Classifier       ─ نوع المقطع + مستوى المحتوى (أ/ب/ج/د)
   │                   types: quran | hadith | term_heavy | general | fatwa_like
   ▼
[3] Router
   ├─ quran      → Quran Resolver : يطابق الآية ← يدرج الترجمة المعتمدة + (سورة:آية)
   │                                لا ترجمة آلية للآيات أبدًا. آية غير مطابقة ← تنبيه "نص محرّف؟"
   ├─ hadith     → Hadith Handler : يحتفظ بالمصدر والدرجة، "ترجمة معنى"، بلا مصدر ← مراجعة بشرية
   ├─ fatwa_like → Level-D Guard  : لا يوطّن حكمًا شخصيًا؛ يترجم المعلومة العامة + إحالة
   └─ general / term_heavy
                 → Term Lock      : يستخرج المصطلحات من المسرد ويقفل مقابلها
                 → Localizer (LLM): يكيّف الأسلوب والأمثلة للجمهور، مقيَّدًا بالمصطلحات المقفلة
   │
   ▼
[4] Verifier
   ├─ Term check (deterministic) : هل كل مصطلح مقفل ظهر بمقابله المعتمد؟
   ├─ Back-translation            : ترجمة عكسية للعربية + مقارنة دلالية
   └─ Judge (LLM مختلف)           : هل تغيّر الجوهر؟ هل أضيف ادعاء؟  → score 0–1
   │
   ▼
[5] Report
   ├─ localized_text
   ├─ per-segment: type, level, locked_terms[], sources[], confidence, flags[]
   └─ review_queue: المقاطع دون العتبة
```

## 3. قواعد ملزمة (من الحزمة العلمية)
| القاعدة | التطبيق |
|---|---|
| المسرد مقدَّم على الترجمة الآلية | Term Lock قبل الـ LLM + Term check بعده |
| موثوقية نقل الآيات | Quran Resolver من ترجمة معتمدة فقط |
| لا يُنسب حديث دون مصدر | Hadith Handler يعلّم المقطع للمراجعة |
| عدم الاستقلال بالفتوى | Level-D Guard |
| مقاومة الهلوسة | ثقة منخفضة ← تحفّظ ومراجعة بشرية لا توليد |
| الترجمة لا تغيّر المضمون لإرضاء الجمهور | Judge يفحص "تغيّر الجوهر" |
| الشفافية | شارة "أداة مدعومة بالذكاء الاصطناعي" في الواجهة والتقرير |
| الخصوصية | لا حسابات، لا تخزين للنصوص إلا بموافقة |

## 4. عقد الـ API

> **المرجع الوحيد للعقد.** الواجهة (`frontend/src/lib/api.js`) وصفحة المطوّرين (`/developers`) مبنيتان عليه.
> أي تغيير هنا يُحدَّث في الـ PR نفسه مع الواجهة. المسار `/v1/translate` يطابق لوحة التصميم.

`POST /v1/translate`
```json
{
  "text": "النص العربي (حتى 4000 حرف)",
  "target_lang": "en",
  "audience": "general_non_muslim",
  "mode": "localize"
}
```
- `target_lang`: `en | fr`
- `audience`: `general_non_muslim | new_muslim | youth | academic`
- `mode`: `localize` (مُوطِّن كامل) · `raw` (النموذج نفسه بلا مُوطِّن، للمقارنة والقياس) · `compare` (الاثنان معًا)

الاستجابة `200`:
```json
{
  "segments": [
    {
      "id": 1,
      "source": "التوحيد أساس الإسلام، وهو إفراد الله بالعبادة.",
      "output": "Tawhid (the Oneness of God) is the foundation of Islam: devoting all worship to God alone.",
      "type": "term_heavy",
      "level": "A",
      "locked_terms": [{ "ar": "التوحيد", "out": "Tawhid", "glossary_id": "tawhid" }],
      "marks": ["Tawhid", "Islam", "worship"],
      "sources": [{ "kind": "glossary", "ref": "المسرد: التوحيد" }],
      "confidence": 0.95,
      "flags": [],
      "baseline": { "output": "…", "wrong": ["unity"], "why": "…" },
      "back_translation": "التوحيد أساس الإسلام…"
    }
  ],
  "summary": { "segments": 4, "flagged": 0, "avg_confidence": 0.94 },
  "review_queue": [],
  "disclosure": "مخرجات مدعومة بالذكاء الاصطناعي، وتحتاج مراجعة بشرية مؤهلة قبل النشر."
}
```

| الحقل | النوع | الوصف |
|---|---|---|
| `type` | `quran \| hadith \| term_heavy \| general \| fatwa_like` | نوع المقطع |
| `level` | `A \| B \| C \| D` | مستوى المحتوى (أ–د) من الحزمة العلمية |
| `output` | string \| null | `null` = لم يُترجَم (أُوقف وأُحيل) |
| `marks` | string[] | الكلمات في `output` التي تُلوَّن كمصطلحات مقفلة |
| `sources[]` | `{kind: glossary\|quran\|hadith, ref, edition?, grade?}` | |
| `confidence` | 0–1 | من طبقة التحقق؛ < 0.75 يُحال تلقائيًا |
| `flags[]` | `{severity: info\|warn\|block, text}` | `text` بالعربية لعرضه للمستخدم |
| `baseline` | `{output, wrong[], why}` | فقط في `mode=compare` |
| `back_translation` | string \| null | الترجمة العكسية إلى العربية التي قارنها المتحقق بالأصل؛ `null` حين لا توجد (D-049) |

الأخطاء: `400` مدخل غير صالح · `413` النص أطول من الحد · `429` تجاوز حد الطلبات · `5xx` الخادم.

`GET /v1/glossary?q=` — بحث في المسرد. · `GET /health` — للمراقبة وإيقاظ الخادم.

## 5. مزودو النماذج
- **Localizer:** مزوّد أساسي (يُحدَّد).
- **Judge:** نموذج **مختلف** عن الـ Localizer لتجنّب تحيّز التقييم الذاتي.
- **Fallback:** عند فشل الأساسي ← المزوّد البديل تلقائيًا، ويُسجَّل ذلك في التقرير.
- كل الاستدعاءات بـ `temperature` منخفضة + seed/إعدادات ثابتة لتكرار النتائج.

## 6. التقييم (eval/)
- `data/testset/` ≥ 100 مقطع، مصنّفة حسب النوع.
- بدائل المقارنة: (1) ترجمة آلية عامة، (2) LLM بدون ضوابط، (3) مُوطِّن.
- 3 محاولات لكل مقطع ← متوسط + انحراف.
- المقاييس:
  | المقياس | يقيس | طريقة |
  |---|---|---|
  | Term Accuracy | دقة المصطلحات | آلي مقابل المسرد |
  | Scripture Integrity | سلامة الآيات والأحاديث | آلي |
  | Meaning Preservation | الحفاظ على الجوهر | Judge + عيّنة بشرية |
  | Clarity & Cultural Fit | الوضوح والملاءمة | تقييم بشري (ناطقون أصليون) 1–5 |
  | Safe Handling | الامتناع/الإحالة في مستوى د | آلي |

## 7. الـ Stack
| الطبقة | التقنية | النشر |
|---|---|---|
| Backend | Python 3.11 + FastAPI | Render |
| Frontend | React + Vite + Tailwind (RTL/LTR) | Cloudflare Pages |
| البيانات | JSON داخل المستودع | — |

## 8. هيكل الكود المخطط
```
backend/app/
  main.py            # FastAPI routes
  config.py          # env + providers
  llm/               # provider clients + fallback
  pipeline/
    segmenter.py
    classifier.py
    quran.py
    hadith.py
    glossary.py      # term lock + term check
    localizer.py
    verifier.py
    report.py
eval/
  run_benchmark.py
  baselines.py
  metrics.py
frontend/src/
  pages/Localize.tsx
  pages/Compare.tsx
  components/SegmentCard.tsx
  components/TermChip.tsx
```

## 9. خطة البناء
| اليوم | الهدف بنهاية اليوم |
|---|---|
| 4 أكتوبر | `v0-start` ← pipeline كامل end-to-end على EN + API شغّال + واجهة أولية |
| 5 أكتوبر | FR + Verifier كامل + صفحة المقارنة + نشر أول نسخة Live + تشغيل الـ benchmark |
| 6 أكتوبر | اختبار المستخدمين + إصلاحات + README/EVALUATION + فيديو + عرض + **تحويل المستودع Public** قبل 11:59 م |
