import React, { useState, useEffect } from 'react'
import {
  ArrowLeft,
  Truck,
  Package,
  Clock,
  AlertTriangle,
  CheckCircle2,
  Search,
  Copy,
  Check,
  FileText,
  Boxes,
  HelpCircle,
  Info
} from 'lucide-react'
import WarehouseScene from '../components/fulfillment/WarehouseScene'
import { parseFulfillmentContent } from '../utils/fulfillmentParser'
import './FulfillmentDashboard.css'

export default function FulfillmentDashboard({
  selectedMessage,
  currentUser,
  onBackToChat
}) {
  const [copied, setCopied] = useState(false)

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

  const parsed = parseFulfillmentContent(content, fulfillmentDetails, routing)

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

  const copyOrderId = (e) => {
    e?.stopPropagation()
    if (!parsed.orderId) return
    navigator.clipboard.writeText(parsed.orderId)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  // Format Semantic Status Badge
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
      {/* ── SECTION A: COMPACT HEADER ── */}
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
              <span className="fc-brand-title">Fulfillment Control Center</span>
              <span className="fc-brand-sub">Warehouse Operations & Logistics</span>
            </div>
          </div>
        </div>

        <div className="fc-nav-right">
          {parsed.orderId && !parsed.isNotFound && !parsed.isMissingId && (
            <div className="fc-order-chip" title="Active Order ID">
              <Package size={14} />
              <span>Order: <strong>{parsed.orderId}</strong></span>
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
        </div>
      </header>

      {/* ── MAIN DASHBOARD CONTAINER ── */}
      <main className="fc-main-container">
        {/* STANDBY / EMPTY STATE */}
        {!selectedMessage && (
          <div className="fc-empty-state-card">
            <div className="fc-empty-icon-wrap">
              <Truck size={28} />
            </div>
            <h2 className="fc-empty-title">Fulfillment Control Center Standby</h2>
            <p className="fc-empty-desc">
              No active fulfillment query is selected. Enter an order inquiry in chat (e.g. status, delays, carrier shipping) to inspect live operational data.
            </p>
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

        {/* ORDER NOT FOUND STATE */}
        {selectedMessage && parsed.isNotFound && (
          <div className="fc-empty-state-card">
            <div className="fc-empty-icon-wrap error">
              <Search size={28} />
            </div>
            <h2 className="fc-empty-title">Order Not Found in Registry</h2>
            <p className="fc-empty-desc">
              The requested order ID <code>{parsed.orderId || 'unknown'}</code> was not found in the warehouse database.
            </p>
            <div className="fc-format-chips-wrap">
              <span>Standard Valid Formats:</span>
              <code>ORD-1001</code>
              <code>ORD-1002</code>
              <code>ORD-1003</code>
            </div>
          </div>
        )}

        {/* MISSING ORDER ID STATE */}
        {selectedMessage && parsed.isMissingId && (
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

        {/* ACTIVE FULFILLMENT RESPONSE */}
        {selectedMessage && !parsed.isNotFound && !parsed.isMissingId && (
          <div className="fc-ops-stage-grid">
            {/* ── SECTION B: EXISTING WAREHOUSE VISUALIZATION ── */}
            <WarehouseScene
              selectedZone={selectedZone}
              onSelectZone={setSelectedZone}
              parsed={parsed}
              orderStatus={parsed.status}
            />

            {/* ── SECTION C: QUERY-SPECIFIC INFORMATION PANEL ── */}
            <div className="fc-info-panel-card">
              <div className="fc-panel-header">
                <div className="fc-panel-header-left">
                  <div className="fc-panel-icon-wrap">
                    {parsed.intent === 'ORDER_STATUS' && <Clock size={18} />}
                    {parsed.intent === 'ORDER_DELAY' && <AlertTriangle size={18} />}
                    {parsed.intent === 'ORDER_DETAILS' && <FileText size={18} />}
                    {parsed.intent === 'SHIPPING_STATUS' && <Truck size={18} />}
                    {parsed.intent === 'FULFILLMENT_PROGRESS' && <Boxes size={18} />}
                    {parsed.intent === 'UNKNOWN_FULFILLMENT' && <HelpCircle size={18} />}
                  </div>
                  <div>
                    <h3 className="fc-panel-title">
                      {parsed.intent === 'ORDER_STATUS' && 'Order Status Summary'}
                      {parsed.intent === 'ORDER_DELAY' && 'Order Delay Investigation'}
                      {parsed.intent === 'ORDER_DETAILS' && 'Order Manifest Details'}
                      {parsed.intent === 'SHIPPING_STATUS' && 'Shipping & Carrier Dispatch'}
                      {parsed.intent === 'FULFILLMENT_PROGRESS' && 'Fulfillment Progress'}
                      {parsed.intent === 'UNKNOWN_FULFILLMENT' && 'Fulfillment Clarification'}
                    </h3>
                    <span className="fc-panel-subtitle">
                      {parsed.orderId ? `Operational summary for ${parsed.orderId}` : 'Warehouse fulfillment query'}
                    </span>
                  </div>
                </div>
              </div>

              <div className="fc-panel-body">
                {/* 1. ORDER_STATUS INTENT */}
                {parsed.intent === 'ORDER_STATUS' && (
                  <div className="fc-panel-content">
                    <div className="fc-data-grid">
                      <div className="fc-data-field">
                        <span className="fc-field-label">Order ID</span>
                        <span className="fc-field-value font-mono text-blue">{parsed.orderId || 'Unassigned'}</span>
                      </div>
                      <div className="fc-data-field">
                        <span className="fc-field-label">Current Status</span>
                        <span className="fc-field-value">{renderStatusBadge()}</span>
                      </div>
                    </div>

                    <div className="fc-factual-summary">
                      <span className="fc-summary-label">Status Explanation</span>
                      <p className="fc-summary-text">
                        {parsed.status === 'DELAYED' && `Order ${parsed.orderId || ''} is currently delayed in warehouse fulfillment.`}
                        {parsed.status === 'SHIPPED' && `Order ${parsed.orderId || ''} has been processed and is currently marked as shipped.`}
                        {parsed.status === 'PENDING' && `Order ${parsed.orderId || ''} is currently pending processing in the fulfillment queue.`}
                        {parsed.status === 'CANCELLED' && `Order ${parsed.orderId || ''} is currently marked as cancelled.`}
                        {!['DELAYED', 'SHIPPED', 'PENDING', 'CANCELLED'].includes(parsed.status) && (parsed.status ? `Order ${parsed.orderId || ''} is currently ${parsed.status.toLowerCase()}.` : `Order record ${parsed.orderId || ''} is active.`)}
                      </p>
                    </div>
                  </div>
                )}

                {/* 2. ORDER_DELAY INTENT */}
                {parsed.intent === 'ORDER_DELAY' && (
                  <div className="fc-panel-content">
                    <div className="fc-data-grid">
                      <div className="fc-data-field">
                        <span className="fc-field-label">Order ID</span>
                        <span className="fc-field-value font-mono text-blue">{parsed.orderId || 'Unassigned'}</span>
                      </div>
                      <div className="fc-data-field">
                        <span className="fc-field-label">Current Status</span>
                        <span className="fc-field-value">{renderStatusBadge()}</span>
                      </div>
                      {parsed.carrierName && (
                        <div className="fc-data-field">
                          <span className="fc-field-label">Carrier</span>
                          <span className="fc-field-value text-blue">{parsed.carrierName}</span>
                        </div>
                      )}
                      {parsed.revisedDate && (
                        <div className="fc-data-field">
                          <span className="fc-field-label">Revised Delivery Date</span>
                          <span className="fc-field-value text-coral">{parsed.revisedDate}</span>
                        </div>
                      )}
                      {parsed.crossAgent?.involved && parsed.crossAgent.sku && (
                        <div className="fc-data-field">
                          <span className="fc-field-label">Related SKU</span>
                          <span className="fc-field-value font-mono text-amber">{parsed.crossAgent.sku}</span>
                        </div>
                      )}
                      {parsed.crossAgent?.involved && (
                        <div className="fc-data-field">
                          <span className="fc-field-label">Stock Availability</span>
                          <span className="fc-field-value">
                            <span className={`fc-status-pill ${parsed.crossAgent.stockStatus === 'OUT_OF_STOCK' ? 'status-delayed' : 'status-shipped'}`}>
                              {parsed.crossAgent.stockStatus === 'OUT_OF_STOCK' ? 'Out of Stock (0 units)' : 'Stock Available'}
                            </span>
                          </span>
                        </div>
                      )}
                    </div>

                    {/* Recorded Delay Reason vs Cross-Agent Stock Investigation */}
                    {parsed.delayReason ? (
                      <div className="fc-factual-summary delay-highlight">
                        <span className="fc-summary-label">Recorded Delay Reason</span>
                        <p className="fc-summary-text font-semibold">{parsed.delayReason}</p>
                      </div>
                    ) : parsed.crossAgent?.involved ? (
                      <div className="fc-factual-summary delay-inventory-note">
                        <span className="fc-summary-label">Inventory Investigation Note</span>
                        <p className="fc-summary-text">
                          Inventory investigation confirmed {parsed.crossAgent.stockStatus === 'OUT_OF_STOCK' ? `zero stock on hand for SKU ${parsed.crossAgent.sku}. This stock shortage may be contributing to the delay.` : `stock is available for SKU ${parsed.crossAgent.sku}.`}
                        </p>
                        <div className="fc-notice-pill">
                          <Info size={13} />
                          <span>No confirmed delay reason is recorded in the order manifest.</span>
                        </div>
                      </div>
                    ) : (
                      <div className="fc-factual-summary">
                        <span className="fc-summary-label">Delay Status Note</span>
                        <p className="fc-summary-text text-muted">
                          Order {parsed.orderId || ''} is marked as delayed, but no confirmed delay reason is recorded in the order manifest.
                        </p>
                      </div>
                    )}
                  </div>
                )}

                {/* 3. ORDER_DETAILS INTENT */}
                {parsed.intent === 'ORDER_DETAILS' && (
                  <div className="fc-panel-content">
                    <div className="fc-data-grid">
                      <div className="fc-data-field">
                        <span className="fc-field-label">Order ID</span>
                        <span className="fc-field-value font-mono text-blue">{parsed.orderId || 'Unassigned'}</span>
                      </div>
                      {parsed.orderDetails?.customer && (
                        <div className="fc-data-field">
                          <span className="fc-field-label">Customer Name</span>
                          <span className="fc-field-value">{parsed.orderDetails.customer}</span>
                        </div>
                      )}
                      {parsed.orderDetails?.sku && (
                        <div className="fc-data-field">
                          <span className="fc-field-label">SKU</span>
                          <span className="fc-field-value font-mono text-amber">{parsed.orderDetails.sku}</span>
                        </div>
                      )}
                      {parsed.orderDetails?.quantity && (
                        <div className="fc-data-field">
                          <span className="fc-field-label">Quantity</span>
                          <span className="fc-field-value font-mono">{parsed.orderDetails.quantity} units</span>
                        </div>
                      )}
                      <div className="fc-data-field">
                        <span className="fc-field-label">Order Status</span>
                        <span className="fc-field-value">{renderStatusBadge()}</span>
                      </div>
                      {parsed.orderDetails?.createdAt && (
                        <div className="fc-data-field">
                          <span className="fc-field-label">Created Date</span>
                          <span className="fc-field-value font-mono">{parsed.orderDetails.createdAt}</span>
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {/* 4. SHIPPING_STATUS INTENT */}
                {parsed.intent === 'SHIPPING_STATUS' && (
                  <div className="fc-panel-content">
                    <div className="fc-data-grid">
                      <div className="fc-data-field">
                        <span className="fc-field-label">Order ID</span>
                        <span className="fc-field-value font-mono text-blue">{parsed.orderId || 'Unassigned'}</span>
                      </div>
                      <div className="fc-data-field">
                        <span className="fc-field-label">Shipping Status</span>
                        <span className="fc-field-value">{renderStatusBadge()}</span>
                      </div>
                      {parsed.carrierName && (
                        <div className="fc-data-field">
                          <span className="fc-field-label">Assigned Carrier</span>
                          <span className="fc-field-value font-semibold text-blue">{parsed.carrierName}</span>
                        </div>
                      )}
                    </div>

                    <div className="fc-factual-summary">
                      <span className="fc-summary-label">Shipping Explanation</span>
                      <p className="fc-summary-text">
                        {parsed.status === 'SHIPPED'
                          ? `Consignment ${parsed.orderId || ''} is marked as shipped${parsed.carrierName ? ` and handed over to ${parsed.carrierName}` : ''}.`
                          : `Consignment ${parsed.orderId || ''} is currently ${parsed.status ? parsed.status.toLowerCase() : 'in progress'} and has not yet been dispatched.`}
                      </p>
                    </div>
                  </div>
                )}

                {/* 5. FULFILLMENT_PROGRESS INTENT */}
                {parsed.intent === 'FULFILLMENT_PROGRESS' && (
                  <div className="fc-panel-content">
                    <div className="fc-data-grid">
                      <div className="fc-data-field">
                        <span className="fc-field-label">Order ID</span>
                        <span className="fc-field-value font-mono text-blue">{parsed.orderId || 'Unassigned'}</span>
                      </div>
                      <div className="fc-data-field">
                        <span className="fc-field-label">Current Status</span>
                        <span className="fc-field-value">{renderStatusBadge()}</span>
                      </div>
                    </div>

                    <div className="fc-factual-summary">
                      <span className="fc-summary-label">Fulfillment Summary</span>
                      <p className="fc-summary-text">
                        {parsed.status === 'SHIPPED'
                          ? `Fulfillment is complete for order ${parsed.orderId || ''}. Consignment is dispatched.`
                          : parsed.status === 'DELAYED'
                          ? `Fulfillment for order ${parsed.orderId || ''} is currently delayed. Processing is pending resolution.`
                          : `Order ${parsed.orderId || ''} is currently in ${parsed.status ? parsed.status.toLowerCase() : 'processing'} status in the warehouse fulfillment workflow.`}
                      </p>
                    </div>
                  </div>
                )}

                {/* 6. UNKNOWN_FULFILLMENT / FALLBACK */}
                {(parsed.intent === 'UNKNOWN_FULFILLMENT' || (!['ORDER_STATUS', 'ORDER_DELAY', 'ORDER_DETAILS', 'SHIPPING_STATUS', 'FULFILLMENT_PROGRESS'].includes(parsed.intent))) && (
                  <div className="fc-panel-content">
                    <div className="fc-data-grid">
                      {parsed.orderId && (
                        <div className="fc-data-field">
                          <span className="fc-field-label">Order ID</span>
                          <span className="fc-field-value font-mono text-blue">{parsed.orderId}</span>
                        </div>
                      )}
                      {parsed.status && (
                        <div className="fc-data-field">
                          <span className="fc-field-label">Known Status</span>
                          <span className="fc-field-value">{renderStatusBadge()}</span>
                        </div>
                      )}
                    </div>

                    <div className="fc-factual-summary">
                      <span className="fc-summary-label">Clarification</span>
                      <p className="fc-summary-text">
                        Please specify what operational detail you need for {parsed.orderId || 'this order'} (e.g., status inquiry, delay root cause, carrier shipping, or manifest details).
                      </p>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  )
}
