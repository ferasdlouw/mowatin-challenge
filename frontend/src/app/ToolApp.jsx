// Copyright (c) 2026 Athar Al-Madinah Team (فريق أثر المدينة). All rights reserved.
// Mowatin (مُوطِّن) — Proprietary. Source-available for evaluation only. See LICENSE.
import { useCallback, useEffect, useState } from 'react'
import { Languages, Columns2, ShieldCheck, ArrowLeft, ArrowRight, Radio, CircleHelp, X, Globe } from 'lucide-react'
import TranslateView from './TranslateView'
import CompareView from './CompareView'
import ReviewView from './ReviewView'
import Tour from './Tour'
import { translate, MODE, needsReview } from '../lib/api'
import { EXAMPLES } from '../data/examples'
import { useLang } from '../lib/i18n'

const TABS = [
  ['translate', 'الترجمة', 'Translate', Languages],
  ['compare', 'قبل وبعد', 'Before & after', Columns2],
  ['review', 'لوحة المراجع', 'Reviewer panel', ShieldCheck],
]

// [Arabic, English]; queue items keep both so the reviewer panel follows the interface language.
const REASON = {
  quran: ['آية لا تطابق النص المعتمد', 'Verse does not match the authoritative text'],
  hadith: ['قول بلا مصدر معتمد', 'Saying with no authoritative source'],
  fatwa_like: ['حالة شخصية تتطلب فتوى', 'Personal case that needs a fatwa'],
  term_heavy: ['ثقة منخفضة في مصطلح', 'Low confidence in a term'],
  general: ['ثقة منخفضة', 'Low confidence'],
}
// A quote found in several verses: not a mismatch, the place is unknown (D-076).
const AMBIGUOUS_REASON = ['نص يرد في أكثر من موضع من القرآن', 'Text found in more than one place in the Quran']
const TITLE = { quran: ['آية قرآنية', 'Quran verse'], hadith: ['حديث نبوي', 'Hadith'], fatwa_like: ['سؤال شخصي', 'Personal question'], term_heavy: ['مصطلح شرعي', 'Islamic term'], general: ['نص عام', 'General text'] }

// Only translated segments (confidence set) reach the reviewer; detection-only
// results have nothing to approve.
function toQueueItems(segments, lang, queueIds) {
  const flagged = queueIds ? (s) => queueIds.includes(s.id) : needsReview
  return segments.filter((s) => s.confidence != null && flagged(s)).map((s) => ({
    id: `${lang}:${s.source}`, type: s.type, lang, source: s.source, proposed: s.output, ref: s.sources[0]?.ref ?? s.candidates?.map((c) => c.ref).join('، '),
    flags: s.flags, title: TITLE[s.type] ?? TITLE.general, snippet: s.source.replace(/^(قال الله تعالى|وقال النبي ﷺ|قال النبي ﷺ):?\s*/, '').slice(0, 34),
    reason: s.verification === 'ambiguous_verse' ? AMBIGUOUS_REASON : REASON[s.type] ?? REASON.general, status: 'pending', reviewerNote: '',
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

// English visitors get a short note: the interface is English, but the text to translate is Arabic.
const enNoteClosed = () => {
  try { return sessionStorage.getItem('mowatin.enNote') === 'closed' } catch { return false }
}

const tabFromHash = () => (TABS.some(([k]) => `#${k}` === window.location.hash) ? window.location.hash.slice(1) : 'translate')

export default function ToolApp() {
  const { t, lang, setLang } = useLang()
  const [tab, setTab] = useState(tabFromHash)
  const [state, setState] = useState({ text: '', lang: 'en', audience: 'general_non_muslim', status: 'idle', result: null, error: null, exampleId: null })
  // Live mode starts empty: the queue holds only real results, never demo items.
  const [queue, setQueue] = useState(() => (MODE === 'demo' ? seedQueue() : []))
  const [tour, setTour] = useState(() => tabFromHash() === 'translate' && !tourSeen())
  const [enNoteOpen, setEnNoteOpen] = useState(() => !enNoteClosed())
  const enNote = lang === 'en' && enNoteOpen
  const closeEnNote = () => { setEnNoteOpen(false); try { sessionStorage.setItem('mowatin.enNote', 'closed') } catch { /* storage blocked */ } }

  useEffect(() => {
    const on = () => setTab(tabFromHash())
    window.addEventListener('hashchange', on)
    return () => window.removeEventListener('hashchange', on)
  }, [])
  useEffect(() => { document.title = t('مُوطِّن · الأداة', 'Mowatin · Tool') }, [t])
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
      setState((s) => ({ ...s, status: 'error', error: e.message || t('حدث خطأ غير متوقع.', 'An unexpected error occurred.') }))
    }
  }, [state.text, state.lang, state.audience, t])

  const pending = queue.filter((q) => q.status === 'pending').length

  return (
    <div className="min-h-screen bg-[#F4F7F6]">
      <header className="sticky top-0 z-30 border-b border-slate-200/70 bg-white/90 backdrop-blur-md">
        <div className="mx-auto flex h-[4rem] max-w-[90rem] items-center justify-between gap-[1rem] px-4 xl:px-[2rem]">
          <a href="/" className="flex items-center gap-[0.5rem]" aria-label={t('مُوطِّن: العودة إلى الموقع', 'Mowatin: back to the website')}>
            <img src="/images/logo_icon.webp" alt="" className="h-[2.6rem] w-auto mix-blend-multiply" />
            <span className="hidden text-[1.6rem] font-extrabold text-brand-800 sm:inline">{t('مُوطِّن', 'Mowatin')}</span>
          </a>
          <nav data-tour="tabs" className="flex rounded-[0.8rem] bg-paper p-[0.25rem]" aria-label={t('شاشات الأداة', 'Tool screens')}>
            {TABS.map(([k, ar, en, I]) => (
              <button key={k} type="button" onClick={() => go(k)} aria-current={tab === k ? 'page' : undefined}
                className={`relative flex items-center gap-[0.4rem] rounded-[0.6rem] px-[0.7rem] py-[0.45rem] text-[0.88rem] font-bold transition-all sm:px-[1rem] ${tab === k ? 'bg-white text-brand-800 shadow-sm' : 'text-ink-600 hover:text-ink-900'}`}>
                <I className="h-[1rem] w-[1rem]" aria-hidden /><span className="sr-only sm:not-sr-only">{t(ar, en)}</span>
                {k === 'review' && pending > 0 && <span className="tabular grid h-[1.15rem] min-w-[1.15rem] place-items-center rounded-full bg-danger-fg px-[0.25rem] text-[0.72rem] text-white">{pending}</span>}
              </button>
            ))}
          </nav>
          <div className="flex items-center gap-[0.8rem]">
            <button type="button" onClick={() => { go('translate'); setTour(true) }} title={t('جولة تعريفية', 'Guided tour')} aria-label={t('جولة تعريفية بالأداة', 'Guided tour of the tool')}
              className="inline-flex items-center gap-[0.3rem] rounded-full p-[0.35rem] text-[0.86rem] font-bold text-ink-600 hover:bg-paper hover:text-brand-800 lg:px-[0.6rem]">
              <CircleHelp className="h-[1.15rem] w-[1.15rem]" aria-hidden /><span className="hidden lg:inline">{t('جولة تعريفية', 'Guided tour')}</span>
            </button>
            <span className={`hidden items-center gap-[0.35rem] rounded-full px-[0.7rem] py-[0.25rem] text-[0.74rem] font-bold md:inline-flex ${MODE === 'live' ? 'bg-brand-50 text-brand-800' : 'bg-pending-bg text-pending-fg'}`} title={MODE === 'live' ? t('متصل بخادم مُوطِّن', 'Connected to the Mowatin server') : t('الخادم غير متصل بعد؛ الأمثلة مُعدّة مسبقًا', 'Server not connected yet; the examples are prepared in advance')}>
              <Radio className="h-[0.8rem] w-[0.8rem]" aria-hidden />{MODE === 'live' ? t('متصل', 'Live') : t('عرض تجريبي', 'Demo')}
            </span>
            <button type="button" onClick={() => setLang(lang === 'ar' ? 'en' : 'ar')} lang={lang === 'ar' ? 'en' : 'ar'} aria-label={lang === 'ar' ? 'Switch to English' : 'التبديل إلى العربية'}
              className="inline-flex items-center gap-[0.3rem] rounded-full p-[0.35rem] text-[0.86rem] font-bold text-ink-600 hover:bg-paper hover:text-brand-800 lg:px-[0.6rem]">
              <Globe className="h-[1.1rem] w-[1.1rem]" aria-hidden /><span className="hidden lg:inline">{lang === 'ar' ? 'English' : 'العربية'}</span>
            </button>
            <a href="/" className="hidden items-center gap-[0.3rem] text-[0.86rem] font-bold text-ink-600 hover:text-brand-800 lg:inline-flex">{lang === 'en' ? <ArrowLeft className="h-[1rem] w-[1rem]" aria-hidden /> : <ArrowRight className="h-[1rem] w-[1rem]" aria-hidden />} {t('الموقع', 'Website')}</a>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-[90rem] px-4 py-[1.4rem] xl:px-[2rem]">
        {enNote && (
          <div role="note" className="mb-[1rem] flex items-start gap-[0.6rem] rounded-[0.8rem] border border-brand-100 bg-white px-[0.9rem] py-[0.65rem] text-[0.86rem] leading-[1.4rem] text-ink-900">
            <Languages className="mt-[0.15rem] h-[1rem] w-[1rem] shrink-0 text-brand-800" aria-hidden />
            <p className="flex-1">Paste an <b>Arabic</b> text, choose <b>English</b> or <b>Français</b>, and press <b>Translate safely</b>. Try one of the examples under the text box first. Notes the server adds to each segment are in Arabic for now.</p>
            <button type="button" onClick={closeEnNote} className="-m-[0.2rem] rounded-full p-[0.2rem] text-ink-600 hover:bg-paper" aria-label="Close"><X className="h-[0.9rem] w-[0.9rem]" aria-hidden /></button>
          </div>
        )}
        {tab === 'translate' && (
          <div className="mb-[1.2rem]">
            <h1 className="text-[1.6rem] font-extrabold text-ink-900">{t('من النص العربي إلى ترجمة دقيقة وآمنة', 'From Arabic text to an accurate, safe translation')}</h1>
            <p className="text-ink-600">{t('الآيات من ترجمات معتمدة، والمصطلحات مقفلة على المسرد، وكل ما لا يمكن التحقق منه يُحال إلى مراجع.', 'Verses come from approved translations, terms are locked to the glossary, and anything that cannot be verified goes to a reviewer.')}</p>
          </div>
        )}
        {tab === 'translate' && <TranslateView state={state} setState={setState} run={run} />}
        {tour && tab === 'translate' && <Tour onClose={() => setTour(false)} />}
        {tab === 'compare' && <CompareView state={state} goTranslate={() => go('translate')} />}
        {tab === 'review' && <ReviewView queue={queue} setQueue={setQueue} />}
        {/* Required attribution for the verse text and translations: docs/SOURCES.md Q2, T1 */}
        <p className="mt-[1.4rem] text-center text-[0.76rem] text-ink-600">
          {t('نص القرآن الكريم:', 'Quran text:')} <a href="https://tanzil.net" target="_blank" rel="noopener noreferrer" className="underline underline-offset-2 hover:text-brand-800">{t('مشروع تنزيل (tanzil.net)', 'Tanzil project (tanzil.net)')}</a>
          {' · '}{t('ترجمات المعاني:', 'Translations of the meanings:')} <a href="https://quranenc.com" target="_blank" rel="noopener noreferrer" className="underline underline-offset-2 hover:text-brand-800">QuranEnc.com</a>
          {' · '}<a href="/about" className="underline underline-offset-2 hover:text-brand-800">{t('المصادر وحقوق النشر', 'Sources and copyright')}</a>
        </p>
      </main>
    </div>
  )
}
