import React, { useState } from 'react'
import {
  Truck,
  Package,
  PackageCheck,
  Clock,
  AlertTriangle,
  CheckCircle2,
  Search,
  Layers,
  Bot,
  Calendar,
  Copy,
  Check,
  ArrowRight,
  Boxes,
  HelpCircle,
  Activity,
  FileText
} from 'lucide-react'

/**
 * Parses raw fulfillment agent text responses safely into structured fields.
 * Fails gracefully without throwing errors or creating fake data.
 */
function parseFulfillmentContent(content = '', fulfillmentDetails = {}, routing = {}) {
  const text = String(content || '')
  
  // 1. Order ID resolution
  let orderId = fulfillmentDetails?.order_id || null
  if (!orderId) {
    const match = text.match(/\b(ORD-\d+)\b/i)
    if (match) orderId = match[1].toUpperCase()
  }

  // 2. Intent resolution
  const intent = fulfillmentDetails?.intent || routing?.intent || 'ORDER_STATUS'

  // 3. Special state flags
  const isNotFound = /not found in the system/i.test(text)
  const isMissingId = /provide a valid order ID/i.test(text)
  const isUnknownIntent = intent === 'UNKNOWN_FULFILLMENT' || /could not confidently determine your fulfillment request/i.test(text)

  // 4. Status determination
  let status = null
  if (isNotFound) {
    status = 'NOT_FOUND'
  } else if (isMissingId) {
    status = 'MISSING_ID'
  } else if (/is currently delayed/i.test(text) || /status: delayed/i.test(text)) {
    status = 'DELAYED'
  } else if (/marked as shipped/i.test(text) || /is currently shipped/i.test(text) || /status: shipped/i.test(text)) {
    status = 'SHIPPED'
  } else if (/is currently pending/i.test(text) || /status: pending/i.test(text)) {
    status = 'PENDING'
  } else if (/is currently cancelled/i.test(text) || /status: cancelled/i.test(text)) {
    status = 'CANCELLED'
  }

  // 5. Delay Analysis Fields
  let delayReason = null
  let carrierName = null
  let revisedDate = null

  const reasonMatch = text.match(/Reason:\s*([^.\n]+)/i)
  if (reasonMatch) delayReason = reasonMatch[1].trim()

  const carrierMatch = text.match(/Carrier:\s*([^.\n]+)/i)
  if (carrierMatch) carrierName = carrierMatch[1].trim()

  const dateMatch = text.match(/Revised delivery date:\s*([^.\n]+)/i)
  if (dateMatch) revisedDate = dateMatch[1].trim()

  // 6. Cross-Agent Inventory Investigation Detection
  let crossAgent = null
  const skuMatch = text.match(/\b(SKU-\d+)\b/i)
  const isOutOfStock = /is currently out of stock/i.test(text) || /stock: 0/i.test(text)
  const isStockAvailable = /currently has stock available/i.test(text)

  if (isOutOfStock && skuMatch) {
    crossAgent = {
      involved: true,
      sku: skuMatch[1].toUpperCase(),
      stockStatus: 'OUT_OF_STOCK',
      findings: 'Inventory investigation confirmed zero stock on hand, contributing to dispatch delay.'
    }
  } else if (isStockAvailable && skuMatch) {
    crossAgent = {
      involved: true,
      sku: skuMatch[1].toUpperCase(),
      stockStatus: 'IN_STOCK',
      findings: 'Inventory investigation confirmed stock is available. Delay is related to logistics/carrier bottlenecks.'
    }
  }

  // 7. Order Details Fields
  let orderDetails = null
  if (intent === 'ORDER_DETAILS' && !isNotFound) {
    const custMatch = text.match(/Customer:\s*([^\n]+)/i)
    const skuDetailMatch = text.match(/SKU:\s*([^\n]+)/i)
    const qtyMatch = text.match(/Quantity:\s*([^\n]+)/i)
    const statusDetailMatch = text.match(/Status:\s*([^\n]+)/i)
    const createdMatch = text.match(/Created At:\s*([^\n]+)/i)

    if (custMatch || skuDetailMatch || qtyMatch) {
      orderDetails = {
        customer: custMatch ? custMatch[1].trim() : null,
        sku: skuDetailMatch ? skuDetailMatch[1].trim() : null,
        quantity: qtyMatch ? qtyMatch[1].trim() : null,
        status: statusDetailMatch ? statusDetailMatch[1].trim() : null,
        createdAt: createdMatch ? createdMatch[1].trim().slice(0, 19) : null
      }
    }
  }

  return {
    orderId,
    intent,
    status,
    isNotFound,
    isMissingId,
    isUnknownIntent,
    delayReason,
    carrierName,
    revisedDate,
    crossAgent,
    orderDetails
  }
}

export default function FulfillmentCard({
  message,
  onSendQuery,
  onInspectOrder
}) {
  const [copied, setCopied] = useState(false)

  const content = message?.content || ''
  const fulfillmentDetails = message?.fulfillment_details || message?.metadata?.fulfillment_details || {}
  const routing = message?.routing || message?.metadata?.routing || {}
  const confidence = routing?.confidence ? Math.round(routing.confidence * 100) : null

  const parsed = parseFulfillmentContent(content, fulfillmentDetails, routing)

  const copyOrderId = (e) => {
    e.stopPropagation()
    if (!parsed.orderId) return
    navigator.clipboard.writeText(parsed.orderId)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  // Generate contextual follow-up query suggestions
  const getFollowUpQueries = () => {
    if (!parsed.orderId || parsed.isNotFound || parsed.isMissingId) {
      return [
        { label: 'Check Status of ORD-1001', query: 'What is the status of ORD-1001?' },
        { label: 'Investigate Delay on ORD-1001', query: 'Why is ORD-1001 delayed?' },
        { label: 'Check Shipped Order ORD-1003', query: 'Has ORD-1003 shipped?' }
      ]
    }

    const followUps = []
    if (parsed.intent !== 'ORDER_STATUS') {
      followUps.push({
        label: `Order Status for ${parsed.orderId}`,
        query: `What is the status of ${parsed.orderId}?`
      })
    }
    if (parsed.intent !== 'ORDER_DELAY' && parsed.status === 'DELAYED') {
      followUps.push({
        label: `Investigate Delay (${parsed.orderId})`,
        query: `Why is ${parsed.orderId} delayed?`
      })
    }
    if (parsed.intent !== 'ORDER_DETAILS') {
      followUps.push({
        label: `Show Details for ${parsed.orderId}`,
        query: `Show me details for ${parsed.orderId}`
      })
    }
    if (parsed.intent !== 'SHIPPING_STATUS') {
      followUps.push({
        label: `Check Shipping for ${parsed.orderId}`,
        query: `Has ${parsed.orderId} shipped?`
      })
    }
    return followUps.slice(0, 3)
  }

  const followUpQueries = getFollowUpQueries()

  // Format Status Badge
  const renderStatusBadge = () => {
    switch (parsed.status) {
      case 'DELAYED':
        return (
          <span className="hud-status-badge badge-coral">
            <AlertTriangle size={11} />
            <span>DELAYED</span>
          </span>
        )
      case 'SHIPPED':
        return (
          <span className="hud-status-badge badge-emerald">
            <CheckCircle2 size={11} />
            <span>SHIPPED</span>
          </span>
        )
      case 'PENDING':
        return (
          <span className="hud-status-badge badge-blue">
            <Clock size={11} />
            <span>PENDING</span>
          </span>
        )
      case 'CANCELLED':
        return (
          <span className="hud-status-badge badge-muted">
            <span>CANCELLED</span>
          </span>
        )
      default:
        return null
    }
  }

  // Format human-readable Intent Label
  const formatIntentLabel = (intentStr) => {
    switch (intentStr) {
      case 'ORDER_DELAY':
        return 'Order Delay Investigation'
      case 'ORDER_DETAILS':
        return 'Order Manifest Details'
      case 'SHIPPING_STATUS':
        return 'Dispatch & Carrier Status'
      case 'FULFILLMENT_PROGRESS':
        return 'Fulfillment Stage Tracking'
      case 'ORDER_STATUS':
        return 'Order Status Ingestion'
      case 'UNKNOWN_FULFILLMENT':
        return 'Fulfillment Request Clarification'
      default:
        return 'Fulfillment Query'
    }
  }

  return (
    <div className="fulfillment-card-container">
      {/* ── CARD HEADER ── */}
      <div className="fulfillment-card-header">
        <div className="fulfillment-header-left">
          <div className="agent-identity-badge">
            <Truck size={14} className="text-blue" />
            <span className="agent-identity-title">FULFILLMENT AGENT</span>
          </div>
          {parsed.orderId && (
            <div className="fulfillment-order-chip" title="Order Identifier">
              <Package size={12} className="text-amber" />
              <span className="order-id-text">{parsed.orderId}</span>
              <button
                type="button"
                onClick={copyOrderId}
                className="btn-mini-copy"
                title="Copy Order ID"
                aria-label="Copy Order ID"
              >
                {copied ? <Check size={11} className="text-emerald" /> : <Copy size={11} />}
              </button>
            </div>
          )}
        </div>

        <div className="fulfillment-header-right">
          {renderStatusBadge()}
          {confidence !== null && (
            <span className="confidence-chip" title="Coordinator Routing Confidence">
              {confidence}% match
            </span>
          )}
        </div>
      </div>

      {/* ── CARD BODY (INTENT-SPECIFIC) ── */}
      <div className="fulfillment-card-body">
        {/* State 1: Order Not Found */}
        {parsed.isNotFound && (
          <div className="fulfillment-state-box state-not-found">
            <div className="state-box-header">
              <Search size={15} className="text-coral" />
              <strong>Order Not Found in Registry</strong>
            </div>
            <p className="state-box-desc">
              The requested identifier <code>{parsed.orderId || 'unknown'}</code> was not found in the active database.
            </p>
            <div className="format-hint">
              <span>Standard Order Format:</span>
              <code>ORD-1001</code>
              <code>ORD-1002</code>
              <code>ORD-1003</code>
            </div>
          </div>
        )}

        {/* State 2: Missing / Invalid Order ID */}
        {parsed.isMissingId && (
          <div className="fulfillment-state-box state-missing-id">
            <div className="state-box-header">
              <HelpCircle size={15} className="text-amber" />
              <strong>Valid Order ID Required</strong>
            </div>
            <p className="state-box-desc">
              Please specify an order ID (e.g., <code>ORD-1001</code>) so the Fulfillment Agent can retrieve the record.
            </p>
          </div>
        )}

        {/* State 3: Unknown / Clarification Intent */}
        {parsed.isUnknownIntent && !parsed.isNotFound && !parsed.isMissingId && (
          <div className="fulfillment-state-box state-clarification">
            <div className="state-box-header">
              <HelpCircle size={15} className="text-blue" />
              <strong>Fulfillment Clarification Needed</strong>
            </div>
            <p className="state-box-desc">
              Tell me what specific operational detail you need for {parsed.orderId || 'this order'}:
            </p>
          </div>
        )}

        {/* State 4: ORDER_DELAY Rich Investigation */}
        {!parsed.isNotFound && !parsed.isMissingId && parsed.intent === 'ORDER_DELAY' && (
          <div className="delay-investigation-section">
            {parsed.delayReason && (
              <div className="delay-root-cause-banner">
                <div className="banner-title-row">
                  <AlertTriangle size={14} className="text-coral" />
                  <span className="banner-title">Delay Root Cause Analysis</span>
                </div>
                <div className="banner-reason-text">{parsed.delayReason}</div>
              </div>
            )}

            {/* Carrier & Revised ETA Grid */}
            {(parsed.carrierName || parsed.revisedDate) && (
              <div className="fulfillment-meta-grid">
                {parsed.carrierName && (
                  <div className="meta-tile">
                    <span className="meta-tile-label">ASSIGNED CARRIER FLEET</span>
                    <div className="meta-tile-value">
                      <Truck size={13} className="text-blue" />
                      <span>{parsed.carrierName}</span>
                    </div>
                  </div>
                )}
                {parsed.revisedDate && (
                  <div className="meta-tile">
                    <span className="meta-tile-label">REVISED DELIVERY TARGET</span>
                    <div className="meta-tile-value">
                      <Calendar size={13} className="text-amber" />
                      <span>{parsed.revisedDate}</span>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Cross-Agent Inventory Investigation Banner (Strictly when genuine) */}
            {parsed.crossAgent && parsed.crossAgent.involved && (
              <div className="cross-agent-investigation-card">
                <div className="collaboration-stepper-header">
                  <div className="stepper-title-wrap">
                    <Bot size={13} className="text-amber" />
                    <span>Cross-Agent Stock Investigation</span>
                  </div>
                  <span className={`hud-status-badge ${parsed.crossAgent.stockStatus === 'OUT_OF_STOCK' ? 'badge-coral' : 'badge-emerald'}`}>
                    {parsed.crossAgent.stockStatus === 'OUT_OF_STOCK' ? 'STOCK DEPLETED' : 'STOCK AVAILABLE'}
                  </span>
                </div>

                {/* Visual Collaboration Stepper */}
                <div className="agent-collaboration-stepper">
                  <div className="stepper-node">
                    <span className="node-icon">🤖</span>
                    <span className="node-name">Coordinator</span>
                  </div>
                  <div className="stepper-arrow"><ArrowRight size={12} /></div>
                  <div className="stepper-node active">
                    <Truck size={12} className="text-blue" />
                    <span className="node-name">Fulfillment</span>
                  </div>
                  <div className="stepper-arrow"><ArrowRight size={12} /></div>
                  <div className="stepper-node active">
                    <Boxes size={12} className="text-amber" />
                    <span className="node-name">Inventory Agent</span>
                  </div>
                </div>

                <div className="investigation-findings-text">
                  <strong>Findings for {parsed.crossAgent.sku}:</strong> {parsed.crossAgent.findings}
                </div>
              </div>
            )}
          </div>
        )}

        {/* State 5: ORDER_DETAILS Grid */}
        {!parsed.isNotFound && !parsed.isMissingId && parsed.orderDetails && (
          <div className="order-details-spec-grid">
            {parsed.orderDetails.customer && (
              <div className="meta-tile">
                <span className="meta-tile-label">CUSTOMER / RECIPIENT</span>
                <span className="meta-tile-value text-light font-medium">
                  {parsed.orderDetails.customer}
                </span>
              </div>
            )}
            {parsed.orderDetails.sku && (
              <div className="meta-tile">
                <span className="meta-tile-label">ORDERED SKU</span>
                <span className="meta-tile-value text-amber font-mono font-bold">
                  {parsed.orderDetails.sku}
                </span>
              </div>
            )}
            {parsed.orderDetails.quantity && (
              <div className="meta-tile">
                <span className="meta-tile-label">QUANTITY</span>
                <span className="meta-tile-value text-light font-mono">
                  {parsed.orderDetails.quantity} units
                </span>
              </div>
            )}
            {parsed.orderDetails.createdAt && (
              <div className="meta-tile">
                <span className="meta-tile-label">CREATED AT</span>
                <span className="meta-tile-value text-muted font-mono text-xs">
                  {parsed.orderDetails.createdAt}
                </span>
              </div>
            )}
          </div>
        )}

        {/* State 6: FULFILLMENT_PROGRESS note */}
        {!parsed.isNotFound && !parsed.isMissingId && parsed.intent === 'FULFILLMENT_PROGRESS' && (
          <div className="fulfillment-progress-note-box">
            <div className="note-title-row">
              <Activity size={13} className="text-blue" />
              <span>Current Status: <strong>{parsed.status || 'Active'}</strong></span>
            </div>
            <p className="note-body">
              Detailed intermediate stage milestones (picking, packing, staging) are not tracked in the current order manifest.
            </p>
          </div>
        )}

        {/* ── ARTIFACT INSPECTION TRIGGER ── */}
        {onInspectOrder && parsed.orderId && !parsed.isNotFound && (
          <button
            type="button"
            onClick={() => onInspectOrder({ id: parsed.orderId, parsed })}
            className="btn-inspect-fulfillment-artifact"
            title="Inspect full fulfillment telemetry in side panel"
          >
            <Layers size={13} className="text-blue" />
            <span>Inspect Fulfillment Telemetry & Order Records</span>
          </button>
        )}
      </div>

      {/* ── CONTEXTUAL FOLLOW-UP ACTION CHIPS ── */}
      {followUpQueries.length > 0 && onSendQuery && (
        <div className="fulfillment-followup-container">
          <div className="followup-label">Suggested Next Steps:</div>
          <div className="followup-chips-row">
            {followUpQueries.map((item, idx) => (
              <button
                key={idx}
                type="button"
                className="btn-followup-chip"
                onClick={() => onSendQuery(item.query)}
              >
                <span>{item.label}</span>
                <ArrowRight size={10} className="chip-arrow" />
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
