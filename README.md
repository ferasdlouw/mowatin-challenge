# مُوطِّن · Mowatin

> **أداة توطين للمحتوى الدعوي تحافظ على المعنى الشرعي.**
> Localizing Islamic da'wah content into other languages and cultures, without changing its religious meaning.

**المسار:** 02 — صناعة المحتوى متعدد اللغات والتوطين الثقافي
**الفريق:** فريق أثر المدينة — تحدي الذكاء الاصطناعي في خدمة المحتوى الإسلامي 2026

| | |
|---|---|
| 🔗 Live Demo | [mowatin.pages.dev](https://mowatin.pages.dev) |
| 🎬 فيديو (≤ دقيقتين) | _يُضاف قبل التسليم_ |
| 📊 نتائج الاختبار | [`docs/EVALUATION.md`](docs/EVALUATION.md) |

---

## المشكلة
_تُكتب يوم 4 أكتوبر._

## الحل وآلية العمل
_ملخص الـ pipeline + رسم المعمارية ← [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)_

## النتائج
_جدول المقارنة مع البدائل (ترجمة آلية عامة / نموذج لغوي بدون ضوابط) ← [`docs/EVALUATION.md`](docs/EVALUATION.md)_

## الموثوقية والمصادر
- المصطلحات مقيّدة بمسرد الجمهرة، ولها الأولوية على الترجمة الآلية.
- الآيات تُدرج من الترجمات المعتمدة، ولا تُترجم آليًا أبدًا.
- الأحاديث تُعرض مع مصدرها ودرجتها.
- التفاصيل ← [`docs/SOURCES.md`](docs/SOURCES.md) و[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md)

## التشغيل محليًا
يحتاج Python 3.11 (وNode 20+ للواجهة فقط). كل الأوامر من جذر المستودع؛ على Windows استخدم `.venv\Scriptsctivate` و`copy` بدل `source` و`cp`.

```bash
git clone https://github.com/ferasdlouw/mowatin.git && cd mowatin
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
- بلا مفاتيح (dev، 44 حالة، 88 وحدة): سلامة النصوص الشرعية 76.5%، استدعاء الإحالة ودقتها 100%، الإحالة الزائدة 0%؛ دقة المصطلحات 0% حتى تُضاف مفاتيح النماذج.
- يشغّل الأنظمة `raw` (نموذج لغوي بلا ضوابط) و`localize` (مُوطِّن)، و`gt` (Google Translate) فقط إن وُجد `GT_API_KEY`.
- المخرجات في `eval/results/runs/` (`{system}_run{n}.jsonl` و`metrics.json`)، وهي غير مرفوعة إلى git. المقاييس معرّفة في [`docs/DECISIONS.md`](docs/DECISIONS.md) D-015.
- مجموعة الاختبار المجمّدة لا تُقرأ إلا بـ `--split test --i-confirm-frozen --runs 3`، ثم `python scripts/build_summary.py` يملأ `eval/results/summary.json`.

## الإفصاح
- ما جُهّز قبل 4 أكتوبر ← [`docs/PRE_CHALLENGE.md`](docs/PRE_CHALLENGE.md)
- الحل أداة مدعومة بالذكاء الاصطناعي، ومخرجاته تحتاج مراجعة بشرية مؤهلة قبل النشر.

## المراجعة واختبار المستخدمين
_أسماء المراجعين الشرعيين والمختبرين (بإذنهم)._

## الترخيص
ملكية خاصة — منشور للاطلاع والتحكيم فقط. انظر [`LICENSE`](LICENSE) و[`LICENSE.ar.md`](LICENSE.ar.md).
© 2026 فريق أثر المدينة.
