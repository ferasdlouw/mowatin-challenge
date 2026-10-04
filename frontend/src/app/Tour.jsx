// Copyright (c) 2026 Athar Al-Madinah Team (فريق أثر المدينة). All rights reserved.
// Mowatin (مُوطِّن) — Proprietary. Source-available for evaluation only. See LICENSE.
//
// First-visit guided tour of the translate screen. Each step spotlights an
// element marked with data-tour="<id>" and explains it in one or two lines.
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'
import { X } from 'lucide-react'
import { MODE } from '../lib/api'

// The first step has no target: it explains what the tool is before showing where things are.
const STEPS = [
  { id: 'intro', title: 'أهلًا بك في مُوطِّن', body: 'أداة تترجم المحتوى الدعوي من العربية إلى الإنجليزية والفرنسية دون أن يضيع المعنى الشرعي:',
    points: ['الآيات لا تُترجم آليًا، بل تُدرج من ترجمة معتمدة مع اسم السورة ورقم الآية.', 'المصطلحات الشرعية تُترجم بمقابل ثابت من مسرد موثّق.', 'ما يُشكّ فيه (آية محرّفة، قول بلا مصدر، سؤال يحتاج فتوى) يُحال إلى مراجع شرعي بدل نشره.'] },
  { id: 'input', title: 'الصق نصك العربي هنا', body: 'أي نص دعوي تريد نشره بلغة أخرى: خطبة، أو مقال، أو منشور فيه آية أو حديث أو مصطلحات شرعية. ويمكنك رفع ملف Word أو PDF؛ يُقرأ داخل متصفحك، ولا يُرسل منه إلا النص عند الترجمة. ولا نخزّن نصك: يبقى في ذاكرة الخادم ساعة واحدة فقط.' },
  { id: 'examples', title: 'أول مرة؟ جرّب مثالًا', body: 'الأمثلة تعرض النتيجة كاملة بضغطة. ابدأ بـ«نص فيه أخطاء»: فيه آية محرّفة وقول بلا مصدر، وسترى كيف يكشفهما مُوطِّن.',
    note: MODE === 'demo' ? 'الأداة الآن نسخة تجريبية: تعمل الأمثلة الجاهزة فقط، وترجمة نصك أنت تعمل عند ربط الخادم قريبًا.' : null },
  { id: 'options', title: 'اللغة والجمهور', body: 'اختر لغة الترجمة (الإنجليزية أو الفرنسية)، ومن ستُوجَّه إليه، فيتغيّر الأسلوب والشرح دون المعنى.' },
  { id: 'run', title: 'ابدأ الترجمة', body: 'اضغط هنا: نكشف الآيات والأحاديث والمصطلحات، ثم نترجم، ثم نتحقق ونُحيل ما يحتاج مراجعة.' },
  { id: 'results', title: 'ماذا تحصل عليه؟', body: 'تظهر هنا النتيجة مقطعًا مقطعًا:',
    points: ['ترجمة كل مقطع مع نوعه: آية، حديث، مصطلح، نص عادي.', 'مصدر كل آية وحديث، ودرجة ثقة لكل مقطع.', 'تنبيه واضح على ما لا يُنشر قبل مراجعته. واضغط أي مصطلح ملوّن لترى شرحه.'] },
  { id: 'tabs', title: 'شاشات أخرى', body: '«قبل وبعد» تقارن نتيجة مُوطِّن بالترجمة التقليدية على النص نفسه، و«لوحة المراجع» يعتمد فيها المراجع الشرعي ما أُحيل إليه.' },
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
  const { id, title, body, points, note } = STEPS[i]
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
      if (e.key === 'Escape') finish()
      else if (e.key === 'ArrowLeft' && !last) setI((n) => n + 1) // RTL: left is forward
      else if (e.key === 'ArrowRight' && i > 0) setI((n) => n - 1)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [finish, last, i])

  const spot = rect && {
    top: Math.max(rect.top - PAD, 4), left: Math.max(rect.left - PAD, 4),
    width: Math.min(rect.width + PAD * 2, window.innerWidth - 8), height: rect.height + PAD * 2,
  }

  return (
    <div className="fixed inset-0 z-50" dir="rtl">
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
          <button type="button" onClick={finish} className="-m-[0.3rem] rounded-full p-[0.3rem] text-ink-600 hover:bg-paper" aria-label="إغلاق الجولة"><X className="h-[1rem] w-[1rem]" aria-hidden /></button>
        </div>
        <h2 id="tour-title" className="mt-[0.2rem] text-[1.05rem] font-bold text-ink-900">{title}</h2>
        <div id="tour-body" className="mt-[0.35rem] text-[0.88rem] leading-[1.55rem] text-ink-600">
          <p>{body}</p>
          {points && (
            <ul className="mt-[0.4rem] space-y-[0.3rem]">
              {points.map((t) => <li key={t} className="flex gap-[0.45rem]"><span className="mt-[0.6rem] h-[0.35rem] w-[0.35rem] shrink-0 rounded-full bg-brand-600" aria-hidden />{t}</li>)}
            </ul>
          )}
          {note && <p className="mt-[0.5rem] rounded-[0.6rem] bg-pending-bg px-[0.7rem] py-[0.45rem] text-[0.8rem] leading-[1.35rem] text-[#8A3A0C]">{note}</p>}
        </div>
        <div className="mt-[0.5rem] flex gap-[0.3rem]" aria-hidden>
          {STEPS.map(({ id: k }, n) => <span key={k} className={`h-[0.3rem] flex-1 rounded-full ${n <= i ? 'bg-brand-600' : 'bg-slate-200'}`} />)}
        </div>
        <div className="mt-[0.9rem] flex items-center justify-between gap-[0.5rem]">
          <button type="button" onClick={finish} className="text-[0.82rem] font-bold text-ink-600 hover:text-ink-900">تخطَّ الجولة</button>
          <div className="flex gap-[0.4rem]">
            {i > 0 && <button type="button" onClick={() => setI(i - 1)} className="rounded-[0.6rem] border border-slate-200 px-[0.8rem] py-[0.4rem] text-[0.85rem] font-bold text-ink-900 hover:bg-paper">السابق</button>}
            <button ref={nextRef} type="button" onClick={() => (last ? finish() : setI(i + 1))} className="rounded-[0.6rem] bg-brand-800 px-[1rem] py-[0.4rem] text-[0.85rem] font-bold text-white hover:bg-brand-900">{last ? 'ابدأ الآن' : 'حسنًا، التالي'}</button>
          </div>
        </div>
      </div>
    </div>
  )
}
