import React, { useState } from 'react'
import {
  Warehouse,
  Boxes,
  Truck,
  ScanBarcode,
  Bot,
  Copy,
  Check,
  ExternalLink,
  ShieldAlert,
  ShieldCheck,
  ThumbsUp,
  ThumbsDown,
  Paperclip,
  Activity,
  Map as MapIcon,
  Volume2,
  VolumeX
} from 'lucide-react'
import MarkdownText from './MarkdownText'
import { agentLabel, isFulfillmentMessage } from '../../chat/messageMapping'
import { parseFulfillmentContent } from '../../utils/fulfillmentParser'
import { useSpeechSynthesis } from '../../voice/useSpeechSynthesis'
import './FulfillmentAction.css'

export default function ChatMessage({
  message,
  onInspectOrder,
  onShowOnMap,
  onOpenFulfillmentDashboard,
  onOpenPricingModal,
  onSwitchSpecialist
}) {
  const [copied, setCopied] = useState(false)
  const isUser = message.role === 'user'

  const { speak, stop: stopSpeech, isSpeaking } = useSpeechSynthesis()
  const [isPlayingThis, setIsPlayingThis] = useState(false)

  const toggleSpeak = () => {
    if (isPlayingThis) {
      stopSpeech()
      setIsPlayingThis(false)
    } else {
      setIsPlayingThis(true)
      speak(message.content, {
        onEnd: () => setIsPlayingThis(false),
        onError: () => setIsPlayingThis(false)
      })
    }
  }

  const copyContent = () => {
    navigator.clipboard.writeText(message.content || '')
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  // Parse structured details if present
  const meta = message.metadata || {}
  const routing = message.routing || meta.routing || {}
  const agentTarget = routing.target_agent || meta.target_agent || 'coordinator'
  const isBlocked = message.status === 'blocked' || routing.status === 'blocked'
  const isRestricted = message.status === 'restricted' || routing.status === 'restricted' || meta.error_code === 'PLAN_RESTRICTED' || message.error_code === 'PLAN_RESTRICTED'
  const isMismatch = message.status === 'mismatch' || routing.status === 'mismatch' || meta.error_code === 'SPECIALIST_MISMATCH' || message.error_code === 'SPECIALIST_MISMATCH'
  const suggestedAgent = message.suggested_agent || meta.suggested_agent || routing.classified_agent
  const isFulfillment = !isBlocked && !isRestricted && !isMismatch && message.status !== 'error' && isFulfillmentMessage(message)
  const fulfillment = isFulfillment
    ? parseFulfillmentContent(message.content, message.fulfillment_details || meta.fulfillment_details, routing) : null

  return (
    <div className={`chat-message-row ${isUser ? 'user-row' : 'assistant-row'}`}>
      {/* Avatar */}
      <div className="message-avatar-container">
        {isUser ? (
          <div className="user-msg-avatar">
            {message.senderName?.[0]?.toUpperCase() || 'U'}
          </div>
        ) : (
          <div className="assistant-msg-avatar warehouse-avatar-glow">
            <img src="/intelliwms_logo.png" alt="IntelliWMS" className="assistant-logo-icon" />
          </div>
        )}
      </div>

      {/* Message Content Bubble */}
      <div className="message-bubble-wrapper">
        {/* Header line for Assistant */}
        {!isUser && (
          <div className="assistant-header-meta">
            <div className="assistant-brand-tag">
              <Warehouse size={13} className="text-amber" />
              <span className="assistant-name">IntelliWMS Coordinator</span>
            </div>
            {!isRestricted && !isBlocked && !isMismatch && agentTarget && agentTarget !== 'coordinator' && (
              <span className="agent-route-tag">
                <Bot size={11} />
                <span>via {agentLabel(agentTarget)} AGENT</span>
              </span>
            )}
            {!isRestricted && !isBlocked && !isMismatch && routing.confidence && (
              <span className="confidence-tag">
                {(routing.confidence * 100).toFixed(0)}% match
              </span>
            )}
            {routing.latency_ms && (
              <span className="latency-tag">{routing.latency_ms}ms</span>
            )}
          </div>
        )}

        <div className={`message-bubble ${isUser ? 'user-bubble' : 'assistant-bubble'} ${isBlocked ? 'blocked-bubble' : ''} ${isRestricted ? 'restricted-bubble' : ''}`}>
          {/* If security blocked */}
          {isBlocked && (
            <div className="security-block-notice">
              <div className="security-notice-title">
                <ShieldAlert size={16} className="text-coral" />
                <strong>Responsible AI Shield Activated</strong>
              </div>
              <p className="security-notice-desc">
                {message.content || routing.message || 'Potential prompt injection or privileged data extraction detected and neutralized.'}
              </p>
              {routing.rule && (
                <div className="security-rule-tag">
                  Security Rule: <code>{routing.rule}</code>
                </div>
              )}
            </div>
          )}

          {/* If Subscription Restricted (Starter Plan) */}
          {isRestricted && (
            <div className="plan-restriction-notice">
              <div className="restriction-title-row">
                <ShieldCheck size={16} className="text-amber" />
                <strong>Subscription Plan Restriction</strong>
              </div>
              <p className="restriction-text">
                {message.content || message.message}
              </p>
              {onOpenPricingModal && (
                <div className="restriction-cta-row">
                  <button
                    type="button"
                    className="btn-view-plans-cta"
                    onClick={onOpenPricingModal}
                  >
                    <span>View Subscription Plans</span>
                    <ExternalLink size={13} />
                  </button>
                </div>
              )}
            </div>
          )}

          {/* If Specialist Mismatch (Professional Plan) */}
          {isMismatch && (
            <div className="specialist-mismatch-notice">
              <div className="mismatch-title-row">
                <Bot size={16} className="text-blue" />
                <strong>Specialist Agent Selection Required</strong>
              </div>
              <p className="mismatch-text">
                {message.content || message.message}
              </p>
              {suggestedAgent && onSwitchSpecialist && (
                <div className="mismatch-cta-row">
                  <button
                    type="button"
                    className="btn-switch-specialist-cta"
                    onClick={() => onSwitchSpecialist(suggestedAgent)}
                  >
                    <span>Switch to {agentLabel(suggestedAgent)}</span>
                  </button>
                </div>
              )}
            </div>
          )}

          {/* Normal Assistant / User Content (agent replies use light Markdown) */}
          {!isBlocked && !isRestricted && !isMismatch && !isUser && (
            <MarkdownText className="message-text-content" text={message.content} allowTables={agentTarget === 'inventory_agent'} />
          )}
          {!isBlocked && !isRestricted && !isMismatch && isUser && message.content && (
            <div className="message-text-content">
              {message.content}
            </div>
          )}

          {/* Fulfillment SOP Citations Chip (if any) */}
          {isFulfillment && fulfillment?.citations?.length > 0 && (
            <div className="fulfillment-citations-chat-list">
              {fulfillment.citations.map((c, i) => (
                <div key={i} className="fulfillment-citation-tag" title={c.disclaimer || 'Demonstration Warehouse SOP'}>
                  <span className="citation-prefix">Source:</span>
                  <span className="citation-sop-id">{c.sop_id}</span>
                  <span className="citation-separator">—</span>
                  <span className="citation-title">{c.title}{c.heading ? ` (${c.heading})` : ''}</span>
                  {c.status === 'demonstration' && (
                    <span className="citation-demo-badge">DEMO SOP</span>
                  )}
                </div>
              ))}
            </div>
          )}

          {isFulfillment && onOpenFulfillmentDashboard && (
            <div className="fulfillment-chat-action-container">
              <button type="button" className="btn-view-fulfillment-dashboard"
                onClick={() => onOpenFulfillmentDashboard(message)}
                aria-label={`Open Fulfillment Dashboard${fulfillment.orderId ? ` for ${fulfillment.orderId}` : (fulfillment.isProcedural ? ' (SOP Guidance)' : '')}`}>
                <span className="btn-icon-wrapper"><Truck size={15} /></span>
                <span className="btn-text">{fulfillment.orderId ? 'View Fulfillment Dashboard' : 'View Fulfillment SOP Dashboard'}</span>
                {fulfillment.orderId && <span className="btn-order-badge">{fulfillment.orderId}</span>}
                {!fulfillment.orderId && fulfillment.isProcedural && <span className="btn-order-badge sop-badge">SOP GUIDANCE</span>}
                <ExternalLink size={13} />
              </button>
            </div>
          )}

          {/* Attached Files (User) */}
          {message.attachments && message.attachments.length > 0 && (
            <div className="message-attachments-list">
              {message.attachments.map((att, i) => (
                <div key={i} className="msg-attachment-item">
                  <Paperclip size={12} className="text-amber" />
                  <span>{att.name}</span>
                </div>
              ))}
            </div>
          )}

          {/* Structured Specialization Cards for Coordinator */}
          {!isUser && !isBlocked && !isRestricted && !isMismatch && (
            <div className="specialist-embedded-cards">
              {/* SKU Location Callout */}
              {message.skuData && (
                <div className="embedded-sku-card">
                  <div className="embedded-card-header">
                    <div className="card-header-left">
                      <ScanBarcode size={15} className="text-amber" />
                      <strong>Inventory Bay Manifest: {message.skuData.sku || '—'}</strong>
                    </div>
                    <span className="hud-status-badge badge-emerald">HIGH-BAY VERIFIED</span>
                  </div>
                  <div className="embedded-card-body">
                    <div className="sku-spec-grid">
                      <div className="spec-tile">
                        <span className="spec-label">HIGH-BAY COORDINATES:</span>
                        <div className="coords-badge-group">
                          <span className="coord-chip">AISLE {message.skuData.aisle ?? '—'}</span>
                          <span className="coord-chip">SHELF {message.skuData.shelf || '—'}</span>
                          <span className="coord-chip accent">{message.skuData.bay ? message.skuData.bay.toUpperCase() : `TIER ${message.skuData.tier || '—'}`}</span>
                        </div>
                      </div>
                      <div className="spec-tile">
                        <span className="spec-label">VERIFIED FLOOR STOCK:</span>
                        <div className="stock-level-container">
                          <span className="spec-val stock-val">{message.skuData?.stock || '—'}</span>
                          <div className="stock-progress-track">
                            <div className="stock-progress-fill" style={{ width: message.skuData?.status === 'OUT_OF_STOCK' ? '8%' : (message.skuData?.status === 'LOW_STOCK' ? '30%' : '85%') }} />
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* Order Status Callout */}
              {!isFulfillment && (message.orderData || meta.order_id) && (
                <div className="embedded-order-card">
                  <div className="embedded-card-header">
                    <div className="card-header-left">
                      <Truck size={15} className="text-blue" />
                      <strong>Fulfillment Consignment: {meta.order_id || message.orderData?.id || '#4521'}</strong>
                    </div>
                    <span className="hud-status-badge badge-blue">ON-SCHEDULE DISPATCH</span>
                  </div>
                  <div className="embedded-card-body">
                    <div className="sku-spec-grid">
                      <div className="spec-tile">
                        <span className="spec-label">DISPATCH TELEMETRY:</span>
                        <span className="spec-val status-in-transit">{message.orderData?.status || 'In Transit (On Schedule)'}</span>
                        <div className="transit-progress-track">
                          <div className="transit-progress-fill" style={{ width: '68%' }} />
                        </div>
                      </div>
                      <div className="spec-tile">
                        <span className="spec-label">ASSIGNED CARRIER FLEET:</span>
                        <span className="spec-val carrier-val">{message.orderData?.carrier || 'FreightExpress Logistics • Priority 1'}</span>
                      </div>
                    </div>
                    <button
                      onClick={() => onInspectOrder(message.orderData || { id: meta.order_id || '#4521' })}
                      className="btn-inspect-artifact"
                    >
                      <Truck size={13} className="text-blue" />
                      <span>Inspect Carrier Fleet Transit Timeline</span>
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Digital Twin: replay this answer on the warehouse map */}
          {!isUser && message.uiCommand && onShowOnMap && (
            <button onClick={() => onShowOnMap(message)} className="btn-inspect-artifact twin-show-on-map">
              <MapIcon size={13} className="text-emerald" />
              <span>Show on warehouse map</span>
            </button>
          )}

          {/* Footer Controls for Assistant */}
          {!isUser && (
            <div className="message-footer-bar">
              <div className="footer-actions-right">
                <button
                  onClick={toggleSpeak}
                  className={`icon-action-btn ${isPlayingThis ? 'is-speaking' : ''}`}
                  title={isPlayingThis ? 'Stop voice readout' : 'Read aloud with AI voice'}
                  aria-label="Read aloud with AI voice"
                >
                  {isPlayingThis ? <VolumeX size={13} className="text-cyan animate-pulse" /> : <Volume2 size={13} />}
                </button>
                <button onClick={copyContent} className="icon-action-btn" title="Copy response">
                  {copied ? <Check size={13} className="text-emerald" /> : <Copy size={13} />}
                </button>
                <button className="icon-action-btn" title="Accurate warehouse response">
                  <ThumbsUp size={13} />
                </button>
                <button className="icon-action-btn" title="Inaccurate">
                  <ThumbsDown size={13} />
                </button>
              </div>
            </div>
          )}
        </div>

        <div className="message-timestamp">
          {new Date(message.timestamp || Date.now()).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
        </div>
      </div>
    </div>
  )
}
