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
  Layers,
  ThumbsUp,
  ThumbsDown,
  Paperclip,
  Activity
} from 'lucide-react'

export default function ChatMessage({
  message,
  onOpenArtifact,
  onInspectLocation,
  onOpenFulfillmentDashboard,
  onSendQuery
}) {
  const [copied, setCopied] = useState(false)
  const isUser = message.role === 'user'

  const copyContent = () => {
    navigator.clipboard.writeText(message.content || '')
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  // Parse structured details if present
  const meta = message.metadata || {}
  const routing = message.routing || meta.routing || {}
  const agentTarget = routing.target_agent || meta.target_agent || message.agent_used || 'coordinator'
  const isBlocked = message.status === 'blocked' || routing.status === 'blocked'

  // Strict fulfillment detection: only genuine fulfillment responses
  const isFulfillment =
    !isUser &&
    !isBlocked &&
    (agentTarget === 'fulfillment_agent' ||
      message.agent_used === 'fulfillment_agent' ||
      meta.agent_used === 'fulfillment_agent' ||
      !!message.fulfillment_details ||
      !!meta.fulfillment_details ||
      (routing.domain === 'FULFILLMENT' &&
        agentTarget !== 'inventory_agent' &&
        agentTarget !== 'knowledge_agent'))

  // Conservative order ID resolution for the button label
  const parsedOrderId =
    message.fulfillment_details?.order_id ||
    meta.fulfillment_details?.order_id ||
    (typeof message.content === 'string'
      ? message.content.match(/\b(ORD-\d+)\b/i)?.[1]?.toUpperCase()
      : null)

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
            {agentTarget && agentTarget !== 'coordinator' && (
              <span className="agent-route-tag">
                <Bot size={11} />
                <span>via {agentTarget.toUpperCase()} AGENT</span>
              </span>
            )}
            {routing.confidence && (
              <span className="confidence-tag">
                {(routing.confidence * 100).toFixed(0)}% match
              </span>
            )}
            {routing.latency_ms && (
              <span className="latency-tag">{routing.latency_ms}ms</span>
            )}
          </div>
        )}

        <div
          className={`message-bubble ${isUser ? 'user-bubble' : 'assistant-bubble'} ${
            isBlocked ? 'blocked-bubble' : ''
          }`}
        >
          {/* If security blocked */}
          {isBlocked && (
            <div className="security-block-notice">
              <div className="security-notice-title">
                <ShieldAlert size={16} className="text-coral" />
                <strong>Responsible AI Shield Activated</strong>
              </div>
              <p className="security-notice-desc">
                {message.content ||
                  routing.message ||
                  'Potential prompt injection or privileged data extraction detected and neutralized.'}
              </p>
              {routing.rule && (
                <div className="security-rule-tag">
                  Security Rule: <code>{routing.rule}</code>
                </div>
              )}
            </div>
          )}

          {/* Normal Assistant / User Content */}
          {!isBlocked && (
            <div className="message-text-content">
              {message.content}
            </div>
          )}

          {/* Prominent Fulfillment Dashboard Navigation Button (Directly after response) */}
          {isFulfillment && (
            <div className="fulfillment-chat-action-container">
              <button
                type="button"
                onClick={() => onOpenFulfillmentDashboard && onOpenFulfillmentDashboard(message)}
                className="btn-view-fulfillment-dashboard"
                title="Open dedicated Fulfillment Operations Control Center"
              >
                <div className="btn-icon-wrapper">
                  <Truck size={15} />
                </div>
                <span className="btn-text">
                  View Fulfillment Dashboard
                  {parsedOrderId ? ` (${parsedOrderId})` : ''}
                </span>
                <ExternalLink size={13} className="btn-ext-icon" />
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

          {/* Structured Inventory Specialization Card (Inventory Agent) */}
          {!isUser && !isBlocked && (message.skuData || meta.sku) && (
            <div className="specialist-embedded-cards">
              <div className="embedded-sku-card">
                <div className="embedded-card-header">
                  <div className="card-header-left">
                    <ScanBarcode size={15} className="text-amber" />
                    <strong>Inventory Bay Manifest: {meta.sku || message.skuData?.sku || 'SKU-4521'}</strong>
                  </div>
                  <span className="hud-status-badge badge-emerald">HIGH-BAY VERIFIED</span>
                </div>
                <div className="embedded-card-body">
                  <div className="sku-spec-grid">
                    <div className="spec-tile">
                      <span className="spec-label">HIGH-BAY COORDINATES:</span>
                      <div className="coords-badge-group">
                        <span className="coord-chip">AISLE {message.skuData?.aisle || 12}</span>
                        <span className="coord-chip">SHELF {message.skuData?.shelf || 'B3'}</span>
                        <span className="coord-chip accent">
                          {message.skuData?.bay
                            ? message.skuData.bay.toUpperCase()
                            : `TIER ${message.skuData?.tier || 'B'}`}
                        </span>
                      </div>
                    </div>
                    <div className="spec-tile">
                      <span className="spec-label">VERIFIED FLOOR STOCK:</span>
                      <div className="stock-level-container">
                        <span className="spec-val stock-val">
                          {message.skuData?.stock || 'Physical stock verified'}
                        </span>
                        <div className="stock-progress-track">
                          <div
                            className="stock-progress-fill"
                            style={{
                              width:
                                message.skuData?.status === 'OUT_OF_STOCK'
                                  ? '8%'
                                  : message.skuData?.status === 'LOW_STOCK'
                                  ? '30%'
                                  : '85%'
                            }}
                          />
                        </div>
                      </div>
                    </div>
                  </div>
                  {onInspectLocation && (
                    <button
                      type="button"
                      onClick={() => onInspectLocation(message.skuData || { sku: meta.sku || 'SKU-4521' })}
                      className="btn-inspect-artifact"
                    >
                      <Warehouse size={13} className="text-amber" />
                      <span>Inspect Warehouse Floor & 3D Bay Map</span>
                    </button>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* Footer Controls for Assistant */}
          {!isUser && (
            <div className="message-footer-bar">
              {onOpenArtifact && (
                <button
                  type="button"
                  onClick={() => onOpenArtifact(message)}
                  className="btn-view-artifact-link"
                  title="View Routing Telemetry & Artifact"
                >
                  <Layers size={13} className="text-amber" />
                  <span>Telemetry & Visual Artifact</span>
                </button>
              )}

              <div className="footer-actions-right">
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
          {new Date(message.timestamp || Date.now()).toLocaleTimeString([], {
            hour: '2-digit',
            minute: '2-digit'
          })}
        </div>
      </div>
    </div>
  )
}
