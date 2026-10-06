// Copyright (c) 2026 Athar Al-Madinah Team (فريق أثر المدينة). All rights reserved.
// Mowatin (مُوطِّن) — Proprietary. Source-available for evaluation only. See LICENSE.
import { useCallback, useEffect, useId, useMemo, useRef, useState } from 'react'
import { ArrowLeft, ArrowRight, ArrowDown, Copy, Check, Languages, ScanSearch, ShieldCheck, Sparkles, X, Library, Loader2, RotateCcw, UserCheck, Upload, FileText as FileIcon, Volume2, Square, Mic } from 'lucide-react'
import { extractText, ACCEPT } from '../lib/extract'
import { EXAMPLES } from '../data/examples'
import { glossaryById, needsReview as segNeedsReview } from '../lib/api'
import { findTermSpans } from '../lib/termMatch'
import { canSpeak, useSpeaker } from '../lib/speech'
import { canDictate, useDictation } from '../lib/dictation'
import { useLang } from '../lib/i18n'
import { TypeChip, Flag, Confidence, VerifiedRetrieval, LEVEL, LEVEL_HINT, TYPE, highlight, LtrBrackets } from './ui'

const AUDIENCES = [
  ['general_non_muslim', 'غير مسلم (عام)', 'Non-Muslim (general)'],
  ['new_muslim', 'مسلم جديد', 'New Muslim'],
  ['youth', 'الشباب', 'Youth'],
  ['academic', 'أكاديمي / طالب علم', 'Academic / student of knowledge'],
]
const LANGS = [['en', 'English', 'الإنجليزية'], ['fr', 'Français', 'الفرنسية']]
const HOWTO = [['الصق النص أو ارفع ملفًا', 'Paste the text or upload a file'], ['اختر اللغة والجمهور', 'Choose the language and audience'], ['اضغط «ترجم بأمان»', 'Press “Translate safely”']]
const STEPS = [
  [ScanSearch, ['الكشف', 'Detect'], ['تحديد الآيات والأحاديث والمصطلحات', 'Find verses, hadiths and terms']],
  [Languages, ['الترجمة الذكية', 'Smart translation'], ['قفل المصطلحات وإدراج الترجمات المعتمدة', 'Lock terms and insert approved translations']],
  [ShieldCheck, ['التحقق', 'Verify'], ['فحص الجوهر ودرجة الثقة والإحالة', 'Check the meaning, score confidence, refer']],
]

export default function TranslateView({ state, setState, run }) {
  const { text, lang, audience, status, result, error } = state
  const { t: tr, dir } = useLang()
  const [step, setStep] = useState(-1)
  const timers = useRef([])
  const resultsRef = useRef(null)
  useEffect(() => {
    if (status === 'loading' && window.innerWidth < 1280) resultsRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, [status])

  useEffect(() => {
    timers.current.forEach(clearTimeout)
    if (status === 'loading') {
      setStep(0)
      timers.current = [setTimeout(() => setStep(1), 800), setTimeout(() => setStep(2), 1600)]
    } else setStep(status === 'done' ? 3 : -1)
    return () => timers.current.forEach(clearTimeout)
  }, [status])

  const pick = (ex) => setState((s) => ({ ...s, text: ex.text, exampleId: ex.id, fileName: null, ...(s.status === 'demo' ? { status: 'idle' } : {}) }))
  const [upload, setUpload] = useState({ busy: false, error: null, drag: false })
  // Each spoken phrase is appended to the text box (within the 4000-character limit).
  const dict = useDictation(useCallback((said) => setState((s) => ({
    ...s, text: `${s.text ? `${s.text.trimEnd()} ` : ''}${said}`.slice(0, 4000), exampleId: null, fileName: null,
  })), [setState]))
  const fileRef = useRef(null)
  const onFile = async (file) => {
    if (!file) return
    setUpload({ busy: true, error: null, drag: false })
    try {
      const t = await extractText(file)
      setState((s) => ({ ...s, text: t.slice(0, 4000), exampleId: null, fileName: file.name, truncated: t.length > 4000 }))
      setUpload({ busy: false, error: null, drag: false })
    } catch (e) { setUpload({ busy: false, error: e.message || tr('تعذّرت قراءة الملف.', 'Could not read the file.'), drag: false }) }
  }
  const canRun = text.trim().length > 1 && status !== 'loading'

  return (
    <div dir="ltr" className="grid grid-cols-1 gap-[1.4rem] xl:grid-cols-[1fr_30rem]">
      {/* ── RESULTS (left on desktop) ── */}
      <section ref={resultsRef} data-tour="results" dir={dir} aria-live="polite" className="scroll-mt-[5rem] order-2 min-w-0 rounded-[1.2rem] border border-slate-200/70 bg-white shadow-[0_1rem_2.5rem_-1.6rem_rgba(14,58,74,.3)] xl:order-1">
        <Results step={step} lang={state.resultLang ?? lang} status={status} result={result} error={error} onRetry={run} onPick={pick} />
      </section>

      {/* ── INPUT (right on desktop) ── */}
      <section dir={dir} className="order-1 space-y-[1rem] xl:order-2">
        <div className="rounded-[1.2rem] border border-slate-200/70 bg-white p-[1.1rem] shadow-[0_1rem_2.5rem_-1.6rem_rgba(14,58,74,.3)]">
          <div className="flex items-center justify-between">
            <h2 className="rounded-t-[0.8rem] text-[1.15rem] font-bold">{tr('النص الأصلي', 'Source text')}</h2>
            <span className="rounded-full border border-slate-200 px-[0.7rem] py-[0.15rem] text-[0.76rem] font-bold text-ink-600">{tr('العربية', 'Arabic')}</span>
          </div>
          <ol className="mt-[0.6rem] flex flex-wrap gap-x-[0.9rem] gap-y-[0.3rem] text-[0.8rem] text-ink-600" aria-label={tr('طريقة الاستخدام', 'How to use')}>
            {HOWTO.map(([ar, en], i) => (
              <li key={ar} className="flex items-center gap-[0.35rem]">
                <span className="tabular grid h-[1.15rem] w-[1.15rem] place-items-center rounded-full bg-brand-100 text-[0.68rem] font-bold text-brand-800" aria-hidden>{i + 1}</span>{tr(ar, en)}
              </li>
            ))}
          </ol>
          <label htmlFor="src" className="sr-only">{tr('النص العربي', 'Arabic text')}</label>
          <div data-tour="input" className="relative" onDragOver={(e) => { e.preventDefault(); setUpload((u) => ({ ...u, drag: true })) }} onDragLeave={() => setUpload((u) => ({ ...u, drag: false }))} onDrop={(e) => { e.preventDefault(); onFile(e.dataTransfer.files?.[0]) }}>
          {upload.drag && <div className="pointer-events-none absolute inset-0 z-10 mt-[0.8rem] grid place-items-center rounded-[0.9rem] border-2 border-dashed border-brand-600 bg-brand-50/90 text-[0.95rem] font-bold text-brand-800">{tr('أفلت الملف هنا', 'Drop the file here')}</div>}
          <textarea id="src" dir="rtl" rows={7} value={text} maxLength={4000}
            onChange={(e) => setState((s) => ({ ...s, text: e.target.value, exampleId: null, fileName: null }))}
            placeholder={tr('الصق هنا نصًا دعويًا عربيًا: مقالًا، أو موعظة، أو منشورًا…', 'Paste an Arabic da‘wah text here: an article, a sermon or a post…')}
            className="mt-[0.8rem] w-full resize-y rounded-[0.9rem] border border-slate-200 bg-paper/60 p-[0.9rem] text-[1.05rem] leading-[2rem] text-ink-900 placeholder:text-ink-600/70 focus:border-brand-600 focus:bg-white focus:outline-none" />
          </div>
          <div className="mt-[0.4rem] flex flex-wrap items-center justify-between gap-2 text-[0.74rem] text-ink-600">
            <input ref={fileRef} type="file" accept={ACCEPT} className="sr-only" aria-label={tr('رفع ملف Word أو PDF أو نص', 'Upload a Word, PDF or text file')} onChange={(e) => { onFile(e.target.files?.[0]); e.target.value = '' }} />
            <div className="flex flex-wrap items-center gap-[0.4rem]">
              <button type="button" onClick={() => fileRef.current?.click()} disabled={upload.busy}
                className="inline-flex items-center gap-[0.35rem] rounded-full border border-slate-200 px-[0.7rem] py-[0.25rem] font-bold text-ink-900 transition-colors hover:border-brand-600 hover:text-brand-800 disabled:opacity-60">
                {upload.busy ? <Loader2 className="h-[0.85rem] w-[0.85rem] animate-spin" aria-hidden /> : <Upload className="h-[0.85rem] w-[0.85rem]" aria-hidden />}
                {upload.busy ? tr('جارٍ القراءة…', 'Reading…') : tr('ارفع ملف Word أو PDF', 'Upload Word or PDF')}
              </button>
              {canDictate && (
                <button type="button" onClick={dict.listening ? dict.stop : dict.start} aria-pressed={dict.listening}
                  className={`inline-flex items-center gap-[0.35rem] rounded-full border px-[0.7rem] py-[0.25rem] font-bold transition-colors ${dict.listening ? 'border-danger-fg bg-danger-bg text-danger-fg' : 'border-slate-200 text-ink-900 hover:border-brand-600 hover:text-brand-800'}`}>
                  {dict.listening
                    ? <><span className="h-[0.55rem] w-[0.55rem] animate-pulse rounded-full bg-danger-fg" aria-hidden /> {tr('أوقف التسجيل', 'Stop recording')}</>
                    : <><Mic className="h-[0.85rem] w-[0.85rem]" aria-hidden /> {tr('تحدّث بالعربية', 'Speak in Arabic')}</>}
                </button>
              )}
            </div>
            <span className="tabular">{text.length} / 4000</span>
          </div>
          <p className="mt-[0.4rem] flex items-start gap-[0.35rem] text-[0.74rem] leading-[1.2rem] text-ink-600"><ShieldCheck className="mt-[0.1rem] h-[0.85rem] w-[0.85rem] shrink-0 text-brand-800" aria-hidden />{tr('لا نخزّن نصك: يبقى في ذاكرة الخادم ساعة واحدة فقط، ويُرسل للترجمة إلى نماذج Google وOpenRouter المجانية.', 'We do not store your text: it stays in server memory for one hour only, and is sent for translation to the free Google and OpenRouter models.')}</p>
          {dict.listening && (
            <div role="status" className="mt-[0.4rem] rounded-[0.6rem] bg-brand-50 px-[0.7rem] py-[0.45rem] text-[0.78rem] leading-[1.3rem] text-brand-800">
              <p className="font-bold">{tr('نستمع… تحدّث بالعربية، ويُضاف كلامك إلى النص.', 'Listening… speak in Arabic and your words are added to the text.')}</p>
              {dict.interim && <p className="mt-[0.15rem] text-ink-900">{dict.interim}</p>}
              <p className="mt-[0.15rem] text-[0.72rem] text-ink-600">{tr('يحوّل متصفحك الكلام إلى نص عبر خدمته (في Chrome تُرسل الصوت إلى Google)، ولا نسجّله نحن.', 'Your browser turns speech into text with its own service (Chrome sends the audio to Google); we do not record it.')}</p>
            </div>
          )}
          {dict.error && <p role="alert" className="mt-[0.4rem] rounded-[0.6rem] bg-danger-bg px-[0.7rem] py-[0.4rem] text-[0.78rem] text-danger-fg">{dict.error}</p>}
          {state.fileName && !upload.error && (
            <p className="mt-[0.4rem] flex items-center gap-[0.35rem] text-[0.74rem] text-brand-800"><FileIcon className="h-[0.85rem] w-[0.85rem]" aria-hidden />{state.fileName}{state.truncated ? tr(' · أُخذت أول 4000 حرف', ' · first 4000 characters taken') : ''}{tr(' · قُرئ داخل متصفحك ولم يُرفع لأي خادم', ' · read in your browser, not uploaded to any server')}</p>
          )}
          {upload.error && <p role="alert" className="mt-[0.4rem] rounded-[0.6rem] bg-danger-bg px-[0.7rem] py-[0.4rem] text-[0.78rem] text-danger-fg">{upload.error}</p>}

          <p className="mt-[0.8rem] text-[0.8rem] font-bold text-ink-600">{tr('جرّب مثالًا', 'Try an example')}</p>
          <div data-tour="examples" className="mt-[0.4rem] grid grid-cols-3 gap-[0.5rem]">
            {EXAMPLES.map((ex) => (
              <button key={ex.id} type="button" onClick={() => pick(ex)} aria-pressed={state.exampleId === ex.id}
                className={`rounded-[0.7rem] border px-[0.5rem] py-[0.5rem] text-start transition-colors ${state.exampleId === ex.id ? 'border-brand-600 bg-brand-50' : 'border-slate-200 hover:border-brand-300 hover:bg-brand-50/50'}`}>
                <span className="block text-[0.82rem] font-bold text-ink-900">{tr(ex.label, ex.label_en)}</span>
                <span className="block text-[0.72rem] leading-tight text-ink-600">{tr(ex.hint, ex.hint_en)}</span>
              </button>
            ))}
          </div>

          <div data-tour="options" className="mt-[1rem] grid grid-cols-2 gap-[0.7rem]">
            <fieldset>
              <legend className="mb-[0.35rem] text-[0.8rem] font-bold text-ink-600">{tr('لغة الهدف', 'Target language')}</legend>
              <div className="grid grid-cols-2 rounded-[0.7rem] bg-paper p-[0.2rem]">
                {LANGS.map(([code, native, ar]) => (
                  <button key={code} type="button" onClick={() => setState((s) => ({ ...s, lang: code }))} aria-pressed={lang === code}
                    className={`rounded-[0.55rem] py-[0.45rem] text-[0.82rem] font-bold transition-all ${lang === code ? 'bg-white text-brand-800 shadow-sm' : 'text-ink-600 hover:text-ink-900'}`}>
                    <span className="latin">{native}</span>{dir === 'rtl' && <span className="sr-only"> {ar}</span>}
                  </button>
                ))}
              </div>
            </fieldset>
            <label className="block">
              <span className="mb-[0.35rem] block text-[0.8rem] font-bold text-ink-600">{tr('الجمهور', 'Audience')}</span>
              <select value={audience} onChange={(e) => setState((s) => ({ ...s, audience: e.target.value }))}
                className="h-[2.4rem] w-full rounded-[0.7rem] border border-slate-200 bg-white px-[0.6rem] text-[0.86rem] focus:border-brand-600 focus:outline-none">
                {AUDIENCES.map(([v, ar, en]) => <option key={v} value={v}>{tr(ar, en)}</option>)}
              </select>
            </label>
          </div>

          <button type="button" data-tour="run" onClick={run} disabled={!canRun}
            className="btn-shine group mt-[1.1rem] inline-flex h-[3.1rem] w-full items-center justify-center gap-[0.6rem] rounded-[0.9rem] bg-brand-800 text-[1.05rem] font-bold text-white shadow-[0_0.9rem_1.8rem_-0.9rem_rgba(10,74,55,.7)] transition-colors hover:bg-brand-900 disabled:cursor-not-allowed disabled:bg-slate-300 disabled:shadow-none">
            {status === 'loading' ? <><Loader2 className="h-[1.2rem] w-[1.2rem] animate-spin" aria-hidden /> {tr('جارٍ المعالجة…', 'Processing…')}</> : <>{tr('ترجم بأمان', 'Translate safely')} {dir === 'rtl' ? <ArrowLeft className="h-[1.2rem] w-[1.2rem] transition-transform group-hover:-translate-x-1" aria-hidden /> : <ArrowRight className="h-[1.2rem] w-[1.2rem] transition-transform group-hover:translate-x-1" aria-hidden />}</>}
          </button>
          {status === 'done' && state.resultLang && state.resultLang !== lang && (
            <p role="status" className="mt-[0.5rem] text-center text-[0.78rem] text-pending-fg">{tr('غيّرت لغة الهدف؛ اضغط «ترجم بأمان» لتحديث النتيجة.', 'You changed the target language; press “Translate safely” to update the result.')}</p>
          )}
        </div>

      </section>
    </div>
  )
}

/* ─────────── pipeline: detect → translate → verify (shown where the user is looking) ─────────── */
function Pipeline({ step, running = false }) {
  const { t: tr } = useLang()
  return (
    <ol className={`grid grid-cols-3 gap-[0.5rem] ${running ? 'step-run' : ''}`} aria-label={tr('مراحل المعالجة', 'Processing stages')}>
      {STEPS.map(([I, [t, tEn], [d, dEn]], i) => {
        const done = step > i, active = step === i
        return (
          <li key={t} className="relative text-center" aria-current={active ? 'step' : undefined}>
            {i > 0 && (
              <span className="absolute start-[calc(-50%+1.9rem)] top-[1.6rem] h-[3px] w-[calc(100%-3.8rem)] -translate-y-1/2 overflow-hidden rounded bg-slate-200" aria-hidden>
                <span className="block h-full bg-brand-600 transition-[width] duration-500" style={{ width: step >= i ? '100%' : '0%' }} />
              </span>
            )}
            <span className={`step-dot relative mx-auto grid h-[3.2rem] w-[3.2rem] place-items-center rounded-full transition-colors duration-300 ${done ? 'bg-brand-800 text-white' : active ? 'bg-white text-brand-800 ring-2 ring-brand-600' : 'bg-paper text-ink-600'}`} style={active ? {} : { animation: 'none' }}>
              {done ? <Check className="h-[1.3rem] w-[1.3rem]" aria-hidden /> : <I className="h-[1.3rem] w-[1.3rem]" aria-hidden />}
            </span>
            <p className={`mt-[0.5rem] text-[0.92rem] font-bold ${done || active ? 'text-ink-900' : 'text-ink-600'}`}>{tr(t, tEn)}</p>
            <p className="mx-auto max-w-[11rem] text-[0.74rem] leading-[1.15rem] text-ink-600">{tr(d, dEn)}</p>
          </li>
        )
      })}
    </ol>
  )
}

/** Arabic number agreement: مقطع واحد · مقطعان · 3–10 مقاطع · 11+ مقطعًا */
function segmentsLabel(n, lang) {
  if (lang === 'en') return <><b className="tabular">{n}</b> {n === 1 ? 'segment' : 'segments'}</>
  if (n === 1) return 'مقطع واحد'
  if (n === 2) return 'مقطعان'
  return <><b className="tabular">{n}</b> {n >= 3 && n <= 10 ? 'مقاطع' : 'مقطعًا'}</>
}

/* ───────────────────────── results ───────────────────────── */
function Results({ step, lang, status, result, error, onRetry, onPick }) {
  const [copied, setCopied] = useState(false)
  const { speaking, toggle, stop } = useSpeaker()
  useEffect(() => stop, [result, stop]) // a new result stops any reading
  const { t: tr, lang: ui } = useLang()
  const langLabel = lang === 'fr' ? tr('الفرنسية', 'French') : tr('الإنجليزية', 'English')

  if (status === 'idle') return (
    <div className="grid min-h-[28rem] place-items-center p-[2rem] text-center">
      <div>
        <span className="mx-auto grid h-[4.4rem] w-[4.4rem] place-items-center rounded-full bg-brand-100 text-brand-800"><Sparkles className="h-[2rem] w-[2rem]" aria-hidden /></span>
        <h2 className="mt-[1rem] text-[1.3rem] font-bold">{tr('ستظهر الترجمة هنا، مقطعًا مقطعًا', 'The translation appears here, segment by segment')}</h2>
        <p className="mx-auto mt-[0.5rem] max-w-[28rem] text-[0.95rem] leading-[1.7rem] text-ink-600">{tr('لكل مقطع: نوعه، والمصطلحات المقفلة ومصادرها، ودرجة الثقة، وما يحتاج مراجعة بشرية. ابدأ بمثال «نص فيه أخطاء» لترى كيف يتصرف مُوطِّن.', 'For each segment: its type, the locked terms and their sources, a confidence score, and what needs human review. Start with the “Text with errors” example to see how Mowatin behaves.')}</p>
        <div className="mx-auto mt-[1.8rem] max-w-[34rem]"><Pipeline step={-1} /></div>
      </div>
    </div>
  )

  if (status === 'loading') return (
    <div className="space-y-[0.8rem] p-[1.2rem]" aria-busy="true">
      <div className="rounded-[1rem] border border-brand-100 bg-brand-50/60 px-[1rem] pb-[1.3rem] pt-[1rem]">
        <p className="mb-[1.1rem] flex items-center justify-center gap-[0.5rem] text-[1.05rem] font-bold text-brand-800">
          <Loader2 className="h-[1.1rem] w-[1.1rem] animate-spin" aria-hidden />{tr(...STEPS[Math.min(Math.max(step, 0), STEPS.length - 1)][1])}…
        </p>
        <Pipeline step={step} running />
      </div>
      {[0, 1].map((i) => <div key={i} className="skeleton h-[6rem] rounded-[1rem]" />)}
      <p className="text-center text-[0.82rem] text-ink-600">{tr('إن كان الخادم في وضع السكون فقد تستغرق أول معالجة بضع ثوانٍ.', 'If the server is asleep, the first run may take a few seconds.')}</p>
    </div>
  )

  if (status === 'demo') return (
    <div className="grid min-h-[22rem] place-items-center p-[2rem] text-center">
      <div>
        <span className="mx-auto grid h-[3.6rem] w-[3.6rem] place-items-center rounded-full bg-pending-bg text-pending-fg"><Sparkles className="h-[1.6rem] w-[1.6rem]" aria-hidden /></span>
        <h2 className="mt-[0.8rem] text-[1.2rem] font-bold">{tr('هذه نسخة تجريبية، جرّب أحد الأمثلة', 'This is a demo version; try one of the examples')}</h2>
        <p className="mx-auto mt-[0.4rem] max-w-[28rem] text-[0.92rem] leading-[1.6rem] text-ink-600">{tr('ترجمة نصك أنت تعمل عند ربط الخادم قريبًا. اختر مثالًا ثم اضغط «ترجم بأمان» لترى النتيجة كاملة.', 'Translating your own text works once the server is connected. Pick an example, then press “Translate safely” to see the full result.')}</p>
        <div className="mt-[1rem] flex flex-wrap justify-center gap-[0.5rem]">
          {EXAMPLES.map((ex) => (
            <button key={ex.id} type="button" onClick={() => onPick(ex)} className="rounded-full border border-brand-300 px-[0.9rem] py-[0.35rem] text-[0.85rem] font-bold text-brand-800 hover:bg-brand-50">{tr(ex.label, ex.label_en)}</button>
          ))}
        </div>
      </div>
    </div>
  )

  if (status === 'error') return (
    <div className="grid min-h-[22rem] place-items-center p-[2rem] text-center">
      <div>
        <span className="mx-auto grid h-[3.6rem] w-[3.6rem] place-items-center rounded-full bg-danger-bg text-danger-fg"><X className="h-[1.6rem] w-[1.6rem]" aria-hidden /></span>
        <p className="mt-[0.8rem] font-bold">{error}</p>
        <button type="button" onClick={onRetry} className="mt-[1rem] inline-flex items-center gap-[0.4rem] rounded-[0.7rem] border border-brand-800 px-[1rem] py-[0.5rem] font-bold text-brand-800 hover:bg-brand-50"><RotateCcw className="h-[1rem] w-[1rem]" aria-hidden /> {tr('إعادة المحاولة', 'Try again')}</button>
      </div>
    </div>
  )

  const { segments, summary, disclosure } = result
  const fullText = segments.map((s) => s.output).filter(Boolean).join(' ')
  const copy = async () => { try { await navigator.clipboard.writeText(fullText); setCopied(true); setTimeout(() => setCopied(false), 1600) } catch { /* clipboard blocked */ } }

  return (
    <div>
      <header className="flex flex-wrap items-center justify-between gap-[0.8rem] border-b border-slate-100 px-[1.2rem] py-[0.9rem]">
        <div className="flex items-center gap-[0.6rem]">
          <h2 className="text-[1.15rem] font-bold">{tr('الترجمة', 'Translation')}</h2>
          <span className="rounded-full border border-slate-200 px-[0.7rem] py-[0.15rem] text-[0.76rem] font-bold text-ink-600">{langLabel}</span>
        </div>
        <div className="flex flex-wrap items-center gap-[0.5rem] text-[0.78rem]">
          <span className="rounded-full bg-paper px-[0.7rem] py-[0.25rem]">{segmentsLabel(summary.segments, ui)}</span>
          <span className={`rounded-full px-[0.7rem] py-[0.25rem] ${summary.flagged ? 'bg-danger-bg text-danger-fg' : 'bg-brand-50 text-brand-800'}`}><b className="tabular">{summary.flagged}</b> {tr('للمراجعة', 'for review')}</span>
          {summary.avg_confidence != null && <ConfidenceInfo summary={summary} />}
          {fullText && canSpeak && (
            <button type="button" onClick={() => toggle('all', fullText, lang)} aria-pressed={speaking === 'all'}
              className="inline-flex items-center gap-[0.3rem] rounded-full border border-slate-200 px-[0.7rem] py-[0.25rem] font-bold hover:border-brand-600 hover:text-brand-800">
              {speaking === 'all' ? <><Square className="h-[0.8rem] w-[0.8rem]" aria-hidden /> {tr('إيقاف', 'Stop')}</> : <><Volume2 className="h-[0.85rem] w-[0.85rem]" aria-hidden /> {tr('استمع', 'Listen')}</>}
            </button>
          )}
          {fullText && (
            <button type="button" onClick={copy} className="inline-flex items-center gap-[0.3rem] rounded-full border border-slate-200 px-[0.7rem] py-[0.25rem] font-bold hover:border-brand-600 hover:text-brand-800">
              {copied ? <><Check className="h-[0.85rem] w-[0.85rem]" aria-hidden /> {tr('نُسخت', 'Copied')}</> : <><Copy className="h-[0.85rem] w-[0.85rem]" aria-hidden /> {tr('نسخ الترجمة', 'Copy translation')}</>}
            </button>
          )}
        </div>
      </header>

      {result.fallback && (
        <p role="status" className="mx-[1.2rem] mt-[1rem] rounded-[0.8rem] bg-pending-bg px-[0.9rem] py-[0.7rem] text-[0.86rem] leading-[1.5rem] text-[#8A3A0C]">
          {tr('جارٍ تشغيل الخادم أو أنه لا يستجيب الآن، فنعرض النتيجة المحفوظة لهذا المثال. أعد المحاولة بعد لحظات.', 'The server is starting or not responding right now, so we show the saved result for this example. Try again in a moment.')}
        </p>
      )}

      <ol className="space-y-[0.9rem] p-[1.2rem]">
        {segments.map((s, i) => <Segment key={s.id} s={s} i={i} lang={lang} speaking={speaking === s.id} onSpeak={() => toggle(s.id, s.output, lang)} />)}
      </ol>

      <footer className="flex items-center gap-[0.5rem] border-t border-slate-100 px-[1.2rem] py-[0.8rem] text-[0.78rem] text-ink-600">
        <Sparkles className="h-[0.9rem] w-[0.9rem] text-brand-600" aria-hidden /><span dir="rtl">{disclosure}</span>
      </footer>
    </div>
  )
}

// The average is shown as computed (report.average_confidence); this only explains it.
// Weights and threshold: verifier.py TERM/BT/JUDGE_WEIGHT and report.py REVIEW_THRESHOLD.
function ConfidenceInfo({ summary }) {
  const [open, setOpen] = useState(false)
  const panelId = useId()
  const { t: tr } = useLang()
  return (
    <span className="inline-flex flex-wrap items-center gap-[0.3rem]">
      <span className="rounded-full bg-paper px-[0.7rem] py-[0.25rem] text-ink-600">{tr('متوسط الثقة', 'Average confidence')} <b className="tabular">{Math.round(summary.avg_confidence * 100)}%</b></span>
      <button type="button" onClick={() => setOpen((v) => !v)} aria-expanded={open} aria-controls={panelId}
        className="rounded-full border border-slate-200 px-[0.6rem] py-[0.2rem] font-bold text-ink-600 hover:border-brand-600 hover:text-brand-800 focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand-600">
        {tr('ما معنى؟', 'What does it mean?')}
      </button>
      {open && (
        <span id={panelId} role="region" aria-label={tr('معنى متوسط الثقة', 'What average confidence means')}
          className="block w-full max-w-[34rem] basis-full space-y-[0.4rem] rounded-[0.8rem] border border-slate-200 bg-white p-[0.8rem] text-start text-[0.82rem] leading-[1.45rem] text-ink-600">
          <span className="block font-bold"><b className="tabular">{summary.flagged}</b> {tr('من', 'of')} <b className="tabular">{summary.segments}</b> {tr('مقاطع أُحيلت للمراجعة', 'segments sent for review')}</span>
          <span className="block">{tr('درجة داخلية تعبّر عن اطمئنان المنظومة لكل مقطع، وليست نسبة صحة الترجمة ولا دقتها.', 'An internal score for how settled the system is about each segment. It is not a measure of how correct or accurate the translation is.')}</span>
          <span className="block">{tr('تجمع فحص المصطلحات (35%) والترجمة العكسية (25%) وحكمًا مستقلًا (40%)، وما دون 75% يُحال تلقائيًا إلى المراجع الشرعي / المختص.', 'It combines the term check (35%), back-translation (25%) and an independent judgement (40%). Anything below 75% goes to the qualified reviewer automatically.')}</span>
          <span className="block">{tr('قد تنخفض لأن المقطع يحتاج مراجعة بشرية بطبيعته: آية أو حديث غير مطابق تمامًا، أو سؤال فتوى، أو مصطلحات كثيرة. في هذه الحالات تختار مُوطِّن الإحالة بدل التخمين.', 'It can be low because a segment needs human review by nature: a verse or hadith that does not match exactly, a fatwa question, or many terms. In these cases Muwattin refers instead of guessing.')}</span>
          <span className="block">{tr('يتغير المتوسط بحسب ما تُدخله: النص العام البسيط يرتفع غالبًا، والنص الكثيف بالنصوص الشرعية أو الأسئلة يميل للانخفاض مع بقاء القرار للمراجع.', 'The average depends on what you enter: plain general text usually scores higher, while text dense with scripture or questions tends to score lower, and the decision stays with the reviewer.')}</span>
        </span>
      )}
    </span>
  )
}

// Explains one segment's score from what the response already carries (no extra API field).
// Weights, cap and threshold mirror verifier.py (TERM/BT/JUDGE_WEIGHT, TERM_FAILURE_CAP) and
// report.py (REVIEW_THRESHOLD).
function ConfidenceWhy({ s, id, needsReview }) {
  const { t: tr } = useLang()
  const pct = s.confidence == null ? null : Math.round(s.confidence * 100)
  const reasons = s.flags.filter((f) => f.severity !== 'info')
  const lines = []
  if (s.verification === 'verified_retrieval') {
    lines.push(tr('100% لأن ترجمة معاني الآية منقولة حرفيًا من الترجمة المعتمدة، دون ترجمة آلية؛ ولهذا لا تدخل في متوسط الثقة.', '100% because the verse meaning is copied verbatim from the approved translation, with no machine translation; so it is left out of the average confidence.'))
  } else if (!s.output) {
    lines.push(tr('لا درجة لهذا المقطع لأنه لم يُترجم آليًا عمدًا: النظام يُحيل بدل أن يخمّن.', 'This segment has no score because it was deliberately not machine-translated: the system refers instead of guessing.'))
  } else if (!s.confidence && reasons.length) {
    lines.push(tr('لم تُقيَّم هذه الترجمة بمعادلة الثقة: أوقفها فحص أمان (مثل آية لا تطابق المصحف)، فأُحيلت إلى المراجع الشرعي / المختص مع التنبيه المذكور أسفل المقطع.', 'This translation was not scored by the confidence formula: a safety check stopped it (for example, a verse that does not match the Mushaf), so it went to the qualified reviewer with the notice listed below.'))
  } else {
    lines.push(tr(`الدرجة ${pct}% = فحص المصطلحات (35%) + الترجمة العكسية (25%) + حكم نموذج مستقل (40%). وهي درجة اطمئنان داخلية، لا نسبة صحة.`, `The score ${pct}% = term check (35%) + back-translation (25%) + an independent model's judgement (40%). It is an internal confidence score, not a measure of correctness.`))
    lines.push(s.locked_terms.length
      ? tr(`مصطلحات مقفلة من المسرد في هذا المقطع: ${s.locked_terms.map((x) => x.ar).join('، ')}. إن غاب مقابلها المعتمد عن الترجمة تُحدّ الدرجة دون 75%.`, `Glossary terms locked in this segment: ${s.locked_terms.map((x) => x.out).join(', ')}. If an approved rendering is missing from the translation, the score is capped below 75%.`)
      : tr('لا مصطلحات مقفلة في هذا المقطع، فجزء المصطلحات لا ينقص الدرجة.', 'No locked glossary terms in this segment, so the term part does not lower the score.'))
    if (s.back_translation) lines.push(tr('الترجمة العكسية المعروضة أدناه هي ما قورن بالأصل: كلما ابتعدت عنه انخفضت الدرجة.', 'The back-translation shown below is what was compared with the source: the further it drifts, the lower the score.'))
    lines.push(pct >= 75
      ? tr(`${pct}% تبلغ حد 75%، فلم تُحِل الدرجة وحدها المقطع للمراجعة.`, `${pct}% meets the 75% threshold, so the score alone did not send this segment for review.`)
      : tr(`${pct}% أقل من حد 75%، فأُحيل المقطع تلقائيًا إلى المراجع الشرعي / المختص.`, `${pct}% is below the 75% threshold, so the segment went to the qualified reviewer automatically.`))
  }
  if (needsReview && reasons.length) lines.push(tr(`أسباب الإحالة: ${reasons.length} تنبيه مذكور أسفل المقطع.`, `Review reasons: ${reasons.length} notice(s) listed below this segment.`))
  return (
    <div id={id} role="region" aria-label={tr('سبب الدرجة', 'Why this score')} dir="auto"
      className="mx-[1rem] mt-[0.6rem] space-y-[0.35rem] rounded-[0.8rem] border border-slate-200 bg-paper p-[0.8rem] text-start text-[0.8rem] leading-[1.45rem] text-ink-600">
      {lines.map((line, k) => <p key={k}>{line}</p>)}
    </div>
  )
}

function Segment({ s, i, lang, speaking, onSpeak }) {
  const [open, setOpen] = useState(null)
  const [why, setWhy] = useState(false)
  const whyId = useId()
  const { t: tr, dir } = useLang()
  const ty = TYPE[s.type] ?? TYPE.general
  const needsReview = segNeedsReview(s)
  // Terms come in glossary form; find them in the text even with attached prefixes and tashkeel.
  const spans = useMemo(() => findTermSpans(s.source, s.locked_terms.map((x) => ({
    key: x.glossary_id, forms: [x.ar, ...(glossaryById[x.glossary_id]?.variants_ar ?? [])],
  }))), [s.source, s.locked_terms])
  const termOf = (id) => s.locked_terms.find((x) => x.glossary_id === id)
  const source = []
  let at = 0
  for (const { start, end, key } of spans) {
    if (start > at) source.push(s.source.slice(at, start))
    const m = s.source.slice(start, end)
    source.push(<button key={start} type="button" className="term-hit font-sans font-bold text-term-fg" aria-expanded={open === key} onClick={() => setOpen(open === key ? null : key)}>{m}</button>)
    at = end
  }
  source.push(s.source.slice(at))

  return (
    <li className="seg-in relative overflow-hidden rounded-[1rem] border border-slate-200/80 bg-white" style={{ '--i': i }}>
      <span className="absolute inset-y-0 start-0 w-[3px]" style={{ background: ty.bar }} aria-hidden />
      <div className="flex flex-wrap items-center justify-between gap-2 px-[1rem] pt-[0.8rem]">
        <div className="flex items-center gap-[0.5rem]">
          <TypeChip type={s.type} />
          <span className="rounded-full bg-paper px-[0.55rem] py-[0.12rem] text-[0.7rem] font-bold text-ink-600" title={LEVEL_HINT[s.level] && tr(...LEVEL_HINT[s.level])}>{tr(`المستوى (${LEVEL[s.level]})`, `Level ${s.level}`)}</span>
          {needsReview && <span className="inline-flex items-center gap-[0.25rem] rounded-full bg-danger-bg px-[0.55rem] py-[0.12rem] text-[0.7rem] font-bold text-danger-fg"><UserCheck className="h-[0.8rem] w-[0.8rem]" aria-hidden /> {tr('محال للمراجعة', 'Sent for review')}</span>}
        </div>
        <div className="flex flex-wrap items-center gap-[0.5rem]">
          {s.verification === 'verified_retrieval' ? <VerifiedRetrieval /> : !needsReview && <Confidence value={s.confidence} />}
          <button type="button" onClick={() => setWhy((v) => !v)} aria-expanded={why} aria-controls={whyId}
            className="rounded-full border border-slate-200 px-[0.55rem] py-[0.1rem] text-[0.72rem] font-bold text-ink-600 hover:border-brand-600 hover:text-brand-800 focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand-600">
            {tr('لماذا هذه الدرجة؟', 'Why this score?')}
          </button>
        </div>
      </div>
      {why && <ConfidenceWhy s={s} id={whyId} needsReview={needsReview} />}

      <div dir="ltr" className="grid grid-cols-1 gap-[0.6rem] p-[1rem] md:grid-cols-[1fr_auto_1fr] md:items-start">
        {/* output (left) */}
        <div className={`order-3 rounded-[0.8rem] p-[0.8rem] md:order-1 ${s.output ? 'bg-[#F6F8FA]' : 'border border-dashed border-slate-300'}`}>
          {s.output
            ? <div className="flex items-start gap-[0.5rem]">
                <p className="latin min-w-0 flex-1 whitespace-pre-line text-left text-[0.98rem] leading-[1.75rem] text-ink-900"><LtrBrackets>{highlight(s.output, s.marks, (m, k) => <span key={k} className="mark-ok">{m}</span>)}</LtrBrackets></p>
                {canSpeak && (
                  <button type="button" onClick={onSpeak} aria-pressed={speaking} aria-label={speaking ? tr('إيقاف القراءة', 'Stop reading') : tr('استمع إلى الترجمة', 'Listen to the translation')} title={speaking ? tr('إيقاف القراءة', 'Stop reading') : tr('استمع إلى الترجمة', 'Listen to the translation')}
                    className={`grid h-[2rem] w-[2rem] shrink-0 place-items-center rounded-full transition-colors ${speaking ? 'bg-brand-800 text-white' : 'text-ink-600 hover:bg-white hover:text-brand-800'}`}>
                    {speaking ? <Square className="h-[0.8rem] w-[0.8rem]" aria-hidden /> : <Volume2 className="h-[1rem] w-[1rem]" aria-hidden />}
                  </button>
                )}
              </div>
            : s.verification === 'ambiguous_verse' && s.candidates.length > 0
            ? <VerseCandidates candidates={s.candidates} lang={lang} />
            : <p dir={dir} className="text-[0.86rem] leading-[1.5rem] text-ink-600">{s.confidence == null ? tr('الترجمة تظهر عند ربط الخادم.', 'The translation appears once the server is connected.') : tr('لم يُترجَم هذا المقطع، وأُحيل إلى المراجع.', 'This segment was not translated and was sent to the reviewer.')}</p>}
        </div>
        <ArrowLeft className="order-2 mx-auto hidden h-[1.1rem] w-[1.1rem] text-brand-600 md:mt-[0.9rem] md:block" aria-hidden />
        <ArrowDown className="order-2 mx-auto h-[1rem] w-[1rem] text-brand-600 md:hidden" aria-hidden />
        {/* source (right) */}
        <div dir="rtl" className="order-1 md:order-3">
          <p className={`text-[1.02rem] leading-[1.95rem] text-ink-900 ${s.type === 'quran' ? 'font-quran text-[1.12rem]' : ''}`}>
            {source}
          </p>
          {open && <TermCard term={termOf(open)} lang={lang} onClose={() => setOpen(null)} />}
        </div>
      </div>

      {(s.sources.length > 0 || s.flags.length > 0 || s.back_translation) && (
        <div className="space-y-[0.5rem] border-t border-slate-100 px-[1rem] py-[0.7rem]">
          {s.back_translation && (
            <p className="flex items-start gap-[0.4rem] text-[0.8rem] leading-[1.45rem] text-ink-600" title={tr('أعاد النظام ترجمة الناتج إلى العربية ليقارنه بالأصل', 'The system translated the output back into Arabic to compare it with the source')}>
              <RotateCcw className="mt-[0.25rem] h-[0.85rem] w-[0.85rem] shrink-0 text-brand-800" aria-hidden />
              <span><b className="text-ink-900">{tr('الترجمة العكسية للتحقق:', 'Back-translation check:')}</b> <span dir="rtl">«{s.back_translation}»</span></span>
            </p>
          )}
          {s.sources.map((src, k) => (
            <p key={k} className="flex flex-wrap items-center gap-[0.4rem] text-[0.78rem] text-ink-600">
              <Library className="h-[0.9rem] w-[0.9rem] text-brand-800" aria-hidden />
              <b className="text-ink-900">{src.ref}</b>
              {src.grade && <span className="rounded-full bg-brand-50 px-[0.5rem] text-brand-800">{src.grade}</span>}
              {src.edition && <span className="latin">{src.edition}</span>}
            </p>
          ))}
          {s.flags.map((f, k) => <Flag key={k} f={f} />)}
        </div>
      )}
    </li>
  )
}

// A quote found in several verses (server `verification: ambiguous_verse`, D-076): no place
// was chosen, so every place is listed with its approved translation for the reviewer.
function VerseCandidates({ candidates, lang }) {
  const { t: tr, dir } = useLang()
  return (
    <div dir={dir} className="space-y-[0.5rem] text-[0.86rem] leading-[1.5rem] text-ink-600">
      <p className="font-bold text-ink-900">{tr('هذا النص موجود في أكثر من موضع:', 'This text appears in more than one place:')}</p>
      <ul className="max-h-[18rem] space-y-[0.5rem] overflow-y-auto">
        {candidates.map((c) => (
          <li key={c.ref} className="rounded-[0.6rem] bg-[#F6F8FA] p-[0.6rem]">
            <b className="tabular text-ink-900">{c.ref}</b>
            <p dir="rtl" className="font-quran text-[1.02rem] leading-[1.9rem] text-ink-900">﴿{c.ar}﴾</p>
            {c[lang] && (
              <p dir="ltr" className="latin text-left text-ink-900">
                <LtrBrackets>{`﴿${c[lang]}﴾`}</LtrBrackets>
                {c[`${lang}_edition`] && <span className="ms-[0.3rem] text-[0.74rem] text-ink-600">({c[`${lang}_edition`]})</span>}
              </p>
            )}
          </li>
        ))}
      </ul>
      <p>{tr('لم نعتمد أيًّا من هذه المواضع، وأُحيل المقطع إلى المراجع الشرعي لتحديد الموضع.', 'None of these places was chosen; the segment was sent to the Sharia reviewer to pick the right one.')}</p>
    </div>
  )
}

function TermCard({ term, lang, onClose }) {
  const { t: tr } = useLang()
  const g = term && glossaryById[term.glossary_id]
  if (!g) return null
  const L = g[lang]
  return (
    <div role="dialog" aria-label={tr(`المصطلح: ${g.ar}`, `Term: ${g.ar}`)} className="seg-in mt-[0.6rem] rounded-[0.9rem] border border-term-bg bg-[#FFFBF5] p-[0.9rem] text-[0.84rem] shadow-[0_0.8rem_1.6rem_-1rem_rgba(180,83,9,.35)]" style={{ '--i': 0 }}>
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="text-[1rem] font-bold text-ink-900">{g.ar}</p>
          <p className="latin mt-[0.1rem] text-right font-semibold text-brand-800">{L.preferred} <span className="font-normal text-ink-600">— {L.gloss}</span></p>
        </div>
        <button type="button" onClick={onClose} className="rounded-full p-1 text-ink-600 hover:bg-term-bg" aria-label={tr('إغلاق', 'Close')}><X className="h-[1rem] w-[1rem]" /></button>
      </div>
      <p className="mt-[0.5rem] leading-[1.5rem] text-ink-900/80">{g.usage_note_ar}</p>
      {L.avoid?.length > 0 && (
        <p className="mt-[0.5rem] flex flex-wrap items-center gap-[0.35rem]"><span className="font-bold text-danger-fg">{tr('يُتجنّب:', 'Avoid:')}</span>{L.avoid.map((a) => <span key={a} className="latin mark-bad">{a}</span>)}</p>
      )}
      <p className="mt-[0.6rem] flex flex-wrap items-center gap-[0.4rem] text-[0.74rem] text-ink-600">
        <Library className="h-[0.85rem] w-[0.85rem]" aria-hidden /> {g.source.name} · {g.source.ref}
        <span className={`rounded-full px-[0.5rem] font-bold ${g.status[lang] === 'verified' ? 'bg-brand-50 text-brand-800' : 'bg-pending-bg text-pending-fg'}`}>{g.status[lang] === 'verified' ? tr('موثّق', 'Verified') : tr('مسودة بانتظار المراجعة', 'Draft awaiting review')}</span>
      </p>
    </div>
  )
}
