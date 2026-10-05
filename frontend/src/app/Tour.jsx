// Copyright (c) 2026 Athar Al-Madinah Team (فريق أثر المدينة). All rights reserved.
// Mowatin (مُوطِّن) — Proprietary. Source-available for evaluation only. See LICENSE.
//
// First-visit guided tour of the translate screen. Each step spotlights an
// element marked with data-tour="<id>" and explains it in one or two lines.
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'
import { X } from 'lucide-react'
import { MODE } from '../lib/api'
import { useLang } from '../lib/i18n'

// The first step has no target: it explains what the tool is before showing where things are.
// Each step is [Arabic, English]; `pick` reads the interface language.
const STEPS = [
  { id: 'intro', title: ['أهلًا بك في مُوطِّن', 'Welcome to Mowatin'],
    body: ['أداة تترجم المحتوى الدعوي من العربية إلى الإنجليزية والفرنسية دون أن يضيع المعنى الشرعي:', 'A tool that translates da‘wah content from Arabic into English and French without losing the religious meaning:'],
    points: [
      ['الآيات لا تُترجم آليًا، بل تُدرج من ترجمة معتمدة مع اسم السورة ورقم الآية.', 'Verses are not machine-translated: they are inserted from an approved translation with the surah name and verse number.'],
      ['المصطلحات الشرعية تُترجم بمقابل ثابت من مسرد موثّق.', 'Islamic terms get a fixed equivalent from a verified glossary.'],
      ['ما يُشكّ فيه (آية محرّفة، قول بلا مصدر، سؤال يحتاج فتوى) يُحال إلى مراجع شرعي بدل نشره.', 'Anything doubtful (an altered verse, an unsourced saying, a question that needs a fatwa) goes to a qualified reviewer instead of being published.'],
    ] },
  { id: 'input', title: ['الصق نصك العربي هنا', 'Paste your Arabic text here'],
    body: ['أي نص دعوي تريد نشره بلغة أخرى: خطبة، أو مقال، أو منشور فيه آية أو حديث أو مصطلحات شرعية. ويمكنك رفع ملف Word أو PDF؛ يُقرأ داخل متصفحك، ولا يُرسل منه إلا النص عند الترجمة. ولا نخزّن نصك: يبقى في ذاكرة الخادم ساعة واحدة فقط.',
      'Any da‘wah text you want to publish in another language: a sermon, an article, or a post with a verse, a hadith or Islamic terms. You can also upload a Word or PDF file; it is read in your browser and only its text is sent when you translate. We do not store your text: it stays in server memory for one hour only.'] },
  { id: 'examples', title: ['أول مرة؟ جرّب مثالًا', 'First time? Try an example'],
    body: ['الأمثلة تعرض النتيجة كاملة بضغطة. ابدأ بـ«نص فيه أخطاء»: فيه آية محرّفة وقول بلا مصدر، وسترى كيف يكشفهما مُوطِّن.', 'The examples show the full result in one click. Start with “Text with errors”: it has an altered verse and an unsourced saying, and you will see how Mowatin catches them.'],
    note: MODE === 'demo' ? ['الأداة الآن نسخة تجريبية: تعمل الأمثلة الجاهزة فقط، وترجمة نصك أنت تعمل عند ربط الخادم قريبًا.', 'The tool is a demo for now: only the ready examples work, and translating your own text works once the server is connected.'] : null },
  { id: 'options', title: ['اللغة والجمهور', 'Language and audience'],
    body: ['اختر لغة الترجمة (الإنجليزية أو الفرنسية)، ومن ستُوجَّه إليه، فيتغيّر الأسلوب والشرح دون المعنى.', 'Choose the translation language (English or French) and who it is for: the style and explanations change, not the meaning.'] },
  { id: 'run', title: ['ابدأ الترجمة', 'Start translating'],
    body: ['اضغط هنا: نكشف الآيات والأحاديث والمصطلحات، ثم نترجم، ثم نتحقق ونُحيل ما يحتاج مراجعة.', 'Press here: we detect verses, hadiths and terms, then translate, then verify and refer what needs review.'] },
  { id: 'results', title: ['ماذا تحصل عليه؟', 'What do you get?'],
    body: ['تظهر هنا النتيجة مقطعًا مقطعًا:', 'The result appears here, segment by segment:'],
    points: [
      ['ترجمة كل مقطع مع نوعه: آية، حديث، مصطلح، نص عادي.', 'Each segment’s translation with its type: verse, hadith, term, plain text.'],
      ['مصدر كل آية وحديث، ودرجة ثقة لكل مقطع.', 'The source of every verse and hadith, and a confidence score for each segment.'],
      ['تنبيه واضح على ما لا يُنشر قبل مراجعته. واضغط أي مصطلح ملوّن لترى شرحه.', 'A clear warning on what must not be published before review. Click any coloured term to see its explanation.'],
    ] },
  { id: 'tabs', title: ['شاشات أخرى', 'Other screens'],
    body: ['«قبل وبعد» تقارن نتيجة مُوطِّن بالترجمة التقليدية على النص نفسه، و«لوحة المراجع» يعتمد فيها المراجع الشرعي ما أُحيل إليه.', '“Before & after” compares Mowatin with a conventional translation of the same text, and in the “Reviewer panel” the reviewer approves what was referred.'] },
]

const markSeen = () => { try { localStorage.setItem('mowatin.tour.v2', 'done') } catch { /* storage blocked */ } }

const PAD = 8 // spotlight padding around the target
const GAP = 12 // space between spotlight and card

export default function Tour({ onClose }) {
  const [i, setI] = useState(0)
  const [rect, setRect] = useState(null)
  const [pos, setPos] = useState(null)
  const cardRef = useRef(null)
  const nextRef = useRef(null)
  const { t, dir } = useLang()
  const pick = (pair) => pair && t(...pair)
  const { id } = STEPS[i]
  const title = pick(STEPS[i].title), body = pick(STEPS[i].body), note = pick(STEPS[i].note)
  const points = STEPS[i].points?.map(pick)
  const last = i === STEPS.length - 1

  const finish = useCallback(() => {
    markSeen()
    onClose()
    document.getElementById('src')?.focus({ preventScroll: true })
  }, [onClose])

  // Bring the target into view, then track it while the page scrolls or resizes.
  useLayoutEffect(() => {
    const el = document.querySelector(`[data-tour="${id}"]`)
    if (!el) { setRect(null); return } // e.g. the intro: centred card, no spotlight
    const reduce = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
    el.scrollIntoView({ block: 'center', behavior: reduce ? 'auto' : 'smooth' })
    const measure = () => setRect(el.getBoundingClientRect())
    measure()
    window.addEventListener('scroll', measure, { passive: true })
    window.addEventListener('resize', measure)
    return () => { window.removeEventListener('scroll', measure); window.removeEventListener('resize', measure) }
  }, [id])

  // Place the card below the target, or above it, or pinned to the bottom when neither fits.
  useLayoutEffect(() => {
    const card = cardRef.current
    if (!card) return
    const h = card.offsetHeight, w = card.offsetWidth, vw = window.innerWidth, vh = window.innerHeight
    if (!rect) { setPos({ top: (vh - h) / 2, left: (vw - w) / 2 }); return }
    let top = rect.bottom + PAD + GAP
    if (top + h > vh - GAP) top = rect.top - PAD - GAP - h
    if (top < GAP) top = vh - h - GAP
    const left = Math.min(Math.max(rect.left + rect.width / 2 - w / 2, 16), vw - w - 16)
    setPos({ top, left })
  }, [rect, i])

  useEffect(() => { nextRef.current?.focus({ preventScroll: true }) }, [i])
  useEffect(() => {
    const onKey = (e) => {
      const fwd = dir === 'rtl' ? 'ArrowLeft' : 'ArrowRight' // RTL: left is forward
      const back = dir === 'rtl' ? 'ArrowRight' : 'ArrowLeft'
      if (e.key === 'Escape') finish()
      else if (e.key === fwd && !last) setI((n) => n + 1)
      else if (e.key === back && i > 0) setI((n) => n - 1)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [finish, last, i, dir])

  const spot = rect && {
    top: Math.max(rect.top - PAD, 4), left: Math.max(rect.left - PAD, 4),
    width: Math.min(rect.width + PAD * 2, window.innerWidth - 8), height: rect.height + PAD * 2,
  }

  return (
    <div className="fixed inset-0 z-50" dir={dir}>
      {/* blocks clicks on the page while the tour is open */}
      <div className="absolute inset-0" aria-hidden onClick={(e) => e.stopPropagation()} />
      {spot
        ? <div className="pointer-events-none absolute rounded-[1rem] ring-2 ring-brand-300 transition-all duration-300 ease-out" style={{ ...spot, boxShadow: '0 0 0 9999px rgba(14,58,74,.6)' }} aria-hidden />
        : <div className="absolute inset-0 bg-[rgba(14,58,74,.6)]" aria-hidden />}

      <div ref={cardRef} role="dialog" aria-modal="true" aria-labelledby="tour-title" aria-describedby="tour-body"
        className={`absolute ${id === 'intro' ? 'w-[min(26rem,calc(100vw-2rem))]' : 'w-[min(22rem,calc(100vw-2rem))]'} rounded-[1rem] bg-white p-[1rem] shadow-[0_1.4rem_3rem_-1rem_rgba(14,58,74,.5)] transition-[top,left] duration-300 ease-out`}
        style={pos ?? { visibility: 'hidden' }}>
        <div className="flex items-start justify-between gap-[0.5rem]">
          <p className="tabular text-[0.74rem] font-bold text-brand-800">{i + 1} / {STEPS.length}</p>
          <button type="button" onClick={finish} className="-m-[0.3rem] rounded-full p-[0.3rem] text-ink-600 hover:bg-paper" aria-label={t('إغلاق الجولة', 'Close the tour')}><X className="h-[1rem] w-[1rem]" aria-hidden /></button>
        </div>
        <h2 id="tour-title" className="mt-[0.2rem] text-[1.05rem] font-bold text-ink-900">{title}</h2>
        <div id="tour-body" className="mt-[0.35rem] text-[0.88rem] leading-[1.55rem] text-ink-600">
          <p>{body}</p>
          {points && (
            <ul className="mt-[0.4rem] space-y-[0.3rem]">
              {points.map((p) => <li key={p} className="flex gap-[0.45rem]"><span className="mt-[0.6rem] h-[0.35rem] w-[0.35rem] shrink-0 rounded-full bg-brand-600" aria-hidden />{p}</li>)}
            </ul>
          )}
          {note && <p className="mt-[0.5rem] rounded-[0.6rem] bg-pending-bg px-[0.7rem] py-[0.45rem] text-[0.8rem] leading-[1.35rem] text-[#8A3A0C]">{note}</p>}
        </div>
        <div className="mt-[0.5rem] flex gap-[0.3rem]" aria-hidden>
          {STEPS.map(({ id: k }, n) => <span key={k} className={`h-[0.3rem] flex-1 rounded-full ${n <= i ? 'bg-brand-600' : 'bg-slate-200'}`} />)}
        </div>
        <div className="mt-[0.9rem] flex items-center justify-between gap-[0.5rem]">
          <button type="button" onClick={finish} className="text-[0.82rem] font-bold text-ink-600 hover:text-ink-900">{t('تخطَّ الجولة', 'Skip the tour')}</button>
          <div className="flex gap-[0.4rem]">
            {i > 0 && <button type="button" onClick={() => setI(i - 1)} className="rounded-[0.6rem] border border-slate-200 px-[0.8rem] py-[0.4rem] text-[0.85rem] font-bold text-ink-900 hover:bg-paper">{t('السابق', 'Back')}</button>}
            <button ref={nextRef} type="button" onClick={() => (last ? finish() : setI(i + 1))} className="rounded-[0.6rem] bg-brand-800 px-[1rem] py-[0.4rem] text-[0.85rem] font-bold text-white hover:bg-brand-900">{last ? t('ابدأ الآن', 'Start now') : t('حسنًا، التالي', 'OK, next')}</button>
          </div>
        </div>
      </div>
    </div>
  )
}
