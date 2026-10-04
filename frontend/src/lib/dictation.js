// Copyright (c) 2026 Athar Al-Madinah Team (فريق أثر المدينة). All rights reserved.
// Mowatin (مُوطِّن) — Proprietary. Source-available for evaluation only. See LICENSE.
//
// Arabic dictation with the browser's speech recognition (Chrome, Edge, Safari).
// The browser's own service turns speech into text (Chrome sends the audio to Google);
// the UI says so next to the button. Firefox has no support, so the button is hidden there.
import { useCallback, useEffect, useRef, useState } from 'react'

const Recognition = typeof window !== 'undefined' ? (window.SpeechRecognition || window.webkitSpeechRecognition) : undefined
export const canDictate = Boolean(Recognition)

const ERRORS = {
  'not-allowed': 'لم يُسمح باستخدام الميكروفون. فعّله لهذا الموقع من إعدادات المتصفح ثم أعد المحاولة.',
  'service-not-allowed': 'لم يُسمح باستخدام الميكروفون. فعّله لهذا الموقع من إعدادات المتصفح ثم أعد المحاولة.',
  'audio-capture': 'لم نجد ميكروفونًا يعمل على هذا الجهاز.',
  'no-speech': 'لم نسمع كلامًا. اضغط الزر وتحدّث بوضوح.',
  network: 'تعذّر الاتصال بخدمة تحويل الكلام إلى نص. تحقّق من الإنترنت ثم أعد المحاولة.',
}

/** `onText(final)` receives each finished phrase. `interim` is the phrase still being heard. */
export function useDictation(onText) {
  const [listening, setListening] = useState(false)
  const [interim, setInterim] = useState('')
  const [error, setError] = useState(null)
  const rec = useRef(null)
  const onTextRef = useRef(onText)
  useEffect(() => { onTextRef.current = onText }, [onText])

  const stop = useCallback(() => { rec.current?.stop() }, [])

  const start = useCallback(() => {
    if (!Recognition || rec.current) return
    const r = new Recognition()
    r.lang = 'ar-SA'
    r.continuous = true
    r.interimResults = true
    r.onresult = (e) => {
      let live = ''
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const said = e.results[i][0].transcript
        if (e.results[i].isFinal) onTextRef.current(said.trim())
        else live += said
      }
      setInterim(live)
    }
    r.onerror = (e) => { if (e.error !== 'aborted') setError(ERRORS[e.error] ?? 'تعذّر تحويل الكلام إلى نص. أعد المحاولة.') }
    r.onend = () => { rec.current = null; setListening(false); setInterim('') }
    rec.current = r
    setError(null)
    setListening(true)
    try { r.start() } catch { rec.current = null; setListening(false) }
  }, [])

  useEffect(() => () => rec.current?.abort(), []) // stop the microphone when leaving the screen
  return { listening, interim, error, start, stop }
}
