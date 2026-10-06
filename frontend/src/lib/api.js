// Copyright (c) 2026 Athar Al-Madinah Team (فريق أثر المدينة). All rights reserved.
// Mowatin (مُوطِّن) — Proprietary. Source-available for evaluation only. See LICENSE.
//
// Client for POST /v1/translate (docs/ARCHITECTURE.md). When VITE_API_URL is not
// set the UI runs in DEMO mode: the bundled examples return prepared results and
// any other text gets { demo_only: true } (nothing is invented). When the server is
// down, the bundled examples still answer, marked { fallback: true }.
import { EXAMPLES } from '../data/examples'
// المسرد: ملف لكل مجموعة في data/glossary/*.json (انظر data/glossary/SCHEMA.md)
const GLOSSARY_FILES = import.meta.glob('../../../data/glossary/*.json', { eager: true, import: 'default' })
const GLOSSARY = Object.values(GLOSSARY_FILES).flat()

export const API_URL = import.meta.env.VITE_API_URL || ''
export const MODE = API_URL ? 'live' : 'demo'
export const glossaryById = Object.fromEntries(GLOSSARY.map((g) => [g.id, g]))

const strip = (s) => s.replace(/[ً-ْٰـ]/g, '').replace(/[أإآ]/g, 'ا').replace(/ة/g, 'ه').replace(/\s+/g, ' ').trim()
const wait = (ms) => new Promise((r) => setTimeout(r, ms))

function fromExample(ex, lang) {
  const segments = ex.segments.map((s, i) => {
    const L = s[lang]
    const locked = (s.terms || []).map(([ar, gid], k) => ({ ar, glossary_id: gid, out: L.marks[k] ?? null }))
    return {
      id: i + 1, source: s.source, output: L.out, type: s.type, level: s.level,
      locked_terms: locked, marks: L.marks, sources: s.sources.map((x) => ({ ...x, edition: x.edition?.[lang] })),
      confidence: s.confidence, flags: s.flags,
      baseline: { output: L.generic, wrong: L.wrong, why: L.why },
    }
  })
  return finalize(segments)
}

/** Same rule as the server: low confidence, or any warn/block flag. */
export const needsReview = (s) => (s.confidence != null && s.confidence < 0.75) || s.flags.some((f) => f.severity !== 'info')

function finalize(segments) {
  const review_queue = segments.filter(needsReview).map((s) => s.id)
  const scored = segments.filter((s) => s.confidence != null)
  return {
    segments,
    review_queue,
    summary: {
      segments: segments.length,
      flagged: review_queue.length,
      avg_confidence: scored.length ? scored.reduce((a, s) => a + s.confidence, 0) / scored.length : null,
    },
    disclosure: 'مخرجات مدعومة بالذكاء الاصطناعي، وتحتاج مراجعة بشرية مؤهلة قبل النشر.',
  }
}

// The server answers within REQUEST_DEADLINE_S (90 s, D-060); +60 s for a cold start on Render.
const TIMEOUT_MS = 150000

const HTTP_ERROR = {
  400: 'النص فارغ أو غير صالح. اكتب نصًا عربيًا ثم أعد المحاولة.',
  413: 'النص أطول من 4000 حرف.',
  429: 'طلبات كثيرة في وقت قصير. انتظر قليلًا ثم أعد المحاولة.',
}

/** Fill in optional fields so a partial server response never breaks the UI. */
function normalize(data) {
  if (!data || !Array.isArray(data.segments)) throw new Error('وصلت استجابة غير متوقعة من الخادم.')
  const segments = data.segments.map((s, i) => ({
    ...s,
    id: s.id ?? i + 1,
    source: s.source ?? '',
    output: s.output ?? null,
    type: s.type ?? 'general',
    locked_terms: s.locked_terms ?? [],
    marks: s.marks ?? [],
    sources: s.sources ?? [],
    flags: s.flags ?? [],
    confidence: s.confidence ?? null,
    back_translation: s.back_translation ?? null,
  }))
  const base = finalize(segments)
  return {
    ...base, ...data, segments,
    review_queue: Array.isArray(data.review_queue) ? data.review_queue : base.review_queue,
    summary: data.summary ?? base.summary,
    disclosure: data.disclosure ?? base.disclosure,
  }
}

// mode=compare returns Mowatin's output plus the same model without Mowatin
// (segment.baseline), which the «قبل وبعد» screen needs.
const findExample = (text) => EXAMPLES.find((e) => strip(e.text) === strip(text))
const SERVER_DOWN = 'الخادم قيد التشغيل أو لا يستجيب الآن. حاول بعد لحظات، أو جرّب أحد الأمثلة.'

export async function translate({ text, target_lang, audience, mode = 'compare' }) {
  if (API_URL) {
    try {
      return await translateLive({ text, target_lang, audience, mode })
    } catch (e) {
      // Server asleep or down: the bundled examples still work.
      const ex = e.serverDown && findExample(text)
      if (ex) return { ...fromExample(ex, target_lang), fallback: true }
      throw e
    }
  }
  await wait(2400) // demo: long enough to see each pipeline step
  const ex = findExample(text)
  return ex ? fromExample(ex, target_lang) : { demo_only: true }
}

const fail = (message, serverDown = false) => Object.assign(new Error(message), { serverDown })

async function translateLive({ text, target_lang, audience, mode }) {
  {
    const ctrl = new AbortController()
    const timer = setTimeout(() => ctrl.abort(), TIMEOUT_MS)
    let res
    try {
      res = await fetch(`${API_URL.replace(/\/$/, '')}/v1/translate`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text, target_lang, audience, mode }),
        signal: ctrl.signal,
      })
    } catch (e) {
      throw fail(e.name === 'AbortError' ? 'استغرق الخادم وقتًا أطول من المعتاد. ' + SERVER_DOWN : 'تعذّر الاتصال بالخادم. تحقّق من الإنترنت، أو جرّب أحد الأمثلة.', true)
    } finally {
      clearTimeout(timer)
    }
    if (!res.ok) throw fail(HTTP_ERROR[res.status] ?? (res.status >= 500 ? SERVER_DOWN : 'تعذّر معالجة النص. تحقّق منه وحاول مجددًا.'), res.status >= 500)
    let data
    try { data = await res.json() } catch { throw new Error('وصلت استجابة غير متوقعة من الخادم.') }
    return normalize(data)
  }
}
