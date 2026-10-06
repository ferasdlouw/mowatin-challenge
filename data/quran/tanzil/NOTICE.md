# إشعار حقوق نص القرآن — Tanzil

الملف `quran-simple-clean.txt` في هذا المجلد هو نص القرآن الكريم من **مشروع تنزيل (Tanzil Project)**، ويُستخدم في مُوطِّن لمطابقة الآيات المقتبسة مع نص المصحف (ولا يُعدَّل أبدًا).

- **المصدر:** [tanzil.net](https://tanzil.net) — نوع النص: Simple Clean، بصيغة `سورة|آية|النص`، مع البسملة في أول الآية الأولى من كل سورة.
- **الترخيص:** [Creative Commons Attribution 3.0](https://tanzil.net/docs/text_license).
- **متابعة التحديثات:** [tanzil.net/updates](http://tanzil.net/updates/).

## نص الإشعار (كما نشره مشروع تنزيل)

> شروط تنزيل تنص على أن هذا الإشعار «shall be included in all verbatim copies of the text, and shall be reproduced appropriately in all files derived from or containing substantial portion of this text». الملف النصي في هذا المجلد لا يحتوي كتلة الإشعار في داخله (حتى يقرأه الكود سطرًا سطرًا)، فهذا الملف يرافقه بالإشعار كاملًا.

```
Tanzil Quran Text
Copyright (C) 2007-2021 Tanzil Project
License: Creative Commons Attribution 3.0

This copy of the Quran text is carefully produced, highly verified and
continuously monitored by a group of specialists in Tanzil Project.

TERMS OF USE:

- Permission is granted to copy and distribute verbatim copies of this text,
  but CHANGING IT IS NOT ALLOWED.

- This Quran text can be used in any website or application, provided that
  its source (Tanzil Project) is clearly indicated, and a link is made to
  tanzil.net to enable users to keep track of changes.

- This copyright notice shall be included in all verbatim copies of the text,
  and shall be reproduced appropriately in all files derived from or
  containing substantial portion of this text.

Please check updates at: http://tanzil.net/updates/
```

## كيف نلتزم بالشروط

| الشرط | التطبيق في مُوطِّن |
|---|---|
| لا تغيير في النص | الملف لا يُعدَّل يدويًا ولا آليًا؛ الكود يقرؤه فقط (`backend/app/pipeline/quran.py`)، والتطبيع للمطابقة يتم في الذاكرة دون الكتابة على الملف |
| ذكر المصدر بوضوح مع رابط tanzil.net | هذا الملف، و`docs/SOURCES.md` (المصدر Q2). **مطلوب:** ذكر «نص القرآن: مشروع تنزيل» مع رابط tanzil.net في واجهة الموقع (م. فارس) |
| إرفاق الإشعار مع النسخ | هذا الملف `NOTICE.md` بجانب النص |
| متابعة التحديثات | عند تحديث النص من tanzil.net يُستبدل الملف كاملًا ويُحدَّث تاريخ التنزيل أدناه |

## معلومات النسخة في المستودع

- أُضيف الملف في: 2026-10-02 (commit `6cefc60`).
- عدد الأسطر: 6236 آية.
- SHA-256: `7b5fad15f662402ed9c811045ed4a3e5e0d4aa7ffdc0dfd0f484c16bde3328ee`
- رقم إصدار النص في Tanzil: يُكتب هنا عند إعادة التنزيل (لم يُحفظ مع الملف الحالي).

## الملف المشكول `quran-simple.txt` (D-044)

يُعرض منه نص الآية المطابَقة بتشكيله كما هو، ولا تُطابَق عليه الآيات (المطابقة على `quran-simple-clean.txt` وحده). نُسخة حرفية من تنزيل لم تُعدَّل، وكتلة الإشعار في آخره كما نشرها المشروع.

- **المصدر:** [tanzil.net/download](https://tanzil.net/download/) — نوع النص: Simple، بصيغة `سورة|آية|النص` (Text with aya numbers)، دون علامات الوقف ودون علامة السجدة ودون علامة الربع، مع الألف الخنجرية والتطويل (الخياران الافتراضيان).
- **الإصدار:** Tanzil Quran Text (Simple, Version 1.1)، Copyright (C) 2007-2026 Tanzil Project.
- **تاريخ التنزيل:** 2026-10-03.
- **عدد الأسطر:** 6236 آية.
- **SHA-256:** `7c30902a1060d14249791a24cb364ac8ae178455373fd545633b33a2254d3151`
- **اختلاف الرسم:** 6 آيات يختلف رسمها بين هذا الإصدار وملف المطابقة الأقدم (2:181، 5:31، 8:6، 13:37، 17:32، 39:56: «بعدما/بعد ما»، «ويلتا/ويلتى»، «الزنا/الزنى»، «حسرتا/حسرتى»). تُربط كلماتها بقاعدتين محددتين (D-045): كلمة تُكتب كلمتين، وألف أخيرة تُكتب ألفًا مقصورة؛ ويُعرض نص هذا الملف بتشكيله كما هو، والمطابقة تبقى على ملف المطابقة دون تغيير.

## الملف العثماني `quran-uthmani.txt`

للقياس والاختبار فقط: يُقاس به أن الآية المنسوخة من مصحف إلكتروني بالرسم العثماني تُطابَق مع آيتها. لا يُعرض منه شيء ولا يُطابَق عليه في التشغيل (المطابقة على `quran-simple-clean.txt` وحده). نُسخة حرفية من تنزيل لم تُعدَّل، وكتلة الإشعار في آخره كما نشرها المشروع.

- **المصدر:** [tanzil.net/download](https://tanzil.net/download/) — نوع النص: Uthmani، بصيغة `سورة|آية|النص` (Text with aya numbers)، بالخيارات الافتراضية.
- **الإصدار:** Tanzil Quran Text (Uthmani, Version 1.1)، Copyright (C) 2007-2026 Tanzil Project.
- **تاريخ التنزيل:** 2026-10-06.
- **عدد الأسطر:** 6236 آية.
- **SHA-256:** `bf4f57b968d03f4131c070b1e285da9be0e0a108a21c910e872801ca273312c8`
