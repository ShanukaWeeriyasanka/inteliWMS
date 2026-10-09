import React from 'react'
import {
  Truck,
  ExternalLink,
  Package,
  AlertTriangle,
  CheckCircle2,
  Clock
} from 'lucide-react'
import { parseFulfillmentContent } from '../../utils/fulfillmentParser'

/**
 * FulfillmentActionCard — Compact, clean action link for Fulfillment Agent in chat.
 */
export default function FulfillmentCard({
  message,
  onOpenFulfillmentDashboard
}) {
  const content = message?.content || ''
  const fulfillmentDetails =
    message?.fulfillment_details || message?.metadata?.fulfillment_details || {}
  const routing = message?.routing || message?.metadata?.routing || {}

  const parsed = parseFulfillmentContent(content, fulfillmentDetails, routing)

  return (
    <div className="fulfillment-chat-action-container">
      <button
        type="button"
        onClick={() => onOpenFulfillmentDashboard && onOpenFulfillmentDashboard(message)}
        className="btn-view-fulfillment-dashboard"
        title="Open dedicated Fulfillment Operations Control Center"
        aria-label={`Open Fulfillment Dashboard${parsed.orderId ? ` for ${parsed.orderId}` : ''}`}
      >
        <span className="btn-icon-wrapper">
          <Truck size={15} className="btn-action-icon" />
        </span>
        <span className="btn-text">View Fulfillment Dashboard</span>
        {parsed.orderId && (
          <span className="btn-order-badge">{parsed.orderId}</span>
        )}
        <ExternalLink size={13} className="btn-ext-icon" />
      </button>
    </div>
  )
}
