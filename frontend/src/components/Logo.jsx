// Copyright (c) 2026 Athar Al-Madinah Team (فريق أثر المدينة). All rights reserved.
// Mowatin (مُوطِّن) — Proprietary. Source-available for evaluation only. See LICENSE.
import { useLang } from '../lib/i18n'

export default function Logo({ light = false, size = 'md' }) {
  const { t } = useLang()
  const big = size === 'md'
  return (
    <a href={typeof window !== 'undefined' && window.location.pathname !== '/' ? '/' : '#top'} className="group flex items-center gap-[0.5rem]" aria-label={t('مُوطِّن، الصفحة الرئيسية', 'Mowatin, home')}>
      <img src="/images/logo_icon.webp" alt={t('شعار مُوطِّن', 'Mowatin logo')} width="60" height="64"
        className={`${big ? 'h-[3.6rem]' : 'h-[3rem]'} w-auto transition-transform duration-500 group-hover:-translate-y-0.5 ${light ? 'rounded-xl bg-white p-1' : 'mix-blend-multiply'}`} />
      <span className="leading-none">
        <span className={`block ${big ? 'text-[2.45rem]' : 'text-[2rem]'} font-extrabold tracking-tight ${light ? 'text-white' : 'text-brand-800'}`}>{t('مُوطِّن', 'Mowatin')}</span>
        <span className={`mt-[0.2rem] block text-[0.72rem] font-medium ${light ? 'text-brand-300' : 'text-brand-800'}`}>{t('ترجمة آمنة .. لمعنى أصيل', 'Safe translation, authentic meaning')}</span>
      </span>
    </a>
  )
}
