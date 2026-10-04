// Copyright (c) 2026 Athar Al-Madinah Team (فريق أثر المدينة). All rights reserved.
// Mowatin (مُوطِّن) — Proprietary. Source-available for evaluation only. See LICENSE.
// Illustrative example. Verify every scripture reference and translation against
// the approved sources (docs/SOURCES.md) before publication.
import { useEffect, useRef, useState } from 'react'
import { BookOpen, ScrollText, Layers, FileText, Globe, ChevronDown } from 'lucide-react'
import { useInView, prefersReducedMotion } from '../lib/useInView'
import { useLang } from '../lib/i18n'

const DETECTED = [
  { Icon: BookOpen, title: 'آيات قرآنية', sub: 'سورة الحجرات (10)', en: ['Qur’anic verses', 'Al-Hujurat 10'], bar: '#1FA672', bg: '#EEF8F2', ic: '#0F6B4F', tt: '#0E3A4A', glow: 'rgba(31,166,114,.35)' },
  { Icon: ScrollText, title: 'أحاديث نبوية', sub: 'صحيح البخاري (1)', en: ['Hadith', 'Sahih al-Bukhari 1'], bar: '#6D4FC2', bg: '#F5F1FD', ic: '#6D4FC2', tt: '#0E3A4A', glow: 'rgba(109,79,194,.3)' },
  { Icon: Layers, title: 'مصطلحات شرعية', sub: 'التقوى - الإحسان - الزكاة', en: ['Islamic terms', 'Taqwa · Ihsan · Zakah'], bar: '#F0A43A', bg: '#FFF6E8', ic: '#E08A1E', tt: '#B45309', glow: 'rgba(240,164,58,.38)' },
  { Icon: FileText, title: 'نص عادي', sub: 'يتم ترجمته بشكل طبيعي', en: ['Plain text', 'Translated naturally'], bar: '#CBD5E1', bg: '#F4F6F9', ic: '#64748B', tt: '#0E3A4A', glow: 'rgba(100,116,139,.25)' },
]

function Arrow({ i, muted, flip }) {
  return (
    <svg viewBox="0 0 24 24" className={`route h-[1.15rem] w-[1.15rem] ${flip ? '-scale-x-100' : ''}`} style={{ '--i': i }} fill="none" stroke={muted ? '#94A3B8' : '#1FA672'} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M4 12h15M13 6l6 6-6 6" />
    </svg>
  )
}

function ShieldTile() {
  return (
    <span className="stamp relative grid h-[3.45rem] w-[3.1rem] place-items-center" aria-hidden>
      <svg viewBox="0 0 50 56" className="absolute inset-0 h-full w-full drop-shadow-[0_0.4rem_0.6rem_rgba(10,74,55,.35)]">
        <defs><linearGradient id="sh" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#1FA672" /><stop offset="1" stopColor="#0A4A37" /></linearGradient></defs>
        <path d="M25 2 46 10v17c0 13-9 22-21 27C13 49 4 40 4 27V10Z" fill="url(#sh)" stroke="#E6F4ED" strokeWidth="2.5" />
      </svg>
      <svg viewBox="0 0 24 24" className="relative h-[1.5rem] w-[1.5rem]" fill="none" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 3 19 6v5c0 4.5-3 8-7 9.5C8 19 5 15.5 5 11V6Z" />
        <path className="stamp-check" d="m9 12 2 2 4-4" />
      </svg>
    </span>
  )
}

export default function DemoCard() {
  const [ref, inView] = useInView({ threshold: 0.35, once: false })
  const [run, setRun] = useState(0)
  const tiltRef = useRef(null)
  const { t, dir } = useLang()

  // Play when it enters view, then replay every 10s while it stays visible.
  useEffect(() => {
    if (!inView) return
    setRun((r) => r + 1)
    if (prefersReducedMotion()) return
    const t = setInterval(() => setRun((r) => r + 1), 10000)
    return () => clearInterval(t)
  }, [inView])

  const onMove = (e) => {
    const el = tiltRef.current
    if (!el || prefersReducedMotion() || window.matchMedia('(pointer: coarse)').matches) return
    const r = el.getBoundingClientRect()
    const x = (e.clientX - r.left) / r.width - 0.5
    const y = (e.clientY - r.top) / r.height - 0.5
    el.style.transform = `perspective(1400px) rotateY(${x * 5}deg) rotateX(${-y * 4}deg)`
    el.style.setProperty('--mx', `${(x + 0.5) * 100}%`)
    el.style.setProperty('--my', `${(y + 0.5) * 100}%`)
  }
  const onLeave = () => { if (tiltRef.current) tiltRef.current.style.transform = '' }

  return (
    <div ref={ref} dir="rtl" className="relative" onMouseMove={onMove} onMouseLeave={onLeave}>
      <div key={run} className={run ? 'scan-play' : ''}>
        {/* badge */}
        <div className="absolute -top-[2.5rem] right-[1rem] z-20 flex items-center xl:right-[5.6rem]">
          <span className="flex h-[2.4rem] items-center rounded-r-none rounded-l-[0.8rem] bg-gradient-to-l from-brand-800 to-[#0B5A42] pl-[1.4rem] pr-[1rem] text-[0.82rem] font-bold text-white shadow-[0_0.6rem_1.4rem_-0.4rem_rgba(10,74,55,.55)]">
            {t('ترجمة آمنة بمعايير شرعية', 'Safe translation to Islamic standards')}
          </span>
          <span className="-ml-[0.5rem] order-first"><ShieldTile /></span>
        </div>

        <div ref={tiltRef} className="tilt relative overflow-hidden rounded-[1.15rem] border border-white/80 bg-white/[.93] p-[0.8rem] pt-[0.7rem] shadow-[0_2rem_4rem_-1.5rem_rgba(14,58,74,.28)] backdrop-blur-sm transition-transform duration-500 ease-out [transform-style:preserve-3d]"
          style={{ backgroundImage: 'radial-gradient(28rem circle at var(--mx,50%) var(--my,0%), rgba(31,166,114,.07), transparent 60%)' }}>
          <div className="mb-[0.55rem] flex gap-[0.3rem] pl-[0.2rem]" dir="ltr" aria-hidden>
            <i className="h-[0.42rem] w-[0.42rem] rounded-full bg-slate-300" /><i className="h-[0.42rem] w-[0.42rem] rounded-full bg-slate-300" /><i className="h-[0.42rem] w-[0.42rem] rounded-full bg-slate-300" />
          </div>

          <div dir={dir} className="grid grid-cols-[1fr_1.4rem_1fr] gap-0 xl:grid-cols-[15rem_2.3rem_1fr]" style={{ '--dx': dir === 'rtl' ? '0.6rem' : '-0.6rem' }}>
            {/* detected */}
            <div dir={dir} className="relative overflow-hidden rounded-[0.9rem] bg-white px-[0.75rem] pb-[0.75rem] pt-[0.9rem]">
              <span className="scan-line pointer-events-none absolute inset-x-0 top-0 z-10 h-[2.2rem] bg-gradient-to-b from-transparent via-brand-600/20 to-transparent opacity-0" aria-hidden />
              <p className="mb-[0.75rem] text-[0.86rem] font-bold text-ink-900">{t('تم اكتشاف العناصر التالية', 'Detected elements')}</p>
              <ul className="space-y-[0.5rem]">
                {DETECTED.map(({ Icon, title, sub, en, bar, bg, ic, tt, glow }, i) => (
                  <li key={title} className="detect relative flex min-h-[4.2rem] items-center justify-between gap-1 rounded-[0.65rem] py-1 ps-[0.7rem] pe-[0.6rem] xl:ps-[1.2rem] xl:pe-[1rem]" style={{ background: bg, '--i': i, '--glow': glow }}>
                    <span className="detect-bar absolute inset-y-0 start-0 w-[3px] rounded-s-[0.65rem]" style={{ background: bar, '--i': i }} aria-hidden />
                    <div className="min-w-0">
                      <p className="text-[0.95rem] font-bold" style={{ color: tt }}>{t(title, en[0])}</p>
                      <p className="mt-[0.15rem] text-[0.74rem] text-ink-600">{t(sub, en[1])}</p>
                    </div>
                    <Icon className="h-[1.45rem] w-[1.45rem] shrink-0" style={{ color: ic }} strokeWidth={1.75} aria-hidden />
                  </li>
                ))}
              </ul>
            </div>

            {/* routes */}
            <div className="flex flex-col items-center pt-[2.75rem]" aria-hidden>
              {DETECTED.map((d, i) => (
                <div key={d.title} className="grid h-[4.7rem] place-items-center"><Arrow i={i} muted={i === 0} flip={dir === 'rtl'} /></div>
              ))}
            </div>

            {/* output */}
            <div dir={dir} className="rounded-[0.9rem] bg-[#F6F8FA] p-[0.5rem]">
              <div className="mb-[0.4rem] flex justify-end">
                <span className="inline-flex items-center gap-[0.35rem] rounded-full border border-slate-200 bg-white px-[0.6rem] py-[0.2rem] text-[0.72rem] font-bold text-ink-900">
                  <Globe className="h-[0.85rem] w-[0.85rem] text-brand-800" aria-hidden /> {t('الإنجليزية', 'English')} <ChevronDown className="h-[0.75rem] w-[0.75rem]" aria-hidden />
                </span>
              </div>
              <div className="space-y-[0.5rem]">
                <div className="resolve rounded-[0.7rem] bg-white px-[0.8rem] py-[0.6rem] shadow-[0_1px_2px_rgba(14,58,74,.06)]" style={{ '--i': 0 }}>
                  <p dir="rtl" className="text-right font-quran text-[1.2rem] leading-[1.9rem] text-ink-900">﴿إِنَّمَا الْمُؤْمِنُونَ إِخْوَةٌ﴾</p>
                  <p dir="rtl" className="text-left text-[0.72rem] text-ink-600">(الحجرات: 10)</p>
                  <div className="relative mt-[0.4rem] rounded-[0.5rem] pl-[0.8rem] pr-[0.6rem]">
                    <span className="absolute inset-y-[0.15rem] left-0 w-[2px] rounded bg-brand-300" aria-hidden />
                    <p className="text-[0.74rem] font-bold text-brand-800">{t('الترجمة المعتمدة', 'Approved translation')}</p>
                    <p className="latin mt-[0.25rem] text-left text-[0.74rem] leading-[1.1rem] text-ink-900">The believers are but brothers…</p>
                    <p className="latin text-left text-[0.72rem] text-ink-600">(Al-Hujurat: 10)</p>
                  </div>
                </div>
                <div className="resolve relative rounded-[0.7rem] bg-white py-[0.55rem] pl-[1rem] pr-[0.8rem] shadow-[0_1px_2px_rgba(14,58,74,.06)]" style={{ '--i': 2 }}>
                  <span className="absolute inset-y-[0.5rem] left-[0.45rem] w-[2px] rounded bg-brand-300" aria-hidden />
                  <p className="text-[0.72rem] font-bold text-brand-800">{t('المصطلح الشرعي', 'Islamic term')}</p>
                  <p dir="rtl" className="mt-[0.15rem] text-right text-[0.98rem] font-bold text-brand-800">التقوى</p>
                  <p className="text-left text-[0.72rem] text-ink-600">{t(<><span className="latin">Taqwa</span> (التقوى: مراقبة الله في السر والعلن)</>, 'Taqwa (God-consciousness, in private and in public)')}</p>
                </div>
                <div className="resolve relative rounded-[0.7rem] bg-white py-[0.55rem] pl-[1rem] pr-[0.8rem] shadow-[0_1px_2px_rgba(14,58,74,.06)]" style={{ '--i': 3 }}>
                  <span className="absolute inset-y-[0.5rem] left-[0.45rem] w-[2px] rounded bg-slate-300" aria-hidden />
                  <p className="text-[0.72rem] font-bold text-ink-600">{t('النص العادي', 'Plain text')}</p>
                  <p className="latin mt-[0.2rem] text-left text-[0.72rem] leading-[1.05rem] text-ink-600">So worship includes every word and deed that God loves.</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
