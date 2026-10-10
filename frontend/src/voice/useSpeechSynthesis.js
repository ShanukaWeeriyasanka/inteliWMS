import { useState, useEffect, useRef, useCallback } from 'react'

/**
 * Strips raw markdown, code blocks, tables, and special syntax
 * so the synthetic voice sounds natural and conversational.
 */
export function cleanTextForSpeech(raw) {
  if (!raw || typeof raw !== 'string') return ''

  let text = raw
    // Remove fenced code blocks completely or replace with summary
    .replace(/```[\s\S]*?```/g, '')
    // Remove inline code backticks
    .replace(/`([^`]+)`/g, '$1')
    // Remove markdown table lines
    .replace(/^\|.*\|$/gm, '')
    .replace(/^[-:| ]+$/gm, '')
    // Remove markdown images and links: [Text](url) -> Text
    .replace(/!\[.*?\]\(.*?\)/g, '')
    .replace(/\[([^\]]+)\]\(.*?\)/g, '$1')
    // Remove bold, italics, strikethrough
    .replace(/(\*\*|__)(.*?)\1/g, '$2')
    .replace(/(\*|_)(.*?)\1/g, '$2')
    .replace(/~~(.*?)~~/g, '$1')
    // Remove blockquotes and headers
    .replace(/^>+\s*/gm, '')
    .replace(/^#{1,6}\s+/gm, '')
    // Clean bullet points
    .replace(/^[\*\-\+]\s+/gm, '')
    .replace(/^\d+\.\s+/gm, '')
    // Remove multiple newlines and spaces
    .replace(/\n+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()

  return text
}

/**
 * ChatGPT-Grade Speech Synthesis Hook
 * Natural human-like voice selection, markdown filtering, interrupt handling.
 */
export function useSpeechSynthesis() {
  const [isSpeaking, setIsSpeaking] = useState(false)
  const [voices, setVoices] = useState([])
  const [selectedVoice, setSelectedVoice] = useState(null)
  const utteranceRef = useRef(null)
  const keepAliveIntervalRef = useRef(null)

  const isSupported = typeof window !== 'undefined' && 'speechSynthesis' in window

  // Load and rank voices to pick the most natural English voice
  const updateVoices = useCallback(() => {
    if (!isSupported) return
    const available = window.speechSynthesis.getVoices()
    if (!available || available.length === 0) return

    setVoices(available)

    // Preferred natural conversational voices in order
    const preferredNames = [
      'Google US English',
      'Microsoft Jenny Online (Natural)',
      'Microsoft Guy Online (Natural)',
      'Microsoft Aria Online (Natural)',
      'Samantha',
      'Karen',
      'Daniel',
      'Alex',
      'Google UK English Female',
      'Microsoft Zira',
      'Microsoft David'
    ]

    let bestVoice = null
    for (const name of preferredNames) {
      const match = available.find(v => v.name.includes(name) || v.voiceURI.includes(name))
      if (match) {
        bestVoice = match
        break
      }
    }

    if (!bestVoice) {
      // Find any high-quality English voice
      bestVoice = available.find(v => v.lang && v.lang.startsWith('en')) || available[0]
    }

    setSelectedVoice(bestVoice)
  }, [isSupported])

  useEffect(() => {
    if (!isSupported) return
    updateVoices()
    if (window.speechSynthesis.onvoiceschanged !== undefined) {
      window.speechSynthesis.onvoiceschanged = updateVoices
    }
    return () => {
      if (window.speechSynthesis) {
        window.speechSynthesis.cancel()
      }
      if (keepAliveIntervalRef.current) {
        clearInterval(keepAliveIntervalRef.current)
      }
    }
  }, [isSupported, updateVoices])

  const stop = useCallback(() => {
    if (!isSupported) return
    if (keepAliveIntervalRef.current) {
      clearInterval(keepAliveIntervalRef.current)
      keepAliveIntervalRef.current = null
    }
    window.speechSynthesis.cancel()
    setIsSpeaking(false)
  }, [isSupported])

  const speak = useCallback((rawText, { onStart, onEnd, onError } = {}) => {
    if (!isSupported) {
      console.warn('Speech synthesis not supported in this browser.')
      return
    }

    // Stop any ongoing speech
    stop()

    const clean = cleanTextForSpeech(rawText)
    if (!clean) {
      if (onEnd) onEnd()
      return
    }

    const utterance = new SpeechSynthesisUtterance(clean)
    if (selectedVoice) {
      utterance.voice = selectedVoice
    }
    utterance.lang = selectedVoice?.lang || 'en-US'
    utterance.rate = 1.05  // Crisp, modern conversational pace
    utterance.pitch = 1.0

    utterance.onstart = () => {
      setIsSpeaking(true)
      if (onStart) onStart()

      // Chrome garbage collection keepalive bug fix
      if (keepAliveIntervalRef.current) clearInterval(keepAliveIntervalRef.current)
      keepAliveIntervalRef.current = setInterval(() => {
        if (!window.speechSynthesis.speaking) {
          clearInterval(keepAliveIntervalRef.current)
        } else {
          window.speechSynthesis.pause()
          window.speechSynthesis.resume()
        }
      }, 10000)
    }

    utterance.onend = () => {
      setIsSpeaking(false)
      if (keepAliveIntervalRef.current) {
        clearInterval(keepAliveIntervalRef.current)
        keepAliveIntervalRef.current = null
      }
      if (onEnd) onEnd()
    }

    utterance.onerror = (err) => {
      // Don't warn if manually canceled
      if (err.error !== 'canceled' && err.error !== 'interrupted') {
        console.warn('Speech synthesis error:', err)
      }
      setIsSpeaking(false)
      if (keepAliveIntervalRef.current) {
        clearInterval(keepAliveIntervalRef.current)
        keepAliveIntervalRef.current = null
      }
      if (onError) onError(err)
    }

    utteranceRef.current = utterance
    window.speechSynthesis.speak(utterance)
  }, [isSupported, selectedVoice, stop])

  return {
    isSupported,
    isSpeaking,
    speak,
    stop,
    voices,
    selectedVoice,
    setSelectedVoice
  }
}
