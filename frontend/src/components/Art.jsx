// Copyright (c) 2026 Athar Al-Madinah Team (فريق أثر المدينة). All rights reserved.
// Mowatin (مُوطِّن) — Proprietary. Source-available for evaluation only. See LICENSE.
// Decorative SVG art (skyline, arch, lattice). Replace with real images in /public/images if desired.

export function Skyline({ className = '', color = '#0F6B4F' }) {
  const minaret = (x, h) => (
    <g key={x}>
      <rect x={x - 5} y={200 - h} width="10" height={h} rx="2" />
      <rect x={x - 8} y={200 - h * 0.62} width="16" height="5" rx="2" />
      <rect x={x - 7} y={200 - h * 0.86} width="14" height="4" rx="2" />
      <path d={`M${x - 6} ${200 - h} Q${x} ${200 - h - 22} ${x + 6} ${200 - h} Z`} />
      <rect x={x - 0.8} y={200 - h - 32} width="1.6" height="12" />
    </g>
  )
  const dome = (cx, r, base) => (
    <g key={cx}>
      <path d={`M${cx - r} ${base} a${r} ${r * 1.05} 0 0 1 ${2 * r} 0 Z`} />
      <rect x={cx - r - 6} y={base} width={2 * r + 12} height={200 - base} />
      <rect x={cx - 0.8} y={base - r * 1.05 - 14} width="1.6" height="14" />
    </g>
  )
  return (
    <svg viewBox="0 0 600 200" preserveAspectRatio="xMidYMax slice" className={className} fill={color} aria-hidden>
      {dome(300, 58, 120)}
      {dome(215, 30, 150)}
      {dome(385, 30, 150)}
      {dome(120, 20, 168)}
      {dome(480, 20, 168)}
      {[minaret(250, 150), minaret(350, 150), minaret(165, 115), minaret(435, 115), minaret(60, 95), minaret(545, 95)]}
      <rect x="0" y="185" width="600" height="15" />
    </svg>
  )
}

export function Arch({ className = '' }) {
  return (
    <svg viewBox="0 0 200 320" className={className} aria-hidden fill="none">
      <defs>
        <pattern id="lat" width="24" height="24" patternUnits="userSpaceOnUse">
          <path d="M12 0 L24 12 L12 24 L0 12 Z M12 6 L18 12 L12 18 L6 12 Z" stroke="#0F6B4F" strokeOpacity=".35" strokeWidth="1" />
        </pattern>
      </defs>
      <path d="M100 8 C130 50 190 70 190 150 V320 H10 V150 C10 70 70 50 100 8 Z" fill="#E6F4ED" />
      <path d="M100 8 C130 50 190 70 190 150 V320 H10 V150 C10 70 70 50 100 8 Z" fill="url(#lat)" />
      <path d="M100 8 C130 50 190 70 190 150 V320 H10 V150 C10 70 70 50 100 8 Z" stroke="#1FA672" strokeOpacity=".5" strokeWidth="3" />
    </svg>
  )
}

export function ArchOutline({ className = '' }) {
  return (
    <svg viewBox="0 0 200 240" className={className} aria-hidden fill="none">
      <path d="M100 6 C130 46 192 64 192 140 V240 H8 V140 C8 64 70 46 100 6 Z" fill="#E6F4ED" fillOpacity=".7" />
    </svg>
  )
}
