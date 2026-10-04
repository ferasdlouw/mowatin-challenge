// Copyright (c) 2026 Athar Al-Madinah Team (فريق أثر المدينة). All rights reserved.
// Mowatin (مُوطِّن) — Proprietary. Source-available for evaluation only. See LICENSE.
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import '@fontsource/tajawal/arabic-400.css'
import '@fontsource/tajawal/arabic-500.css'
import '@fontsource/tajawal/arabic-700.css'
import '@fontsource/tajawal/arabic-800.css'
import '@fontsource/tajawal/latin-400.css'
import '@fontsource/tajawal/latin-700.css'
import '@fontsource/inter/latin-400.css'
import '@fontsource/inter/latin-500.css'
import '@fontsource/inter/latin-600.css'
import '@fontsource/inter/latin-700.css'
import '@fontsource/inter/latin-800.css'
import '@fontsource/amiri-quran/arabic-400.css'
import './index.css'
import App from './App.jsx'
import { LangProvider } from './lib/i18n'
import ErrorBoundary from './components/ErrorBoundary'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <ErrorBoundary>
      <LangProvider><App /></LangProvider>
    </ErrorBoundary>
  </StrictMode>,
)
