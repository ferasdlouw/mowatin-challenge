// Copyright (c) 2026 Athar Al-Madinah Team (فريق أثر المدينة). All rights reserved.
// Mowatin (مُوطِّن) — Proprietary. Source-available for evaluation only. See LICENSE.
//
// Read a translation aloud with the browser's own speech engine (no server, no key).
// One utterance at a time: starting a new one stops the previous.
import { useCallback, useEffect, useState } from 'react'

export const canSpeak = typeof window !== 'undefined' && 'speechSynthesis' in window

const LOCALE = { en: 'en-US', fr: 'fr-FR' }

// Ornate Qur'an brackets and translator's square brackets are read out as symbols by some voices.
const clean = (text) => text.replace(/[﴿﴾[\]]/g, '').replace(/https?:\/\/\S+/g, '').replace(/\s+/g, ' ').trim()

function pickVoice(locale) {
  const voices = window.speechSynthesis.getVoices()
  const prefix = locale.slice(0, 2)
  return voices.find((v) => v.lang === locale) ?? voices.find((v) => v.lang?.startsWith(prefix)) ?? null
}

/** `speaking` is the id being read, or null. `toggle(id, text, lang)` starts it, or stops it if it is the one playing. */
export function useSpeaker() {
  const [speaking, setSpeaking] = useState(null)

  const stop = useCallback(() => {
    if (canSpeak) window.speechSynthesis.cancel()
    setSpeaking(null)
  }, [])

  const toggle = useCallback((id, text, lang) => {
    if (!canSpeak) return
    window.speechSynthesis.cancel()
    if (speaking === id) { setSpeaking(null); return }
    const u = new SpeechSynthesisUtterance(clean(text))
    u.lang = LOCALE[lang] ?? 'en-US'
    const voice = pickVoice(u.lang)
    if (voice) u.voice = voice
    u.rate = 0.95
    u.onend = u.onerror = () => setSpeaking((cur) => (cur === id ? null : cur))
    setSpeaking(id)
    window.speechSynthesis.speak(u)
  }, [speaking])

  useEffect(() => stop, [stop]) // stop reading when the results go away
  return { speaking, toggle, stop }
}
