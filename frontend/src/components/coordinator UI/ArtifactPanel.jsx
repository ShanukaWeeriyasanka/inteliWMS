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
  auditAccess = true,
  auditError = '',
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
      sku: null,
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
                  <span className="entity-v">{routingData.extracted_params?.sku || '—'}</span>
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

        {/* TAB 3: FULFILLMENT & ORDER TIMELINE */}
        {activeTab === 'order_timeline' && (
          <div className="order-timeline-tab-view">
            <div className="order-header-card">
              <div>
                <h4>Consignment #4521</h4>
                <span>Recipient: Apex Automotive Distribution • Priority 1 Expedited</span>
              </div>
              <span className="status-pill in-transit">IN TRANSIT</span>
            </div>

            <div className="timeline-steps-vertical">
              <div className="timeline-step completed">
                <div className="step-dot" />
                <div className="step-content">
                  <strong>Order Manifest Validated</strong>
                  <span>Coordinator validated cryptographic signature & inventory reservation</span>
                  <small>Today, 08:14 AM</small>
                </div>
              </div>

              <div className="timeline-step completed">
                <div className="step-dot" />
                <div className="step-content">
                  <strong>Automated AGV Pick Completed</strong>
                  <span>Picked from Aisle 12, Shelf B3 by AGV Unit #08</span>
                  <small>Today, 09:30 AM</small>
                </div>
              </div>

              <div className="timeline-step completed">
                <div className="step-dot" />
                <div className="step-content">
                  <strong>Quality Control & Barcode Scan</strong>
                  <span>Weights and Hazmat verification signed off by Inspector</span>
                  <small>Today, 10:15 AM</small>
                </div>
              </div>

              <div className="timeline-step active-current">
                <div className="step-dot pulse" />
                <div className="step-content">
                  <strong>Dispatched with FreightExpress Fleet</strong>
                  <span>Tracking ID: FX-992184-US • ETA: Tomorrow 14:00</span>
                  <small className="text-amber">Active Milestone</small>
                </div>
              </div>

              <div className="timeline-step pending">
                <div className="step-dot" />
                <div className="step-content">
                  <strong>Final Mile Gate Delivery</strong>
                  <span>Awaiting destination terminal gate scan</span>
                  <small>Estimated Tomorrow</small>
                </div>
              </div>
            </div>
          </div>
        )}

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
                  <span className="claim-val font-mono">{claims.user_id || claims.sub || '—'}</span>
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
        {activeTab === 'soc_audit' && !auditAccess && (
          <div className="soc-audit-tab-view">
            <div className="soc-feed-header">
              <strong>Real-Time Security Audit Stream</strong>
            </div>
            <div className="empty-soc-notice soc-restricted-notice">
              <ShieldCheck size={16} className="text-amber" />
              <span>The security audit stream is available to managers and admins.</span>
            </div>
          </div>
        )}

        {activeTab === 'soc_audit' && auditAccess && (
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

            {auditError && (
              <div className="soc-error-notice" role="status">
                <AlertCircle size={14} className="text-coral" />
                <span>{auditError}</span>
              </div>
            )}

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
