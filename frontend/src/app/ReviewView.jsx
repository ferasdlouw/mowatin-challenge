// Copyright (c) 2026 Athar Al-Madinah Team (فريق أثر المدينة). All rights reserved.
// Mowatin (مُوطِّن) — Proprietary. Source-available for evaluation only. See LICENSE.
import { useState } from 'react'
import { ClipboardCheck, History, Download, Check, PenLine, X, Clock, Inbox, Lock } from 'lucide-react'
import { TypeChip, Flag, LtrBrackets } from './ui'

const STATUS = {
  pending: ['بانتظار المراجعة', 'bg-pending-bg text-pending-fg', Clock],
  approved: ['معتمد', 'bg-brand-800 text-white', Check],
  edited: ['معدّل ومعتمد', 'bg-brand-100 text-brand-900', PenLine],
  rejected: ['مرفوض', 'bg-danger-bg text-danger-fg', X],
}
const LANG = { en: 'English', fr: 'Français' }

export default function ReviewView({ queue, setQueue }) {
  const [selId, setSelId] = useState(queue.find((q) => q.status === 'pending')?.id ?? queue[0]?.id)
  const [filter, setFilter] = useState('pending')
  const [panel, setPanel] = useState('queue')
  const sel = queue.find((q) => q.id === selId)
  const [draft, setDraft] = useState(null)
  const [note, setNote] = useState('')

  const list = queue.filter((q) => filter === 'all' || (filter === 'pending' ? q.status === 'pending' : q.status !== 'pending'))
  const pending = queue.filter((q) => q.status === 'pending').length

  const choose = (id) => { setSelId(id); setDraft(null); setNote(queue.find((q) => q.id === id)?.reviewerNote ?? '') }
  const decide = (status) => {
    setQueue((qs) => qs.map((q) => q.id === sel.id ? { ...q, status, reviewerNote: note, proposed: status === 'edited' && draft != null ? draft.trim() : q.proposed, decidedAt: new Date().toLocaleTimeString('ar-SA', { hour: '2-digit', minute: '2-digit' }), decidedIso: new Date().toISOString() } : q))
    setDraft(null)
    const next = queue.find((q) => q.status === 'pending' && q.id !== sel.id)
    if (next) choose(next.id)
  }

  const sidebar = (
    <aside dir="rtl" className="order-1 rounded-[1.2rem] border border-slate-200/70 bg-white p-[1rem] xl:order-3">
      <div className="flex items-center gap-[0.7rem]">
        <img src="/images/scholar.webp" alt="صورة رمزية للمراجع الشرعي" className="h-[3rem] w-[3rem] rounded-full" />
        <div><p className="text-[0.95rem] font-bold">المراجع الشرعي</p><p className="text-[0.74rem] text-ink-600">حساب تجريبي</p></div>
      </div>
      <nav className="mt-[1.1rem] grid grid-cols-2 gap-[0.3rem] xl:grid-cols-1" aria-label="أقسام المراجع">
        {[['queue', ClipboardCheck, 'المراجعات', pending], ['log', History, 'سجل القرارات', queue.length - pending]].map(([k, I, l, n]) => (
          <button key={k} type="button" onClick={() => setPanel(k)} aria-current={panel === k ? 'page' : undefined}
            className={`flex items-center justify-between gap-[0.5rem] rounded-[0.6rem] px-[0.7rem] py-[0.55rem] text-[0.86rem] ${panel === k ? 'bg-brand-50 font-bold text-brand-800' : 'text-ink-600 hover:bg-paper'}`}>
            <span className="flex items-center gap-[0.5rem]"><I className="h-[1rem] w-[1rem]" aria-hidden />{l}</span><span className="tabular text-[0.76rem]">{n}</span>
          </button>
        ))}
      </nav>
      <p className="mt-[1rem] rounded-[0.7rem] bg-paper p-[0.7rem] text-[0.74rem] leading-[1.3rem] text-ink-600">كل قرار يُسجَّل مع ملاحظته ووقته، ولا يُنشر مقطع محال قبل اعتماده. السجل محفوظ في هذه الجلسة فقط؛ صدّره (CSV أو JSON) قبل إغلاق الصفحة.</p>
    </aside>
  )

  if (panel === 'log') return (
    <>
      <PrivateNotice />
      <div dir="ltr" className="grid grid-cols-1 gap-[1.2rem] xl:grid-cols-[1fr_14rem]">
        <LogView items={queue.filter((q) => q.status !== 'pending')} />
        {sidebar}
      </div>
    </>
  )

  return (
    <>
    <PrivateNotice />
    <div dir="ltr" className="grid grid-cols-1 gap-[1.2rem] xl:grid-cols-[1fr_1.35fr_14rem]">
      {/* ── detail (left) ── */}
      <section dir="rtl" className="order-3 rounded-[1.2rem] border border-slate-200/70 bg-white p-[1.2rem] shadow-[0_1rem_2.5rem_-1.6rem_rgba(14,58,74,.3)] xl:order-1">
        {sel ? (
          <div key={sel.id} className="seg-in" style={{ '--i': 0 }}>
            <div className="flex items-center justify-between gap-2"><h3 className="text-[1.1rem] font-bold">الترجمة المقترحة</h3><TypeChip type={sel.type} /></div>
            <p className={`mt-[0.8rem] rounded-[0.8rem] bg-paper p-[0.8rem] text-[0.95rem] leading-[1.8rem] ${sel.type === 'quran' ? 'font-quran' : ''}`}>{sel.source}</p>
            {draft == null ? (
              <div className="mt-[0.6rem] rounded-[0.8rem] border border-slate-200 p-[0.8rem]">
                {sel.proposed ? <p className="latin whitespace-pre-line text-left text-[0.92rem] leading-[1.6rem]"><LtrBrackets>{sel.proposed}</LtrBrackets></p> : <p className="text-[0.86rem] text-ink-600">لا توجد ترجمة مقترحة؛ المقطع أُوقف قبل النشر.</p>}
                {sel.ref && <p className="latin mt-[0.3rem] text-left text-[0.74rem] text-ink-600">{sel.ref}</p>}
              </div>
            ) : (
              <textarea dir="ltr" value={draft} onChange={(e) => setDraft(e.target.value)} rows={4} aria-label="تعديل الترجمة"
                className="latin mt-[0.6rem] w-full rounded-[0.8rem] border border-brand-600 p-[0.8rem] text-[0.92rem] leading-[1.6rem] focus:outline-none" />
            )}
            <div className="mt-[0.7rem] space-y-[0.4rem]">{sel.flags.map((f, k) => <Flag key={k} f={f} />)}</div>

            <label className="mt-[1rem] block">
              <span className="text-[0.9rem] font-bold">ملاحظات المراجع</span>
              <textarea value={note} onChange={(e) => setNote(e.target.value)} rows={3} placeholder="مثال: الترجمة دقيقة، أو: يُستبدل المصدر بـ…"
                className="mt-[0.4rem] w-full rounded-[0.8rem] border border-slate-200 p-[0.7rem] text-[0.88rem] focus:border-brand-600 focus:outline-none" />
            </label>

            {sel.status === 'pending' ? (
              <div className="mt-[0.9rem] grid grid-cols-3 gap-[0.5rem]">
                <button type="button" onClick={() => decide('rejected')} className="h-[2.6rem] rounded-[0.7rem] border border-danger-fg/40 font-bold text-danger-fg hover:bg-danger-bg">رفض</button>
                {draft == null ? (
                  <>
                    <button type="button" onClick={() => setDraft(sel.proposed ?? '')} className="h-[2.6rem] rounded-[0.7rem] border border-brand-300 font-bold text-ink-900 hover:bg-brand-50">تعديل</button>
                    <button type="button" onClick={() => decide('approved')} disabled={!sel.proposed} className="h-[2.6rem] rounded-[0.7rem] bg-brand-800 font-bold text-white hover:bg-brand-900 disabled:bg-slate-300">اعتماد</button>
                  </>
                ) : (
                  <>
                    <button type="button" onClick={() => setDraft(null)} className="h-[2.6rem] rounded-[0.7rem] border border-slate-200 font-bold text-ink-600 hover:bg-paper">إلغاء التعديل</button>
                    <button type="button" onClick={() => decide(draft.trim() === (sel.proposed ?? '').trim() ? 'approved' : 'edited')} disabled={!draft.trim()} className="h-[2.6rem] rounded-[0.7rem] bg-brand-800 font-bold text-white hover:bg-brand-900 disabled:bg-slate-300">حفظ واعتماد</button>
                  </>
                )}
              </div>
            ) : (
              <p className={`mt-[0.9rem] flex items-center justify-center gap-[0.4rem] rounded-[0.7rem] py-[0.6rem] text-[0.9rem] font-bold ${STATUS[sel.status][1]}`}>
                {STATUS[sel.status][0]} · <span className="tabular">{sel.decidedAt}</span>
              </p>
            )}
          </div>
        ) : <Empty />}
      </section>

      {/* ── queue (middle) ── */}
      <section dir="rtl" className="order-2 min-w-0 rounded-[1.2rem] border border-slate-200/70 bg-white shadow-[0_1rem_2.5rem_-1.6rem_rgba(14,58,74,.3)]">
        <header className="flex flex-wrap items-center justify-between gap-2 px-[1.2rem] py-[1rem]">
          <h2 className="flex items-center gap-[0.6rem] text-[1.15rem] font-bold">محتوى بانتظار المراجعة <span className="tabular grid h-[1.9rem] min-w-[1.9rem] place-items-center rounded-[0.5rem] bg-brand-800 px-[0.4rem] text-[0.9rem] text-white">{pending}</span></h2>
          <div className="flex rounded-[0.6rem] bg-paper p-[0.2rem] text-[0.78rem]">
            {[['pending', 'المعلّق'], ['done', 'المنجز'], ['all', 'الكل']].map(([v, l]) => (
              <button key={v} type="button" onClick={() => setFilter(v)} aria-pressed={filter === v} className={`rounded-[0.45rem] px-[0.7rem] py-[0.3rem] font-bold ${filter === v ? 'bg-white text-brand-800 shadow-sm' : 'text-ink-600'}`}>{l}</button>
            ))}
          </div>
        </header>
        <div className="hidden grid-cols-[1fr_5.5rem_8.5rem] bg-paper px-[1.2rem] py-[0.55rem] text-[0.78rem] font-bold text-ink-600 md:grid">
          <span>المحتوى</span><span>اللغة</span><span>الحالة</span>
        </div>
        {list.length === 0 ? <Empty small /> : (
          <ul className="divide-y divide-slate-100">
            {list.map((q, i) => {
              const [label, cls, Icon] = STATUS[q.status]
              return (
                <li key={q.id} className="seg-in" style={{ '--i': i }}>
                  <button type="button" onClick={() => choose(q.id)} aria-current={q.id === selId}
                    className={`grid w-full grid-cols-[1fr_auto] items-center gap-[0.6rem] px-[1.2rem] py-[0.85rem] text-right transition-colors md:grid-cols-[1fr_5.5rem_8.5rem] ${q.id === selId ? 'bg-brand-50/70' : 'hover:bg-paper'}`}>
                    <span className="min-w-0"><span className="block truncate text-[0.92rem] font-bold">{q.title}</span><span className="block truncate text-[0.74rem] text-ink-600">{q.reason}</span></span>
                    <span className="latin hidden text-[0.82rem] text-ink-600 md:block">{LANG[q.lang]}</span>
                    <span className={`inline-flex w-fit items-center gap-[0.3rem] rounded-full px-[0.6rem] py-[0.2rem] text-[0.72rem] font-bold ${cls}`}><Icon className="h-[0.8rem] w-[0.8rem]" aria-hidden />{label}</span>
                  </button>
                </li>
              )
            })}
          </ul>
        )}
      </section>

      {sidebar}
    </div>
    </>
  )
}

/** The panel belongs to the reviewer; end users only ever receive approved output. */
function PrivateNotice() {
  return (
    <div role="note" className="mb-[1.2rem] flex items-start gap-[0.8rem] rounded-[1rem] border border-hadith-fg/20 bg-hadith-bg px-[1.1rem] py-[0.85rem]">
      <span className="grid h-[2.3rem] w-[2.3rem] shrink-0 place-items-center rounded-full bg-white text-hadith-fg"><Lock className="h-[1.1rem] w-[1.1rem]" aria-hidden /></span>
      <div className="text-[0.86rem] leading-[1.45rem]">
        <p className="font-bold text-ink-900">لوحة خاصة بالمراجع الشرعي، ولا تظهر للمستخدم</p>
        <p className="text-ink-600">في النسخة الفعلية يدخلها المراجع بحساب مستقل، ولا يصل للمستخدم إلا ما اعتمده. تظهر هنا مفتوحة للعرض التجريبي فقط.</p>
      </div>
    </div>
  )
}

function Empty({ small }) {
  return (
    <div className={`grid place-items-center p-[2rem] text-center ${small ? 'min-h-[10rem]' : 'min-h-[20rem]'}`}>
      <div><Inbox className="mx-auto h-[2rem] w-[2rem] text-brand-300" aria-hidden /><p className="mt-[0.5rem] text-[0.9rem] text-ink-600">لا توجد عناصر هنا.</p></div>
    </div>
  )
}

const CSV_COLS = [['decidedIso', 'وقت القرار'], ['status', 'القرار'], ['lang', 'اللغة'], ['type', 'النوع'], ['source', 'النص الأصلي'], ['proposed', 'الترجمة المعتمدة/المقترحة'], ['ref', 'المرجع'], ['reason', 'سبب الإحالة'], ['reviewerNote', 'ملاحظة المراجع']]
const STATUS_AR = { approved: 'معتمد', edited: 'معدّل ومعتمد', rejected: 'مرفوض', pending: 'معلّق' }

function download(name, content, type) {
  const url = URL.createObjectURL(new Blob([content], { type }))
  const a = Object.assign(document.createElement('a'), { href: url, download: name })
  document.body.appendChild(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000)
}

const today = () => new Date().toISOString().slice(0, 10)

function LogView({ items }) {
  const toCsv = () => {
    const stamp = today()
    // A leading = + - @ would run as a formula in Excel; prefix it with an apostrophe.
    const esc = (v) => `"${String(v ?? '').replace(/^[=+\-@\t\r]/, "'$&").replace(/"/g, '""')}"`
    const rows = items.map((q) => CSV_COLS.map(([k]) => esc(k === 'status' ? STATUS_AR[q.status] : q[k])).join(','))
    download(`mowatin-review-log-${stamp}.csv`, '\uFEFF' + [CSV_COLS.map(([, h]) => esc(h)).join(','), ...rows].join('\n'), 'text/csv;charset=utf-8')
  }
  const toJson = () => download(`mowatin-review-log-${today()}.json`, JSON.stringify(items.map((q) => Object.fromEntries(CSV_COLS.map(([k]) => [k, q[k]]))), null, 2), 'application/json')
  const counts = ['approved', 'edited', 'rejected'].map((k) => [k, items.filter((q) => q.status === k).length])

  return (
    <section dir="rtl" className="order-2 min-w-0 rounded-[1.2rem] border border-slate-200/70 bg-white shadow-[0_1rem_2.5rem_-1.6rem_rgba(14,58,74,.3)] xl:order-1">
      <header className="flex flex-wrap items-center justify-between gap-[0.8rem] px-[1.2rem] py-[1rem]">
        <div>
          <h2 className="text-[1.15rem] font-bold">سجل القرارات</h2>
          <p className="text-[0.8rem] text-ink-600">{counts.map(([k, n]) => `${STATUS_AR[k]}: ${n}`).join(' · ')}</p>
        </div>
        <div className="flex gap-[0.5rem]">
          <button type="button" onClick={toCsv} disabled={!items.length} className="inline-flex items-center gap-[0.4rem] rounded-[0.7rem] bg-brand-800 px-[0.9rem] py-[0.5rem] text-[0.85rem] font-bold text-white hover:bg-brand-900 disabled:bg-slate-300"><Download className="h-[0.95rem] w-[0.95rem]" aria-hidden /> تصدير CSV</button>
          <button type="button" onClick={toJson} disabled={!items.length} className="inline-flex items-center gap-[0.4rem] rounded-[0.7rem] border border-slate-200 px-[0.9rem] py-[0.5rem] text-[0.85rem] font-bold hover:border-brand-600 disabled:opacity-40">JSON</button>
        </div>
      </header>
      {items.length === 0 ? <Empty /> : (
        <ol className="divide-y divide-slate-100">
          {[...items].sort((a, b) => (b.decidedIso || '').localeCompare(a.decidedIso || '')).map((q, i) => {
            const [label, cls, Icon] = STATUS[q.status]
            return (
              <li key={q.id} className="seg-in grid grid-cols-[auto_1fr] gap-[0.8rem] px-[1.2rem] py-[0.9rem]" style={{ '--i': i }}>
                <span className={`mt-[0.15rem] grid h-[2rem] w-[2rem] place-items-center rounded-full ${cls}`}><Icon className="h-[0.95rem] w-[0.95rem]" aria-hidden /></span>
                <div className="min-w-0">
                  <p className="flex flex-wrap items-center gap-x-[0.6rem] text-[0.9rem]"><b>{q.title}</b><span className="text-[0.76rem] text-ink-600">{label} · <span className="tabular">{q.decidedAt}</span> · <span className="latin">{LANG[q.lang]}</span></span></p>
                  {q.proposed && <p className="latin mt-[0.2rem] whitespace-pre-line text-left text-[0.84rem] text-ink-900/80"><LtrBrackets>{q.proposed}</LtrBrackets></p>}
                  {q.reviewerNote && <p className="mt-[0.3rem] rounded-[0.5rem] bg-paper px-[0.6rem] py-[0.3rem] text-[0.8rem]">ملاحظة: {q.reviewerNote}</p>}
                </div>
              </li>
            )
          })}
        </ol>
      )}
    </section>
  )
}
