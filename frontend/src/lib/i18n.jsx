// Copyright (c) 2026 Athar Al-Madinah Team (فريق أثر المدينة). All rights reserved.
// Mowatin (مُوطِّن) — Proprietary. Source-available for evaluation only. See LICENSE.
// Minimal bilingual layer for the landing page and the tool (/app). Copy lives next to its
// markup as t('عربي', 'English') so the two versions are reviewed together.
// In the tool only the interface is bilingual; server messages stay Arabic (D-050).
// Results and developer pages are Arabic-only for now.
import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { ArrowLeft, ArrowRight } from 'lucide-react'

const Ctx = createContext({ lang: 'ar', dir: 'rtl', t: (ar) => ar, setLang: () => {} })

const isHome = () => typeof window !== 'undefined' && window.location.pathname === '/'
const isTool = () => typeof window !== 'undefined' && window.location.pathname.startsWith('/app')
const bilingual = () => isHome() || isTool()

function initialLang() {
  if (!bilingual()) return 'ar'
  const q = new URLSearchParams(window.location.search).get('lang')
  if (q === 'en' || q === 'ar') return q
  try { return localStorage.getItem('mowatin.lang') === 'en' ? 'en' : 'ar' } catch { return 'ar' }
}

export function LangProvider({ children }) {
  const [lang, setLangState] = useState(initialLang)
  const dir = lang === 'en' ? 'ltr' : 'rtl'
  useEffect(() => {
    document.documentElement.lang = lang
    document.documentElement.dir = dir
    if (isHome()) document.title = lang === 'en' ? 'Mowatin · We teach the machine to serve the message' : 'مُوطِّن · نُعلِّم الآلة لتخدم الرسالة'
    // Remember the language the page was read in (also for ?lang=en links), so «Start» keeps it in /app.
    if (bilingual()) { try { localStorage.setItem('mowatin.lang', lang) } catch { /* storage blocked */ } }
  }, [lang, dir])
  const setLang = (l) => {
    setLangState(l)
    try { localStorage.setItem('mowatin.lang', l) } catch { /* storage blocked */ }
    const url = new URL(window.location.href); url.searchParams.set('lang', l); window.history.replaceState(null, '', url)
  }
  const t = useCallback((ar, en) => (lang === 'en' && en != null ? en : ar), [lang])
  return <Ctx.Provider value={{ lang, dir, t, setLang, canSwitch: bilingual() }}>{children}</Ctx.Provider>
}

export const useLang = () => useContext(Ctx)

/** "Forward" arrow: points left in Arabic, right in English. */
export function Fwd(props) {
  const { lang } = useLang()
  const I = lang === 'en' ? ArrowRight : ArrowLeft
  return <I {...props} />
}
