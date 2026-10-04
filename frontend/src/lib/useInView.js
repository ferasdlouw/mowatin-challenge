// Copyright (c) 2026 Athar Al-Madinah Team (فريق أثر المدينة). All rights reserved.
// Mowatin (مُوطِّن) — Proprietary. Source-available for evaluation only. See LICENSE.
import { useEffect, useRef, useState } from 'react'

/** Observe an element. `once` keeps it true after first entry. */
export function useInView({ threshold = 0.25, once = true, rootMargin = '0px' } = {}) {
  const ref = useRef(null)
  const [inView, setInView] = useState(false)
  useEffect(() => {
    const el = ref.current
    if (!el || typeof IntersectionObserver === 'undefined') { setInView(true); return }
    const io = new IntersectionObserver(([e]) => {
      if (e.isIntersecting) { setInView(true); if (once) io.disconnect() }
      else if (!once) setInView(false)
    }, { threshold, rootMargin })
    io.observe(el)
    return () => io.disconnect()
  }, [threshold, once, rootMargin])
  return [ref, inView]
}

export const prefersReducedMotion = () =>
  typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
