// Copyright (c) 2026 Athar Al-Madinah Team (فريق أثر المدينة). All rights reserved.
// Mowatin (مُوطِّن) — Proprietary. Source-available for evaluation only. See LICENSE.
//
// DEMO DATA — used only while the backend is not connected (no VITE_API_URL).
// Shapes follow the API contract in docs/ARCHITECTURE.md. Verse translations are
// copied verbatim from data/quran/translations/{en,fr}.json (QuranEnc.com, docs/SOURCES.md T1),
// wrapped in ﴿﴾ like the server does; a partial quote gets the full verse (D-006).

const QURAN_EN = 'Saheeh International — QuranEnc.com v1.1.2'
const QURAN_FR = 'Rachid Maach — QuranEnc.com v1.0.3'

const info = (text) => ({ severity: 'info', text })
const warn = (text) => ({ severity: 'warn', text })
const block = (text) => ({ severity: 'block', text })

export const EXAMPLES = [
  {
    id: 'basics',
    label: 'فقرة دعوية',
    label_en: 'Da‘wah paragraph',
    hint: 'مصطلحات + آية + حديث',
    hint_en: 'Terms + verse + hadith',
    text: 'التوحيد أساس الإسلام، وهو إفراد الله بالعبادة. قال الله تعالى: ﴿إِنَّمَا الْمُؤْمِنُونَ إِخْوَةٌ﴾. وقال النبي ﷺ: «إنما الأعمال بالنيات». فالعبادة تشمل كل ما يحبه الله من الأقوال والأعمال.',
    segments: [
      {
        source: 'التوحيد أساس الإسلام، وهو إفراد الله بالعبادة.',
        type: 'term_heavy', level: 'A', confidence: 0.95,
        terms: [['التوحيد', 'tawhid'], ['الإسلام', 'islam'], ['بالعبادة', 'ibadah']],
        en: { out: 'Tawhid (the Oneness of God) is the foundation of Islam: devoting all worship to God alone.', marks: ['Tawhid', 'Islam', 'worship'],
          generic: 'Monotheism is the basis of Islam, which is the unity of God in worship.', wrong: ['unity'], why: '«unity» من المقابلات التي يحذّر منها المسرد؛ توحي بالوحدانية العددية فقط.' },
        fr: { out: 'Le Tawhîd (l\'unicité de Dieu) est le fondement de l\'islam : vouer toute adoration à Dieu seul.', marks: ['Tawhîd', 'l\'islam', 'adoration'],
          generic: 'Le monothéisme est la base de l\'islam, c\'est l\'unité de Dieu dans le culte.', wrong: ['unité'], why: '«unité» مقابل يحذّر منه المسرد للتوحيد.' },
        sources: [{ kind: 'glossary', ref: 'المسرد: التوحيد، الإسلام، العبادة' }],
        flags: [],
      },
      {
        source: 'قال الله تعالى: ﴿إِنَّمَا الْمُؤْمِنُونَ إِخْوَةٌ﴾.',
        type: 'quran', level: 'A', confidence: 1,
        en: { out: '﴿The believers are but brothers, so make settlement between your brothers. And fear Allāh that you may receive mercy.﴾', marks: [],
          generic: 'God Almighty said: Indeed, the believers are brothers.', wrong: ['Indeed, the believers are brothers.'], why: 'ترجمة آلية حرّة للآية دون مرجع ولا ترجمة معتمدة.' },
        fr: { out: '﴿En réalité, les croyants sont des frères. Réconciliez donc vos frères ! Craignez Allah de manière à être touchés par Sa grâce !﴾', marks: [],
          generic: 'Dieu Tout-Puissant a dit : En effet, les croyants sont frères.', wrong: ['En effet, les croyants sont frères.'], why: 'ترجمة آلية حرّة للآية دون مرجع.' },
        sources: [{ kind: 'quran', ref: 'الحجرات 49:10', edition: { en: QURAN_EN, fr: QURAN_FR } }],
        flags: [info('أُدرجت ترجمة الآية كاملة من ترجمة معتمدة، ولم تُترجم آليًا.')],
      },
      {
        source: 'وقال النبي ﷺ: «إنما الأعمال بالنيات».',
        type: 'hadith', level: 'A', confidence: 0.93,
        en: { out: 'The Prophet ﷺ said: “Actions are only by intentions.” (Al-Bukhari 1; Muslim 1907)', marks: [],
          generic: 'The Prophet said: Works are by intentions.', wrong: ['Works are by intentions.'], why: 'نُقل الحديث دون مصدر ولا درجة.' },
        fr: { out: 'Le Prophète ﷺ a dit : « Les actes ne valent que par les intentions. » (Al-Bukhârî 1 ; Muslim 1907)', marks: [],
          generic: 'Le Prophète a dit : Les œuvres sont par les intentions.', wrong: ['Les œuvres sont par les intentions.'], why: 'نُقل الحديث دون مصدر ولا درجة.' },
        sources: [{ kind: 'hadith', ref: 'صحيح البخاري 1 · صحيح مسلم 1907', grade: 'صحيح' }],
        flags: [info('ترجمة معنى؛ المصدر والدرجة محفوظان.')],
      },
      {
        source: 'فالعبادة تشمل كل ما يحبه الله من الأقوال والأعمال.',
        type: 'general', level: 'B', confidence: 0.9,
        terms: [['فالعبادة', 'ibadah']],
        en: { out: 'So worship includes every word and deed that God loves.', marks: ['worship'],
          generic: 'Worship includes all words and actions that God loves.', wrong: [], why: '' },
        fr: { out: 'Ainsi, l\'adoration englobe toute parole et tout acte que Dieu aime.', marks: ['l\'adoration'],
          generic: 'Le culte comprend toutes les paroles et actions que Dieu aime.', wrong: ['Le culte'], why: '«le culte» وحده يحصر العبادة في الشعائر.' },
        sources: [{ kind: 'glossary', ref: 'المسرد: العبادة' }],
        flags: [],
      },
    ],
  },
  {
    id: 'errors',
    label: 'نص فيه أخطاء',
    label_en: 'Text with errors',
    hint: 'آية محرّفة + قول بلا مصدر',
    hint_en: 'Altered verse + unsourced saying',
    text: 'قال الله تعالى: ﴿قُلْ هُوَ اللَّهُ وَاحِدٌ﴾. وقال النبي ﷺ: «اطلبوا العلم ولو في الصين». والسنة هدي النبي ﷺ.',
    segments: [
      {
        source: 'قال الله تعالى: ﴿قُلْ هُوَ اللَّهُ وَاحِدٌ﴾.',
        type: 'quran', level: 'A', confidence: 0.4,
        en: { out: '﴿Say, "He is Allāh, [who is] One,﴾', marks: [],
          generic: 'God said: Say, He is God, one.', wrong: ['Say, He is God, one.'], why: 'بنى الترجمة على نص محرّف دون أي تنبيه.' },
        fr: { out: '﴿Dis : « Allah est la seule et unique divinité.﴾', marks: [],
          generic: 'Dieu a dit : Dis, Il est Dieu, un.', wrong: ['Dis, Il est Dieu, un.'], why: 'بنى الترجمة على نص محرّف دون تنبيه.' },
        sources: [{ kind: 'quran', ref: 'الإخلاص 112:1', edition: { en: QURAN_EN, fr: QURAN_FR } }],
        flags: [block('النص المُدخل لا يطابق الآية. الصحيح: ﴿قُلْ هُوَ اللَّهُ أَحَدٌ﴾ (الإخلاص: 1). أُدرجت ترجمة النص الصحيح، ويلزم تصحيح الأصل.')],
        review: true,
      },
      {
        source: 'وقال النبي ﷺ: «اطلبوا العلم ولو في الصين».',
        type: 'hadith', level: 'C', confidence: 0.2,
        en: { out: null, marks: [],
          generic: 'The Prophet said: Seek knowledge even in China.', wrong: ['The Prophet said:'], why: 'نسب القول إلى النبي ﷺ دون أي مصدر.' },
        fr: { out: null, marks: [],
          generic: 'Le Prophète a dit : Cherchez la science même en Chine.', wrong: ['Le Prophète a dit :'], why: 'نسب القول إلى النبي ﷺ دون مصدر.' },
        sources: [],
        flags: [block('لم يُعثر على مصدر معتمد لهذا القول في المصادر المتاحة؛ لم يُترجَم بوصفه حديثًا، وأُحيل للمراجعة.')],
        review: true,
      },
      {
        source: 'والسنة هدي النبي ﷺ.',
        type: 'term_heavy', level: 'A', confidence: 0.93,
        terms: [['والسنة', 'sunnah']],
        en: { out: 'The Sunnah is the guidance and way of the Prophet ﷺ.', marks: ['Sunnah'],
          generic: 'The year is the guidance of the Prophet.', wrong: ['The year'], why: 'خلط بين «السُّنّة» و«السَّنة» (العام).' },
        fr: { out: 'La Sunna est la guidance et la voie du Prophète ﷺ.', marks: ['La Sunna'],
          generic: 'L\'année est la guidance du Prophète.', wrong: ['L\'année'], why: 'خلط بين «السُّنّة» و«السَّنة».' },
        sources: [{ kind: 'glossary', ref: 'المسرد: السنة' }],
        flags: [],
      },
    ],
  },
  {
    id: 'fatwa',
    label: 'سؤال شخصي',
    label_en: 'Personal question',
    hint: 'مستوى (د): إحالة لا حكم',
    hint_en: 'Level D: referral, not a ruling',
    text: 'أنا أعيش في فرنسا، هل يجوز لي أن أتزوج بهذه الطريقة؟',
    segments: [
      {
        source: 'أنا أعيش في فرنسا، هل يجوز لي أن أتزوج بهذه الطريقة؟',
        type: 'fatwa_like', level: 'D', confidence: 0.88,
        en: { out: 'I live in France. Is it permissible for me to marry in this way?', marks: [],
          generic: 'I live in France, is it permissible for me to marry this way? Yes, it is allowed if…', wrong: ['Yes, it is allowed if…'], why: 'أضاف حكمًا شرعيًا من عنده.' },
        fr: { out: 'Je vis en France. M\'est-il permis de me marier de cette manière ?', marks: [],
          generic: 'Je vis en France, ai-je le droit de me marier ainsi ? Oui, c\'est permis si…', wrong: ['Oui, c\'est permis si…'], why: 'أضاف حكمًا شرعيًا من عنده.' },
        sources: [],
        flags: [warn('حالة شخصية تتطلب فتوى من مختص. تُرجم السؤال كما هو دون إضافة أي حكم، ويُحال لجهة مؤهلة.')],
        review: true,
      },
    ],
  },
]
