// Copyright (c) 2026 Athar Al-Madinah Team (فريق أثر المدينة). All rights reserved.
// Mowatin (مُوطِّن) — Proprietary. Source-available for evaluation only. See LICENSE.
import { useCallback, useEffect, useState } from 'react'
import { Languages, Columns2, ShieldCheck, ArrowRight, Radio, CircleHelp, X } from 'lucide-react'
import TranslateView from './TranslateView'
import CompareView from './CompareView'
import ReviewView from './ReviewView'
import Tour from './Tour'
import { translate, MODE, needsReview } from '../lib/api'
import { EXAMPLES } from '../data/examples'

const TABS = [
  ['translate', 'الترجمة', Languages],
  ['compare', 'قبل وبعد', Columns2],
  ['review', 'لوحة المراجع', ShieldCheck],
]

const REASON = { quran: 'آية لا تطابق النص المعتمد', hadith: 'قول بلا مصدر معتمد', fatwa_like: 'حالة شخصية تتطلب فتوى', term_heavy: 'ثقة منخفضة في مصطلح', general: 'ثقة منخفضة' }
const TITLE = { quran: 'آية قرآنية', hadith: 'حديث نبوي', fatwa_like: 'سؤال شخصي', term_heavy: 'مصطلح شرعي', general: 'نص عام' }

// Only translated segments (confidence set) reach the reviewer; detection-only
// results have nothing to approve.
function toQueueItems(segments, lang, queueIds) {
  const flagged = queueIds ? (s) => queueIds.includes(s.id) : needsReview
  return segments.filter((s) => s.confidence != null && flagged(s)).map((s) => ({
    id: `${lang}:${s.source}`, type: s.type, lang, source: s.source, proposed: s.output, ref: s.sources[0]?.ref,
    flags: s.flags, title: `${TITLE[s.type]} · ${s.source.replace(/^(قال الله تعالى|وقال النبي ﷺ|قال النبي ﷺ):?\s*/, '').slice(0, 34)}`,
    reason: REASON[s.type], status: 'pending', reviewerNote: '',
  }))
}

function seedQueue() {
  const out = []
  for (const [exId, lang] of [['errors', 'en'], ['fatwa', 'fr']]) {
    const ex = EXAMPLES.find((e) => e.id === exId)
    const segs = ex.segments.map((s) => ({ ...s, output: s[lang].out, sources: s.sources }))
    out.push(...toQueueItems(segs, lang))
  }
  return out
}

// The guided tour opens once, on the first visit to the translate screen.
const tourSeen = () => { try { return localStorage.getItem('mowatin.tour.v2') === 'done' } catch { return false } }

// Visitors who read the landing page in English get a short English note on how to use the Arabic tool.
const cameFromEnglish = () => {
  try { return localStorage.getItem('mowatin.lang') === 'en' && sessionStorage.getItem('mowatin.enNote') !== 'closed' } catch { return false }
}

const tabFromHash = () => (TABS.some(([k]) => `#${k}` === window.location.hash) ? window.location.hash.slice(1) : 'translate')

export default function ToolApp() {
  const [tab, setTab] = useState(tabFromHash)
  const [state, setState] = useState({ text: '', lang: 'en', audience: 'general_non_muslim', status: 'idle', result: null, error: null, exampleId: null })
  const [queue, setQueue] = useState(seedQueue)
  const [tour, setTour] = useState(() => tabFromHash() === 'translate' && !tourSeen())
  const [enNote, setEnNote] = useState(cameFromEnglish)
  const closeEnNote = () => { setEnNote(false); try { sessionStorage.setItem('mowatin.enNote', 'closed') } catch { /* storage blocked */ } }

  useEffect(() => {
    const on = () => setTab(tabFromHash())
    window.addEventListener('hashchange', on)
    document.title = 'مُوطِّن · الأداة'
    return () => window.removeEventListener('hashchange', on)
  }, [])
  const go = (k) => { window.history.pushState(null, '', `#${k}`); setTab(k) }

  const run = useCallback(async () => {
    setState((s) => ({ ...s, status: 'loading', error: null }))
    try {
      const result = await translate({ text: state.text, target_lang: state.lang, audience: state.audience })
      if (result.demo_only) { setState((s) => ({ ...s, status: 'demo', result: null })); return }
      setState((s) => ({ ...s, status: 'done', result, resultLang: state.lang }))
      const items = toQueueItems(result.segments, state.lang, result.review_queue)
      if (items.length) setQueue((q) => [...items.filter((it) => !q.some((x) => x.id === it.id)), ...q])
    } catch (e) {
      setState((s) => ({ ...s, status: 'error', error: e.message || 'حدث خطأ غير متوقع.' }))
    }
  }, [state.text, state.lang, state.audience])

  const pending = queue.filter((q) => q.status === 'pending').length

  return (
    <div className="min-h-screen bg-[#F4F7F6]">
      <header className="sticky top-0 z-30 border-b border-slate-200/70 bg-white/90 backdrop-blur-md">
        <div className="mx-auto flex h-[4rem] max-w-[90rem] items-center justify-between gap-[1rem] px-4 xl:px-[2rem]">
          <a href="/" className="flex items-center gap-[0.5rem]" aria-label="مُوطِّن: العودة إلى الموقع">
            <img src="/images/logo_icon.webp" alt="" className="h-[2.6rem] w-auto mix-blend-multiply" />
            <span className="text-[1.6rem] font-extrabold text-brand-800">مُوطِّن</span>
          </a>
          <nav data-tour="tabs" className="flex rounded-[0.8rem] bg-paper p-[0.25rem]" aria-label="شاشات الأداة">
            {TABS.map(([k, l, I]) => (
              <button key={k} type="button" onClick={() => go(k)} aria-current={tab === k ? 'page' : undefined}
                className={`relative flex items-center gap-[0.4rem] rounded-[0.6rem] px-[0.7rem] py-[0.45rem] text-[0.88rem] font-bold transition-all sm:px-[1rem] ${tab === k ? 'bg-white text-brand-800 shadow-sm' : 'text-ink-600 hover:text-ink-900'}`}>
                <I className="h-[1rem] w-[1rem]" aria-hidden /><span className="sr-only sm:not-sr-only">{l}</span>
                {k === 'review' && pending > 0 && <span className="tabular grid h-[1.15rem] min-w-[1.15rem] place-items-center rounded-full bg-danger-fg px-[0.25rem] text-[0.72rem] text-white">{pending}</span>}
              </button>
            ))}
          </nav>
          <div className="flex items-center gap-[0.8rem]">
            <button type="button" onClick={() => { go('translate'); setTour(true) }} title="جولة تعريفية" aria-label="جولة تعريفية بالأداة"
              className="inline-flex items-center gap-[0.3rem] rounded-full p-[0.35rem] text-[0.86rem] font-bold text-ink-600 hover:bg-paper hover:text-brand-800 lg:px-[0.6rem]">
              <CircleHelp className="h-[1.15rem] w-[1.15rem]" aria-hidden /><span className="hidden lg:inline">جولة تعريفية</span>
            </button>
            <span className={`hidden items-center gap-[0.35rem] rounded-full px-[0.7rem] py-[0.25rem] text-[0.74rem] font-bold md:inline-flex ${MODE === 'live' ? 'bg-brand-50 text-brand-800' : 'bg-pending-bg text-pending-fg'}`} title={MODE === 'live' ? 'متصل بخادم مُوطِّن' : 'الخادم غير متصل بعد؛ الأمثلة مُعدّة مسبقًا'}>
              <Radio className="h-[0.8rem] w-[0.8rem]" aria-hidden />{MODE === 'live' ? 'متصل' : 'عرض تجريبي'}
            </span>
            <a href="/" className="hidden items-center gap-[0.3rem] text-[0.86rem] font-bold text-ink-600 hover:text-brand-800 sm:inline-flex"><ArrowRight className="h-[1rem] w-[1rem]" aria-hidden /> الموقع</a>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-[90rem] px-4 py-[1.4rem] xl:px-[2rem]">
        {enNote && (
          <div dir="ltr" lang="en" role="note" className="mb-[1rem] flex items-start gap-[0.6rem] rounded-[0.8rem] border border-brand-100 bg-white px-[0.9rem] py-[0.65rem] text-[0.86rem] leading-[1.4rem] text-ink-900">
            <Languages className="mt-[0.15rem] h-[1rem] w-[1rem] shrink-0 text-brand-800" aria-hidden />
            <p className="flex-1">This tool is in Arabic: paste an Arabic text, choose <b>English</b> or <b>Français</b>, and press the green button. Try one of the examples under the text box first.</p>
            <button type="button" onClick={closeEnNote} className="-m-[0.2rem] rounded-full p-[0.2rem] text-ink-600 hover:bg-paper" aria-label="Close"><X className="h-[0.9rem] w-[0.9rem]" aria-hidden /></button>
          </div>
        )}
        {tab === 'translate' && (
          <div className="mb-[1.2rem]">
            <h1 className="text-[1.6rem] font-extrabold text-ink-900">من النص العربي إلى ترجمة دقيقة وآمنة</h1>
            <p className="text-ink-600">الآيات من ترجمات معتمدة، والمصطلحات مقفلة على المسرد، وكل ما لا يمكن التحقق منه يُحال إلى مراجع.</p>
          </div>
        )}
        {tab === 'translate' && <TranslateView state={state} setState={setState} run={run} />}
        {tour && tab === 'translate' && <Tour onClose={() => setTour(false)} />}
        {tab === 'compare' && <CompareView state={state} goTranslate={() => go('translate')} />}
        {tab === 'review' && <ReviewView queue={queue} setQueue={setQueue} />}
        {/* Required attribution for the verse text and translations: docs/SOURCES.md Q2, T1 */}
        <p className="mt-[1.4rem] text-center text-[0.76rem] text-ink-600">
          نص القرآن الكريم: <a href="https://tanzil.net" target="_blank" rel="noopener noreferrer" className="underline underline-offset-2 hover:text-brand-800">مشروع تنزيل (tanzil.net)</a>
          {' · '}ترجمات المعاني: <a href="https://quranenc.com" target="_blank" rel="noopener noreferrer" className="underline underline-offset-2 hover:text-brand-800">QuranEnc.com</a>
          {' · '}<a href="/about" className="underline underline-offset-2 hover:text-brand-800">المصادر وحقوق النشر</a>
        </p>
      </main>
    </div>
  )
}
