# صيغة مجموعة الاختبار

`data/testset/testset.jsonl` — سطر لكل حالة:

```json
{"id":"T001","category":"term_critical","level":"A","text_ar":"…","targets":["en","fr"],
 "expect":{"terms":["tawhid"],"quran_refs":[],"hadith_refs":[],"must_flag":false,"must_refer":false},
 "source":{"name":"…","ref":"…"},"notes":"…"}
```

## التصنيفات والحد الأدنى المستهدف (100 حالة)
| category | يختبر | العدد |
|---|---|---|
| `term_critical` | مصطلحات حساسة (توحيد، عبادة، شريعة…) | 30 |
| `quran_quote` | آية صحيحة ← ترجمة معتمدة + مرجع | 15 |
| `quran_misquote` | آية منقولة بخطأ ← تنبيه وعدم البناء عليها | 5 |
| `hadith_quote` | حديث بمصدره ← يُحفظ المصدر والدرجة | 10 |
| `hadith_unsourced` | نسبة بلا مصدر ← مراجعة بشرية | 5 |
| `cultural` | أمثلة/أسلوب يحتاج تكييفًا للجمهور دون تغيير الجوهر | 20 |
| `level_d` | محتوى فتوى/حالة شخصية ← لا حكم مستقل + إحالة | 5 |
| `mixed` | فقرة دعوية حقيقية كاملة تجمع ما سبق | 10 |

المصادر المقترحة للنصوص: dawa.center، «بيّنات»، islamic-content.com — مع ذكر المرجع لكل حالة.

## الملفات
- `testset.jsonl` = `dev.jsonl` + `test.jsonl` (162 حالة: 47 + 115). `test.jsonl` مختوم بـ `test.sha256` ومجمّد في `testset-v1`.
- `split.json`: جهة كل حالة (dev أو test) مع البذرة والنسبة.
- `official_scenarios.jsonl`: أصل الحالات الـ 12 المبنية على أمثلة المرجعية الرسمية (O01–O12)، وهي داخلة في `testset.jsonl`.
- الأداة: `scripts/split_testset.py` (`validate`، و`add` لإضافة حالات دون إعادة الخلط، و`split` قبل التطوير فقط).
