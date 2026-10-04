// Copyright (c) 2026 Athar Al-Madinah Team (فريق أثر المدينة). All rights reserved.
// Mowatin (مُوطِّن) — Proprietary. Source-available for evaluation only. See LICENSE.
import { lazy, Suspense } from 'react'
import Navbar from './components/Navbar'
import Footer from './components/Footer'
import { Hero, Why, HowItWorks, Features, Faq, Cta } from './components/Sections'
import { useLang } from './lib/i18n'

const ToolApp = lazy(() => import('./app/ToolApp'))
const ResultsPage = lazy(() => import('./results/ResultsPage'))
const DevelopersPage = lazy(() => import('./results/DevelopersPage'))
const AboutPage = lazy(() => import('./results/AboutPage'))

export default function App() {
  if (typeof window !== 'undefined' && window.location.pathname.startsWith('/app')) {
    return <Suspense fallback={<div className="grid min-h-screen place-items-center text-brand-800">…</div>}><ToolApp /></Suspense>
  }
  if (typeof window !== 'undefined' && window.location.pathname.startsWith('/developers')) {
    return <Suspense fallback={<div className="grid min-h-screen place-items-center text-brand-800">…</div>}><DevelopersPage /></Suspense>
  }
  if (typeof window !== 'undefined' && window.location.pathname.startsWith('/about')) {
    return <Suspense fallback={<div className="grid min-h-screen place-items-center text-brand-800">…</div>}><AboutPage /></Suspense>
  }
  if (typeof window !== 'undefined' && window.location.pathname.startsWith('/results')) {
    return <Suspense fallback={<div className="grid min-h-screen place-items-center text-brand-800">…</div>}><ResultsPage /></Suspense>
  }
  return <Home />
}

function Home() {
  const { t } = useLang()
  return (
    <>
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:start-4 focus:top-4 focus:z-50 focus:rounded-lg focus:bg-white focus:px-4 focus:py-2">{t('تخطَّ إلى المحتوى', 'Skip to content')}</a>
      <Navbar />
      <main id="main" className="overflow-x-clip">
        <Hero />
        <Why />
        <HowItWorks />
        <Features />
        <Faq />
        <Cta />
      </main>
      <Footer />
    </>
  )
}
