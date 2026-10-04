// Copyright (c) 2026 Athar Al-Madinah Team (فريق أثر المدينة). All rights reserved.
// Mowatin (مُوطِّن) — Proprietary. Source-available for evaluation only. See LICENSE.
// Extract plain text from an uploaded file entirely in the browser (nothing is uploaded).
const MAX_BYTES = 10 * 1024 * 1024

export const ACCEPT = '.docx,.pdf,.txt,application/vnd.openxmlformats-officedocument.wordprocessingml.document,application/pdf,text/plain'

export async function extractText(file) {
  if (file.size > MAX_BYTES) throw new Error('الملف أكبر من 10 ميغابايت.')
  const name = file.name.toLowerCase()
  if (name.endsWith('.txt')) return clean(await file.text())
  if (name.endsWith('.docx')) {
    const mammoth = (await import('mammoth/mammoth.browser.js')).default
    const { value } = await mammoth.extractRawText({ arrayBuffer: await file.arrayBuffer() })
    return clean(value)
  }
  if (name.endsWith('.pdf')) {
    const pdfjs = await import('pdfjs-dist/build/pdf.min.mjs')
    pdfjs.GlobalWorkerOptions.workerSrc = (await import('pdfjs-dist/build/pdf.worker.min.mjs?url')).default
    // isEvalSupported: false — pdf.js never compiles code from the file (defence in depth, CSP has no unsafe-eval).
    const doc = await pdfjs.getDocument({ data: await file.arrayBuffer(), isEvalSupported: false }).promise
    const pages = []
    for (let i = 1; i <= Math.min(doc.numPages, 40); i++) {
      const page = await doc.getPage(i)
      const tc = await page.getTextContent()
      pages.push(tc.items.map((it) => it.str + (it.hasEOL ? '\n' : ' ')).join(''))
    }
    const text = clean(pages.join('\n'))
    if (!text) throw new Error('لم نجد نصًا في هذا الملف. قد يكون PDF مصوّرًا (صور لا نصوص).')
    return text
  }
  if (name.endsWith('.doc')) throw new Error('صيغة .doc القديمة غير مدعومة. احفظ الملف بصيغة .docx ثم أعد المحاولة.')
  throw new Error('الصيغ المدعومة: Word (.docx) وPDF ونص (.txt).')
}

const clean = (s) => s.replace(/\r/g, '').replace(/[ \t]+\n/g, '\n').replace(/\n{3,}/g, '\n\n').replace(/[ \t]{2,}/g, ' ').trim()
