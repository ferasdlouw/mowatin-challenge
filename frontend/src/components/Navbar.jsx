// Copyright (c) 2026 Athar Al-Madinah Team (فريق أثر المدينة). All rights reserved.
// Mowatin (مُوطِّن) — Proprietary. Source-available for evaluation only. See LICENSE.
import { useEffect, useState } from 'react'
import { Menu, X, Globe } from 'lucide-react'
import Logo from './Logo'
import { useLang, Fwd } from '../lib/i18n'

const LINKS = [
  ['#top', 'الرئيسية', 'Home'],
  ['#how', 'كيف يعمل؟', 'How it works'],
  ['#features', 'المميزات', 'Features'],
  ['/results', 'النتائج', 'Results'],
  ['#faq', 'الأسئلة الشائعة', 'FAQ'],
  ['#contact', 'تواصل معنا', 'Contact'],
]

export default function Navbar() {
  const { t, lang, setLang, canSwitch } = useLang()
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(() => (window.location.pathname !== '/' ? window.location.pathname : '#top'))
  const [scrolled, setScrolled] = useState(false)

  useEffect(() => {
    if (window.location.pathname !== '/') return
    const ids = LINKS.filter(([h]) => h.startsWith('#')).map(([h]) => h.slice(1))
    const onScroll = () => {
      setScrolled(window.scrollY > 8)
      let cur = '#top'
      for (const id of ids) {
        const el = document.getElementById(id)
        if (el && el.getBoundingClientRect().top < window.innerHeight * 0.35) cur = `#${id}`
      }
      setActive(cur)
    }
    onScroll()
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  return (
    <header className={`sticky top-0 z-40 bg-white/90 backdrop-blur-md transition-shadow duration-300 ${scrolled ? 'shadow-[0_0.5rem_2rem_-1rem_rgba(14,58,74,.25)]' : ''}`}>
      <nav className="shell flex h-[4.2rem] items-center justify-between xl:h-[5.3rem] xl:w-[82rem]">
        <Logo />
        <ul className="hidden items-center gap-[2.3rem] text-[1rem] font-medium xl:flex">
          {LINKS.map(([href, label, en]) => (
            <li key={href}>
              <a href={href.startsWith('#') && typeof window !== 'undefined' && window.location.pathname !== '/' ? `/${href}` : href} aria-current={active === href ? 'page' : undefined}
                className={`relative block py-[0.5rem] transition-colors duration-200 hover:text-brand-800 after:absolute after:inset-x-0 after:-bottom-[0.15rem] after:h-[2px] after:origin-center after:rounded after:bg-brand-800 after:transition-transform after:duration-300 ${active === href ? 'font-bold text-brand-800 after:scale-x-100' : 'text-ink-900 after:scale-x-0'}`}>{t(label, en)}</a>
            </li>
          ))}
        </ul>
        <div className="hidden items-center gap-[2.4rem] xl:flex">
          {canSwitch && (
            <button type="button" onClick={() => setLang(lang === 'ar' ? 'en' : 'ar')} lang={lang === 'ar' ? 'en' : 'ar'}
              className="flex items-center gap-[0.5rem] text-[0.95rem] font-medium text-ink-900 hover:text-brand-800" aria-label={lang === 'ar' ? 'Switch to English' : 'التبديل إلى العربية'}>
              <Globe className="h-[1.35rem] w-[1.35rem]" strokeWidth={1.75} aria-hidden /> {lang === 'ar' ? 'English' : 'العربية'}
            </button>
          )}
          <a href="/app" className="btn-shine inline-flex h-[2.5rem] w-[7.9rem] items-center justify-center rounded-[0.8rem] bg-brand-800 text-[0.95rem] font-bold text-white transition-colors hover:bg-brand-900">{t('ابدأ الآن', 'Get started')}</a>
        </div>
        <button className="rounded-lg p-2 xl:hidden" onClick={() => setOpen(!open)} aria-label={t('القائمة', 'Menu')} aria-expanded={open}>
          {open ? <X /> : <Menu />}
        </button>
      </nav>
      {open && (
        <ul className="shell flex flex-col gap-1 pb-4 xl:hidden">
          {LINKS.map(([href, label, en]) => (
            <li key={href}><a onClick={() => setOpen(false)} className="block rounded-lg px-3 py-2.5 hover:bg-brand-50" href={href.startsWith('#') && window.location.pathname !== '/' ? `/${href}` : href}>{t(label, en)}</a></li>
          ))}
          {canSwitch && <li><button type="button" onClick={() => { setLang(lang === 'ar' ? 'en' : 'ar'); setOpen(false) }} className="flex w-full items-center gap-2 rounded-lg px-3 py-2.5 hover:bg-brand-50"><Globe size={18} aria-hidden /> {lang === 'ar' ? 'English' : 'العربية'}</button></li>}
          <li><a href="/app" className="mt-2 flex items-center justify-center gap-2 rounded-xl bg-brand-800 py-3 font-bold text-white">{t('ابدأ الآن', 'Get started')} <Fwd size={18} aria-hidden /></a></li>
        </ul>
      )}
    </header>
  )
}
