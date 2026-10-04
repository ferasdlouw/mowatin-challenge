# مُوطِّن · Mowatin

> **أداة لترجمة المحتوى الدعوي من العربية تحافظ على المعنى الشرعي.**
> Translating Islamic da'wah content from Arabic into English and French without changing its religious meaning.

**التحدي:** تحدي الذكاء الاصطناعي في خدمة المحتوى الإسلامي 2026
**المسار:** 02 — صناعة المحتوى متعدد اللغات والتوطين الثقافي
**الفريق:** فريق أثر المدينة

---

## المشكلة

حين يُترجم المحتوى الدعوي بأدوات الترجمة العامة أو بالنماذج اللغوية وحدها، قد يتغيّر معناه الشرعي دون أن يلاحظ أحد:

- تُترجم الآية ترجمةً آلية بدل الترجمة المعتمدة لمعانيها.
- يُنقل قولٌ على أنه حديث وهو بلا مصدر أو موضوع.
- يُترجم المصطلح الشرعي (التوحيد، العبادة، الزكاة…) بكلمة تغيّر دلالته.
- يجيب النظام عن سؤال فتوى شخصي بدل أن يحيله إلى أهل العلم.

## الحل

**مُوطِّن** طبقة فوق الترجمة الآلية، يستخدمها صانع المحتوى الدعوي العربي حين يريد نشر نصه بلغة أخرى. يلصق النص العربي، ويختار اللغة (الإنجليزية أو الفرنسية) والجمهور، فيحصل على ترجمة مقطعًا مقطعًا:

| ما في النص | ما يفعله مُوطِّن |
|---|---|
| **آية** | يطابقها مع نص القرآن (مشروع تنزيل)، ويُدرج ترجمة معانيها المعتمدة من QuranEnc.com مع رقم السورة والآية. لا يترجم آية آليًا أبدًا. وإن كانت الآية محرّفة نبّه عليها. |
| **حديث** | يطابقه مع قائمة أحاديث موثّقة بمصدرها ودرجتها. والقول الموضوع أو الذي بلا مصدر لا يُترجم، ويُحال إلى المراجعة. |
| **مصطلح شرعي** | يقفل ترجمته على مقابل ثابت من مسرد موثّق (150 مصطلحًا)، ويُظهر تعريفه ومصدره. |
| **سؤال فتوى** | لا يجيب عنه؛ يترجم السؤال ويحيل السائل إلى جهات الفتوى المعتمدة. |
| **نص عادي** | يترجمه النموذج اللغوي ضمن قيود صريحة، ثم يتحقق منه (ترجمة عكسية ونموذج حَكَم) ويعطيه درجة ثقة. |

كل ما يشك فيه النظام يذهب إلى **لوحة المراجع** ليقرّه مراجع شرعي قبل النشر. وشاشة **«قبل وبعد»** تقارن نتيجة مُوطِّن بالترجمة العادية على النص نفسه.
 
## كيف يعمل

```
النص العربي
   │
   ├─ الكشف: تقسيم النص، وتحديد الآيات والأحاديث والمصطلحات وأسئلة الفتوى
   ├─ الترجمة: إدراج الترجمات المعتمدة، وقفل المصطلحات، وترجمة الباقي بالنموذج اللغوي
   └─ التحقق: فحص المصطلحات، وترجمة عكسية، ونموذج حَكَم ← درجة ثقة لكل مقطع
                                                      └─ أقل من الحد ← لوحة المراجع
```

- **الخادم:** Python (FastAPI)، منشور على Render.
- **الواجهة:** React (Vite + Tailwind)، منشورة على Cloudflare Pages، وتدعم العربية من اليمين إلى اليسار والجوال.
- **النماذج اللغوية:** Gemini (أساسي وحَكَم)، وOpenRouter (احتياطي عند الفشل).

التفاصيل: المعمارية وعقد الـ API في [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)، والقرارات في [`docs/DECISIONS.md`](docs/DECISIONS.md)، والتقييم في [`docs/EVALUATION.md`](docs/EVALUATION.md)، والأمان في [`docs/security/`](docs/security/).

## المصادر

- **نص القرآن الكريم:** [مشروع تنزيل](https://tanzil.net) (CC BY 3.0).
- **ترجمات معاني القرآن:** [QuranEnc.com](https://quranenc.com): Saheeh International (الإنجليزية) ورشيد معاش (الفرنسية).
- **المسرد:** مصطلحات موثّقة بمصادرها، راجعتها م. ردينة بلال.

قائمة المصادر ورخصها في [`docs/SOURCES.md`](docs/SOURCES.md) و[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).

## التشغيل محليًا
يحتاج Python 3.11 (وNode 20+ للواجهة فقط). كل الأوامر من جذر المستودع؛ على Windows استخدم `.venv\Scripts\activate` و`copy` بدل `source` و`cp`.

```bash
git clone https://github.com/ferasdlouw/mowatin-challenge.git && cd mowatin-challenge
python -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements-dev.txt     # يشمل backend/requirements.txt وأدوات الاختبار
cp .env.example .env                            # المفاتيح اختيارية محليًا (انظر أدناه)
uvicorn --factory app.main:create_app --app-dir backend --reload
```

في طرفية أخرى:
```bash
curl http://127.0.0.1:8000/health
curl -X POST http://127.0.0.1:8000/v1/translate   -H "Content-Type: application/json" --data-binary @- <<'EOF'
{"text": "قال الله تعالى: ﴿وَمَا أَرْسَلْنَاكَ إِلَّا رَحْمَةً لِّلْعَالَمِينَ﴾", "target_lang": "en", "audience": "general_non_muslim", "mode": "localize"}
EOF
```
النتيجة المتوقعة حتى بلا مفاتيح: مقطع `quran` بترجمة Saheeh International المعتمدة للآية 21:107 وثقة 1.0 (النص العربي يُرسل عبر stdin حتى لا تُفسد طرفية Windows ترميزه).
شكل الطلب والرد في [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) §4.

- **بلا مفاتيح:** الآيات تُدرج من الترجمة المعتمدة، والأحاديث تُطابق مع مصدرها، وأسئلة الفتوى تُحال؛ أما المقاطع التي تحتاج نموذجًا لغويًا فترجع `output: null` وتذهب للمراجعة.
- **مع المفاتيح:** املأ `LLM_*` و`FALLBACK_*` و`JUDGE_*` في `.env` (الأسماء فقط في [`.env.example`](.env.example)). النماذج المجانية اليوم: `gemini-3.5-flash-lite` (أساسي)، و`qwen/qwen3.8-27b:free` عبر OpenRouter (احتياطي)، و`gemini-3.1-flash-lite` (حَكَم) (D-028..D-030). تحقق منها: `cd backend && python -m app.llm.smoke --env-file ../.env`. بلا `JUDGE_*` تبقى الثقة ≤ 0.60، فكل مقطع مترجم يذهب للمراجعة (D-021).
- **الواجهة:** `cd frontend && npm ci && npm run dev`. لربطها بالخادم المحلي: `VITE_API_URL=http://127.0.0.1:8000` في `frontend/.env.local`، و`ALLOWED_ORIGINS=http://localhost:5173` في `.env`. بلا `VITE_API_URL` تعمل الواجهة بالأمثلة التجريبية.

## الاختبارات
```bash
cd backend && pytest -q && cd ..                # بلا شبكة: النماذج اللغوية مُحاكاة
```
فحوص CI الكاملة (ruff وbandit وpip-audit والمدققات) في [`.github/workflows/ci.yml`](.github/workflows/ci.yml).

## إعادة القياس
```bash
# من جذر المستودع، يستخدم مفاتيح .env إن وُجدت
python scripts/run_eval.py --split dev --runs 1
```
- يشغّل الأنظمة `raw` (نموذج لغوي بلا ضوابط) و`localize` (مُوطِّن)، و`gt` (Google Translate) فقط إن وُجد `GT_API_KEY`.
- المخرجات في `eval/results/runs/` (`{system}_run{n}.jsonl` و`metrics.json`)، وهي غير مرفوعة إلى git. المقاييس معرّفة في [`docs/DECISIONS.md`](docs/DECISIONS.md) D-015.
- مجموعة الاختبار المجمّدة لا تُقرأ إلا بـ `--split test --i-confirm-frozen --runs 3`، ثم `python scripts/build_summary.py` يملأ `eval/results/summary.json`.

## ما قبل التحدي وما بعده

بدأ العمل على مُوطِّن في 1 أكتوبر 2026، قبل التحدي. هذا المستودع أُنشئ لأيام التحدي، وأول ما رُفع فيه (4 أكتوبر) نسخةٌ من مستودع التطوير السابق [`ferasdlouw/mowatin`](https://github.com/ferasdlouw/mowatin).
ما كان موجودًا قبل التحدي محدّد هناك بالوسم [`v0-start`](https://github.com/ferasdlouw/mowatin/tree/v0-start)، وموثّق في [`docs/PRE_CHALLENGE.md`](docs/PRE_CHALLENGE.md)، وسجلّ التطوير الكامل قبل ذلك في المستودع نفسه. شارك في الإعداد قبل التحدي أعضاء سابقون في الفريق.

## الإفصاح

- مُوطِّن أداة مدعومة بالذكاء الاصطناعي، ومخرجاته تحتاج **مراجعة بشرية مؤهلة قبل النشر**.
- لا نخزّن النصوص: يبقى النص في ذاكرة الخادم ساعة واحدة فقط، ويُرسل للترجمة إلى نماذج Google وOpenRouter المجانية.
- كُتب جزء كبير من الكود والتوثيق بمساعدة وكيل برمجة بالذكاء الاصطناعي، بإشراف الفريق ومراجعته.

## الفريق

| الاسم | الدور |
|---|---|
| م. فارس دلو | الواجهة والنشر |
| م. محمد سعدالدين | الخادم وخط المعالجة |
| م. ردينة بلال | المحتوى الشرعي والمسرد والمراجعة |

## الترخيص

الكود منشور **للاطلاع والتحكيم فقط**، وليس مفتوح المصدر. التفاصيل في [`LICENSE`](LICENSE) وملخصه العربي في [`LICENSE.ar.md`](LICENSE.ar.md).

---

### English summary

**Mowatin** is a layer on top of machine translation for Arabic da'wah content creators. It translates Arabic texts into English and French segment by segment:

- **Qur'an verses** are matched against the Tanzil text and replaced with an approved translation of their meanings (QuranEnc.com), never machine-translated.
- **Hadith** are matched against a sourced list. Fabricated or unsourced sayings are not translated and go to review.
- **Islamic terms** are locked to a verified glossary.
- **Fatwa questions** are referred to qualified bodies instead of being answered.
- Everything else is translated by an LLM under explicit constraints, then checked (back-translation and an LLM judge). Low-confidence segments go to a human reviewer.

Live: [mowatin.pages.dev](https://mowatin.pages.dev) · Code: [ferasdlouw/mowatin-challenge](https://github.com/ferasdlouw/mowatin-challenge) (development history before the challenge: [ferasdlouw/mowatin](https://github.com/ferasdlouw/mowatin)) · License: proprietary, source-available for evaluation only.
