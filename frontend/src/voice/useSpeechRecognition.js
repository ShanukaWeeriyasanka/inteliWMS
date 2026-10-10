import { useState, useEffect, useRef, useCallback } from 'react'
import { normalizeSpokenText } from './voiceNormalizer'

/**
 * ChatGPT-Grade Speech Recognition Hook
 * Continuous listening, real-time audio volume analyser,
 * logistics terminology booster, silence auto-send detection.
 */
export function useSpeechRecognition({
  onTranscriptChange,
  onFinalTranscript,
  onSilenceDetected,
  silenceThresholdMs = 1600,
  language = 'en-US'
} = {}) {
  const [isListening, setIsListening] = useState(false)
  const [transcript, setTranscript] = useState('')
  const [interimTranscript, setInterimTranscript] = useState('')
  const [volumeLevel, setVolumeLevel] = useState(0)
  const [hasMicPermission, setHasMicPermission] = useState(null)

  const recognitionRef = useRef(null)
  const silenceTimerRef = useRef(null)
  const audioContextRef = useRef(null)
  const analyserRef = useRef(null)
  const micStreamRef = useRef(null)
  const animFrameRef = useRef(null)
  const isExplicitStopRef = useRef(false)
  const accumulatedFinalRef = useRef('')

  const isSupported = typeof window !== 'undefined' &&
    ('SpeechRecognition' in window || 'webkitSpeechRecognition' in window)

  // Web Audio API: Live volume meter for the animated audio orb
  const startVolumeAnalyser = useCallback(async () => {
    try {
      if (!navigator.mediaDevices?.getUserMedia) return
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      micStreamRef.current = stream
      setHasMicPermission(true)

      const AudioContextClass = window.AudioContext || window.webkitAudioContext
      const ctx = new AudioContextClass()
      audioContextRef.current = ctx

      const analyser = ctx.createAnalyser()
      analyser.fftSize = 256
      analyser.smoothingTimeConstant = 0.5
      analyserRef.current = analyser

      const source = ctx.createMediaStreamSource(stream)
      source.connect(analyser)

      const dataArray = new Uint8Array(analyser.frequencyBinCount)

      const updateVolume = () => {
        if (!analyserRef.current) return
        analyserRef.current.getByteFrequencyData(dataArray)

        let sum = 0
        for (let i = 0; i < dataArray.length; i++) {
          sum += dataArray[i]
        }
        const avg = sum / dataArray.length
        // Scale 0-100 with sensitivity
        const normalized = Math.min(100, Math.round((avg / 128) * 100))
        setVolumeLevel(normalized)

        animFrameRef.current = requestAnimationFrame(updateVolume)
      }

      updateVolume()
    } catch (err) {
      console.warn('Microphone audio stream error:', err)
      setHasMicPermission(false)
    }
  }, [])

  const stopVolumeAnalyser = useCallback(() => {
    if (animFrameRef.current) {
      cancelAnimationFrame(animFrameRef.current)
      animFrameRef.current = null
    }
    if (micStreamRef.current) {
      micStreamRef.current.getTracks().forEach(track => track.stop())
      micStreamRef.current = null
    }
    if (audioContextRef.current && audioContextRef.current.state !== 'closed') {
      audioContextRef.current.close().catch(() => {})
      audioContextRef.current = null
    }
    setVolumeLevel(0)
  }, [])

  const resetSilenceTimer = useCallback(() => {
    if (silenceTimerRef.current) {
      clearTimeout(silenceTimerRef.current)
      silenceTimerRef.current = null
    }

    if (silenceThresholdMs && onSilenceDetected) {
      silenceTimerRef.current = setTimeout(() => {
        const fullCurrent = (accumulatedFinalRef.current + ' ' + interimTranscript).trim()
        if (fullCurrent.length > 2) {
          const normalized = normalizeSpokenText(fullCurrent)
          onSilenceDetected(normalized)
        }
      }, silenceThresholdMs)
    }
  }, [silenceThresholdMs, onSilenceDetected, interimTranscript])

  const stopListening = useCallback(() => {
    isExplicitStopRef.current = true
    if (silenceTimerRef.current) {
      clearTimeout(silenceTimerRef.current)
      silenceTimerRef.current = null
    }
    if (recognitionRef.current) {
      try {
        recognitionRef.current.stop()
      } catch (_) {}
    }
    stopVolumeAnalyser()
    setIsListening(false)
  }, [stopVolumeAnalyser])

  const startListening = useCallback(() => {
    if (!isSupported) {
      console.warn('SpeechRecognition API not available in this browser.')
      return
    }

    isExplicitStopRef.current = false
    accumulatedFinalRef.current = ''
    setTranscript('')
    setInterimTranscript('')

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
    const recognition = new SpeechRecognition()
    recognition.continuous = true
    recognition.interimResults = true
    recognition.maxAlternatives = 3
    recognition.lang = language

    recognition.onstart = () => {
      setIsListening(true)
      startVolumeAnalyser()
    }

    recognition.onresult = (event) => {
      let interim = ''
      let finalChunk = ''

      for (let i = event.resultIndex; i < event.results.length; i++) {
        const item = event.results[i]
        const bestAlt = item[0]?.transcript || ''
        if (item.isFinal) {
          finalChunk += bestAlt + ' '
        } else {
          interim += bestAlt
        }
      }

      if (finalChunk) {
        accumulatedFinalRef.current = (accumulatedFinalRef.current + ' ' + finalChunk).trim()
        const normalizedFinal = normalizeSpokenText(accumulatedFinalRef.current)
        setTranscript(normalizedFinal)
        if (onFinalTranscript) onFinalTranscript(normalizedFinal)
      }

      const normalizedInterim = normalizeSpokenText(interim)
      setInterimTranscript(normalizedInterim)

      const fullCombined = (accumulatedFinalRef.current + ' ' + interim).trim()
      const normalizedCombined = normalizeSpokenText(fullCombined)
      if (onTranscriptChange) onTranscriptChange(normalizedCombined)

      // Restart silence timer on each spoken utterance
      resetSilenceTimer()
    }

    recognition.onerror = (event) => {
      // Ignore routine aborts or temporary no-speech
      if (event.error === 'no-speech' || event.error === 'aborted') {
        return
      }
      console.warn('SpeechRecognition error:', event.error)
      if (event.error === 'not-allowed') {
        setHasMicPermission(false)
        stopListening()
      }
    }

    recognition.onend = () => {
      // Auto-reconnect if continuous session is active and not explicitly stopped
      if (!isExplicitStopRef.current && isListening) {
        try {
          recognition.start()
          return
        } catch (_) {}
      }
      setIsListening(false)
      stopVolumeAnalyser()
    }

    recognitionRef.current = recognition
    try {
      recognition.start()
    } catch (e) {
      console.warn('Recognition start exception:', e)
    }
  }, [isSupported, language, startVolumeAnalyser, stopVolumeAnalyser, onTranscriptChange, onFinalTranscript, resetSilenceTimer, isListening, stopListening])

  useEffect(() => {
    return () => {
      stopListening()
    }
  }, [stopListening])

  return {
    isSupported,
    isListening,
    startListening,
    stopListening,
    transcript,
    interimTranscript,
    volumeLevel,
    hasMicPermission,
    clearTranscript: () => {
      accumulatedFinalRef.current = ''
      setTranscript('')
      setInterimTranscript('')
    }
  }
}
