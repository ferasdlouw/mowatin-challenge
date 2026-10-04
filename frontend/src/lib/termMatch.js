// Copyright (c) 2026 Athar Al-Madinah Team (فريق أثر المدينة). All rights reserved.
// Mowatin (مُوطِّن) — Proprietary. Source-available for evaluation only. See LICENSE.
//
// Find where locked glossary terms appear in the Arabic source. The server sends each
// term in its glossary form («العبادة»), while the text may say «فالعبادةِ» or «بالعبادة»,
// so an exact search misses them. Matching is per word, after normalising and peeling
// the attached prefixes و/ف + ب/ل/ك + «ال».

const TASHKEEL = /[ً-ْٰـ]/g
const WORD = /[ء-يً-ْٰـٱ]+/g

export const normAr = (s) =>
  s.replace(TASHKEEL, '').replace(/[أإآٱ]/g, 'ا').replace(/ة/g, 'ه').replace(/ى/g, 'ي')

const MIN_STEM = 3 // shorter stems match too many unrelated words

/** The word itself plus its stems once attached prefixes are removed. */
function stems(word) {
  const out = new Set([word])
  for (const a of ['', 'و', 'ف']) {
    if (a && !word.startsWith(a)) continue
    const w1 = word.slice(a.length)
    for (const b of ['', 'ب', 'ل', 'ك']) {
      if (b && !w1.startsWith(b)) continue
      let w2 = w1.slice(b.length)
      if (b === 'ل' && w2.startsWith('ل')) w2 = `ا${w2}` // لل = ل + ال
      if (w2.length >= MIN_STEM) out.add(w2)
      if (w2.startsWith('ال') && w2.length - 2 >= MIN_STEM) out.add(w2.slice(2))
    }
  }
  return out
}

/** Accepted spellings of one glossary word: with and without «ال». */
function forms(word) {
  const w = normAr(word)
  const out = new Set([w])
  if (w.startsWith('ال') && w.length - 2 >= MIN_STEM) out.add(w.slice(2))
  return out
}

/**
 * @param {string} source Arabic text
 * @param {{key: string, forms: string[]}[]} terms each term with its glossary form and variants
 * @returns {{start: number, end: number, key: string}[]} non-overlapping spans, in text order
 */
export function findTermSpans(source, terms) {
  if (!source || !terms?.length) return []
  const words = [...source.matchAll(WORD)].map((m) => ({ start: m.index, end: m.index + m[0].length, norm: normAr(m[0]) }))
  // Longer phrases first, so «توحيد الربوبية» wins over «توحيد».
  const phrases = terms
    .flatMap(({ key, forms: fs }) => fs.filter(Boolean).map((f) => ({ key, parts: f.trim().split(/\s+/).map(forms) })))
    .sort((a, b) => b.parts.length - a.parts.length)
  const taken = new Array(words.length).fill(false)
  const spans = []
  for (const { key, parts } of phrases) {
    for (let i = 0; i + parts.length <= words.length; i++) {
      if (taken.slice(i, i + parts.length).some(Boolean)) continue
      const first = stems(words[i].norm)
      if (![...parts[0]].some((f) => first.has(f))) continue
      if (!parts.slice(1).every((p, j) => p.has(words[i + 1 + j].norm))) continue
      for (let k = i; k < i + parts.length; k++) taken[k] = true
      spans.push({ start: words[i].start, end: words[i + parts.length - 1].end, key })
    }
  }
  return spans.sort((a, b) => a.start - b.start)
}
