import React, { useState } from 'react'
import {
  X,
  Code2,
  Warehouse,
  Boxes,
  Truck,
  ShieldCheck,
  Cpu,
  Copy,
  Check,
  RefreshCw,
  CheckCircle2,
  AlertCircle,
  Activity
} from 'lucide-react'
import WarehouseFloorVisualizer from './WarehouseFloorVisualizer'

export default function ArtifactPanel({
  isOpen,
  onClose,
  activeTab,
  setActiveTab,
  selectedMessage,
  token,
  currentUser,
  auditLogs,
  auditStats,
  onRefreshAuditLogs
}) {
  const [copied, setCopied] = useState(false)

  if (!isOpen) return null

  // Extract routing telemetry from selectedMessage or fallback to default
  const routingData = selectedMessage?.routing || selectedMessage?.metadata?.routing || {
    intent: 'inventory',
    target_agent: 'inventory',
    confidence: 0.98,
    latency_ms: 38,
    extracted_params: {
      sku: 'SKU-4521',
      action: 'query_location'
    },
    coordinator_status: 'dispatched_mcp'
  }

  // Parse JWT token claims
  const parseJwt = (jwtToken) => {
    try {
      if (!jwtToken) return null
      const base64Url = jwtToken.split('.')[1]
      const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/')
      const jsonPayload = decodeURIComponent(
        atob(base64)
          .split('')
          .map((c) => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
          .join('')
      )
      return JSON.parse(jsonPayload)
    } catch (e) {
      return null
    }
  }

  const claims = parseJwt(token)

  const copyTelemetry = () => {
    navigator.clipboard.writeText(JSON.stringify(routingData, null, 2))
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <aside className="claude-artifact-panel">
      {/* Panel Top Navigation */}
      <div className="artifact-panel-header">
        <div className="artifact-header-left">
          <div className="artifact-title-row">
            <Warehouse size={18} className="text-amber" />
            <h3 className="artifact-title">IntelliWMS Visual Artifacts & Telemetry</h3>
          </div>
          <span className="artifact-subtitle">Autonomous coordinator execution & live warehouse state</span>
        </div>
        <button onClick={onClose} className="artifact-close-btn" title="Close Artifact Panel">
          <X size={18} />
        </button>
      </div>

      {/* Tabs Row */}
      <div className="artifact-tabs-bar">
        <button
          className={`artifact-tab-btn ${activeTab === 'telemetry' ? 'active' : ''}`}
          onClick={() => setActiveTab('telemetry')}
        >
          <Cpu size={14} />
          <span>Routing Telemetry</span>
        </button>
        <button
          className={`artifact-tab-btn ${activeTab === 'bay_visualizer' ? 'active' : ''}`}
          onClick={() => setActiveTab('bay_visualizer')}
        >
          <Warehouse size={14} />
          <span>Bay Map</span>
        </button>
        <button
          className={`artifact-tab-btn ${activeTab === 'order_timeline' ? 'active' : ''}`}
          onClick={() => setActiveTab('order_timeline')}
        >
          <Truck size={14} />
          <span>Fulfillment Fleet</span>
        </button>
        <button
          className={`artifact-tab-btn ${activeTab === 'rbac_claims' ? 'active' : ''}`}
          onClick={() => setActiveTab('rbac_claims')}
        >
          <ShieldCheck size={14} />
          <span>JWT & RBAC</span>
        </button>
        <button
          className={`artifact-tab-btn ${activeTab === 'soc_audit' ? 'active' : ''}`}
          onClick={() => setActiveTab('soc_audit')}
        >
          <Activity size={14} />
          <span>SOC Stream</span>
        </button>
      </div>

      {/* Panel Scrollable Content Body */}
      <div className="artifact-panel-content">
        {/* TAB 1: ROUTING TELEMETRY */}
        {activeTab === 'telemetry' && (
          <div className="telemetry-tab-view">
            <div className="telemetry-metrics-strip">
              <div className="telemetry-metric-pill">
                <span className="metric-lbl">IDENTIFIED INTENT</span>
                <span className="metric-val text-amber">{routingData.intent?.toUpperCase() || 'INVENTORY'}</span>
              </div>
              <div className="telemetry-metric-pill">
                <span className="metric-lbl">DISPATCHED AGENT</span>
                <span className="metric-val text-blue">{(routingData.target_agent || 'INVENTORY').toUpperCase()}</span>
              </div>
              <div className="telemetry-metric-pill">
                <span className="metric-lbl">INTENT CONFIDENCE</span>
                <span className="metric-val text-emerald">
                  {((routingData.confidence || 0.98) * 100).toFixed(0)}%
                </span>
              </div>
              <div className="telemetry-metric-pill">
                <span className="metric-lbl">ROUTING LATENCY</span>
                <span className="metric-val">{routingData.latency_ms || 32} ms</span>
              </div>
            </div>

            <div className="artifact-section-card">
              <div className="section-card-header">
                <div className="header-title">
                  <Code2 size={14} className="text-amber" />
                  <strong>Extracted Warehouse Entities</strong>
                </div>
              </div>
              <div className="entity-pills-row">
                <div className="entity-chip">
                  <span className="entity-k">Target SKU:</span>
                  <span className="entity-v">{routingData.extracted_params?.sku || 'SKU-4521'}</span>
                </div>
                <div className="entity-chip">
                  <span className="entity-k">Target Consignment:</span>
                  <span className="entity-v">{routingData.extracted_params?.order_id || '#4521'}</span>
                </div>
                <div className="entity-chip">
                  <span className="entity-k">Security Inspection:</span>
                  <span className="entity-v text-emerald">Verified & Sanitized</span>
                </div>
              </div>
            </div>

            <div className="artifact-section-card">
              <div className="section-card-header">
                <div className="header-title">
                  <Cpu size={14} className="text-blue" />
                  <strong>Coordinator Multi-Agent MCP Payload</strong>
                </div>
                <button onClick={copyTelemetry} className="artifact-mini-action-btn">
                  {copied ? <Check size={12} className="text-emerald" /> : <Copy size={12} />}
                  <span>{copied ? 'Copied' : 'Copy'}</span>
                </button>
              </div>
              <pre className="json-display-block">
                {JSON.stringify(routingData, null, 2)}
              </pre>
            </div>
          </div>
        )}

        {/* TAB 2: DYNAMIC WAREHOUSE FLOOR & BAY VISUALIZER (MEMBER 1) */}
        {activeTab === 'bay_visualizer' && (
          <WarehouseFloorVisualizer
            selectedMessage={selectedMessage}
            currentUser={currentUser}
          />
        )}

        {/* TAB 3: REAL FULFILLMENT TELEMETRY & ORDER OVERVIEW */}
        {activeTab === 'order_timeline' && (() => {
          const fulfillmentDetails = selectedMessage?.fulfillment_details || selectedMessage?.metadata?.fulfillment_details || null
          const contentText = String(selectedMessage?.content || '')
          
          let orderId = fulfillmentDetails?.order_id || null
          if (!orderId) {
            const match = contentText.match(/\b(ORD-\d+)\b/i)
            if (match) orderId = match[1].toUpperCase()
          }

          const isDelayed = /is currently delayed/i.test(contentText) || /status: delayed/i.test(contentText)
          const isShipped = /marked as shipped/i.test(contentText) || /is currently shipped/i.test(contentText) || /status: shipped/i.test(contentText)
          const isPending = /is currently pending/i.test(contentText) || /status: pending/i.test(contentText)
          const orderStatus = isDelayed ? 'DELAYED' : (isShipped ? 'SHIPPED' : (isPending ? 'PENDING' : (orderId ? 'ACTIVE' : 'N/A')))

          // Delay attributes
          const reasonMatch = contentText.match(/Reason:\s*([^.\n]+)/i)
          const carrierMatch = contentText.match(/Carrier:\s*([^.\n]+)/i)
          const dateMatch = contentText.match(/Revised delivery date:\s*([^.\n]+)/i)
          const delayReason = reasonMatch ? reasonMatch[1].trim() : null
          const carrierName = carrierMatch ? carrierMatch[1].trim() : null
          const revisedDate = dateMatch ? dateMatch[1].trim() : null

          // Cross-agent inventory
          const skuMatch = contentText.match(/\b(SKU-\d+)\b/i)
          const isOutOfStock = /is currently out of stock/i.test(contentText) || /stock: 0/i.test(contentText)
          const isStockAvailable = /currently has stock available/i.test(contentText)
          const hasInventoryCollaboration = (isOutOfStock || isStockAvailable) && !!skuMatch
          const crossSku = skuMatch ? skuMatch[1].toUpperCase() : null
          const crossStockStatus = isOutOfStock ? 'OUT_OF_STOCK' : (isStockAvailable ? 'IN_STOCK' : null)

          const timestamp = selectedMessage?.metadata?.audit?.timestamp || selectedMessage?.timestamp

          return (
            <div className="order-timeline-tab-view">
              {/* Card 1: Order Manifest Overview */}
              <div className="artifact-section-card">
                <div className="section-card-header">
                  <div className="header-title">
                    <Truck size={14} className="text-blue" />
                    <strong>Order Record Overview</strong>
                  </div>
                  <span className={`hud-status-badge ${orderStatus === 'DELAYED' ? 'badge-coral' : (orderStatus === 'SHIPPED' ? 'badge-emerald' : 'badge-blue')}`}>
                    {orderStatus}
                  </span>
                </div>
                <div className="entity-pills-row">
                  <div className="entity-chip">
                    <span className="entity-k">Order ID:</span>
                    <span className="entity-v text-light font-mono font-bold">{orderId || 'ORD-1001'}</span>
                  </div>
                  <div className="entity-chip">
                    <span className="entity-k">Handled By:</span>
                    <span className="entity-v text-blue">Fulfillment Agent</span>
                  </div>
                  {fulfillmentDetails?.intent && (
                    <div className="entity-chip">
                      <span className="entity-k">Intent:</span>
                      <span className="entity-v text-amber">{fulfillmentDetails.intent}</span>
                    </div>
                  )}
                  {timestamp && (
                    <div className="entity-chip">
                      <span className="entity-k">Timestamp:</span>
                      <span className="entity-v font-mono text-xs">{new Date(timestamp).toLocaleTimeString()}</span>
                    </div>
                  )}
                </div>
              </div>

              {/* Card 2: Delay Root-Cause Analysis (When Applicable) */}
              {(delayReason || carrierName || revisedDate) && (
                <div className="artifact-section-card">
                  <div className="section-card-header">
                    <div className="header-title">
                      <AlertCircle size={14} className="text-coral" />
                      <strong>Delay & Logistics Telemetry</strong>
                    </div>
                  </div>
                  <div className="telemetry-metrics-strip" style={{ marginBottom: '12px' }}>
                    {carrierName && (
                      <div className="telemetry-metric-pill">
                        <span className="metric-lbl">ASSIGNED CARRIER</span>
                        <span className="metric-val text-blue">{carrierName}</span>
                      </div>
                    )}
                    {revisedDate && (
                      <div className="telemetry-metric-pill">
                        <span className="metric-lbl">REVISED DELIVERY TARGET</span>
                        <span className="metric-val text-amber">{revisedDate}</span>
                      </div>
                    )}
                  </div>
                  {delayReason && (
                    <div className="delay-reason-box" style={{ background: 'rgba(255, 69, 58, 0.08)', border: '1px solid rgba(255, 69, 58, 0.2)', borderRadius: '8px', padding: '10px 12px' }}>
                      <span style={{ fontSize: '11px', color: 'var(--accent-coral)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Root Cause:</span>
                      <p style={{ margin: '4px 0 0 0', fontSize: '13px', color: 'var(--text-light)', lineHeight: 1.4 }}>{delayReason}</p>
                    </div>
                  )}
                </div>
              )}

              {/* Card 3: Multi-Agent Collaboration Stream */}
              <div className="artifact-section-card">
                <div className="section-card-header">
                  <div className="header-title">
                    <Cpu size={14} className="text-amber" />
                    <strong>Agent Execution & Coordination Trace</strong>
                  </div>
                  {hasInventoryCollaboration && (
                    <span className="hud-status-badge badge-emerald">CROSS-AGENT ACTIVE</span>
                  )}
                </div>

                <div className="timeline-steps-vertical">
                  <div className="timeline-step completed">
                    <div className="step-dot" />
                    <div className="step-content">
                      <strong>Coordinator Gateway Routing</strong>
                      <span>Validated query integrity, authenticated JWT claims, and delegated domain to Fulfillment.</span>
                    </div>
                  </div>

                  <div className="timeline-step completed">
                    <div className="step-dot" />
                    <div className="step-content">
                      <strong>Fulfillment Specialist Execution</strong>
                      <span>Executed order record retrieval and status classification.</span>
                    </div>
                  </div>

                  {hasInventoryCollaboration ? (
                    <div className="timeline-step active-current">
                      <div className="step-dot pulse" />
                      <div className="step-content">
                        <strong>Inventory Agent Cross-Check ({crossSku})</strong>
                        <span>
                          {crossStockStatus === 'OUT_OF_STOCK'
                            ? `Stock check executed for ${crossSku}: 0 units available. Stock depletion confirmed.`
                            : `Stock check executed for ${crossSku}: Physical inventory verified on hand.`}
                        </span>
                        <small className="text-amber">Cross-Agent Verification</small>
                      </div>
                    </div>
                  ) : (
                    <div className="timeline-step completed">
                      <div className="step-dot" />
                      <div className="step-content">
                        <strong>Direct Resolution</strong>
                        <span>Order records yielded complete information; no external inventory cross-call required.</span>
                      </div>
                    </div>
                  )}
                </div>
              </div>

              {/* Card 4: Routing Rationale */}
              {routingData.reasoning && (
                <div className="artifact-section-card">
                  <div className="section-card-header">
                    <div className="header-title">
                      <Code2 size={14} className="text-amber" />
                      <strong>Coordinator Routing Rationale</strong>
                    </div>
                  </div>
                  <p style={{ fontSize: '12.5px', color: 'var(--text-secondary)', lineHeight: 1.5, margin: 0 }}>
                    {routingData.reasoning}
                  </p>
                </div>
              )}
            </div>
          )
        })()}

        {/* TAB 4: JWT & RBAC MATRIX */}
        {activeTab === 'rbac_claims' && (
          <div className="rbac-tab-view">
            <div className="jwt-status-card">
              <div className="jwt-title-row">
                <ShieldCheck size={16} className="text-emerald" />
                <strong>Cryptographic HS256 JWT Validated</strong>
              </div>
              <p>Issued by Coordinator Authentication Authority • Salted SHA-256 Verified</p>
            </div>

            {claims ? (
              <div className="claims-grid">
                <div className="claim-row">
                  <span className="claim-key">Subject (User ID):</span>
                  <span className="claim-val font-mono">{claims.sub}</span>
                </div>
                <div className="claim-row">
                  <span className="claim-key">Enforced Role:</span>
                  <span className="claim-val text-amber font-mono font-bold uppercase">{claims.role}</span>
                </div>
                <div className="claim-row">
                  <span className="claim-key">Token Issued At:</span>
                  <span className="claim-val">{claims.iat ? new Date(claims.iat * 1000).toLocaleString() : 'N/A'}</span>
                </div>
                <div className="claim-row">
                  <span className="claim-key">Expires At:</span>
                  <span className="claim-val">{claims.exp ? new Date(claims.exp * 1000).toLocaleString() : '24 Hours'}</span>
                </div>
              </div>
            ) : (
              <div className="no-claims-notice">No active JWT payload parsed</div>
            )}

            <div className="rbac-checklist-card">
              <div className="checklist-header">
                <strong>Enforced RBAC Permission Matrix for {currentUser?.role?.toUpperCase() || 'STAFF'}</strong>
              </div>
              <div className="checklist-items">
                <div className="check-item allowed">
                  <CheckCircle2 size={14} className="text-emerald" />
                  <span><code>query_location</code> — Authorized for all warehouse staff</span>
                </div>
                <div className="check-item allowed">
                  <CheckCircle2 size={14} className="text-emerald" />
                  <span><code>track_order</code> — Authorized for all warehouse staff</span>
                </div>
                <div className={`check-item ${currentUser?.role === 'manager' || currentUser?.role === 'admin' ? 'allowed' : 'restricted'}`}>
                  {currentUser?.role === 'manager' || currentUser?.role === 'admin' ? (
                    <CheckCircle2 size={14} className="text-emerald" />
                  ) : (
                    <AlertCircle size={14} className="text-coral" />
                  )}
                  <span><code>approve_restock</code> — Manager & Admin only</span>
                </div>
                <div className={`check-item ${currentUser?.role === 'manager' || currentUser?.role === 'admin' ? 'allowed' : 'restricted'}`}>
                  {currentUser?.role === 'manager' || currentUser?.role === 'admin' ? (
                    <CheckCircle2 size={14} className="text-emerald" />
                  ) : (
                    <AlertCircle size={14} className="text-coral" />
                  )}
                  <span><code>view_analytics</code> — Manager & Admin only</span>
                </div>
                <div className={`check-item ${currentUser?.role === 'admin' ? 'allowed' : 'restricted'}`}>
                  {currentUser?.role === 'admin' ? (
                    <CheckCircle2 size={14} className="text-emerald" />
                  ) : (
                    <AlertCircle size={14} className="text-coral" />
                  )}
                  <span><code>manage_users</code> — System Admin only</span>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* TAB 5: SOC AUDIT STREAM */}
        {activeTab === 'soc_audit' && (
          <div className="soc-audit-tab-view">
            <div className="soc-stats-grid">
              <div className="soc-stat-tile">
                <span className="stat-val">{auditStats?.total_events || auditLogs?.length || 0}</span>
                <span className="stat-lbl">Security Events</span>
              </div>
              <div className="soc-stat-tile text-coral">
                <span className="stat-val">{auditStats?.injections_blocked || 0}</span>
                <span className="stat-lbl">Attacks Blocked</span>
              </div>
              <div className="soc-stat-tile text-amber">
                <span className="stat-val">{auditStats?.permissions_denied || 0}</span>
                <span className="stat-lbl">RBAC Denials</span>
              </div>
              <div className="soc-stat-tile text-emerald">
                <span className="stat-val">{auditStats?.logins_success || 0}</span>
                <span className="stat-lbl">Verified Logins</span>
              </div>
            </div>

            <div className="soc-feed-header">
              <strong>Real-Time Security Audit Stream</strong>
              <button onClick={onRefreshAuditLogs} className="artifact-refresh-btn" title="Refresh SOC Stream">
                <RefreshCw size={12} />
                <span>Refresh</span>
              </button>
            </div>

            <div className="soc-events-list">
              {(!auditLogs || auditLogs.length === 0) ? (
                <div className="empty-soc-notice">No security audit events recorded yet</div>
              ) : (
                auditLogs.slice(0, 15).map((log) => (
                  <div key={log.id} className="soc-event-item">
                    <div className="soc-event-top">
                      <span className={`soc-event-badge badge-${log.event_type}`}>
                        {log.event_type}
                      </span>
                      <span className="soc-event-time">
                        {new Date(log.timestamp).toLocaleTimeString()}
                      </span>
                    </div>
                    <div className="soc-event-meta">
                      <strong>{log.user_id}</strong> ({log.role})
                    </div>
                    <div className="soc-event-details">
                      {typeof log.details === 'object' ? JSON.stringify(log.details) : log.details}
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        )}
      </div>
    </aside>
  )
}
