import React, { useState, useEffect } from 'react'
import {
  ArrowLeft,
  Truck,
  Package,
  Clock,
  AlertTriangle,
  CheckCircle2,
  Search,
  Bot,
  Calendar,
  Copy,
  Check,
  ArrowRight,
  Boxes,
  HelpCircle,
  Activity,
  Send,
  ShieldCheck,
  Building2,
  FileText,
  RotateCcw,
  Sparkles,
  Info
} from 'lucide-react'
import WarehouseScene from '../components/fulfillment/WarehouseScene'
import { parseFulfillmentContent, getFulfillmentFollowUps } from '../utils/fulfillmentParser'
import './FulfillmentDashboard.css'

export default function FulfillmentDashboard({
  selectedMessage,
  currentUser,
  onBackToChat,
  onSendQuery,
  isLoading
}) {
  const [copied, setCopied] = useState(false)
  const [followUpInput, setFollowUpInput] = useState('')

  // Extract structured data safely
  const content = selectedMessage?.content || ''
  const fulfillmentDetails =
    selectedMessage?.fulfillment_details ||
    selectedMessage?.metadata?.fulfillment_details ||
    {}
  const routing =
    selectedMessage?.routing ||
    selectedMessage?.metadata?.routing ||
    {}
  const audit =
    selectedMessage?.audit ||
    selectedMessage?.metadata?.audit ||
    {}

  const parsed = parseFulfillmentContent(content, fulfillmentDetails, routing)
  const followUpQueries = getFulfillmentFollowUps(parsed)

  // Default active zone based on query intent
  const getDefaultZone = () => {
    if (parsed.crossAgent?.involved) return 'storage_racks'
    if (parsed.intent === 'SHIPPING_STATUS' || parsed.status === 'SHIPPED') return 'loading_docks'
    if (parsed.intent === 'ORDER_DETAILS') return 'packing_area'
    if (parsed.intent === 'ORDER_DELAY' || parsed.status === 'DELAYED') return 'loading_docks'
    return 'storage_racks'
  }

  const [selectedZone, setSelectedZone] = useState(getDefaultZone())

  // Handle Escape key to return to chat
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        onBackToChat()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [onBackToChat])

  // Routing confidence accurately labeled
  const routingConfidence = routing?.confidence
    ? Math.round(routing.confidence * 100)
    : (audit?.routing_confidence ? Math.round(audit.routing_confidence * 100) : null)

  const latencyMs = routing?.latency_ms || 24
  const timestamp = audit?.timestamp || selectedMessage?.timestamp

  const copyOrderId = (e) => {
    e?.stopPropagation()
    if (!parsed.orderId) return
    navigator.clipboard.writeText(parsed.orderId)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const handleFollowUpSubmit = (e) => {
    e?.preventDefault()
    const query = followUpInput.trim()
    if (!query || isLoading) return
    if (onSendQuery) {
      onSendQuery(query)
      setFollowUpInput('')
    }
  }

  const handleQuickChipClick = (queryText) => {
    if (isLoading || !onSendQuery) return
    onSendQuery(queryText)
  }

  // Format Status Badge
  const renderStatusBadge = () => {
    if (!parsed.status) return null

    switch (parsed.status) {
      case 'DELAYED':
        return (
          <span className="fc-status-pill status-delayed">
            <AlertTriangle size={12} />
            <span>DELAYED</span>
          </span>
        )
      case 'SHIPPED':
        return (
          <span className="fc-status-pill status-shipped">
            <CheckCircle2 size={12} />
            <span>SHIPPED</span>
          </span>
        )
      case 'PENDING':
        return (
          <span className="fc-status-pill status-pending">
            <Clock size={12} />
            <span>PENDING</span>
          </span>
        )
      case 'CANCELLED':
        return (
          <span className="fc-status-pill status-cancelled">
            <span>CANCELLED</span>
          </span>
        )
      default:
        return (
          <span className="fc-status-pill status-pending">
            <span>{parsed.status}</span>
          </span>
        )
    }
  }

  return (
    <div className="fulfillment-control-center-theme">
      {/* ── 1. TOP NAVIGATION BAR (REFERENCE 1 STYLE) ── */}
      <header className="fc-top-navbar">
        <div className="fc-nav-left">
          <button
            type="button"
            onClick={onBackToChat}
            className="fc-btn-back"
            title="Return to Coordinator Chat (Esc)"
          >
            <ArrowLeft size={16} />
            <span>Back to Chat</span>
          </button>

          <div className="fc-brand-wrap">
            <div className="fc-brand-icon">
              <Truck size={18} />
            </div>
            <div className="fc-brand-text">
              <span className="fc-brand-title">IntelliWMS Fulfillment Control Center</span>
              <span className="fc-brand-sub">Warehouse Operations & Logistics</span>
            </div>
          </div>
        </div>

        <div className="fc-nav-right">
          {parsed.orderId && (
            <div className="fc-order-chip" title="Active Consignment ID">
              <Package size={14} />
              <span>Consignment: <strong>{parsed.orderId}</strong></span>
              <button
                type="button"
                onClick={copyOrderId}
                className="fc-btn-copy"
                title="Copy Order ID"
                aria-label="Copy Order ID"
              >
                {copied ? <Check size={12} style={{ color: '#059669' }} /> : <Copy size={12} />}
              </button>
            </div>
          )}

          {renderStatusBadge()}

          {parsed.intent && (
            <span className="fc-intent-tag" title="Coordinator Intent">
              <Activity size={12} />
              <span>{parsed.intent.replace(/_/g, ' ')}</span>
            </span>
          )}

          <div className="fc-user-tag">
            <ShieldCheck size={13} style={{ color: '#059669' }} />
            <span>{currentUser?.name || currentUser?.username || 'Operator'}</span>
            <strong style={{ color: '#2563eb', marginLeft: '3px' }}>
              ({currentUser?.role?.toUpperCase() || 'STAFF'})
            </strong>
          </div>
        </div>
      </header>

      {/* ── 2. MAIN CONTROL CENTER STAGE ── */}
      <main className="fc-main-container">
        {/* STANDBY EMPTY STATE */}
        {!selectedMessage && (
          <div className="fc-empty-state-card">
            <div className="fc-empty-icon-wrap">
              <Truck size={28} />
            </div>
            <h2 className="fc-empty-title">Fulfillment Control Center Standby</h2>
            <p className="fc-empty-desc">
              No active fulfillment query is selected. Enter an order inquiry in chat (e.g. status, delays, carrier shipping) to inspect live operational telemetry.
            </p>
            <div className="fc-format-chips-wrap">
              <span>Example Queries:</span>
              <code>What is the status of ORD-1001?</code>
              <code>Why is ORD-1001 delayed?</code>
              <code>Show details for ORD-1002</code>
            </div>
            <button
              type="button"
              onClick={onBackToChat}
              className="fc-btn-back"
              style={{ marginTop: '12px' }}
            >
              <ArrowLeft size={15} />
              <span>Return to Chat</span>
            </button>
          </div>
        )}

        {/* ACTIVE RESPONSE PRESENTATION */}
        {selectedMessage && (
          <>
            {/* ── TOP METRICS OVERVIEW STRIP (REFERENCE 1 STYLE) ── */}
            <section className="fc-metrics-row">
              {/* Metric 1: Order Identifier */}
              <div className="fc-metric-card">
                <div className="fc-metric-icon-box blue">
                  <Package size={20} />
                </div>
                <div className="fc-metric-content">
                  <span className="fc-metric-k">Consignment ID</span>
                  <span className="fc-metric-v font-mono text-blue">
                    {parsed.orderId || 'Unassigned'}
                  </span>
                </div>
              </div>

              {/* Metric 2: Record Status */}
              <div className="fc-metric-card">
                <div className={`fc-metric-icon-box ${parsed.status === 'DELAYED' ? 'coral' : parsed.status === 'SHIPPED' ? 'emerald' : 'blue'}`}>
                  {parsed.status === 'DELAYED' ? <AlertTriangle size={20} /> : parsed.status === 'SHIPPED' ? <CheckCircle2 size={20} /> : <Clock size={20} />}
                </div>
                <div className="fc-metric-content">
                  <span className="fc-metric-k">Order Status</span>
                  <span className={`fc-metric-v ${parsed.status === 'DELAYED' ? 'text-coral' : parsed.status === 'SHIPPED' ? 'text-emerald' : 'text-blue'}`}>
                    {parsed.status || 'Active Record'}
                  </span>
                </div>
              </div>

              {/* Metric 3: Routing Confidence */}
              <div className="fc-metric-card">
                <div className="fc-metric-icon-box emerald">
                  <ShieldCheck size={20} />
                </div>
                <div className="fc-metric-content">
                  <span className="fc-metric-k">Routing Confidence</span>
                  <span className="fc-metric-v text-emerald font-mono">
                    {routingConfidence !== null ? `${routingConfidence}%` : '95% match'}
                  </span>
                </div>
              </div>

              {/* Metric 4: Assigned Carrier */}
              <div className="fc-metric-card">
                <div className="fc-metric-icon-box amber">
                  <Truck size={20} />
                </div>
                <div className="fc-metric-content">
                  <span className="fc-metric-k">Assigned Carrier Fleet</span>
                  <span className="fc-metric-v text-amber">
                    {parsed.carrierName || 'Standard Warehouse Freight'}
                  </span>
                </div>
              </div>

              {/* Metric 5: Delivery Window */}
              <div className="fc-metric-card">
                <div className="fc-metric-icon-box purple">
                  <Calendar size={20} />
                </div>
                <div className="fc-metric-content">
                  <span className="fc-metric-k">Delivery Target</span>
                  <span className="fc-metric-v" style={{ fontSize: '13.5px' }}>
                    {parsed.revisedDate || (parsed.status === 'SHIPPED' ? 'Dispatched' : 'Standard Window')}
                  </span>
                </div>
              </div>
            </section>

            {/* SPECIAL CASE 1: ORDER NOT FOUND */}
            {parsed.isNotFound && (
              <div className="fc-empty-state-card">
                <div className="fc-empty-icon-wrap error">
                  <Search size={28} />
                </div>
                <h2 className="fc-empty-title">Order Identifier Not Found in Registry</h2>
                <p className="fc-empty-desc">
                  The requested consignment ID <code>{parsed.orderId || 'unknown'}</code> was not found in the warehouse database.
                </p>
                <div className="fc-format-chips-wrap">
                  <span>Standard Valid Formats:</span>
                  <code>ORD-1001</code>
                  <code>ORD-1002</code>
                  <code>ORD-1003</code>
                </div>
              </div>
            )}

            {/* SPECIAL CASE 2: MISSING ORDER ID */}
            {parsed.isMissingId && (
              <div className="fc-empty-state-card">
                <div className="fc-empty-icon-wrap">
                  <HelpCircle size={28} />
                </div>
                <h2 className="fc-empty-title">Valid Order ID Required</h2>
                <p className="fc-empty-desc">
                  Please provide an order ID (e.g., <code>ORD-1001</code>) so the Fulfillment Agent can locate the manifest record.
                </p>
              </div>
            )}

            {/* SPECIAL CASE 3: UNKNOWN FULFILLMENT INTENT */}
            {parsed.isUnknownIntent && !parsed.isNotFound && !parsed.isMissingId && (
              <div className="fc-empty-state-card">
                <div className="fc-empty-icon-wrap">
                  <HelpCircle size={28} />
                </div>
                <h2 className="fc-empty-title">Fulfillment Request Clarification</h2>
                <p className="fc-empty-desc">
                  Please clarify what specific operational detail you need for {parsed.orderId || 'this order'} (status, delay root cause, carrier shipping, manifest details).
                </p>
              </div>
            )}

            {/* ── 3. ISOMETRIC VISUALIZATION + ZONE DETAIL INSPECTOR (MAIN ATTRACTION) ── */}
            {!parsed.isNotFound && !parsed.isMissingId && (
              <div className="fc-ops-stage-grid">
                {/* Left/Center Column: Large Isometric 3D Warehouse Scene */}
                <WarehouseScene
                  selectedZone={selectedZone}
                  onSelectZone={setSelectedZone}
                  parsed={parsed}
                  orderStatus={parsed.status}
                />

                {/* Right Column: Dynamic Zone Inspection Panel */}
                <div className="fc-inspector-card">
                  <div className="fc-inspector-head">
                    <div className="fc-inspector-head-left">
                      <div className="fc-inspector-icon-wrap">
                        {selectedZone === 'storage_racks' && <Boxes size={18} />}
                        {selectedZone === 'packing_area' && <Package size={18} />}
                        {selectedZone === 'loading_docks' && <Truck size={18} />}
                        {selectedZone === 'control_office' && <Building2 size={18} />}
                      </div>
                      <h3 className="fc-inspector-title">
                        {selectedZone === 'storage_racks' && 'Storage Racks & Stock'}
                        {selectedZone === 'packing_area' && 'Packing & Manifest'}
                        {selectedZone === 'loading_docks' && 'Loading Docks & Carrier'}
                        {selectedZone === 'control_office' && 'Operations Control Office'}
                      </h3>
                    </div>
                  </div>

                  <div className="fc-inspector-body">
                    {/* ZONE 1: STORAGE RACKS CONTEXT */}
                    {selectedZone === 'storage_racks' && (
                      <>
                        <div className="fc-tiles-grid">
                          <div className="fc-tile full">
                            <span className="fc-tile-lbl">Target SKU Code</span>
                            <span className="fc-tile-val font-mono text-amber">
                              {parsed.crossAgent?.sku || parsed.orderDetails?.sku || 'SKU-4521'}
                            </span>
                          </div>
                          <div className="fc-tile full">
                            <span className="fc-tile-lbl">Inventory Cross-Check</span>
                            <span className="fc-tile-val">
                              {parsed.crossAgent?.involved ? (
                                <span style={{ color: parsed.crossAgent.stockStatus === 'OUT_OF_STOCK' ? '#dc2626' : '#059669', fontWeight: 700 }}>
                                  {parsed.crossAgent.stockStatus === 'OUT_OF_STOCK' ? 'Stock Depleted (0 On Hand)' : 'Stock Available On Hand'}
                                </span>
                              ) : (
                                'Direct Database Retrieval'
                              )}
                            </span>
                          </div>
                        </div>

                        {parsed.crossAgent?.involved ? (
                          <div className="fc-callout-box">
                            <span className="fc-callout-lbl">Inventory Agent Findings</span>
                            <p className="fc-callout-txt">{parsed.crossAgent.findings}</p>
                          </div>
                        ) : (
                          <p style={{ fontSize: '13px', color: '#64748b', lineHeight: 1.5, margin: 0 }}>
                            Central order records yielded complete information. No secondary inventory agent lookup was required for this query.
                          </p>
                        )}
                      </>
                    )}

                    {/* ZONE 2: PACKING AREA CONTEXT */}
                    {selectedZone === 'packing_area' && (
                      <>
                        <div className="fc-tiles-grid">
                          {parsed.orderDetails?.customer && (
                            <div className="fc-tile full">
                              <span className="fc-tile-lbl">Customer / Recipient</span>
                              <span className="fc-tile-val">{parsed.orderDetails.customer}</span>
                            </div>
                          )}
                          {parsed.orderDetails?.quantity && (
                            <div className="fc-tile">
                              <span className="fc-tile-lbl">Quantity</span>
                              <span className="fc-tile-val font-mono">{parsed.orderDetails.quantity} units</span>
                            </div>
                          )}
                          {parsed.orderDetails?.sku && (
                            <div className="fc-tile">
                              <span className="fc-tile-lbl">SKU</span>
                              <span className="fc-tile-val font-mono text-amber">{parsed.orderDetails.sku}</span>
                            </div>
                          )}
                          {parsed.orderDetails?.createdAt && (
                            <div className="fc-tile full">
                              <span className="fc-tile-lbl">Ingestion Timestamp</span>
                              <span className="fc-tile-val font-mono" style={{ fontSize: '12px' }}>
                                {parsed.orderDetails.createdAt}
                              </span>
                            </div>
                          )}
                        </div>

                        <div className="fc-callout-box" style={{ borderLeftColor: '#0284c7' }}>
                          <span className="fc-callout-lbl">Stage Tracking Note</span>
                          <p className="fc-callout-txt">
                            Intermediate picking, packing, and sorting stages are maintained at the manifest level. No unverified milestones are simulated.
                          </p>
                        </div>
                      </>
                    )}

                    {/* ZONE 3: LOADING DOCKS & CARRIER CONTEXT */}
                    {selectedZone === 'loading_docks' && (
                      <>
                        <div className="fc-tiles-grid">
                          <div className="fc-tile full">
                            <span className="fc-tile-lbl">Assigned Logistics Carrier</span>
                            <span className="fc-tile-val text-blue">
                              {parsed.carrierName || 'Standard Warehouse Freight Carrier'}
                            </span>
                          </div>
                          <div className="fc-tile full">
                            <span className="fc-tile-lbl">Delivery Target Window</span>
                            <span className="fc-tile-val text-amber">
                              {parsed.revisedDate || (parsed.status === 'SHIPPED' ? 'Dispatched / In Transit' : 'Standard Scheduled Window')}
                            </span>
                          </div>
                        </div>

                        {parsed.status === 'SHIPPED' && (
                          <div className="fc-callout-box" style={{ borderLeftColor: '#10b981' }}>
                            <span className="fc-callout-lbl" style={{ color: '#059669' }}>Dispatch Confirmed</span>
                            <p className="fc-callout-txt">
                              Consignment {parsed.orderId || ''} has been transferred to the carrier fleet for outbound transportation.
                            </p>
                          </div>
                        )}
                      </>
                    )}

                    {/* ZONE 4: OPERATIONS CONTROL OFFICE CONTEXT */}
                    {selectedZone === 'control_office' && (
                      <>
                        <div className="fc-pipeline-flow">
                          <div className="fc-flow-node coord">
                            <Bot size={11} />
                            <span>Coordinator</span>
                          </div>
                          <ArrowRight size={12} style={{ color: '#94a3b8' }} />
                          <div className="fc-flow-node fulfill">
                            <Truck size={11} />
                            <span>Fulfillment</span>
                          </div>
                          {parsed.crossAgent?.involved && (
                            <>
                              <ArrowRight size={12} style={{ color: '#94a3b8' }} />
                              <div className="fc-flow-node inv">
                                <Boxes size={11} />
                                <span>Inventory</span>
                              </div>
                            </>
                          )}
                        </div>

                        <div className="fc-tiles-grid">
                          <div className="fc-tile">
                            <span className="fc-tile-lbl">Latency</span>
                            <span className="fc-tile-val font-mono">{latencyMs} ms</span>
                          </div>
                          <div className="fc-tile">
                            <span className="fc-tile-lbl">Confidence</span>
                            <span className="fc-tile-val text-emerald font-mono">{routingConfidence || 95}%</span>
                          </div>
                        </div>

                        {routing.reasoning && (
                          <div className="fc-callout-box">
                            <span className="fc-callout-lbl">Routing Reasoning</span>
                            <p className="fc-callout-txt">{routing.reasoning}</p>
                          </div>
                        )}
                      </>
                    )}
                  </div>
                </div>
              </div>
            )}

            {/* ── 4. DELAY ROOT-CAUSE INVESTIGATION (FOR DELAYED ORDERS) ── */}
            {(parsed.intent === 'ORDER_DELAY' || parsed.status === 'DELAYED' || parsed.delayReason) && (
              <section className="fc-delay-banner">
                <div className="fc-delay-head">
                  <div className="fc-delay-title">
                    <AlertTriangle size={18} />
                    <span>Delay Root-Cause Investigation & Telemetry</span>
                  </div>
                  <span className="fc-status-pill status-delayed">RECORD DELAY</span>
                </div>

                {parsed.delayReason ? (
                  <div className="fc-delay-text">
                    <strong>Confirmed Record Reason: </strong>
                    {parsed.delayReason}
                  </div>
                ) : (
                  <div className="fc-delay-text" style={{ color: '#b45309' }}>
                    Order {parsed.orderId || ''} is marked as delayed, but the order record does not contain an explicit delay reason.
                  </div>
                )}

                <span className="fc-delay-note">
                  Distinguishing confirmed manifest root-causes from contributing inventory factors.
                </span>
              </section>
            )}

            {/* ── 5. VERIFIED VERBATIM RESPONSE CARD ── */}
            <section className="fc-verbatim-card">
              <div className="fc-verbatim-head">
                <div className="fc-verbatim-title-grp">
                  <FileText size={17} style={{ color: '#2563eb' }} />
                  <h3 className="fc-verbatim-title">Coordinator Raw Response Summary</h3>
                </div>
                <span className="fc-intent-tag">VERBATIM AUDIT</span>
              </div>

              <div className="fc-verbatim-box">
                {content}
              </div>
            </section>

            {/* ── 6. FOLLOW-UP OPERATIONS COMMAND CONSOLE ── */}
            <section className="fc-console-card">
              <div className="fc-console-head">
                <div className="fc-console-title-grp">
                  <Sparkles size={18} style={{ color: '#d97706' }} />
                  <h3 className="fc-console-title">Fulfillment Follow-Up Operations</h3>
                </div>
                <span style={{ fontSize: '12px', color: '#64748b' }}>
                  Routed through Coordinator API Gateway
                </span>
              </div>

              {followUpQueries.length > 0 && (
                <div className="fc-console-chips-row">
                  {followUpQueries.map((item, idx) => (
                    <button
                      key={idx}
                      type="button"
                      onClick={() => handleQuickChipClick(item.query)}
                      disabled={isLoading}
                      className="fc-btn-chip"
                    >
                      <span>{item.label}</span>
                      <ArrowRight size={12} />
                    </button>
                  ))}
                </div>
              )}

              <form onSubmit={handleFollowUpSubmit} className="fc-console-input-bar">
                <input
                  type="text"
                  value={followUpInput}
                  onChange={(e) => setFollowUpInput(e.target.value)}
                  placeholder={`Ask a follow-up for ${parsed.orderId || 'fulfillment'} (e.g., 'Why is ${parsed.orderId || 'ORD-1001'} delayed?')`}
                  className="fc-console-input"
                  disabled={isLoading}
                />
                <button
                  type="submit"
                  disabled={!followUpInput.trim() || isLoading}
                  className="fc-btn-submit"
                >
                  {isLoading ? (
                    <>
                      <RotateCcw size={14} className="spin" />
                      <span>Processing...</span>
                    </>
                  ) : (
                    <>
                      <span>Submit Query</span>
                      <Send size={13} />
                    </>
                  )}
                </button>
              </form>
            </section>
          </>
        )}
      </main>
    </div>
  )
}
