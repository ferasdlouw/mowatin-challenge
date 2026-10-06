// Copyright (c) 2026 Athar Al-Madinah Team (فريق أثر المدينة). All rights reserved.
// Mowatin (مُوطِّن) — Proprietary. Source-available for evaluation only. See LICENSE.
import { useLang } from '../lib/i18n'
import { BookOpen, ScrollText, Layers, FileText, Scale, TriangleAlert, Info, OctagonAlert } from 'lucide-react'

export const TYPE = {
  quran: { label: 'آية قرآنية', en: 'Quran verse', Icon: BookOpen, cls: 'bg-quran-bg text-quran-fg', bar: '#1FA672' },
  hadith: { label: 'حديث نبوي', en: 'Hadith', Icon: ScrollText, cls: 'bg-hadith-bg text-hadith-fg', bar: '#6D4FC2' },
  term_heavy: { label: 'مصطلح شرعي', en: 'Islamic term', Icon: Layers, cls: 'bg-term-bg text-term-fg', bar: '#F0A43A' },
  general: { label: 'نص عادي', en: 'Plain text', Icon: FileText, cls: 'bg-general-bg text-general-fg', bar: '#94A3B8' },
  fatwa_like: { label: 'مسألة فتوى', en: 'Fatwa question', Icon: Scale, cls: 'bg-pending-bg text-pending-fg', bar: '#C2410C' },
}

export const LEVEL = { A: 'أ', B: 'ب', C: 'ج', D: 'د' }
export const LEVEL_HINT = {
  A: ['معلومات أصلية مستقرة', 'Settled core information'],
  B: ['شرح وتعريف واستدلال', 'Explanation, definition and evidence'],
  C: ['مسائل خلافية أو عالية الحساسية', 'Disputed or highly sensitive matters'],
  D: ['فتوى أو حالة شخصية: إحالة لمختص', 'Fatwa or personal case: referred to a specialist'],
}

export function TypeChip({ type }) {
  const t = TYPE[type] ?? TYPE.general
  const { lang } = useLang()
  return (
    <span className={`inline-flex items-center gap-[0.35rem] whitespace-nowrap rounded-full px-[0.65rem] py-[0.22rem] text-[0.74rem] font-bold ${t.cls}`}>
      <t.Icon className="h-[0.9rem] w-[0.9rem]" strokeWidth={1.9} aria-hidden />{lang === 'en' ? t.en : t.label}
    </span>
  )
}

const FLAG = {
  info: { Icon: Info, cls: 'bg-brand-50 text-brand-900' },
  warn: { Icon: TriangleAlert, cls: 'bg-pending-bg text-[#8A3A0C]' },
  block: { Icon: OctagonAlert, cls: 'bg-danger-bg text-danger-fg' },
}
// A verse inside a flag (﴿…﴾, e.g. quran_diacritized, D-044) is shown in the Quran font so its
// tashkeel reads as in the source column; the rest of the message keeps the body font.
const VERSE = /(﴿[^﴾]*﴾)/
export function Flag({ f }) {
  const { Icon, cls } = FLAG[f.severity] ?? FLAG.info
  const parts = f.text.split(VERSE)
  return (
    <p dir="rtl" className={`flex items-start gap-[0.5rem] rounded-[0.6rem] px-[0.7rem] py-[0.5rem] text-[0.82rem] leading-[1.35rem] ${cls}`}>
      <Icon className="mt-[0.15rem] h-[1rem] w-[1rem] shrink-0" aria-hidden />
      <span>{parts.map((part, k) => (k % 2 ? <span key={k} className="font-quran text-[0.98rem] leading-[1.7rem]">{part}</span> : part))}</span>
    </p>
  )
}

export function Confidence({ value }) {
  const { t } = useLang()
  if (value == null) return null
  const pct = Math.round(value * 100)
  const color = value >= 0.85 ? '#0F6B4F' : value >= 0.6 ? '#C2410C' : '#B42318'
  return (
    <span className="flex items-center gap-[0.5rem] text-[0.76rem] text-ink-600" title={t('درجة الثقة من طبقة التحقق', 'Confidence score from the verification layer')}>
      {t('الثقة', 'Confidence')}
      <span className="relative h-[0.35rem] w-[4.5rem] overflow-hidden rounded-full bg-slate-200" aria-hidden>
        <span className="absolute inset-y-0 start-0 rounded-full transition-[width] duration-700" style={{ width: `${pct}%`, background: color }} />
      </span>
      <b className="tabular" style={{ color }}>{pct}%</b>
    </span>
  )
}

// ﴿ ﴾ (U+FD3F/U+FD3E) are not bidi-mirrored, so in left-to-right output each faces away from
// the verse and reads as ")…(". Only their glyphs are flipped; the text, and what is copied,
// stays exactly as the API sent it.
const ORNATE = /([﴾﴿])/
/** `children` (a string, or `highlight()` output) with each ornate bracket drawn for LTR text. */
export function LtrBrackets({ children }) {
  const list = Array.isArray(children) ? children : [children]
  return list.flatMap((node, i) => (typeof node === 'string'
    ? node.split(ORNATE).map((part, k) => (k % 2 ? <span key={`o${i}-${k}`} className="inline-block -scale-x-100">{part}</span> : part))
    : [node]))
}

/** Wrap occurrences of `needles` inside `text` with `wrap(match, key)`. */
export function highlight(text, needles, wrap) {
  if (!text || !needles?.length) return text
  const list = needles.filter(Boolean).sort((a, b) => b.length - a.length)
  // Only blank needles would build the pattern `()`, which splits the text into single letters.
  if (!list.length) return text
  const esc = list.map((n) => n.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))
  const re = new RegExp(`(${esc.join('|')})`, 'g')
  return text.split(re).map((part, i) => (list.includes(part) ? wrap(part, i) : part))
}
