import React, { useEffect, useId, useState, useRef } from 'react'
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
  Layers,
  Sparkles,
  ChevronDown,
  Check
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
import { suggestionKeyAction, suggestionOptionId } from '../../chat/inventorySuggestions'
import { useInventorySuggestions } from '../../chat/useInventorySuggestions'
import InventorySuggestions from './InventorySuggestions'

// Reads the start of a text file (enough for one message); `truncated` when the file is longer
const readTextFile = (file) =>
  new Promise((resolve, reject) => {
    const truncated = file.size > READ_LIMIT_BYTES
    const reader = new FileReader()
    reader.onload = () => resolve({ content: String(reader.result || ''), truncated })
    reader.onerror = () => reject(reader.error)
    reader.readAsText(truncated ? file.slice(0, READ_LIMIT_BYTES) : file)
  })

const SPECIALISTS = [
  { id: 'inventory_agent', label: 'Inventory Agent', icon: Boxes },
  { id: 'fulfillment_agent', label: 'Fulfillment Agent', icon: Truck },
  { id: 'knowledge_agent', label: 'Knowledge Agent', icon: ClipboardList }
]

export default function PromptCapsule({
  onSend,
  isLoading,
  currentUser,
  selectedAgent,
  setSelectedAgent,
  onOpenOperationalModal,
  authToken
}) {
  const [inputVal, setInputVal] = useState('')
  const [isRecording, setIsRecording] = useState(false)
  const [attachments, setAttachments] = useState([]) // readable text files: { name, size, content, truncated }
  const [fileNotices, setFileNotices] = useState([]) // files that could not be attached / sent
  const [workMode, setWorkMode] = useState('floor') // 'floor' | 'cowork'
  const [isDropdownOpen, setIsDropdownOpen] = useState(false)
  const fileInputRef = useRef(null)
  const dropdownRef = useRef(null)

  const plan = currentUser?.plan || 'starter'

  // Default specialist for professional plan if none selected
  const activeSpecialist = (plan === 'professional' && (!selectedAgent || selectedAgent === 'auto'))
    ? 'inventory_agent'
    : selectedAgent || 'inventory_agent'

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target)) {
        setIsDropdownOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const textareaRef = useRef(null)
  const suggestListId = `inv-suggest-${useId().replace(/:/g, '')}`
  // Inventory suggestions only while the message can reach the Inventory Agent under the user's plan
  const reachesInventory = plan !== 'professional' || activeSpecialist === 'inventory_agent'
  const suggest = useInventorySuggestions(inputVal, authToken, {
    enabled: reachesInventory && !isLoading && !isRecording && attachments.length === 0
  })

  // A suggestion only fills the input; the user still decides to send it
  const pickSuggestion = (item) => {
    setInputVal(item.text)
    suggest.close(item.text)
    textareaRef.current?.focus()
  }

  const handleKeyDown = (e) => {
    const action = suggestionKeyAction(e.key, { open: suggest.open, index: suggest.index, shiftKey: e.shiftKey })
    if (action) {
      e.preventDefault()
      if (action === 'next') suggest.move(1)
      else if (action === 'prev') suggest.move(-1)
      else if (action === 'close') suggest.close()
      else if (action === 'select') pickSuggestion(suggest.items[suggest.index])
      return
    }
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

    // Starter: Inventory only. Professional: the chosen specialist. Enterprise: the Coordinator decides.
    const effectiveAgent = plan === 'starter'
      ? 'inventory_agent'
      : plan === 'professional'
        ? activeSpecialist
        : 'auto'

    onSend({
      text: text.trim(),
      attachments,
      mode: workMode,
      targetAgent: effectiveAgent
    })

    setInputVal('')
    setAttachments([])
    suggest.close('')
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

  // Dynamic Suggestion Chips based on Plan & Active Specialist
  const getQuickActionChips = () => {
    if (plan === 'starter' || (plan === 'professional' && activeSpecialist === 'inventory_agent')) {
      return [
        {
          id: 'sku-loc',
          icon: ScanBarcode,
          label: 'Find SKU-4521',
          prompt: 'Where is SKU-4521 located and how many units in stock?'
        },
        {
          id: 'sku-stock',
          icon: Boxes,
          label: 'Check SKU-3300',
          prompt: 'Check stock availability for SKU-3300.'
        },
        {
          id: 'reorder',
          icon: Warehouse,
          label: 'Reorder Levels',
          prompt: 'Which warehouse inventory items are below safety stock threshold?'
        }
      ]
    }

    if (plan === 'professional' && activeSpecialist === 'fulfillment_agent') {
      return [
        {
          id: 'ord-status',
          icon: Truck,
          label: 'Status of ORD-1001',
          prompt: 'What is the status of ORD-1001?'
        },
        {
          id: 'ord-delay',
          icon: AlertTriangle,
          label: 'Delay on ORD-1002',
          prompt: 'Why is ORD-1002 delayed?'
        },
        {
          id: 'ord-ship',
          icon: ScanBarcode,
          label: 'Consignment Shipping',
          prompt: 'Has order ORD-1001 shipped and what is the assigned carrier?'
        }
      ]
    }

    if (plan === 'professional' && activeSpecialist === 'knowledge_agent') {
      return [
        {
          id: 'sop-storage',
          icon: ClipboardList,
          label: 'SOP-STG-002 Storage',
          prompt: 'What does SOP-STG-002 explain regarding warehouse storage guidelines?'
        },
        {
          id: 'sop-hazmat',
          icon: AlertTriangle,
          label: 'Hazmat & Spill SOP',
          prompt: 'What is the standard operating procedure for hazardous battery leaks and warehouse water damage?'
        },
        {
          id: 'sop-return',
          icon: CheckCircle,
          label: 'Return Logistics SOP',
          prompt: 'What is the standard procedure for processing customer returns?'
        }
      ]
    }

    // Enterprise: Full multi-agent coordinator experience
    return [
      {
        id: 'sku',
        icon: ScanBarcode,
        label: 'Find SKU-4521',
        prompt: 'Where is SKU-4521 located and how many units in stock?'
      },
      {
        id: 'order',
        icon: Truck,
        label: 'Track Order ORD-1001',
        prompt: 'What is the status and carrier tracking of order ORD-1001?'
      },
      {
        id: 'sop',
        icon: AlertTriangle,
        label: 'Hazmat & Spill SOP',
        prompt: 'What is the standard operating procedure for hazardous battery leaks and warehouse water damage?'
      }
    ]
  }

  // Dynamic Placeholder
  const getPlaceholder = () => {
    if (plan === 'starter') {
      return "Ask Inventory Agent (e.g., 'Check stock availability for SKU-3300' or 'Where is SKU-4521?')..."
    }
    if (plan === 'professional') {
      if (activeSpecialist === 'inventory_agent') {
        return "Ask Inventory Agent (e.g., 'Check stock availability for SKU-3300' or 'Where is SKU-4521?')..."
      }
      if (activeSpecialist === 'fulfillment_agent') {
        return "Ask Fulfillment Agent (e.g., 'What is the status of ORD-1001?' or 'Why is ORD-1002 delayed?')..."
      }
      if (activeSpecialist === 'knowledge_agent') {
        return "Ask Knowledge Agent (e.g., 'What does SOP-002 explain?' or 'Hazmat spill procedure')..."
      }
    }
    return "Ask warehouse coordinator (e.g., 'Where is SKU-4521?' or 'Track order ORD-1001')..."
  }

  const quickActionChips = getQuickActionChips()

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

      {/* Specialist Selector Dropdown for Professional Tier */}
      {plan === 'professional' && (
        <div className="professional-dropdown-bar" ref={dropdownRef}>
          <span className="professional-dropdown-label">Choose your AI Specialist:</span>
          
          <div className="specialist-dropdown-wrapper">
            <button
              type="button"
              id="specialist-dropdown-trigger"
              className={`specialist-dropdown-trigger ${isDropdownOpen ? 'open' : ''}`}
              onClick={() => setIsDropdownOpen(!isDropdownOpen)}
              aria-haspopup="listbox"
              aria-expanded={isDropdownOpen}
            >
              <div className="selected-specialist-info">
                {(() => {
                  const currentSpec = SPECIALISTS.find((s) => s.id === activeSpecialist) || SPECIALISTS[0]
                  const SelectedIcon = currentSpec.icon
                  return (
                    <>
                      <SelectedIcon size={14} className="selected-spec-icon" />
                      <span className="selected-spec-text">{currentSpec.label}</span>
                    </>
                  )
                })()}
              </div>
              <ChevronDown size={14} className={`dropdown-chevron ${isDropdownOpen ? 'rotated' : ''}`} />
            </button>

            {isDropdownOpen && (
              <div className="specialist-dropdown-menu" role="listbox">
                {SPECIALISTS.map((spec) => {
                  const Icon = spec.icon
                  const isSelected = activeSpecialist === spec.id
                  return (
                    <button
                      key={spec.id}
                      type="button"
                      role="option"
                      aria-selected={isSelected}
                      className={`specialist-dropdown-option ${isSelected ? 'selected' : ''}`}
                      onClick={() => {
                        setSelectedAgent(spec.id)
                        setIsDropdownOpen(false)
                      }}
                    >
                      <Icon size={14} className="option-spec-icon" />
                      <span className="option-spec-label">{spec.label}</span>
                      {isSelected && <Check size={13} className="option-check-icon" />}
                    </button>
                  )
                })}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Active Agent Banner for Starter Tier */}
      {plan === 'starter' && (
        <div className="starter-agent-banner">
          <div className="starter-badge-wrap">
            <Boxes size={13} className="text-amber" />
            <span>Active Specialist: <strong>Inventory Agent</strong></span>
          </div>
          <span className="starter-tier-badge">Starter Plan (Single Specialist)</span>
        </div>
      )}

      {/* Active Agent Banner for Enterprise Tier */}
      {plan === 'enterprise' && (
        <div className="enterprise-agent-banner">
          <div className="enterprise-badge-wrap">
            <Sparkles size={13} className="text-emerald" />
            <span>Coordinator Agent: <strong>Autonomous Intelligent Routing & Multi-Agent Collaboration Active</strong></span>
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
          ref={textareaRef}
          value={inputVal}
          onChange={(e) => setInputVal(e.target.value)}
          onKeyDown={handleKeyDown}
          onBlur={() => suggest.open && suggest.close()}
          role="combobox"
          aria-label="Message the warehouse coordinator"
          aria-autocomplete="list"
          aria-expanded={suggest.open}
          aria-controls={suggestListId}
          aria-activedescendant={suggest.index >= 0 ? suggestionOptionId(suggestListId, suggest.index) : undefined}
          placeholder={getPlaceholder()}
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

      {/* Inventory question suggestions, directly below the input */}
      <InventorySuggestions
        id={suggestListId}
        items={suggest.items}
        activeIndex={suggest.index}
        onSelect={pickSuggestion}
        onHighlight={suggest.setIndex}
      />

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
      {!suggest.open && <div className="prompt-quick-chips-row">
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
      </div>}
    </div>
  )
}
