# كيف يستخدم «مُوطِّن» الذكاء الاصطناعي

> ملخص للجنة التحكيم. كل جملة تشير إلى ملف في المستودع يمكن التحقق منه.

## الفكرة في سطر
«مُوطِّن» نظام **معرفة مغلقة**: لا يعتمد على ذاكرة النموذج في أي معلومة دينية. المعرفة تأتي من بيانات خاصة معتمدة، يُسترجع منها ما يلزم فقط، ثم يُطلب من النموذج **ترجمة النص لا أكثر** بقيود صريحة، ولا يُحفظ نص المستخدم في قاعدة بيانات أو ملف (تبقى الردود في ذاكرة مؤقتة ساعةً واحدة فقط، انظر القسم ٤).

## الأجزاء الأربعة

### ١. قاعدة بيانات خاصة
كل ما يعرفه النظام موجود في مجلد [`data/`](../data) ويراجعه أصحاب الاختصاص:
- المسرد: 150 مصطلحًا مع الترجمة المعتمدة واستراتيجية كل مصطلح: [`data/glossary/`](../data/glossary) (المخطط: [`data/glossary/SCHEMA.md`](../data/glossary/SCHEMA.md)).
- نص القرآن من Tanzil: [`data/quran/tanzil/quran-simple-clean.txt`](../data/quran/tanzil/quran-simple-clean.txt)، والترجمات المعتمدة (6236 آية لكل لغة): [`data/quran/translations/`](../data/quran/translations).
- الأحاديث بمصدرها ودرجتها، وقائمة الموضوعات: [`data/hadith/hadith.json`](../data/hadith/hadith.json)، [`data/hadith/fabricated.json`](../data/hadith/fabricated.json).
- عبارات الفتوى وجهات الإحالة: [`data/policy/`](../data/policy).
- سلامة هذه البيانات مفحوصة آليًا في كل تشغيل للـCI: [`backend/tests/data/test_data_integrity.py`](../backend/tests/data/test_data_integrity.py) (لا تعارض في المصطلحات، لا حديث في القائمتين معًا، أمثلة العرض ليست من مجموعة الاختبار، 6236 آية بمفاتيح صحيحة).

### ٢. استرجاع ذكي
الاسترجاع **لفظي** من البيانات المعتمدة فقط، بعد توحيد الكتابة العربية (الهمزات، التاء المربوطة، الألف المقصورة، التشكيل، التطويل): [`backend/app/pipeline/normalize.py`](../backend/app/pipeline/normalize.py).
- المصطلحات: [`backend/app/pipeline/glossary.py`](../backend/app/pipeline/glossary.py).
- الآيات: مطابقة مع نص Tanzil، وإن كان النقل خاطئًا تُدرج الترجمة الصحيحة مع تنبيه: [`backend/app/pipeline/quran.py`](../backend/app/pipeline/quran.py).
- الأحاديث: مطابقة مع القائمتين، والموضوع يُكشف قبل غيره: [`backend/app/pipeline/hadith.py`](../backend/app/pipeline/hadith.py).
- أسئلة الفتوى: [`backend/app/pipeline/classifier.py`](../backend/app/pipeline/classifier.py) و[`backend/app/pipeline/fatwa_guard.py`](../backend/app/pipeline/fatwa_guard.py).

### ٣. توليد آمن
- **النموذج لا يكتب القرآن أبدًا:** مقطع الآية لا يُرسل إلى أي نموذج في ناتج «مُوطِّن»؛ تُدرج الترجمة المعتمدة كما هي: [`backend/app/pipeline/orchestrator.py`](../backend/app/pipeline/orchestrator.py) (الدالة `_quran`).
- **الحديث غير الموثق لا يُترجم:** لا استدعاء للنموذج، والمخرج `null` مع مراجعة بشرية (D-023 في [`docs/DECISIONS.md`](DECISIONS.md)).
- **لا فتوى:** سؤال الفتوى يُترجم حرفيًا ثم تُضاف الإحالة إلى جهة مختصة (D-022).
- **قيود صريحة في التعليمات:** [`backend/app/prompts/localize_v3.txt`](../backend/app/prompts/localize_v3.txt) يأمر النموذج بأن يترجم ما في `<user_text>` فقط، ولا يضيف حكمًا أو فتوى أو نسبة أو حديثًا أو آية أو شرحًا أو رأيًا، ولا يقتبس نصًا شرعيًا من ذاكرته، ويلتزم بترجمات المصطلحات المعطاة حرفيًا، ويُخرج JSON فقط (D-025). نص المستخدم داخل وسوم ويُعامل كبيانات، فلا تُنفَّذ أي تعليمات مكتوبة فيه؛ وتُعطَّل أي وسوم بالاسم نفسه داخل النص، وتُكرَّر القاعدة بعد النص، ويُحال إلى المراجعة كل مخرج فيه وسم أو عبارة تخاطب النموذج أو طول غير معتاد (D-037).
- **تحقق بعد التوليد:** فحص المصطلحات، والترجمة العكسية، وحَكَم من نموذج آخر يعاقب أي إضافة؛ الثقة أقل من 0.75 تعني مراجعة بشرية، والفحص الذي لم يعمل يُحسب صفرًا: [`backend/app/pipeline/verifier.py`](../backend/app/pipeline/verifier.py)، [`backend/app/prompts/judge_v2.txt`](../backend/app/prompts/judge_v2.txt) (D-004، D-021، D-037).

### ٤. حماية البيانات
- **ما الذي يُرسل لكل مزوّد؟**

  | الخطوة | المزوّد (متغيرات البيئة) | ما يُرسل | الملف |
  |---|---|---|---|
  | الترجمة والتوطين | `LLM_*` ثم `FALLBACK_*` | نص المقطع العربي + ترجمات مصطلحاته فقط (لا المسرد كله) | [`localizer.py`](../backend/app/pipeline/localizer.py)، [`localize_v3.txt`](../backend/app/prompts/localize_v3.txt) |
  | سؤال الفتوى، ووضع المقارنة `compare` والوضع `raw` | `LLM_*` ثم `FALLBACK_*` | نص المقطع بترجمة مباشرة بلا قيود (ناتج `raw` ثقته صفر ويُحال دائمًا إلى المراجعة، D-038) | [`raw_v3.txt`](../backend/app/prompts/raw_v3.txt) |
  | الترجمة العكسية | `LLM_*` ثم `FALLBACK_*` | الترجمة فقط | [`backtranslate_v2.txt`](../backend/app/prompts/backtranslate_v2.txt) |
  | الحَكَم | `JUDGE_*` | المقطع العربي + ترجمته | [`judge_v2.txt`](../backend/app/prompts/judge_v2.txt) |

  تنبيه صريح: في وضع المقارنة `compare` يُرسل كل مقطع، ومنه مقطع الآية، إلى ترجمة مباشرة بلا قيود لتُعرض **عمود مقارنة** يبيّن الخطأ الذي يتجنبه «مُوطِّن» (`_baseline` في [`orchestrator.py`](../backend/app/pipeline/orchestrator.py)). هذا العمود لا يصبح ناتج «مُوطِّن» أبدًا.
- **ما الذي يُسجَّل؟** الطول وأول 12 حرفًا من بصمة SHA-256، والعدادات (مقاطع، رموز، تكلفة، زمن)، ولا يُسجَّل نص المستخدم ولا ناتج النموذج ولا المفاتيح: [`backend/app/security/privacy.py`](../backend/app/security/privacy.py)، [`backend/app/llm/router.py`](../backend/app/llm/router.py) (`_fingerprint`)، [`backend/app/security/request_log.py`](../backend/app/security/request_log.py) (لا query string). الاختبارات: [`backend/tests/security/test_privacy_logs.py`](../backend/tests/security/test_privacy_logs.py).
- **ما الذي يُخزَّن؟** لا قاعدة بيانات ولا حسابات ولا ملفات. المراجعة البشرية في المتصفح فقط (D-005). الشيء الوحيد هو ذاكرة مؤقتة في الذاكرة لـ1,000 رد (64 ميغابايت على الأكثر) ولمدة ساعة، تضيع عند إعادة التشغيل، ولا يُحفظ فيها رد فشل فيه أي استدعاء للنموذج أو تجاوز حدًّا (D-039): [`backend/app/pipeline/cache.py`](../backend/app/pipeline/cache.py).

## الطبقات المجانية واستخدام المزوّدين للبيانات (D-033)
النماذج الحالية تعمل على طبقات مجانية (D-028..D-030). نقولها بوضوح: على الطبقة المجانية قد تسمح شروط المزوّد له باستخدام النص المُرسل لتحسين خدماته.
- **Google (Gemini API):** تنص الشروط على أن محتوى الخدمات غير المدفوعة يُستخدم لتحسين منتجات Google، وقد يقرؤه مراجعون بشريون: [Gemini API Additional Terms](https://ai.google.dev/gemini-api/terms).
- **OpenRouter (النموذج المجاني `:free`):** معالجة البيانات تتبع سياسة المزوّد الذي يشغّل النموذج: [الشروط](https://openrouter.ai/terms)، [الخصوصية](https://openrouter.ai/privacy)، [السجلات والتدريب](https://openrouter.ai/docs/features/privacy-and-logging).
- **مُوطِّن نفسه لا يخزّن شيئًا:** لا قاعدة بيانات ولا حسابات، ولا يُسجَّل نص المستخدم (القسم ٤ أعلاه، D-005).
- **كيف يزول هذا:** طبقة مدفوعة لدى المزوّد، أو نموذج محلي عبر `openai_compat` فلا يغادر النص الجهاز (D-026). التبديل متغيرات بيئة فقط، بلا تغيير في الكود.

## لماذا استرجاع لفظي وتعليمات مقيدة، لا ضبط دقيق (fine-tuning) ولا قاعدة متجهات؟ (D-027)
- **النص الشرعي لا يُولَّد:** الآية تُدرج من الملف المعتمد كما هي. نموذج مضبوط دقيقًا يبقى يولّد من ذاكرته، وقد يخطئ في حرف.
- **التحديث بلا إعادة تدريب:** تعديل مصطلح أو إضافة حديث هو تعديل ملف JSON في `data/`، ويظهر أثره عند التشغيل التالي.
- **قابل للتدقيق:** كل مخرج يحمل مصدره (مرجع الآية، رقم الحديث ودرجته، معرّف المصطلح)، والمطابقة اللفظية حتمية: النص نفسه يعطي النتيجة نفسها دائمًا. قاعدة المتجهات تعيد «الأقرب» لا «المطابق»، وهذا خطر مع النص الشرعي.
- **أرخص:** لا تدريب ولا استضافة نموذج ولا خدمة متجهات؛ الاسترجاع بمكتبة بايثون القياسية: [`backend/requirements.txt`](../backend/requirements.txt).

## الرموز (tokens) ونافذة السياق
- الحد الأقصى للنص `MAX_TEXT_CHARS` = 4000 حرف افتراضيًا: [`backend/app/config.py`](../backend/app/config.py)، ويُرفض ما زاد بالرمز 413: [`backend/app/main.py`](../backend/app/main.py)، [`backend/app/security/body_limit.py`](../backend/app/security/body_limit.py).
- النص يُقسَّم إلى جمل ومقاطع، وكل استدعاء للنموذج يحمل **مقطعًا واحدًا** ومصطلحاته فقط: [`backend/app/pipeline/segmenter.py`](../backend/app/pipeline/segmenter.py) (D-024).
- النتيجة: تعليمات قصيرة، فاستهلاك أقل للرموز وتكلفة وزمن أقل، ولا خطر لتجاوز نافذة السياق، ويتركز انتباه النموذج على نص قصير فتقل فرصة الإضافة. التكلفة والزمن يُسجّلان لكل طلب: [`docs/MODELS.md`](MODELS.md).

## خيار النماذج مفتوحة المصدر أو المحلية
أي خانة (`LLM_*` أو `FALLBACK_*` أو `JUDGE_*`) يمكن توجيهها إلى أي خادم متوافق مع OpenAI (OpenAI-compatible endpoint)، ومنها النماذج المحلية عبر Ollama أو LM Studio على الجهاز نفسه، فلا يغادر النص الجهاز: [`backend/app/llm/openai_compat.py`](../backend/app/llm/openai_compat.py) (D-026). الشروط: `https` لأي خادم، و`http` لـ`localhost` أو `127.0.0.1` فقط. طريقة التشغيل: [`docs/dev/DEPLOY.md`](dev/DEPLOY.md) §8. المزوّدون الحاليون: D-028 إلى D-030.

## اختيار النموذج: الذكاء والسرعة والتكلفة
جدول المقارنة وطريقة ملئه من تشغيل حقيقي على مجموعة التطوير: [`docs/MODELS.md`](MODELS.md). الأرقام تُملأ بعد ضبط مفاتيح النماذج، ولا تُقدَّر أبدًا.
