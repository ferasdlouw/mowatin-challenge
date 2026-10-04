// Copyright (c) 2026 Athar Al-Madinah Team (فريق أثر المدينة). All rights reserved.
// Mowatin (مُوطِّن) — Proprietary. Source-available for evaluation only. See LICENSE.
import { BookOpen, ScrollText, Layers, FileText, TriangleAlert } from 'lucide-react'
import { useLang } from '../lib/i18n'

export const SEGMENT = {
  quran:   { label: 'آية قرآنية', en: 'Qur\'anic verse',  Icon: BookOpen,      cls: 'bg-quran-bg text-quran-fg' },
  hadith:  { label: 'حديث نبوي', en: 'Hadith',   Icon: ScrollText,    cls: 'bg-hadith-bg text-hadith-fg' },
  term:    { label: 'مصطلح شرعي', en: 'Islamic term',  Icon: Layers,        cls: 'bg-term-bg text-term-fg' },
  general: { label: 'نص عام', en: 'Plain text',      Icon: FileText,      cls: 'bg-general-bg text-general-fg' },
  flag:    { label: 'يحتاج مراجعة', en: 'Needs review', Icon: TriangleAlert, cls: 'bg-danger-bg text-danger-fg' },
}

export default function Chip({ type, children }) {
  const { t } = useLang()
  const { label, en, Icon, cls } = SEGMENT[type]
  return (
    <span className={`inline-flex items-center gap-[0.35rem] whitespace-nowrap rounded-full px-[0.65rem] py-[0.22rem] text-[0.74rem] font-bold ${cls}`}>
      <Icon className="h-[0.9rem] w-[0.9rem]" strokeWidth={1.9} aria-hidden />
      {children ?? t(label, en)}
    </span>
  )
}
