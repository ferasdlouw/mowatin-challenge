// Copyright (c) 2026 Athar Al-Madinah Team (فريق أثر المدينة). All rights reserved.
// Mowatin (مُوطِّن) — Proprietary. Source-available for evaluation only. See LICENSE.
//
// Last line of defence: any render error shows a calm Arabic message instead of a blank page.
import { Component } from 'react'

export default class ErrorBoundary extends Component {
  state = { failed: false }

  static getDerivedStateFromError() {
    return { failed: true }
  }

  render() {
    if (!this.state.failed) return this.props.children
    return (
      <div dir="rtl" lang="ar" role="alert" className="grid min-h-screen place-items-center bg-paper p-6 text-center">
        <div className="max-w-[26rem] rounded-[1.2rem] border border-slate-200/70 bg-white p-[1.6rem] shadow-card">
          <img src="/images/logo_icon.webp" alt="شعار مُوطِّن" className="mx-auto h-[3.2rem] w-auto mix-blend-multiply" />
          <h1 className="mt-[0.8rem] text-[1.3rem] font-bold text-ink-900">حدث خطأ غير متوقع</h1>
          <p className="mt-[0.4rem] text-[0.95rem] leading-[1.7rem] text-ink-600">نعتذر عن ذلك. أعد تحميل الصفحة وجرّب مرة أخرى.</p>
          <div className="mt-[1.1rem] flex justify-center gap-[0.6rem]">
            <button type="button" onClick={() => window.location.reload()} className="rounded-[0.8rem] bg-brand-800 px-[1.2rem] py-[0.55rem] font-bold text-white hover:bg-brand-900">إعادة التحميل</button>
            <a href="/" className="rounded-[0.8rem] border border-slate-200 px-[1.2rem] py-[0.55rem] font-bold text-ink-900 hover:bg-paper">الصفحة الرئيسية</a>
          </div>
        </div>
      </div>
    )
  }
}
