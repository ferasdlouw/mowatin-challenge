// Copyright (c) 2026 Athar Al-Madinah Team (فريق أثر المدينة). All rights reserved.
// Mowatin (مُوطِّن) — Proprietary. Source-available for evaluation only. See LICENSE.
// Layout is measured from the design boards (1536px wide; 1rem = 16px at that width).
import {
  PlayCircle, ShieldCheck, Globe, Star, Settings, Handshake, ScanSearch, Languages,
  Clock, Check, PenLine, BookOpen, BrainCircuit, Zap, ChevronDown, Rocket, Sparkles, Layers, ScrollText,
  CircleCheck, CloudCog,
} from 'lucide-react'
import Chip from './Chip'
import DemoCard from './DemoCard'
import { Skyline } from './Art'
import { useInView } from '../lib/useInView'
import { useLang, Fwd } from '../lib/i18n'

function Eyebrow({ children, light, className = '' }) {
  return <span className={`eyebrow ${light ? '!text-white' : ''} ${className}`}>{children}</span>
}

/* ═════════════════════════════ HERO ═════════════════════════════ */
export function Hero() {
  const { t, dir, lang } = useLang()
  return (
    <section id="top" className={`relative isolate overflow-hidden ${lang === 'en' ? 'xl:min-h-[33rem] xl:pb-[2.4rem]' : 'xl:h-[33rem]'}`}>
      {/* sky */}
      <div className="absolute inset-0 -z-10 bg-[linear-gradient(100deg,#DCE6EC_0%,#F1EADF_30%,#F7EEE2_48%,#EEF1F1_68%,#DDE8EF_100%)]" aria-hidden />
      <div className="absolute inset-0 -z-10 bg-[radial-gradient(60rem_26rem_at_30%_30%,rgba(255,244,226,.9),transparent_70%)]" aria-hidden />
      <div className="absolute inset-x-0 bottom-0 -z-10 h-[6rem] bg-gradient-to-t from-[#F3F2EE] to-transparent" aria-hidden />
      {/* imagery */}
      <div className="pointer-events-none absolute bottom-0 left-0 -z-10 hidden h-full w-[21.9rem] overflow-hidden xl:block mask-hero-left">
        <img src="/images/hero_left.webp" alt={t('مسجد بمآذن وقباب عند الغروب', 'A mosque with minarets and domes at sunset')} className="drift h-full w-full object-cover object-left-bottom" />
      </div>
      <div className="pointer-events-none absolute bottom-0 right-0 -z-10 hidden h-full w-[10.9rem] xl:block mask-hero-right">
        <img src="/images/hero_right.webp" alt={t('قوس بزخرفة إسلامية هندسية ومصحف مفتوح على حامل خشبي', 'An arch with Islamic geometric patterns and an open Qur’an on a wooden stand')} className="h-full w-full object-cover object-left" />
      </div>

      <div dir="ltr" className="shell relative grid grid-cols-1 gap-12 py-12 xl:w-[82rem] xl:grid-cols-[39.75rem_34.5rem] xl:gap-[3.55rem] xl:py-0 xl:pr-[4.1rem]">
        <div dir={dir} className={`min-w-0 xl:pt-[3.85rem] ${lang === 'en' ? 'text-left' : 'text-right'}`}>
          <p className="text-[1.8rem] font-bold leading-none text-brand-800 sm:text-[2.2rem] xl:text-[2.5rem]">{t('مُوطِّن', 'Mowatin')}</p>
          <h1 className={`mt-[0.9rem] text-[1.6rem] font-bold leading-[1.4] sm:text-[2.1rem] sm:leading-[1.32] text-ink-900 [text-wrap:balance] ${lang === 'en' ? 'xl:text-[2.5rem] xl:leading-[3.3rem] xl:tracking-[-0.01em]' : 'xl:text-[2.85rem] xl:leading-[3.8rem]'}`}>
            {t('أداة تحمي المعنى الشرعي', 'Protecting Islamic meaning')}<br />{t('عند ترجمة المحتوى الإسلامي', 'when Islamic content is translated')}
          </h1>
          <p className="mt-[0.7rem] text-[1.15rem] text-ink-900 sm:text-[1.4rem] xl:text-[1.72rem]">{t('من العربية إلى لغات أخرى.', 'From Arabic into other languages.')}</p>
          <p className={`mt-[1.6rem] text-[1rem] text-ink-900/80 xl:text-[1.07rem] ${lang === 'en' ? 'max-w-[36rem] leading-[1.8rem]' : 'leading-[2rem]'}`}>
            {t('تضع مُوطِّن طبقة ذكية فوق أي أداة ترجمة، لتضمن أن تبقى الآيات والأحاديث', 'Mowatin adds a smart layer on top of any translation tool, so Qur’anic verses, hadith')}
            {' '}{lang === 'en' ? null : <br className="hidden xl:block" />}{t('والمصطلحات الشرعية صحيحة، وأن يصل المحتوى الإسلامي إلى العالم بأمان.', 'and Islamic terms stay correct, and Islamic content reaches the world safely.')}
          </p>
          <div className={`flex flex-wrap justify-start gap-[1.7rem] ${lang === 'en' ? 'mt-[2.2rem]' : 'mt-[2.75rem]'}`}>
            <a href="/app" className="btn-shine group inline-flex h-[3.45rem] w-[12.3rem] items-center justify-center gap-[0.8rem] rounded-[0.9rem] bg-brand-800 text-[1.12rem] font-bold text-white shadow-[0_0.9rem_1.8rem_-0.8rem_rgba(10,74,55,.7)] transition-colors hover:bg-brand-900">
              {t('ابدأ الآن', 'Get started')} <Fwd className="h-[1.35rem] w-[1.35rem] transition-transform duration-300 rtl:group-hover:-translate-x-1 ltr:group-hover:translate-x-1" aria-hidden />
            </a>
            <a href="#how" className="group inline-flex h-[3.45rem] w-[11rem] items-center justify-center gap-[0.7rem] rounded-[0.9rem] border-[1.5px] border-brand-800 bg-white/60 text-[1.12rem] font-bold text-brand-800 backdrop-blur-sm transition-colors hover:bg-white">
              {t('معرفة المزيد', 'Learn more')} <PlayCircle className="h-[1.5rem] w-[1.5rem] transition-transform duration-300 group-hover:scale-110" strokeWidth={1.75} aria-hidden />
            </a>
          </div>
          {lang === 'en' && <p className="mt-[1rem] max-w-[34rem] text-[0.9rem] leading-[1.5rem] text-ink-600">The tool itself is in Arabic: it is built for Arabic-speaking content creators, who paste an Arabic text and get it in English or French.</p>}
        </div>
        <div className="min-w-0 pt-12 xl:pt-[5.9rem]">
          <DemoCard />
        </div>
      </div>
    </section>
  )
}

/* ═════════════════════════════ WHY ═════════════════════════════ */
const WHY = [
  [ShieldCheck, 'يحمي المعنى الشرعي', 'من الأخطاء في الترجمة\nوالتأويل الخاطئ.', false, 'Protects Islamic meaning', 'From translation errors\nand misreadings.'],
  [Globe, 'يوصل رسالتك للعالم', 'بترجمات دقيقة ومعتمدة\nبالإنجليزية والفرنسية.', false, 'Carries your message', 'With accurate, approved translations\nin English and French.'],
  [Handshake, 'يعزز الثقة', 'بين المؤسسات الدعوية\nوالذكاء الاصطناعي.', true, 'Builds trust', 'Between da’wah organisations\nand AI.'],
  [Settings, 'مرن وسهل التكامل', 'يتوفر كخدمة (API) تدعم\nالجمعيات والتطبيقات والمنصات.', true, 'Easy to integrate', 'Available as an API for\norganisations, apps and platforms.'],
  [Star, 'محتوى بجودة عالية', 'مراعاة للسياق الشرعي\nوالثقافي لكل لغة.', true, 'High-quality content', 'Respects the religious and\ncultural context of each language.'],
]
export function Why() {
  const { t, dir } = useLang()
  return (
    <section className="bg-[#F6F9F8] pb-[2rem] pt-[2.7rem]">
      <div className="shell text-center xl:w-[85rem]">
        <Eyebrow className="text-[1.2rem]">{t('لماذا مُوطِّن؟', 'Why Mowatin?')}</Eyebrow>
        <h2 className="mt-[0.9rem] text-[1.45rem] font-bold text-ink-900 xl:text-[1.65rem]">{t('الجسر الآمن بين الذكاء الاصطناعي والمعنى الشرعي', 'A safe bridge between AI and Islamic meaning')}</h2>
        <ul className={`mt-[2.3rem] grid gap-y-10 sm:grid-cols-2 xl:grid-cols-5 xl:divide-x xl:divide-slate-200 ${dir === 'rtl' ? 'xl:divide-x-reverse' : ''}`}>
          {WHY.map(([I, ar, dar, filled, en, den]) => (
            <li key={ar} className="group px-[1rem] py-[0.6rem]">
              <span className="mx-auto grid h-[3.9rem] w-[3.9rem] place-items-center rounded-full bg-brand-100 text-brand-800 transition-transform duration-500 ease-out group-hover:-translate-y-1 group-hover:rotate-[8deg]">
                <I className="h-[1.85rem] w-[1.85rem]" strokeWidth={filled ? 1.5 : 1.75} fill={filled ? 'currentColor' : 'none'} fillOpacity={filled ? 0.9 : 0} stroke={filled ? '#0A4A37' : 'currentColor'} aria-hidden />
              </span>
              <h3 className="mt-[1.3rem] text-[1.12rem] font-bold text-ink-900">{t(ar, en)}</h3>
              <p className="mt-[0.55rem] whitespace-pre-line text-[0.98rem] leading-[1.7rem] text-ink-600">{t(dar, den)}</p>
            </li>
          ))}
        </ul>
      </div>
    </section>
  )
}

/* ═════════════════════════════ HOW ═════════════════════════════ */
function FlowArrow() {
  const { dir } = useLang()
  return (
    <li className="hidden self-center xl:block" aria-hidden>
      {/* points the reading direction: left in Arabic, right in English */}
      <svg viewBox="0 0 40 24" className={`flow-arrow mx-auto h-[1.6rem] w-[2.2rem] ${dir === 'rtl' ? '-scale-x-100' : ''}`} fill="none" stroke="#1FA672" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="M3 12h32M27 4l8 8-8 8" />
      </svg>
    </li>
  )
}

function StepCard({ n, title, body, violet, blue, children, footIcon: FootIcon, foot }) {
  const { dir } = useLang()
  return (
    <li dir={dir} className={`lift flex flex-col rounded-[1.4rem] border p-[1.6rem] ${violet ? 'border-[#E4DDF7] bg-gradient-to-b from-[#F7F3FE] to-[#FBFAFF]' : blue ? 'border-[#DCE8F5] bg-gradient-to-b from-[#F5F9FE] to-[#FAFCFF]' : 'border-[#DCEFE5] bg-gradient-to-b from-[#FBFEFC] to-[#F6FBF8]'}`}>
      <div className="flex items-center gap-[0.9rem]">
        <span className={`grid h-[3rem] w-[3rem] place-items-center rounded-full text-[1.45rem] font-bold text-white shadow-[0_0.5rem_1rem_-0.4rem_rgba(10,74,55,.6)] ${violet ? 'bg-[#6D4FC2]' : 'bg-brand-800'}`}>{n}</span>
        <h3 className={`text-[1.8rem] font-extrabold ${violet ? 'text-[#5B3FB0]' : 'text-ink-900'}`}>{title}</h3>
      </div>
      <p className="mt-[1.3rem] min-h-[5.1rem] text-[0.98rem] leading-[1.7rem] text-ink-900/75">{body}</p>
      <div className="mt-[1rem] flex-1 rounded-[0.9rem] border border-slate-100 bg-white p-[0.9rem] shadow-[0_0.6rem_1.6rem_-1rem_rgba(14,58,74,.25)]">{children}</div>
      <div className={`mt-[1.1rem] flex items-center gap-[0.9rem] rounded-[0.9rem] px-[1.1rem] py-[0.9rem] ${violet ? 'bg-[#F1ECFC]' : 'bg-brand-50'}`}>
        <FootIcon className={`h-[1.9rem] w-[1.9rem] shrink-0 ${violet ? 'text-[#6D4FC2]' : 'text-brand-800'}`} strokeWidth={1.75} aria-hidden />
        <div className="text-[0.86rem]"><b className="block text-[0.95rem] text-ink-900">{foot[0]}</b><span className="text-ink-600">{foot[1]}</span></div>
      </div>
    </li>
  )
}

export function HowItWorks() {
  const [ref, inView] = useInView({ threshold: 0.2 })
  const { t, dir, lang } = useLang()
  const en = lang === 'en'
  const rows2 = [
    ['general', <span key="g" className="latin block text-left">The text is translated smoothly and naturally.</span>],
    ['term', en
      ? <span key="t"><b>Taqwa</b> (God-consciousness)<span className="block text-[0.7rem] text-ink-600">with a short gloss</span></span>
      : <span key="t"><b>التقوى</b><span className="latin block text-right">(God-consciousness)</span><span className="text-[0.7rem] text-ink-600">مع شرح مختصر</span></span>],
    ['quran', <span key="q"><b>{t('سورة الحجرات (10)', 'Al-Hujurat 10')}</b><br /><span className="text-[0.7rem] text-ink-600">{t('(من الترجمة المعتمدة)', '(approved translation)')}</span></span>],
    ['hadith', <span key="h"><b>{t('صحيح البخاري (1)', 'Sahih al-Bukhari 1')}</b><br /><span className="text-[0.7rem] text-ink-600">{t('(من المصادر المعتمدة)', '(authenticated source)')}</span></span>],
  ]
  return (
    <section id="how" className="bg-[#F6F9F8] pb-[3rem]">
      <div ref={ref} className={`shell xl:w-[83.5rem] ${inView ? 'reveal-in' : 'reveal-wait'}`}>
        <div className="relative pt-[2.6rem]">
          <div className="relative text-center">
            <Eyebrow className="text-[1.45rem]">{t('كيف يعمل؟', 'How it works')}</Eyebrow>
            <h2 className="mt-[0.9rem] text-[1.9rem] font-extrabold text-ink-900 xl:text-[2.45rem]">{t('ثلاث خطوات لحماية المعنى الشرعي', 'Three steps to protect Islamic meaning')}</h2>
            <p className="mt-[0.8rem] text-[1.12rem] text-ink-900/70">{t('من الكشف إلى الترجمة الذكية ثم مراجعة المختص، ليُراجَع المعنى قبل النشر.', 'Detection, then smart translation, then a specialist’s review, so the meaning is checked before publishing.')}</p>
          </div>

          <ol dir={dir} className="relative mt-[2.2rem] grid items-stretch gap-6 xl:grid-cols-[1fr_2.6rem_1fr_2.6rem_1fr] xl:gap-0">
            <StepCard n={1} title={t('الكشف', 'Detect')} body={t('يقرأ النص ويحدد أين الآيات والأحاديث والمصطلحات الشرعية والنص العادي.', 'Reads the text and marks where the verses, hadith, Islamic terms and plain text are.')} footIcon={ScanSearch} foot={[t('تحليل ذكي للنص', 'Smart text analysis'), t('لكل نوع معاملة مختلفة.', 'Each type is handled differently.')]}>
              <div dir="rtl" className="flex gap-[0.8rem]">
                <div className="min-w-0 flex-1">
                  <p className="text-[0.86rem] leading-[1.75rem] text-ink-900">
                    قال الله تعالى: <mark className="hl rounded px-[0.2rem] font-quran text-quran-fg" style={{ '--i': 0, backgroundImage: 'linear-gradient(#E6F4ED,#E6F4ED)', backgroundColor: 'transparent' }}>﴿إِنَّمَا الْمُؤْمِنُونَ إِخْوَةٌ﴾</mark>{' '}
                    ثم قال النبي ﷺ: <mark className="hl rounded px-[0.2rem] text-hadith-fg" style={{ '--i': 1, backgroundImage: 'linear-gradient(#F0EBFB,#F0EBFB)', backgroundColor: 'transparent' }}>«إنما الأعمال بالنيات»</mark>{' '}
                    وهذا أصل في <mark className="hl rounded px-[0.2rem] text-term-fg" style={{ '--i': 2, backgroundImage: 'linear-gradient(#FDF1E3,#FDF1E3)', backgroundColor: 'transparent' }}>التقوى</mark>.
                  </p>
                  <div className="mt-[0.8rem] space-y-[0.45rem]">
                    {['quran', 'hadith', 'term', 'general'].map((t) => (
                      <div key={t} className="flex items-center justify-start rounded-[0.6rem] bg-paper px-[0.5rem] py-[0.35rem]"><Chip type={t}>{t === 'term' ? (en ? 'Islamic term (Taqwa)' : 'مصطلح شرعي (التقوى)') : undefined}</Chip></div>
                    ))}
                  </div>
                </div>
                <div className="hidden w-[4.4rem] shrink-0 space-y-[0.45rem] pt-[0.3rem] sm:block" aria-hidden>
                  {['#C9D4F0', '#D9D3F5', '#DCE5EF', '#BFE6D2', '#DCE5EF', '#F7DDBA', '#DCE5EF', '#DCE5EF'].map((c, i) => <i key={i} className="block h-[0.32rem] rounded-full" style={{ background: c, width: `${[100, 80, 92, 70, 96, 84, 74, 90][i]}%` }} />)}
                </div>
              </div>
            </StepCard>
            <FlowArrow />
            <StepCard blue n={2} title={t('الترجمة الذكية', 'Smart translation')} body={t('النص العادي يُترجم بسلاسة. المصطلحات الشرعية تُشرح أو تبقى بالعربية مع شرح مختصر. والآيات والأحاديث لا تُترجم من الصفر بل تُربط بترجمات معتمدة.', 'Plain text is translated fluently. Islamic terms are explained, or kept in Arabic with a short gloss. Verses and hadith are never translated from scratch; they are linked to approved translations.')} footIcon={Languages} foot={[t('ترجمة دقيقة ومتوازنة', 'Accurate, balanced translation'), t('يحافظ على المعنى الشرعي والسياق.', 'Keeps the religious meaning and context.')]}>
              <ul className="space-y-[0.5rem] text-[0.78rem]">
                {rows2.map(([t, o]) => (
                  <li key={t} dir={dir} className="grid grid-cols-[auto_1rem_1fr] items-center gap-[0.4rem]">
                    <Chip type={t} />
                    <Fwd className="h-[0.85rem] w-[0.85rem] text-brand-300" aria-hidden />
                    <span dir={dir} className="rounded-[0.6rem] bg-paper px-[0.7rem] py-[0.45rem] leading-[1.15rem] text-ink-900">{o}</span>
                  </li>
                ))}
              </ul>
            </StepCard>
            <FlowArrow />
            <StepCard violet n={3} title={t('مراجعة المختص', 'Specialist review')} body={t('النص الحساس يصل تلقائيًا إلى مراجع شرعي يوافق عليه أو يعدّله قبل النشر.', 'Sensitive passages go automatically to a qualified reviewer, who approves or edits them before publishing.')} footIcon={ShieldCheck} foot={[t('مراجعة بشرية قبل النشر', 'Human review before publishing'), t('ليُراجَع المعنى ويُعتمد قبل النشر.', 'So the meaning is checked and approved before publishing.')]}>
              <div dir={dir} className="flex items-start gap-[0.8rem]">
                <div className="w-[5.2rem] shrink-0 text-center">
                  <img src="/images/scholar.webp" alt={t('صورة رمزية لمراجع شرعي', 'Illustration of a reviewer')} className="mx-auto h-[4.3rem] w-[4.3rem] rounded-full ring-4 ring-[#F1ECFC]" />
                  <p className="mt-[0.35rem] text-[0.86rem] font-bold">{t('مراجع شرعي', 'Reviewer')}</p>
                  <p className="text-[0.72rem] leading-tight text-ink-600">{t('مراجعة وتدقيق المحتوى', 'Checks and verifies')}</p>
                </div>
                <div className="min-w-0 flex-1">
                  <span className="inline-flex items-center gap-[0.35rem] rounded-full border border-slate-200 px-[0.6rem] py-[0.2rem] text-[0.7rem] font-bold"><Clock className="h-[0.8rem] w-[0.8rem]" aria-hidden /> {t('قيد المراجعة', 'In review')}</span>
                  <div dir="rtl" className="mt-[0.6rem] rounded-[0.6rem] border border-slate-100 p-[0.6rem] text-right text-[0.78rem] leading-[1.45rem] shadow-sm">
                    قال تعالى: <span className="rounded bg-quran-bg px-1 font-quran text-quran-fg">﴿إِنَّمَا الْمُؤْمِنُونَ إِخْوَةٌ﴾</span><br />ثم قال النبي ﷺ: «إنما الأعمال بالنيات».
                  </div>
                </div>
              </div>
              <div className="mt-[0.9rem] grid grid-cols-2 gap-[0.6rem]" aria-hidden>
                <span className="inline-flex h-[2.4rem] items-center justify-center gap-[0.4rem] rounded-[0.6rem] border border-brand-300 text-[0.86rem] font-bold text-ink-900"><PenLine className="h-[1rem] w-[1rem]" aria-hidden /> {t('تعديل', 'Edit')}</span>
                <span className="inline-flex h-[2.4rem] items-center justify-center gap-[0.4rem] rounded-[0.6rem] bg-brand-800 text-[0.86rem] font-bold text-white"><Check className="h-[1rem] w-[1rem]" aria-hidden /> {t('موافق', 'Approve')}</span>
              </div>
            </StepCard>
          </ol>
        </div>

        <Banner title={t('مع مُوطِّن … أنت مطمئن', 'With Mowatin, publish with confidence')} sub={t('ذكاء اصطناعي يحترم قدسية النصوص، ويمنحك ثقة أكبر في نشر المحتوى الإسلامي عالميًا.', 'AI that respects the sanctity of the texts, and gives you more confidence publishing Islamic content worldwide.')} icon="side" />
      </div>
    </section>
  )
}

function Banner({ title, sub, icon = 'top' }) {
  const { dir } = useLang()
  return (
    <div className="relative mt-[2.4rem] overflow-hidden rounded-[1.4rem] border border-brand-100 bg-[linear-gradient(90deg,#EEF7F2,#F7FBF9_45%,#EEF7F2)] px-6 py-[2.2rem] text-center">
      <Skyline className="absolute bottom-0 left-0 h-[7rem] w-[18rem] opacity-[.09]" />
      <Skyline className="absolute bottom-0 right-0 h-[7rem] w-[18rem] opacity-[.09]" />
      {icon === 'top' && <ShieldCheck className="relative mx-auto h-[2rem] w-[2rem] text-brand-800" aria-hidden />}
      {icon === 'side' && (
        <span className={`absolute ${dir === 'rtl' ? 'right-[3.5rem]' : 'left-[3.5rem]'} top-1/2 hidden h-[5rem] w-[4.4rem] -translate-y-1/2 place-items-center xl:grid`} aria-hidden>
          <svg viewBox="0 0 50 56" className="absolute inset-0 h-full w-full"><path d="M25 2 46 10v17c0 13-9 22-21 27C13 49 4 40 4 27V10Z" fill="#0F6B4F" stroke="#E6F4ED" strokeWidth="3" /></svg>
          <Check className="relative h-[2rem] w-[2rem] text-white" strokeWidth={3} />
        </span>
      )}
      <h3 className="relative mt-[0.5rem] text-[1.6rem] font-extrabold text-brand-800 xl:text-[2rem]">{title}</h3>
      <p className="relative mt-[0.6rem] text-[1rem] text-ink-900/70">{sub}</p>
    </div>
  )
}

/* ═════════════════════════════ FEATURES ═════════════════════════════ */
function Feature({ Icon, title, body }) {
  return (
    <article className="lift flex gap-[1.1rem] rounded-[1rem] border border-slate-200/70 bg-white p-[1.4rem] shadow-[0_0.5rem_1.5rem_-1.2rem_rgba(14,58,74,.25)]">
      <span className="grid h-[3.9rem] w-[3.9rem] shrink-0 place-items-center rounded-full bg-brand-100 text-brand-800"><Icon className="h-[1.85rem] w-[1.85rem]" strokeWidth={1.75} aria-hidden /></span>
      <div className="pt-[0.35rem]">
        <h3 className="text-[1.22rem] font-bold leading-[1.75rem] text-ink-900">{title}</h3>
        <p className="mt-[0.7rem] text-[0.95rem] leading-[1.6rem] text-ink-900/65">{body}</p>
      </div>
    </article>
  )
}

export function Features() {
  const { t } = useLang()
  return (
    <section id="features" className="bg-[#F6F9F8] pb-[3rem] pt-[3.6rem]">
      <div className="shell xl:w-[89.5rem]">
        <div className="text-center">
          <Eyebrow className="text-[1.75rem]">{t('المميزات', 'Features')}</Eyebrow>
          <h2 className="mt-[0.9rem] text-[1.9rem] font-extrabold text-ink-900 xl:text-[2.5rem]">{t('كل ما تحتاجه لنشر المحتوى الإسلامي بأمان', 'Everything you need to publish Islamic content safely')}</h2>
          <p className="mx-auto mt-[0.9rem] max-w-[40rem] text-[1.05rem] leading-[1.75rem] text-ink-900/70">{t('ميزات تجمع بين الذكاء الاصطناعي ومراجعة المختصين، لحماية المعنى الشرعي وتسهيل نشر المحتوى الإسلامي بلغات أخرى.', 'Features that combine AI with specialist review, to protect Islamic meaning and make publishing in other languages easier.')}</p>
        </div>
        <div className="mt-[2.9rem] grid gap-[1.6rem] xl:grid-cols-[27.8rem_1fr_27.8rem]">
          <div className="grid content-start gap-[1.6rem]">
            <Feature Icon={BookOpen} title={t('ربط الآيات والأحاديث بمصادرها', 'Verses and hadith linked to their sources')} body={t('لا تُترجم الآيات أو الأحاديث من الصفر، بل تُربط بترجمات منشورة معروفة مع ذكر مصدرها.', 'Verses and hadith are never translated from scratch; they are linked to published, well-known translations, with the source named.')} />
            <Feature Icon={ShieldCheck} title={t('مراجعة بشرية متخصصة', 'Human specialist review')} body={t('النصوص الحساسة تُحال تلقائيًا إلى مراجع شرعي لمراجعتها واعتمادها قبل النشر.', 'Sensitive passages go to a qualified reviewer to check and approve before publishing.')} />
            <Feature Icon={Globe} title={t('مناسب للمؤسسات الدعوية', 'Built for da’wah organisations')} body={t('مصمم لاحتياجات الجهات الدعوية والمؤسسات الإسلامية التي تنشر رسالتها بلغات أخرى.', 'Designed around the needs of da’wah bodies and Islamic institutions sharing their message worldwide.')} />
          </div>
          <div className="grid content-between gap-[1.6rem]">
            <Feature Icon={Languages} title={t('دعم متعدد اللغات', 'English and French')} body={t('يتيح نشر المحتوى الإسلامي بالإنجليزية والفرنسية حاليًا، مع الحفاظ على الدقة والجودة في الترجمة.', 'Publish Islamic content in English and French today, with accuracy and quality kept intact.')} />
            <FeatureIllustration />
            <Feature Icon={Zap} title={t('سرعة وكفاءة', 'Fast and efficient')} body={t('يعمل بالذكاء الاصطناعي مع طبقات التحقق والمراجعة، ليوفّر الوقت والجهد.', 'AI with verification and review layers, saving time and effort.')} />
          </div>
          <div className="grid content-start gap-[1.6rem]">
            <Feature Icon={ShieldCheck} title={t('حماية المعنى الشرعي', 'Protects Islamic meaning')} body={t('يكشف الأخطاء في ترجمة الآيات والأحاديث والمصطلحات الشرعية، ويحرص على نقل المعنى الصحيح والموثّق.', 'Catches errors in translated verses, hadith and Islamic terms, and keeps the correct, documented meaning.')} />
            <Feature Icon={BrainCircuit} title={t('ترجمة ذكية للسياق', 'Context-aware translation')} body={t('تفهم السياق الديني واللغوي، وتفرق بين النص العادي والمصطلح الشرعي والآيات والأحاديث لتقديم ترجمة دقيقة ومناسبة.', 'Understands religious and linguistic context, and tells plain text apart from Islamic terms, verses and hadith.')} />
            <Feature Icon={CloudCog} title={t('جاهز للتكامل (API)', 'Ready to integrate (API)')} body={t('يمكن دمج الخدمة مع جمعيات الدعوة، وتطبيقات القرآن، والمنصات الإسلامية لاستخدامها بسهولة.', 'Plug the service into da’wah organisations, Qur’an apps and Islamic platforms with little effort.')} />
          </div>
        </div>
        <Banner title={t('نُعلِّم الآلة لتخدم الرسالة', 'We teach the machine to serve the message')} sub={t('معًا نحو نشر إسلامي آمن … بلغات العالم.', 'Together toward safe Islamic publishing, in the languages of the world.')} />
      </div>
    </section>
  )
}

function FeatureIllustration() {
  const [ref, inView] = useInView({ threshold: 0.4 })
  const { t } = useLang()
  return (
    <div ref={ref} dir="rtl" className={`relative mx-auto w-full max-w-[31rem] py-[1rem] xl:-mx-[1.6rem] xl:w-[calc(100%+3.2rem)] xl:max-w-none ${inView ? 'reveal-in' : 'reveal-wait'}`}>
      <div className="absolute inset-x-[10%] -inset-y-[1rem] rounded-full bg-[radial-gradient(closest-side,rgba(166,215,195,.45),transparent)]" aria-hidden />
      <div className="relative ml-auto w-full rounded-[1rem] border border-slate-100 bg-white p-[0.9rem] sm:w-[76%] sm:pl-[2.6rem] shadow-[0_1.4rem_3rem_-1.4rem_rgba(14,58,74,.35)]">
        <div dir="ltr" className="mb-[0.6rem] flex gap-[0.3rem]" aria-hidden><i className="h-[0.38rem] w-[0.38rem] rounded-full bg-slate-300" /><i className="h-[0.38rem] w-[0.38rem] rounded-full bg-slate-300" /><i className="h-[0.38rem] w-[0.38rem] rounded-full bg-slate-300" /></div>
        <div className="flex items-start justify-between gap-2">
          <div className="rounded-[0.5rem] bg-brand-50 px-[0.5rem] py-[0.3rem]"><Chip type="quran" /></div>
          <p className="text-[0.82rem]">قال تعالى: <span className="font-quran text-[0.95rem]">﴿إِنَّمَا الْمُؤْمِنُونَ إِخْوَةٌ﴾</span><span className="block text-center text-[0.72rem] text-ink-600">(الحجرات: 10)</span></p>
        </div>
        <div className="mt-[0.5rem] flex items-center gap-[0.5rem] rounded-[0.6rem] bg-[#F2F7FB] px-[0.7rem] py-[0.5rem]">
          <CircleCheck className="h-[1.1rem] w-[1.1rem] shrink-0 fill-brand-800 text-white" aria-hidden />
          <span className="latin flex-1 text-left text-[0.72rem] leading-[1.05rem]">The believers are but brothers…<br /><span className="text-brand-800">(Approved translation)</span></span>
        </div>
        <div className="relative mt-[0.8rem] ml-auto flex w-[82%] items-center gap-[0.7rem] rounded-[0.8rem] border border-slate-100 bg-white p-[0.7rem] shadow-[0_0.8rem_1.6rem_-1rem_rgba(14,58,74,.35)]">
          <img src="/images/scholar.webp" alt={t('صورة رمزية لمراجع شرعي', 'Illustration of a reviewer')} className="h-[2.9rem] w-[2.9rem] rounded-full" />
          <div className="flex-1"><p className="text-[0.86rem] font-bold">{t('مراجعة المختص', 'Specialist review')}</p><p className="text-[0.72rem] text-ink-600">{t('تمت المراجعة والموافقة', 'Reviewed and approved')}</p></div>
          <CircleCheck className="h-[1.5rem] w-[1.5rem] shrink-0 fill-brand-800 text-white" aria-hidden />
        </div>
      </div>
      <div className="absolute left-0 top-[2.6rem] hidden w-[30%] space-y-[0.45rem] sm:block rounded-[0.9rem] border border-slate-100 bg-white/95 p-[0.5rem] shadow-[0_1rem_2rem_-1rem_rgba(14,58,74,.35)]">
        {['quran', 'hadith', 'term', 'general'].map((t, i) => (
          <div key={t} className="hl rounded-[0.5rem] px-[0.4rem] py-[0.3rem]" style={{ '--i': i, backgroundImage: `linear-gradient(${['#E6F4ED', '#F0EBFB', '#FDF1E3', '#EEF2F7'][i]},${['#E6F4ED', '#F0EBFB', '#FDF1E3', '#EEF2F7'][i]})` }}><Chip type={t} /></div>
        ))}
      </div>
      <svg viewBox="0 0 60 120" className="flow-arrow pointer-events-none absolute left-[30%] top-[4.5rem] hidden h-[6rem] w-[3rem] xl:block" fill="none" stroke="#A7D7C3" strokeWidth="2" strokeLinecap="round" aria-hidden>
        <path d="M2 20h40M34 13l8 7-8 7" /><path d="M2 95h40M34 88l8 7-8 7" />
      </svg>
    </div>
  )
}

/* ═════════════════════════════ FAQ ═════════════════════════════ */
const FAQ_EN = [
  ['Does Mowatin issue fatwas?', 'No. Mowatin is a localisation tool. It does not issue rulings or judge personal cases. When such a question comes up, it carries over the general information and refers the reader to a qualified authority.'],
  ['Does it translate the Qur’an?', 'It never machine-translates verses. It recognises the verse, inserts a translation of its meanings from an approved source with the surah and verse number, and warns if the verse was quoted incorrectly.'],
  ['Which languages are supported?', 'Today: Arabic into English and French. The architecture is built to add more languages, each with a verified glossary before launch.'],
  ['Does it replace human review?', 'No. Its output is AI-assisted and needs qualified review before publishing. Mowatin shortens that review by pointing to exactly the passages that need it.'],
  ['Do you store the text I enter?', 'We don’t store your text: it stays in the server’s memory for one hour only, and is sent for translation to the free Google and OpenRouter models. The tool doesn’t ask for any personal data.'],
]
const FAQ = [
  ['هل يُصدر مُوطِّن فتاوى؟', 'لا. مُوطِّن أداة توطين، لا يستقل بالفتوى ولا يحكم في الحالات الشخصية. عند ورود مسألة من هذا النوع ينقل المعلومة العامة ويُحيل إلى جهة مؤهلة.'],
  ['هل يترجم القرآن الكريم؟', 'لا يترجم الآيات آليًا. يتعرّف على الآية ويُدرج ترجمة معانيها من مصدر معتمد مع ذكر السورة ورقم الآية، وينبّه إذا كان النص منقولًا بخطأ.'],
  ['ما اللغات المدعومة؟', 'حاليًا: من العربية إلى الإنجليزية والفرنسية. المعمارية مصممة لإضافة لغات أخرى مع مسرد موثّق لكل لغة قبل إطلاقها.'],
  ['هل يغني عن المراجعة البشرية؟', 'لا. مخرجاته مدعومة بالذكاء الاصطناعي وتحتاج مراجعة مؤهلة قبل النشر. مُوطِّن يختصر هذه المراجعة بتحديد المقاطع التي تحتاجها بالضبط.'],
  ['هل تُحفظ النصوص التي أُدخلها؟', 'لا نخزّن نصك: يبقى في ذاكرة الخادم ساعة واحدة فقط، ويُرسل للترجمة إلى نماذج Google وOpenRouter المجانية. ولا نطلب بيانات شخصية لاستخدام الأداة.'],
]
export function Faq() {
  const { t, lang } = useLang()
  return (
    <section id="faq" className="bg-[#F6F9F8] py-[3.6rem]">
      <div className="shell max-w-3xl xl:w-[52rem] xl:max-w-none">
        <div className="text-center">
          <Eyebrow className="text-[1.3rem]">{t('الأسئلة الشائعة', 'FAQ')}</Eyebrow>
          <h2 className="mt-[0.8rem] text-[1.9rem] font-extrabold text-ink-900 xl:text-[2.2rem]">{t('أسئلة قبل أن تبدأ', 'Questions before you start')}</h2>
        </div>
        <div className="mt-[2.2rem] space-y-[0.8rem]">
          {(lang === 'en' ? FAQ_EN : FAQ).map(([q, a]) => (
            <details key={q} className="group rounded-[1rem] border border-slate-200/70 bg-white px-[1.4rem] py-[1.1rem] shadow-[0_0.5rem_1.5rem_-1.2rem_rgba(14,58,74,.25)] transition-shadow open:shadow-[0_1.2rem_2.4rem_-1.4rem_rgba(14,58,74,.35)]">
              <summary className="flex cursor-pointer list-none items-center justify-between gap-4 text-[1.05rem] font-bold text-ink-900 [&::-webkit-details-marker]:hidden">
                {q}<ChevronDown className="h-[1.25rem] w-[1.25rem] shrink-0 text-brand-800 transition-transform duration-300 group-open:rotate-180" aria-hidden />
              </summary>
              <p className="mt-[0.7rem] text-[0.98rem] leading-[1.75rem] text-ink-900/70">{a}</p>
            </details>
          ))}
        </div>
      </div>
    </section>
  )
}

/* ═════════════════════════════ CTA ═════════════════════════════ */
export function Cta() {
  const { t, dir } = useLang()
  const mini = [
    ['quran', '﴿إِنَّمَا الْمُؤْمِنُونَ إِخْوَةٌ﴾', t('(الحجرات: 10)', '(Al-Hujurat 10)'), t('تم ربطها بترجمة معتمدة', 'Linked to an approved translation'), BookOpen, '#E6F4ED', '#0F6B4F', t('آية قرآنية', 'Qur’anic verse')],
    ['hadith', 'قال ﷺ: «إنما الأعمال بالنيات»', '', t('تم ربطه بمرجع موثّق', 'Linked to an authenticated source'), ScrollText, '#F0EBFB', '#6D4FC2', t('حديث نبوي', 'Hadith')],
    ['term', 'التقوى', t('مراقبة الله في السر والعلن.', 'Taqwa: God-consciousness, in private and in public.'), t('مع شرح مختصر', 'With a short gloss'), Layers, '#FDF1E3', '#B45309', t('مصطلح شرعي', 'Islamic term')],
  ]
  const bottom = [
    [Sparkles, t('دقة في المعنى الشرعي', 'Accurate religious meaning'), t('ترجمة ذكية تكشف التحريف وسوء الفهم\nوتُحيل ما يحتاج مراجعة.', 'Smart translation that flags distortion\nand refers what needs review.')],
    [Globe, t('الإنجليزية والفرنسية', 'English and French'), t('انشر رسالتك الإسلامية إلى\nأنحاء العالم.', 'Share your Islamic message\nacross the world.')],
    [ShieldCheck, t('أمان وموثوقية', 'Safe and reliable'), t('لا يُنشر مقطع محال\nقبل اعتماد المراجع.', 'Nothing flagged is published\nbefore a reviewer approves it.')],
    [Rocket, t('سهولة الاستخدام', 'Easy to use'), t('واجهة بسيطة وواضحة\nتجعل الترجمة أكثر سهولة.', 'A simple, clear interface\nthat makes translation easier.')],
  ]
  return (
    <section id="start" className="relative overflow-x-clip overflow-y-hidden bg-[linear-gradient(180deg,#F2F8F5,#F7FAF9_70%,#F6F9F8)]">
      <div className="relative">
        <Skyline className="absolute bottom-0 left-0 h-[13rem] w-[34rem] opacity-[.07]" />
        <Skyline className="absolute bottom-0 right-0 h-[13rem] w-[34rem] opacity-[.07]" />
        <div dir="ltr" className="shell relative grid grid-cols-1 items-center gap-12 py-[3.6rem] xl:w-[86rem] xl:grid-cols-[44rem_1fr] xl:pb-[3rem] xl:pt-[4.2rem]">
          {/* illustration */}
          <div className="relative mx-auto h-[27rem] w-full max-w-[44rem] overflow-hidden sm:overflow-visible">
            <svg viewBox="0 0 200 240" className="absolute left-[11.6rem] top-[-2.6rem] hidden h-[28rem] sm:block" aria-hidden>
              <defs><linearGradient id="arch" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#D6EDE1" /><stop offset="1" stopColor="#D6EDE1" stopOpacity="0" /></linearGradient></defs>
              <path d="M100 6C130 46 192 64 192 140V240H8V140C8 64 70 46 100 6Z" fill="url(#arch)" />
            </svg>
            <img src="/images/quran_leaves.webp" alt={t('مصحف على حامل خشبي بين أوراق خضراء', 'A Qur’an on a wooden stand among green leaves')} className="pointer-events-none absolute bottom-[-0.6rem] left-[-1.5rem] z-20 hidden h-[21rem] w-auto mix-blend-multiply mask-feather sm:block" />
            <div dir={dir} className="lift absolute right-0 top-[0.8rem] z-10 w-[min(29.3rem,100%)] sm:left-[9.5rem] sm:right-auto rounded-[1.1rem] border border-slate-100 bg-white p-[1.1rem] shadow-[0_2rem_4rem_-1.6rem_rgba(14,58,74,.35)]">
              <div className="flex items-center justify-between border-b border-slate-100 pb-[0.7rem]">
                <span className="flex items-center gap-[0.4rem] text-[1.1rem] font-extrabold text-brand-800"><img src="/images/logo_icon.webp" alt={t('شعار مُوطِّن', 'Mowatin logo')} className="h-[1.6rem] w-auto mix-blend-multiply" />{t('مُوطِّن', 'Mowatin')}</span>
                <span dir="ltr" className="flex gap-[0.35rem]" aria-hidden><i className="h-[0.55rem] w-[0.55rem] rounded-full bg-[#F87171]" /><i className="h-[0.55rem] w-[0.55rem] rounded-full bg-[#FBBF24]" /><i className="h-[0.55rem] w-[0.55rem] rounded-full bg-[#34D399]" /></span>
              </div>
              <ul className="mt-[0.9rem] space-y-[0.6rem]">
                {mini.map(([type, s, sub, note, I, bg, fg, label]) => (
                  <li key={type} className="grid grid-cols-2 gap-[0.6rem]">
                    <div className="flex items-center justify-between rounded-[0.8rem] p-[0.7rem]" style={{ background: bg }}>
                      <div>
                        <p className="text-[0.95rem] font-bold" style={{ color: fg }}>{label}</p>
                        <p className="mt-[0.2rem] flex items-center gap-[0.25rem] text-[0.72rem] text-ink-600"><CircleCheck className="h-[0.8rem] w-[0.8rem] fill-brand-800 text-white" aria-hidden />{note}</p>
                      </div>
                      <span className="grid h-[2.6rem] w-[2.6rem] place-items-center rounded-full bg-white/80" style={{ color: fg }}><I className="h-[1.3rem] w-[1.3rem]" strokeWidth={1.75} aria-hidden /></span>
                    </div>
                    <div className="grid place-items-center rounded-[0.8rem] bg-paper p-[0.6rem] text-center">
                      <p dir="rtl" className={type === 'quran' ? 'font-quran text-[0.95rem]' : type === 'term' ? 'text-[0.95rem] font-bold' : 'text-[0.8rem]'}>{s}</p>
                      {sub && <p className="text-[0.72rem] text-ink-600">{sub}</p>}
                    </div>
                  </li>
                ))}
                <li className="flex items-center justify-between rounded-[0.8rem] bg-brand-50 px-[0.9rem] py-[0.7rem]">
                  <span><b className="block text-[0.95rem]">{t('نص عادي', 'Plain text')}</b><span className="text-[0.7rem] text-ink-600">{t('تمت ترجمته بسلاسة', 'Translated fluently')}</span></span>
                  <span className="flex items-center gap-[1rem] text-brand-800"><Fwd className="h-[1.2rem] w-[1.2rem]" aria-hidden /><Globe className="h-[1.3rem] w-[1.3rem]" aria-hidden /></span>
                </li>
              </ul>
            </div>
          </div>

          {/* copy */}
          <div dir={dir} className="text-center">
            <Eyebrow className="text-[1.75rem]">{t('ابدأ الآن', 'Get started')}</Eyebrow>
            <h2 className="mt-[1.4rem] text-[2.4rem] font-extrabold leading-[1.35] text-ink-900 xl:text-[3.35rem] xl:leading-[4.65rem]">{t('انشر المحتوى الإسلامي', 'Publish Islamic content')}<br />{t('بأمان إلى العالم', 'safely, to the world')}</h2>
            <p className="mx-auto mt-[1.2rem] max-w-[38rem] text-[1.1rem] leading-[2.7rem] text-ink-900/75 xl:text-[1.25rem]">{t('استخدم مُوطِّن الآن واحصل على ترجمة دقيقة تراعي المعنى الشرعي', 'Use Mowatin for accurate translation that respects religious meaning')}{dir === 'rtl' ? <br className="hidden xl:block" /> : null} {t('وتحافظ على أصالة النصوص الإسلامية.', 'and keeps Islamic texts authentic.')}</p>
            <a href="/app" className="btn-shine group mx-auto mt-[2.4rem] inline-flex h-[4.9rem] w-[23rem] max-w-full items-center justify-center gap-[1.1rem] rounded-full bg-gradient-to-b from-[#1C7D5A] to-brand-800 text-[1.5rem] font-bold text-white shadow-[0_1.4rem_2.6rem_-1.2rem_rgba(10,74,55,.75)] transition-[filter] hover:brightness-110">
              {t('ابدأ الآن', 'Get started')} <Fwd className="h-[1.7rem] w-[1.7rem] transition-transform duration-300 rtl:group-hover:-translate-x-1.5 ltr:group-hover:translate-x-1.5" aria-hidden />
            </a>
            <p className="mt-[1.3rem] flex items-center justify-center gap-[0.5rem] text-[1rem] text-ink-600"><ShieldCheck className="h-[1.2rem] w-[1.2rem] text-brand-800" aria-hidden /> {t('بدون تسجيل · لا نخزّن نصوصك', 'No sign-up · We don’t store your text')}</p>
          </div>
        </div>
      </div>

      <div className="shell relative pb-[3rem] xl:w-[86rem]">
        <div className="mx-auto mb-[2.4rem] h-px w-full bg-gradient-to-l from-transparent via-brand-300 to-transparent" aria-hidden />
        <ul className={`grid gap-10 sm:grid-cols-2 xl:grid-cols-4 xl:divide-x xl:divide-slate-200 ${dir === 'rtl' ? 'xl:divide-x-reverse' : ''}`}>
          {bottom.map(([I, ti, d]) => (
            <li key={ti} className="group px-6 text-center">
              <span className="mx-auto grid h-[4.1rem] w-[4.1rem] place-items-center rounded-full bg-brand-100 text-brand-800 transition-transform duration-500 group-hover:-translate-y-1"><I className="h-[1.8rem] w-[1.8rem]" strokeWidth={1.75} aria-hidden /></span>
              <h3 className="mt-[1.1rem] text-[1.25rem] font-bold text-brand-900">{ti}</h3>
              <p className="mt-[0.5rem] whitespace-pre-line text-[1rem] leading-[1.7rem] text-ink-600">{d}</p>
            </li>
          ))}
        </ul>
      </div>
    </section>
  )
}
