// Copyright (c) 2026 Athar Al-Madinah Team (فريق أثر المدينة). All rights reserved.
// Mowatin (مُوطِّن) — Proprietary. Source-available for evaluation only. See LICENSE.
import { Check, X, ArrowLeft, ArrowRight, Info } from 'lucide-react'
import { MODE } from '../lib/api'
import { useLang } from '../lib/i18n'
import { TypeChip, highlight, LtrBrackets } from './ui'

export default function CompareView({ state, goTranslate }) {
  const { result } = state
  const { t, dir } = useLang()
  const Fwd = dir === 'rtl' ? ArrowLeft : ArrowRight
  // The server sends an empty baseline when there is no raw output; skip those rows.
  const rows = result?.segments?.filter((s) => s.baseline?.output) ?? []

  if (!rows.length) return (
    <div className="grid min-h-[26rem] place-items-center rounded-[1.2rem] border border-slate-200/70 bg-white p-[2rem] text-center">
      <div>
        <h2 className="text-[1.3rem] font-bold">{t('لا توجد مقارنة بعد', 'No comparison yet')}</h2>
        <p className="mx-auto mt-[0.5rem] max-w-[30rem] text-ink-600">{t('شغّل أحد الأمثلة في شاشة الترجمة، ثم ارجع هنا لترى الترجمة العادية بجانب مُوطِّن مقطعًا مقطعًا.', 'Run one of the examples on the translate screen, then come back here to see a conventional translation next to Mowatin, segment by segment.')}</p>
        <button type="button" onClick={goTranslate} className="mt-[1.2rem] inline-flex items-center gap-[0.5rem] rounded-[0.8rem] bg-brand-800 px-[1.2rem] py-[0.6rem] font-bold text-white hover:bg-brand-900">{t('إلى شاشة الترجمة', 'Go to the translate screen')} <Fwd className="h-[1rem] w-[1rem]" aria-hidden /></button>
      </div>
    </div>
  )

  const issues = rows.filter((r) => r.baseline.wrong.length).length
  return (
    <div className="space-y-[1rem]">
      <div className="flex flex-wrap items-end justify-between gap-[1rem]">
        <div>
          <h2 className="text-[1.6rem] font-extrabold">{t('قبل وبعد', 'Before & after')}</h2>
          <p className="text-ink-600">{t('الفرق الواضح بين الترجمة التقليدية ومُوطِّن، على النص نفسه.', 'The clear difference between a conventional translation and Mowatin, on the same text.')}</p>
        </div>
        <div className="flex gap-[0.6rem] text-[0.86rem]">
          <span className="rounded-[0.8rem] bg-danger-bg px-[0.9rem] py-[0.5rem] text-danger-fg"><b className="tabular text-[1.2rem]">{issues}</b> / {rows.length} {t('مقاطع فيها خطأ في الترجمة التقليدية', 'segments with an error in the conventional translation')}</span>
          <span className="rounded-[0.8rem] bg-brand-50 px-[0.9rem] py-[0.5rem] text-brand-800"><b className="tabular text-[1.2rem]">{result.review_queue.length}</b> {t('أُحيلت للمراجع بدل نشرها', 'sent to the reviewer instead of published')}</span>
        </div>
      </div>

      <div className="overflow-hidden rounded-[1.2rem] border border-slate-200/70 bg-white shadow-[0_1rem_2.5rem_-1.6rem_rgba(14,58,74,.3)]">
        <div dir="ltr" className="hidden grid-cols-[1fr_1fr_16rem] text-[0.95rem] font-bold md:grid">
          <div className="flex items-center justify-center gap-[0.5rem] bg-brand-800 py-[0.8rem] text-white"><Check className="h-[1.1rem] w-[1.1rem]" aria-hidden /> {t('مُوطِّن', 'Mowatin')}</div>
          <div className="bg-slate-100 py-[0.8rem] text-center text-ink-900">{t('الترجمة التقليدية', 'Conventional translation')}</div>
          <div className="bg-slate-50 py-[0.8rem] text-center text-ink-600">{t('النص الأصلي', 'Source text')}</div>
        </div>
        <ul className="divide-y divide-slate-100">
          {rows.map((s, i) => {
            const b = s.baseline, bad = b.wrong.length > 0
            return (
              <li key={s.id} dir="ltr" className="seg-in grid grid-cols-1 md:grid-cols-[1fr_1fr_16rem]" style={{ '--i': i }}>
                <div className="bg-brand-50/40 p-[1rem]">
                  <p className="mb-[0.3rem] text-right text-[0.72rem] font-bold text-brand-800 md:hidden">{t('مُوطِّن', 'Mowatin')}</p>
                  {s.output
                    ? <p className="latin whitespace-pre-line text-left text-[0.94rem] leading-[1.65rem]"><LtrBrackets>{highlight(s.output, s.marks, (m, k) => <span key={k} className="mark-ok">{m}</span>)}</LtrBrackets></p>
                    : <p dir={dir} className="text-start text-[0.86rem] font-bold text-brand-800">{t('لم يُنشر؛ أُحيل إلى المراجع الشرعي.', 'Not published; sent to the qualified reviewer.')}</p>}
                  {s.flags.filter((f) => f.severity !== 'info').map((f, k) => <p key={k} dir="rtl" className="mt-[0.4rem] flex items-start gap-[0.3rem] text-right text-[0.76rem] text-brand-900"><Check className="mt-[0.2rem] h-[0.8rem] w-[0.8rem] shrink-0" aria-hidden />{f.text}</p>)}
                </div>
                <div className="p-[1rem]">
                  <p className="mb-[0.3rem] text-right text-[0.72rem] font-bold text-ink-600 md:hidden">{t('الترجمة التقليدية', 'Conventional translation')}</p>
                  <p className="latin whitespace-pre-line text-left text-[0.94rem] leading-[1.65rem] text-ink-900/85"><LtrBrackets>{highlight(b.output, b.wrong, (m, k) => <span key={k} className="mark-bad">{m}</span>)}</LtrBrackets></p>
                  <p dir={bad ? 'rtl' : dir} className={`mt-[0.4rem] flex items-start gap-[0.3rem] text-start text-[0.76rem] ${bad ? 'text-danger-fg' : 'text-ink-600'}`}>
                    {bad ? <X className="mt-[0.2rem] h-[0.8rem] w-[0.8rem] shrink-0" aria-hidden /> : <Check className="mt-[0.2rem] h-[0.8rem] w-[0.8rem] shrink-0" aria-hidden />}
                    {bad ? b.why : t('لا فرق جوهري في هذا المقطع.', 'No substantive difference in this segment.')}
                  </p>
                </div>
                <div dir="rtl" className="border-slate-100 bg-slate-50/60 p-[1rem] md:border-r">
                  <TypeChip type={s.type} />
                  <p className={`mt-[0.4rem] text-[0.9rem] leading-[1.7rem] ${s.type === 'quran' ? 'font-quran' : ''}`}>{s.source}</p>
                </div>
              </li>
            )
          })}
        </ul>
      </div>

      <p className="flex items-start gap-[0.4rem] text-[0.8rem] leading-[1.4rem] text-ink-600">
        <Info className="mt-[0.15rem] h-[0.9rem] w-[0.9rem] shrink-0" aria-hidden />
        {MODE === 'demo'
          ? t('وضع العرض التجريبي: عمود «الترجمة التقليدية» مثال توضيحي للأخطاء الشائعة. عند ربط الخادم يُعرض هنا مخرج حقيقي من النموذج نفسه دون طبقة مُوطِّن، والنتائج المقاسة على مجموعة الاختبار كاملة في docs/EVALUATION.md.', 'Demo mode: the “Conventional translation” column illustrates common errors. Once the server is connected it shows real output from the same model without the Mowatin layer; the measured results on the full test set are in docs/EVALUATION.md.')
          : t('عمود «الترجمة التقليدية» مخرج حقيقي من النموذج نفسه دون طبقة مُوطِّن.', 'The “Conventional translation” column is real output from the same model without the Mowatin layer.')}
      </p>
    </div>
  )
}
