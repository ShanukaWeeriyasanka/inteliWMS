import React, { useState, useEffect, useRef } from 'react'
import {
  Mic,
  MicOff,
  X,
  Volume2,
  VolumeX,
  Sparkles,
  Bot,
  Warehouse,
  Boxes,
  Truck,
  BookOpen
} from 'lucide-react'
import { useSpeechRecognition } from '../../voice/useSpeechRecognition'
import { useSpeechSynthesis } from '../../voice/useSpeechSynthesis'
import './VoiceModeModal.css'

/**
 * ChatGPT Advanced Voice Mode Modal
 * Features:
 * - Fluid Cyber-Blue glowing animated Voice Orb with real-time audio reactivity
 * - Hands-free conversational loop (Speaks -> Listens -> Responds automatically)
 * - Barge-in interruption: user can interrupt agent speech at any time
 * - Live transcript feed with agent badges
 */
export default function VoiceModeModal({
  isOpen,
  onClose,
  onSendVoiceQuery,
  selectedAgent = 'coordinator',
  onSelectAgent
}) {
  const [voiceStatus, setVoiceStatus] = useState('listening') // 'listening' | 'thinking' | 'speaking' | 'muted'
  const [currentTranscript, setCurrentTranscript] = useState('')
  const [lastAgentReply, setLastAgentReply] = useState('')
  const [isMuted, setIsMuted] = useState(false)
  const [audioRepliesEnabled, setAudioRepliesEnabled] = useState(true)

  const { speak, stop: stopSpeech, isSpeaking } = useSpeechSynthesis()

  const handleSilenceDetected = async (finalQuery) => {
    if (!finalQuery || finalQuery.trim().length < 2) return
    if (voiceStatus === 'thinking' || voiceStatus === 'speaking') return

    // Stop listening while thinking
    stopListening()
    setVoiceStatus('thinking')
    setCurrentTranscript(finalQuery)

    try {
      // Dispatch query to the Coordinator Agent
      const response = await onSendVoiceQuery(finalQuery)
      const replyText = response?.content || response?.message || 'I processed your warehouse request.'
      setLastAgentReply(replyText)

      if (audioRepliesEnabled) {
        setVoiceStatus('speaking')
        speak(replyText, {
          onStart: () => setVoiceStatus('speaking'),
          onEnd: () => {
            setVoiceStatus('listening')
            if (!isMuted) startListening()
          },
          onError: () => {
            setVoiceStatus('listening')
            if (!isMuted) startListening()
          }
        })
      } else {
        setVoiceStatus('listening')
        if (!isMuted) startListening()
      }
    } catch (err) {
      console.warn('Voice query error:', err)
      setVoiceStatus('listening')
      if (!isMuted) startListening()
    }
  }

  const {
    isListening,
    startListening,
    stopListening,
    volumeLevel,
    clearTranscript
  } = useSpeechRecognition({
    onTranscriptChange: (text) => {
      setCurrentTranscript(text)
      // If user starts talking while assistant is speaking, interrupt assistant! (Barge-in)
      if (isSpeaking && text.length > 2) {
        stopSpeech()
        setVoiceStatus('listening')
      }
    },
    onSilenceDetected: handleSilenceDetected,
    silenceThresholdMs: 1500
  })

  // Start voice mode when modal opens
  useEffect(() => {
    if (isOpen) {
      setIsMuted(false)
      setCurrentTranscript('')
      setLastAgentReply('')
      setVoiceStatus('listening')
      startListening()
    } else {
      stopListening()
      stopSpeech()
    }
    return () => {
      stopListening()
      stopSpeech()
    }
  }, [isOpen])

  // Sync speaking state
  useEffect(() => {
    if (isSpeaking) {
      setVoiceStatus('speaking')
    } else if (voiceStatus === 'speaking' && !isSpeaking) {
      setVoiceStatus('listening')
    }
  }, [isSpeaking])

  const toggleMute = () => {
    if (isMuted) {
      setIsMuted(false)
      setVoiceStatus('listening')
      startListening()
    } else {
      setIsMuted(true)
      setVoiceStatus('muted')
      stopListening()
      stopSpeech()
    }
  }

  const handleInterrupt = () => {
    stopSpeech()
    setVoiceStatus('listening')
    if (!isMuted) startListening()
  }

  if (!isOpen) return null

  // Calculate dynamic scale & aura based on real volume or speaking rhythm
  const orbScale = voiceStatus === 'listening'
    ? 1 + Math.min(volumeLevel / 100, 0.45)
    : voiceStatus === 'speaking'
      ? 1.15
      : 1.0

  const agentIcons = {
    coordinator: Bot,
    inventory_agent: Boxes,
    fulfillment_agent: Truck,
    knowledge_agent: BookOpen
  }
  const AgentIcon = agentIcons[selectedAgent] || Bot

  return (
    <div className="voice-mode-overlay" role="dialog" aria-modal="true" aria-label="Voice Assistant Mode">
      {/* Background ambient lighting blur */}
      <div className={`voice-ambient-glow state-${voiceStatus}`} />

      {/* Top Header Controls */}
      <header className="voice-mode-header">
        <div className="voice-agent-pill">
          <AgentIcon size={16} className="text-cyan" />
          <span className="voice-agent-label">
            {selectedAgent === 'coordinator'
              ? 'Autonomous Coordinator'
              : selectedAgent === 'inventory_agent'
                ? 'Inventory Specialist'
                : selectedAgent === 'fulfillment_agent'
                  ? 'Fulfillment Specialist'
                  : 'Knowledge Specialist'}
          </span>
          <span className="voice-active-indicator" />
        </div>

        <button
          onClick={onClose}
          className="voice-close-icon-btn"
          title="Exit Voice Mode"
          aria-label="Exit Voice Mode"
        >
          <X size={20} />
        </button>
      </header>

      {/* Main Center Stage: ChatGPT-Style Animated Blue Glowing Voice Orb */}
      <main className="voice-mode-center-stage">
        {/* Real-time Captions Floating Above */}
        <div className="voice-captions-container">
          {voiceStatus === 'speaking' && lastAgentReply ? (
            <div className="voice-agent-reply-box animate-fade-in">
              <span className="voice-caption-role">IntelliWMS:</span>
              <p className="voice-caption-text">{lastAgentReply}</p>
            </div>
          ) : currentTranscript ? (
            <div className="voice-user-speech-box animate-fade-in">
              <span className="voice-caption-role">You:</span>
              <p className="voice-caption-text">{currentTranscript}</p>
            </div>
          ) : (
            <div className="voice-idle-prompt animate-fade-in">
              <Sparkles size={16} className="text-cyan animate-pulse" />
              <span>
                {voiceStatus === 'listening'
                  ? 'Listening... Speak naturally'
                  : voiceStatus === 'thinking'
                    ? 'Consulting warehouse agents...'
                    : voiceStatus === 'muted'
                      ? 'Microphone muted'
                      : 'Speaking response...'}
              </span>
            </div>
          )}
        </div>

        {/* The Animated 3D Cyber-Blue Orb */}
        <div
          className={`voice-orb-wrapper state-${voiceStatus}`}
          onClick={voiceStatus === 'speaking' ? handleInterrupt : undefined}
          title={voiceStatus === 'speaking' ? 'Tap to interrupt' : undefined}
          role="button"
          tabIndex={0}
        >
          {/* Outer Ripple Rings */}
          <div className="voice-orb-ripple ring-1" style={{ transform: `scale(${orbScale * 1.2})` }} />
          <div className="voice-orb-ripple ring-2" style={{ transform: `scale(${orbScale * 1.45})` }} />
          <div className="voice-orb-ripple ring-3" style={{ transform: `scale(${orbScale * 1.7})` }} />

          {/* Central Photorealistic 3D Glowing Sphere */}
          <div
            className="voice-orb-core"
            style={{ transform: `scale(${orbScale})` }}
          >
            <div className="voice-orb-specular" />
            <div className="voice-orb-inner-wave" />
          </div>
        </div>

        {/* Live Status Tag */}
        <div className="voice-status-badge">
          <span className={`status-dot dot-${voiceStatus}`} />
          <span className="status-label">
            {voiceStatus === 'listening'
              ? 'LIVE LISTENING'
              : voiceStatus === 'thinking'
                ? 'COGNITIVE DISPATCH'
                : voiceStatus === 'speaking'
                  ? 'SPEAKING (TAP TO INTERRUPT)'
                  : 'MUTED'}
          </span>
        </div>
      </main>

      {/* Bottom Control Bar */}
      <footer className="voice-mode-bottom-bar">
        {/* Toggle Audio Output (Speaker) */}
        <button
          onClick={() => {
            const next = !audioRepliesEnabled
            setAudioRepliesEnabled(next)
            if (!next) stopSpeech()
          }}
          className={`voice-control-btn ${!audioRepliesEnabled ? 'is-off' : ''}`}
          title={audioRepliesEnabled ? 'Mute AI voice output' : 'Enable AI voice output'}
        >
          {audioRepliesEnabled ? <Volume2 size={20} /> : <VolumeX size={20} />}
        </button>

        {/* Center Mic Mute / Unmute Button */}
        <button
          onClick={toggleMute}
          className={`voice-mic-main-btn ${isMuted ? 'muted' : 'active'}`}
          title={isMuted ? 'Unmute microphone' : 'Mute microphone'}
        >
          {isMuted ? <MicOff size={24} className="text-coral" /> : <Mic size={24} />}
        </button>

        {/* Quick Close / Exit Voice Mode Button (ChatGPT Blue Circle X) */}
        <button
          onClick={onClose}
          className="voice-close-circle-btn"
          title="End Voice Mode"
          aria-label="End Voice Mode"
        >
          <X size={22} />
        </button>
      </footer>
    </div>
  )
}
