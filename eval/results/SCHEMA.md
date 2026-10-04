# صيغة `summary.json` (تقرأها صفحة `/results` مباشرة)

> الصفحة تعرض «النتائج قيد القياس» ما دام `status = "pending"`، ولا تعرض أي رقم غير موجود في هذا الملف.

| الحقل | النوع | ملاحظات |
|---|---|---|
| `status` | `"pending"` \| `"final"` | اجعله `final` بعد التشغيلات الثلاثة على `test` المجمّد |
| `generated_at` | ISO date | تاريخ آخر تشغيل |
| `testset.size`, `testset.split`, `testset.frozen_at` | | `frozen_at` قبل أول تشغيل لمُوطِّن |
| `runs` | int | عدد التشغيلات (3) |
| `systems[]` | `{id,label,detail}` | لا تغيّر المعرّفات: `mt`, `llm`, `mowatin` |
| `error_categories[]` | `{id,label}` | |
| `errors_per_100[system][category]` | `{mean, sd}` | أخطاء لكل 100 مقطع، متوسط وانحراف عبر التشغيلات |
| `metrics[].values[system]` | `{mean, sd}` | بوحدة `unit` |
| `agreement` | `{kappa, sample_size, raters}` | كابا كوهين بين المقيّمَين على العيّنة المشتركة |
| `examples[]` | `{id, category, source, mt, llm, mowatin, note}` | أقوى 3 أمثلة، من مجموعة الاختبار نفسها |
| `limitations[]` | string | حدود دلالة النتائج بصراحة |

مثال قيمة: `"errors_per_100": { "mowatin": { "quran": { "mean": 0.0, "sd": 0.0 } } }`
