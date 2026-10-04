# طريقة العمل في المستودع

> قواعد قليلة وواضحة حتى نتحرك بسرعة دون أن نكسر بعضنا. **`main` يجب أن يعمل دائمًا**، فهو ما تراه اللجنة.

## 1. ابدأ من Issue

- كل عمل له Issue في [Issues](../../issues). إن لم يوجد، افتحه بالقالب المناسب.
- خذ الـ Issue بتعيين نفسك (Assign)، وحرّكه في لوحة المشروع (تبويب Projects) إلى «قيد العمل».
- الـ Milestone يحدد اليوم المطلوب فيه (اليوم 1 / 2 / 3).

## 2. الفروع

```
feat/<المجال>-<وصف-قصير>     ميزة جديدة          feat/pipeline-term-lock
fix/<وصف>                     إصلاح خطأ           fix/rtl-highlight-offset
data/<وصف>                    المسرد أو الاختبار   data/glossary-batch-2
docs/<وصف>                    توثيق               docs/readme-results
```

ابدأ دائمًا من `main` محدّث: `git switch main && git pull && git switch -c feat/...`

## 3. رسائل الـ Commit

صيغة [Conventional Commits](https://www.conventionalcommits.org) بالإنجليزية، قصيرة وبصيغة الأمر:

```
feat(pipeline): inject locked glossary terms into prompt
fix(ui): correct highlight offsets for RTL text
data(glossary): add 25 creed terms with sources
docs(readme): add benchmark results table
```

## 4. الـ Pull Request

- **صغير ومتكرر:** PR لكل ميزة صغيرة أفضل من PR ضخم آخر اليوم.
- املأ القالب: ماذا تغيّر، ورابط الـ Issue (`Closes #12`)، ولقطة شاشة أو مثال، والتحقق من DoD.
- **من يراجع:**

| نوع التغيير | المراجع |
|---|---|
| المسرد `data/glossary/` | ردينة (إلزامي) |
| مجموعة الاختبار `data/testset/` و `eval/` | مسؤول التقييم |
| الـ API أو العقد `docs/ARCHITECTURE.md (عقد الـ API)` | محمد + فارس |
| الواجهة `frontend/` | فارس أو أي مطوّر |
| التوثيق والعرض | فارس |

- الدمج بـ **Squash and merge** بعد نجاح فحوص CI.
- لا يُدمج PR يكسر الرابط العام. إن انكسر، أولوية الجميع إصلاحه.

## 5. ممنوعات

- ❌ رفع مفاتيح أو كلمات مرور أو ملف `.env`. الإعدادات في متغيرات البيئة. **إن رُفع مفتاح بالخطأ: ألغِه فورًا من لوحة المزود وأبلغ فارس. حذفه من الكود لا يكفي.**
- ❌ أي بيانات أو محادثات مستفيدين حقيقية (شرط التحدي).
- ❌ الدفع المباشر إلى `main` أو `--force`.
- ❌ حسم سؤال شرعي برأي الفريق. يُحال للمراجع عبر ردينة.

## 6. الإعداد المحلي

راجع قسم «التشغيل» في [`README.md`](README.md)، وتأكد قبل أي PR أن بيانات المسرد ومجموعة الاختبار مطابقة لـ `SCHEMA.md` في مجلد كل منهما، وأن الـ frontend يعمل (`npm run dev`).
