import React, { useState, useRef } from 'react'
import {
  ArrowUp,
  Paperclip,
  Mic,
  MicOff,
  Bot,
  Warehouse,
  Boxes,
  Truck,
  ScanBarcode,
  AlertTriangle,
  ShieldCheck,
  ClipboardList,
  CheckCircle,
  X,
  Layers
} from 'lucide-react'
import {
  CHAT_MAX_CHARS,
  READ_LIMIT_BYTES,
  TEXT_FILE_ACCEPT,
  charCounterLabel,
  composeQuery,
  formatFileSize,
  isReadableTextFile,
  omittedFileNotice,
  unsupportedFileNotice
} from '../../chat/attachments'

// Reads the start of a text file (enough for one message); `truncated` when the file is longer
const readTextFile = (file) =>
  new Promise((resolve, reject) => {
    const truncated = file.size > READ_LIMIT_BYTES
    const reader = new FileReader()
    reader.onload = () => resolve({ content: String(reader.result || ''), truncated })
    reader.onerror = () => reject(reader.error)
    reader.readAsText(truncated ? file.slice(0, READ_LIMIT_BYTES) : file)
  })

export default function PromptCapsule({
  onSend,
  isLoading,
  currentUser,
  selectedAgent,
  setSelectedAgent,
  onOpenOperationalModal
}) {
  const [inputVal, setInputVal] = useState('')
  const [isRecording, setIsRecording] = useState(false)
  const [attachments, setAttachments] = useState([]) // readable text files: { name, size, content, truncated }
  const [fileNotices, setFileNotices] = useState([]) // files that could not be attached / sent
  const [workMode, setWorkMode] = useState('floor') // 'floor' | 'cowork'
  const fileInputRef = useRef(null)

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit()
    }
  }

  const handleSubmit = (overrideText) => {
    const text = (overrideText !== undefined ? overrideText : inputVal).slice(0, CHAT_MAX_CHARS)
    if (!text.trim() && attachments.length === 0) return
    if (isLoading) return

    // Files that no longer fit next to the typed text are named, not silently dropped
    const { omitted } = composeQuery(text.trim(), attachments)
    setFileNotices(omitted.map((name) => omittedFileNotice(name)))

    onSend({
      text: text.trim(),
      attachments,
      mode: workMode,
      targetAgent: selectedAgent
    })

    setInputVal('')
    setAttachments([])
  }

  const handleFileUpload = async (e) => {
    const input = e.target
    const files = Array.from(input.files || [])
    if (!files.length) return
    const notices = []
    const added = []
    for (const file of files) {
      if (!isReadableTextFile(file)) {
        notices.push(unsupportedFileNotice(file.name))
        continue
      }
      try {
        const { content, truncated } = await readTextFile(file)
        if (!content.trim()) {
          notices.push(`${file.name} is empty, so it was not attached.`)
          continue
        }
        added.push({ name: file.name, size: formatFileSize(file.size), content, truncated })
      } catch {
        notices.push(`${file.name} could not be read.`)
      }
    }
    input.value = '' // the same file can be picked again
    setFileNotices(notices)
    if (added.length) setAttachments((prev) => [...prev, ...added])
  }

  const removeAttachment = (idx) => {
    setAttachments(attachments.filter((_, i) => i !== idx))
  }

  const recognitionRef = useRef(null)

  const toggleVoice = () => {
    if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
      alert('Voice dictation is supported in Google Chrome, Microsoft Edge, and Chromium browsers.')
      return
    }
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!isRecording) {
      try {
        const recognition = new SpeechRecognition()
        recognition.continuous = true
        recognition.interimResults = true
        recognition.lang = 'en-US'

        recognition.onstart = () => {
          setIsRecording(true)
        }

        recognition.onresult = (event) => {
          let currentSessionText = ''
          for (let i = 0; i < event.results.length; i++) {
            currentSessionText += event.results[i][0].transcript
          }
          setInputVal(currentSessionText.slice(0, CHAT_MAX_CHARS))
        }

        recognition.onerror = (e) => {
          console.warn('Speech recognition error:', e.error)
          setIsRecording(false)
        }

        recognition.onend = () => {
          setIsRecording(false)
        }

        recognitionRef.current = recognition
        recognition.start()
      } catch (e) {
        console.error('Speech recognition start error:', e)
        setIsRecording(false)
      }
    } else {
      if (recognitionRef.current) {
        recognitionRef.current.stop()
      }
      setIsRecording(false)
    }
  }

  const quickActionChips = [
    {
      id: 'sku',
      icon: ScanBarcode,
      label: 'Find SKU-4521',
      prompt: 'Where is SKU-4521 located and how many units in stock?'
    },
    {
      id: 'order',
      icon: Truck,
      label: 'Track Order #4521',
      prompt: "What is the status and carrier tracking of order #4521?"
    },
    {
      id: 'sop',
      icon: AlertTriangle,
      label: 'Hazmat & Spill SOP',
      prompt: 'What is the standard operating procedure for hazardous battery leaks and warehouse water damage?'
    }
  ]

  return (
    <div className="claude-prompt-capsule-container">
      {/* Live Voice Dictation Status Banner */}
      {isRecording && (
        <div className="voice-listening-banner">
          <span className="voice-pulse-ring" />
          <span className="voice-status-text">🎙️ Listening to operator... Speak warehouse query clearly</span>
          <div className="voice-bars">
            <span />
            <span />
            <span />
            <span />
            <span />
          </div>
        </div>
      )}

      <div className={`claude-capsule-box ${inputVal ? 'has-content' : ''}`}>
        <div className="capsule-glow-rim" />
        {/* Attachments preview row */}
        {attachments.length > 0 && (
          <div className="attachments-preview-strip">
            {attachments.map((att, i) => (
              <div key={i} className="attachment-chip">
                <Paperclip size={12} className="text-amber" />
                <span className="attachment-name">{att.name}</span>
                <span className="attachment-size">({att.size})</span>
                <button
                  onClick={() => removeAttachment(i)}
                  className="attachment-remove-btn"
                >
                  <X size={12} />
                </button>
              </div>
            ))}
          </div>
        )}

        {/* Textarea */}
        <textarea
          value={inputVal}
          onChange={(e) => setInputVal(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask warehouse coordinator (e.g., 'Where is SKU-4521?' or 'Track order #4521')..."
          rows={inputVal.split('\n').length > 1 ? Math.min(inputVal.split('\n').length, 5) : 2}
          disabled={isLoading}
          maxLength={CHAT_MAX_CHARS}
          className="capsule-textarea"
        />

        {/* Capsule Bottom Controls */}
        <div className="capsule-controls-row">
          <div className="controls-left">
            {/* Attachment Button */}
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleFileUpload}
              multiple
              accept={TEXT_FILE_ACCEPT}
              className="hidden-file-input"
            />
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              className="capsule-icon-btn"
              title="Attach a text file (.txt, .csv, .eml, .md)"
              aria-label="Attach a text file"
            >
              <Paperclip size={16} />
            </button>

            {/* Voice Dictation Button */}
            <button
              type="button"
              onClick={toggleVoice}
              className={`capsule-icon-btn ${isRecording ? 'recording-active' : ''}`}
              title={isRecording ? 'Listening...' : 'Voice dictation'}
            >
              {isRecording ? <MicOff size={16} className="text-coral pulse" /> : <Mic size={16} />}
            </button>
          </div>

          <div className="controls-right">
            {/* Character counter near the limit */}
            {charCounterLabel(inputVal.length) && (
              <span
                className={`capsule-char-counter ${inputVal.length >= CHAT_MAX_CHARS ? 'at-limit' : ''}`}
                aria-live="polite"
              >
                {charCounterLabel(inputVal.length)}
              </span>
            )}

            {/* Send Button */}
            <button
              type="button"
              onClick={() => handleSubmit()}
              disabled={isLoading || (!inputVal.trim() && attachments.length === 0)}
              className="capsule-send-btn"
              title="Send query (Enter)"
            >
              <ArrowUp size={16} />
            </button>
          </div>
        </div>
      </div>

      {/* Files that could not be attached or sent */}
      {fileNotices.length > 0 && (
        <div className="capsule-file-notice" role="status">
          <div className="capsule-file-notice-lines">
            {fileNotices.map((notice, i) => (
              <span key={i}>{notice}</span>
            ))}
          </div>
          <button
            type="button"
            onClick={() => setFileNotices([])}
            className="attachment-remove-btn"
            aria-label="Dismiss notice"
          >
            <X size={12} />
          </button>
        </div>
      )}

      {/* Clean & Independent Suggestion Chips */}
      <div className="prompt-quick-chips-row">
        {quickActionChips.map((chip) => {
          const Icon = chip.icon
          return (
            <button
              key={chip.id}
              onClick={() => handleSubmit(chip.prompt)}
              className="quick-chip-btn"
              disabled={isLoading}
            >
              <Icon size={13} className="chip-icon text-amber" />
              <span>{chip.label}</span>
            </button>
          )
        })}
      </div>
    </div>
  )
}
