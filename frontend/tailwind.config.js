// Copyright (c) 2026 Athar Al-Madinah Team (فريق أثر المدينة). All rights reserved.
// Mowatin (مُوطِّن) — Proprietary. Source-available for evaluation only. See LICENSE.
/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        brand: { 900: '#0A4A37', 800: '#0F6B4F', 600: '#1FA672', 300: '#A7D7C3', 100: '#E6F4ED', 50: '#F3FAF6' },
        ink: { 900: '#0E3A4A', 600: '#5B6B80', 300: '#CBD5E1' },
        paper: '#F5F7FA',
        quran: { fg: '#0F6B4F', bg: '#E6F4ED' },
        hadith: { fg: '#6D4FC2', bg: '#F0EBFB' },
        term: { fg: '#B45309', bg: '#FDF1E3' },
        danger: { fg: '#B42318', bg: '#FDECEA' },
        general: { fg: '#3B5B8C', bg: '#EEF2F7' },
        pending: { fg: '#C2410C', bg: '#F6E7D7' },
      },
      fontFamily: {
        sans: ['Tajawal', 'Inter', 'system-ui', 'sans-serif'],
        latin: ['Inter', 'system-ui', 'sans-serif'],
        quran: ['Amiri Quran', 'Amiri', 'serif'],
        mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'Consolas', 'Liberation Mono', 'Courier New', 'Tajawal', 'monospace'],
      },
      boxShadow: {
        card: '0 1px 2px rgba(14,58,74,.04), 0 8px 24px rgba(14,58,74,.06)',
        float: '0 24px 60px -12px rgba(10,74,55,.25)',
      },
    },
  },
  plugins: [],
}
