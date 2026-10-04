// Copyright (c) 2026 Athar Al-Madinah Team (فريق أثر المدينة). All rights reserved.
// Mowatin (مُوطِّن) — Proprietary. Source-available for evaluation only. See LICENSE.
//
// Reads eval/results/summary.json (schema: eval/results/SCHEMA.md). Shows no
// number that is not in that file; while status is "pending" it shows the method
// and empty frames only.
import { useEffect, useMemo, useState } from 'react'
import { FlaskConical, Table2, BarChart3, Users, Repeat, Lock, Terminal, TriangleAlert, Clock } from 'lucide-react'
import Navbar from '../components/Navbar'
import Footer from '../components/Footer'
import SUMMARY from '../../../eval/results/summary.json'

// Categorical order is fixed and follows the entity (validated: dataviz validate_palette, light).
const COLOR = { mowatin: '#14855F', llm: '#7A5CD1', mt: '#D97706' }
const fmt = (v, d = 1) => (v == null || Number.isNaN(v) ? '—' : Number(v).toFixed(d))

export default function ResultsPage({ data = SUMMARY }) {
  useEffect(() => { document.title = 'نتائج القياس · مُوطِّن' }, [])
  const ready = data.status === 'final'
  // Blind human scores (meaning, clarity) may come after the automatic run.
  const human = data.metrics.some((m) => (m.id === 'meaning' || m.id === 'clarity') && Object.keys(m.values || {}).length > 0)
  const sys = data.systems
  const totals = useMemo(() => Object.fromEntries(sys.map((s) => {
    const row = data.errors_per_100[s.id] || {}
    const vals = data.error_categories.map((c) => row[c.id]?.mean).filter((v) => v != null)
    return [s.id, vals.length ? vals.reduce((a, b) => a + b, 0) : null]
  })), [data, sys])
  const reduction = totals.llm && totals.mowatin != null ? Math.round((1 - totals.mowatin / totals.llm) * 100) : null

  return (
    <>
      <Navbar />
      <main className="bg-[#F6F9F8]">
        {/* header */}
        <section className="shell pb-[1.5rem] pt-[3rem] xl:w-[82rem]">
          <div className="flex flex-wrap items-center gap-[0.6rem]">
            <span className={`inline-flex items-center gap-[0.4rem] rounded-full px-[0.8rem] py-[0.25rem] text-[0.8rem] font-bold ${ready ? 'bg-brand-50 text-brand-800' : 'bg-pending-bg text-pending-fg'}`}>
              {ready ? <FlaskConical className="h-[0.9rem] w-[0.9rem]" aria-hidden /> : <Clock className="h-[0.9rem] w-[0.9rem]" aria-hidden />}
              {ready ? `نتائج نهائية · ${data.generated_at ?? ''}` : 'النتائج قيد القياس'}
            </span>
            <span className="text-[0.85rem] font-bold text-brand-800">نُعلِّم الآلة لتخدم الرسالة</span>
          </div>
          <h1 className="mt-[1rem] text-[2.1rem] font-extrabold leading-[1.35] text-ink-900 xl:text-[2.75rem]">هل يحمي مُوطِّن المعنى فعلًا؟ نقيس، ولا ندّعي.</h1>
          <p className="mt-[0.8rem] max-w-[48rem] text-[1.08rem] leading-[1.9rem] text-ink-900/75">
            {ready
              ? <>نقارن ثلاثة أنظمة على مجموعة اختبار مجمّدة من {data.testset.size} مقطعًا دعويًا، بـ{data.runs} تشغيلات{human ? '، وتقييم بشري أعمى' : '. الأرقام هنا آلية، والتقييم البشري الأعمى لم يُجرَ بعد'}.</>
              : <>نقارن ثلاثة أنظمة على مجموعة اختبار من {data.testset.size} مقطعًا دعويًا (قيد الإعداد)، بـ{data.runs} تشغيلات، وتقييم بشري أعمى.</>}
            المقارنة الأهم هي مُوطِّن مقابل <b>النموذج نفسه بلا مُوطِّن</b>، لأنها تُثبت أن التحسّن من طبقتنا لا من قوة النموذج.
          </p>
        </section>

        {/* headline */}
        <section className="shell xl:w-[82rem]" aria-label="الخلاصة">
          <div dir="ltr" className="grid grid-cols-1 gap-[1rem] md:grid-cols-[1.3fr_1fr_1fr_1fr]">
            <div dir="rtl" className="rounded-[1.2rem] bg-brand-800 p-[1.4rem] text-white">
              <p className="text-[0.9rem] text-brand-100/85">انخفاض الأخطاء الشرعية مقابل النموذج نفسه بلا مُوطِّن</p>
              <p className="tabular mt-[0.4rem] text-[3.2rem] font-extrabold leading-none">{reduction != null ? `${reduction}%` : '—'}</p>
              {!ready && <p className="mt-[0.6rem] text-[0.8rem] text-brand-100">يظهر الرقم بعد التشغيل النهائي.</p>}
            </div>
            {sys.map((s) => (
              <div key={s.id} dir="rtl" className="rounded-[1.2rem] border border-slate-200/70 bg-white p-[1.2rem]">
                <p className="flex items-center gap-[0.45rem] text-[0.92rem] font-bold text-ink-900"><i className="h-[0.7rem] w-[0.7rem] rounded-[3px]" style={{ background: COLOR[s.id] }} aria-hidden />{s.label}</p>
                <p className="mt-[0.15rem] text-[0.74rem] text-ink-600">{s.detail}</p>
                <p className="tabular mt-[0.7rem] text-[2rem] font-extrabold leading-none text-ink-900">{fmt(totals[s.id])}</p>
                <p className="text-[0.76rem] text-ink-600">خطأ شرعي لكل 100 مقطع</p>
              </div>
            ))}
          </div>
        </section>

        {/* chart */}
        <section className="shell py-[2rem] xl:w-[82rem]">
          <ErrorsChart data={data} ready={ready} />
        </section>

        {/* metrics */}
        <section className="shell pb-[2rem] xl:w-[82rem]">
          <h2 className="text-[1.5rem] font-extrabold">المقاييس</h2>
          <div className="mt-[1rem] overflow-x-auto rounded-[1.2rem] border border-slate-200/70 bg-white">
            <table className="w-full min-w-[44rem] text-right text-[0.9rem]">
              <thead className="bg-paper text-[0.8rem] text-ink-600">
                <tr>
                  <th className="px-[1rem] py-[0.7rem] font-bold">المقياس</th>
                  <th className="px-[1rem] py-[0.7rem] font-bold">طريقة القياس</th>
                  {sys.map((s) => <th key={s.id} className="px-[1rem] py-[0.7rem] font-bold"><span className="inline-flex items-center gap-[0.35rem]"><i className="h-[0.6rem] w-[0.6rem] rounded-[2px]" style={{ background: COLOR[s.id] }} aria-hidden />{s.label}</span></th>)}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {data.metrics.map((m) => (
                  <tr key={m.id}>
                    <td className="px-[1rem] py-[0.8rem] font-bold">{m.label}</td>
                    <td className="px-[1rem] py-[0.8rem] text-[0.82rem] text-ink-600">{m.method}</td>
                    {sys.map((s) => {
                      const v = m.values?.[s.id]
                      return <td key={s.id} className={`tabular px-[1rem] py-[0.8rem] ${s.id === 'mowatin' ? 'font-bold text-brand-900' : ''}`}>{v ? <>{fmt(v.mean)}<span className="text-ink-600">{m.unit}</span> <span className="text-[0.74rem] text-ink-600">± {fmt(v.sd)}</span></> : '—'}</td>
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        {/* method */}
        <section className="shell pb-[2rem] xl:w-[82rem]">
          <h2 className="text-[1.5rem] font-extrabold">المنهجية</h2>
          <ul className="mt-[1rem] grid gap-[1rem] sm:grid-cols-2 xl:grid-cols-4">
            {[
              [Lock, 'مجموعة اختبار مجمّدة', data.testset.frozen_at
                ? `${data.testset.size} مقطعًا (${data.testset.split.dev} للتطوير، ${data.testset.split.test} للاختبار). لم يُلمس قسم الاختبار أثناء التطوير، وجُمّد في ${data.testset.frozen_at}.`
                : `المخطط: ${data.testset.size} مقطعًا (${data.testset.split.dev} للتطوير، ${data.testset.split.test} للاختبار). يُجمَّد قسم الاختبار قبل القياس ولا يُلمس أثناء التطوير.`],
              [Repeat, `${data.runs} تشغيلات`, 'نعرض المتوسط والانحراف المعياري لإثبات ثبات النتائج عبر المحاولات المكررة.'],
              [Users, 'تقييم بشري أعمى', `أسماء الأنظمة مخفية (A/B/C). ${data.agreement.raters} مقيّمَين على عيّنة مشتركة${data.agreement.kappa != null ? `، والاتفاق κ = ${fmt(data.agreement.kappa, 2)}` : ''}.${ready && !human ? ' لم يُجرَ بعد.' : ''}`],
              [FlaskConical, 'بدائل محددة', 'ترجمة آلية عامة، والنموذج نفسه بلا مُوطِّن، ومُوطِّن. بالإعدادات نفسها والنصوص نفسها.'],
            ].map(([I, t, d]) => (
              <li key={t} className="rounded-[1.1rem] border border-slate-200/70 bg-white p-[1.1rem]">
                <span className="grid h-[2.6rem] w-[2.6rem] place-items-center rounded-full bg-brand-100 text-brand-800"><I className="h-[1.2rem] w-[1.2rem]" aria-hidden /></span>
                <h3 className="mt-[0.7rem] font-bold">{t}</h3>
                <p className="mt-[0.35rem] text-[0.88rem] leading-[1.6rem] text-ink-600">{d}</p>
              </li>
            ))}
          </ul>
        </section>

        {/* examples */}
        {data.examples.length > 0 && (
          <section className="shell pb-[2rem] xl:w-[82rem]">
            <h2 className="text-[1.5rem] font-extrabold">أمثلة من مجموعة الاختبار</h2>
            <div className="mt-[1rem] space-y-[0.9rem]">
              {data.examples.map((ex) => (
                <article key={ex.id} className="rounded-[1.1rem] border border-slate-200/70 bg-white p-[1.1rem]">
                  <p className="text-[0.95rem] leading-[1.8rem]">{ex.source}</p>
                  <div dir="ltr" className="mt-[0.7rem] grid gap-[0.6rem] md:grid-cols-3">
                    {['mowatin', 'llm', 'mt'].map((k) => (
                      <div key={k} className="rounded-[0.8rem] bg-paper p-[0.7rem]">
                        <p dir="rtl" className="mb-[0.3rem] flex items-center gap-[0.35rem] text-[0.76rem] font-bold"><i className="h-[0.55rem] w-[0.55rem] rounded-[2px]" style={{ background: COLOR[k] }} aria-hidden />{sys.find((s) => s.id === k)?.label}</p>
                        <p className="latin text-left text-[0.88rem] leading-[1.5rem]">{ex[k]}</p>
                      </div>
                    ))}
                  </div>
                  {ex.note && <p className="mt-[0.6rem] text-[0.84rem] text-ink-600">{ex.note}</p>}
                </article>
              ))}
            </div>
          </section>
        )}

        {/* limits + reproduce */}
        <section className="shell grid grid-cols-1 gap-[1rem] pb-[3rem] xl:w-[82rem] xl:grid-cols-2">
          <div className="rounded-[1.1rem] border border-slate-200/70 bg-white p-[1.2rem]">
            <h2 className="flex items-center gap-[0.5rem] text-[1.2rem] font-extrabold"><TriangleAlert className="h-[1.2rem] w-[1.2rem] text-pending-fg" aria-hidden /> حدود دلالة النتائج</h2>
            {data.limitations.length
              ? <ul className="mt-[0.7rem] list-disc space-y-[0.4rem] pr-[1.2rem] text-[0.9rem] leading-[1.6rem] text-ink-900/80">{data.limitations.map((l) => <li key={l}>{l}</li>)}</ul>
              : <p className="mt-[0.7rem] text-[0.9rem] text-ink-600">تُكتب بعد التشغيل النهائي: حجم العيّنة، واللغات المختبرة، ومصادر النصوص، وما لا تثبته هذه الأرقام.</p>}
          </div>
          <div className="min-w-0 rounded-[1.1rem] border border-slate-200/70 bg-ink-900 p-[1.2rem] text-white">
            <h2 className="flex items-center gap-[0.5rem] text-[1.2rem] font-extrabold"><Terminal className="h-[1.2rem] w-[1.2rem] text-brand-300" aria-hidden /> أعِد الاختبار بنفسك</h2>
            <p className="mt-[0.5rem] text-[0.88rem] text-white/70">كل رقم في هذه الصفحة مصدره <span className="latin">eval/results/summary.json</span> في مستودع المشروع.</p>
            {data.reproduce
              ? <pre dir="ltr" className="mt-[0.8rem] overflow-x-auto rounded-[0.7rem] bg-black/30 p-[0.8rem] text-left font-mono text-[0.82rem] leading-[1.5rem] text-brand-100"><code>{data.reproduce}</code></pre>
              : <p className="mt-[0.8rem] rounded-[0.7rem] bg-black/30 p-[0.8rem] text-[0.86rem] text-white/75">أوامر إعادة التشغيل تُنشر هنا مع النتائج النهائية.</p>}
          </div>
        </section>
      </main>
      <Footer />
    </>
  )
}

/* ─────────── grouped horizontal bars: errors per 100, by category ─────────── */
function ErrorsChart({ data, ready }) {
  const [view, setView] = useState('chart')
  const [tip, setTip] = useState(null)
  const sys = [...data.systems].reverse() // mowatin first in reading order
  const cats = data.error_categories
  const val = (s, c) => data.errors_per_100[s]?.[c]?.mean ?? null
  const max = Math.max(1, ...cats.flatMap((c) => sys.map((s) => val(s.id, c.id) ?? 0)))
  const nice = Math.ceil(max / 5) * 5
  const ticks = [0, nice / 2, nice]

  return (
    <div className="rounded-[1.2rem] border border-slate-200/70 bg-white p-[1.2rem]">
      <div className="flex flex-wrap items-start justify-between gap-[1rem]">
        <div>
          <h2 className="text-[1.3rem] font-extrabold">الأخطاء الشرعية لكل 100 مقطع، حسب النوع</h2>
          <p className="text-[0.85rem] text-ink-600">الأقل أفضل · متوسط {data.runs} تشغيلات على قسم الاختبار</p>
        </div>
        <div className="flex items-center gap-[1rem]">
          <ul className="flex flex-wrap gap-[0.9rem] text-[0.82rem]" aria-label="مفتاح الألوان">
            {sys.map((s) => <li key={s.id} className="flex items-center gap-[0.35rem]"><i className="h-[0.7rem] w-[0.7rem] rounded-[3px]" style={{ background: COLOR[s.id] }} aria-hidden />{s.label}</li>)}
          </ul>
          <div className="flex rounded-[0.6rem] bg-paper p-[0.2rem]">
            {[['chart', BarChart3, 'رسم'], ['table', Table2, 'جدول']].map(([k, I, l]) => (
              <button key={k} type="button" onClick={() => setView(k)} aria-pressed={view === k} aria-label={l}
                className={`rounded-[0.45rem] p-[0.4rem] ${view === k ? 'bg-white text-brand-800 shadow-sm' : 'text-ink-600'}`}><I className="h-[1rem] w-[1rem]" /></button>
            ))}
          </div>
        </div>
      </div>

      {!ready && (
        <p className="mt-[1rem] rounded-[0.8rem] bg-pending-bg px-[0.9rem] py-[0.6rem] text-[0.86rem] text-[#8A3A0C]">
          لم تُنشر الأرقام بعد. تظهر هنا تلقائيًا عندما يكتمل تشغيل القياس على مجموعة الاختبار المجمّدة.
        </p>
      )}

      {view === 'chart' ? (
        <div className="relative mt-[1.2rem]" onMouseLeave={() => setTip(null)}>
          <div dir="ltr" className="grid grid-cols-[1fr_12rem] gap-x-[1rem]">
            {cats.map((c) => (
              <div key={c.id} className="contents">
                <div className="flex flex-col justify-center gap-[2px] border-b border-slate-100 py-[0.6rem]">
                  {sys.map((s) => {
                    const v = val(s.id, c.id)
                    return (
                      <div key={s.id} className="group relative flex h-[0.9rem] items-center"
                        onMouseEnter={(e) => v != null && setTip({ x: e.currentTarget.getBoundingClientRect(), s, c, v, sd: data.errors_per_100[s.id]?.[c.id]?.sd })}>
                        <span className="absolute inset-y-[-3px] left-0 right-0" aria-hidden />
                        <span className="h-full rounded-r-[4px] transition-[width] duration-700 ease-out group-hover:brightness-110"
                          style={{ width: v != null ? `${(v / nice) * 100}%` : '0%', minWidth: v ? 2 : 0, background: COLOR[s.id] }} />
                        {s.id === 'mowatin' && v != null && <span className="tabular ml-[0.4rem] text-[0.74rem] font-bold text-ink-900">{fmt(v)}</span>}
                      </div>
                    )
                  })}
                </div>
                <div dir="rtl" className="flex items-center border-b border-slate-100 py-[0.6rem] text-[0.88rem] font-bold text-ink-900">{c.label}</div>
              </div>
            ))}
            <div className="tabular flex justify-between pt-[0.4rem] text-[0.72rem] text-ink-600">{ticks.map((t) => <span key={t}>{t}</span>)}</div>
          </div>
          {tip && (
            <div className="pointer-events-none fixed z-50 rounded-[0.6rem] border border-slate-200 bg-white px-[0.7rem] py-[0.45rem] text-[0.8rem] shadow-lg"
              style={{ top: tip.x.top - 46, left: tip.x.left + 8 }}>
              <b>{tip.s.label}</b> · {tip.c.label}<br /><span className="tabular">{fmt(tip.v)} لكل 100 مقطع{tip.sd != null ? ` (± ${fmt(tip.sd)})` : ''}</span>
            </div>
          )}
        </div>
      ) : (
        <div className="mt-[1.2rem] overflow-x-auto">
          <table className="w-full min-w-[36rem] text-right text-[0.88rem]">
            <thead className="bg-paper text-ink-600"><tr><th className="px-[0.8rem] py-[0.5rem]">نوع الخطأ</th>{sys.map((s) => <th key={s.id} className="px-[0.8rem] py-[0.5rem]">{s.label}</th>)}</tr></thead>
            <tbody className="divide-y divide-slate-100">
              {cats.map((c) => <tr key={c.id}><td className="px-[0.8rem] py-[0.5rem] font-bold">{c.label}</td>{sys.map((s) => <td key={s.id} className="tabular px-[0.8rem] py-[0.5rem]">{fmt(val(s.id, c.id))}</td>)}</tr>)}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
