// Turns /query responses and stored thread messages into chat UI messages.
// Live answers and reloaded history go through the same mapping, so a conversation
// looks the same after a refresh. Inventory cards are built only from the items the
// backend returned — never from placeholder values.

import { splitAttachedQuery } from './attachments'

let seq = 0
const nextId = (prefix) => `${prefix}-${Date.now()}-${(seq += 1)}`

// "inventory_agent" → "INVENTORY" (the UI adds "AGENT": "via INVENTORY AGENT")
export function agentLabel(target) {
  return String(target || '').trim().replace(/_agent$/i, '').replace(/_+/g, ' ').trim().toUpperCase()
}

export function isFulfillmentMessage(message) {
  if (!message || message.role !== 'assistant') return false
  if (message.status === 'blocked' || message.status === 'restricted' || message.status === 'mismatch' || message.status === 'error') return false
  if (message.error_code === 'PLAN_RESTRICTED' || message.error_code === 'SPECIALIST_MISMATCH') return false
  const meta = message.metadata || {}
  const routing = message.routing || meta.routing || {}
  if (routing.status === 'blocked' || routing.status === 'restricted' || routing.status === 'mismatch' || routing.status === 'error') return false
  if (routing.error_code === 'PLAN_RESTRICTED' || routing.error_code === 'SPECIALIST_MISMATCH') return false

  const target = routing.target_agent || message.agent_used || meta.agent_used
  const fulfillmentDetails = message.fulfillment_details || meta.fulfillment_details
  if (target === 'fulfillment_agent' || !!fulfillmentDetails) {
    if (fulfillmentDetails && fulfillmentDetails.success === false) {
      return false
    }
    return true
  }
  return false
}

export function skuDataFromItem(item) {
  if (!item) return null
  return {
    sku: item.sku,
    name: item.name,
    location: item.location,
    aisle: item.aisle ?? null,
    shelf: item.shelf ?? null,
    tier: item.tier ?? null,
    bay: item.bay ?? null,
    stock: `${item.quantity_on_hand} ${item.unit} (${String(item.status || '').replace(/_/g, ' ')})`,
    available: item.available_quantity,
    status: item.status,
    rawItem: item,
  }
}

export function toAssistantMessage(res, { text = '', id = nextId('a'), timestamp = new Date(), origin = 'live' } = {}) {
  // Live block responses have status "error"; stored ones are saved with status "blocked"
  if ((res.status === 'error' || res.status === 'blocked') && res.error_code === 'PROMPT_INJECTION_DETECTED') {
    const reason = res.message || res.response
    return {
      id,
      role: 'assistant',
      status: 'blocked',
      content: reason || 'Prompt injection attempt detected and neutralized by security shield.',
      routing: { status: 'blocked', target_agent: 'security_sanitizer', rule: reason },
      timestamp,
      origin,
    }
  }

  // Client errors (e.g. an empty question) are plain error messages, not security blocks
  if (res.status === 'error' && res.error_code === 'EMPTY_QUERY') {
    return {
      id,
      role: 'assistant',
      status: 'error',
      content: res.message || res.response || 'Type a question before sending.',
      routing: { target_agent: 'coordinator', status: 'error', error_code: res.error_code },
      timestamp,
      origin,
    }
  }

  // Subscription Plan Restrictions (Starter / Coordinator restriction)
  if (res.status === 'restricted' || res.error_code === 'PLAN_RESTRICTED' || res.plan_restricted) {
    const reason = res.response || res.message || 'This feature is not available in your current subscription plan.'
    return {
      id,
      role: 'assistant',
      status: 'restricted',
      error_code: 'PLAN_RESTRICTED',
      content: reason,
      routing: {
        ...(res.routing || {}),
        status: 'restricted',
        target_agent: 'coordinator',
        classified_agent: res.routing?.classified_agent || res.routing?.target_agent,
      },
      plan: res.plan || 'starter',
      required_plan: res.required_plan || 'professional',
      timestamp,
      origin,
      metadata: {
        agent_used: 'coordinator',
        audit: res.audit,
        error_code: 'PLAN_RESTRICTED',
        status: 'restricted',
        routing: res.routing,
      },
    }
  }

  // Specialist Selection Domain Mismatch (Professional Plan)
  if (res.status === 'mismatch' || res.error_code === 'SPECIALIST_MISMATCH' || res.specialist_mismatch) {
    const reason = res.response || res.message
    return {
      id,
      role: 'assistant',
      status: 'mismatch',
      error_code: 'SPECIALIST_MISMATCH',
      content: reason,
      suggested_agent: res.suggested_agent,
      routing: {
        ...(res.routing || {}),
        status: 'mismatch',
        target_agent: res.agent_used,
        classified_agent: res.suggested_agent,
      },
      timestamp,
      origin,
      metadata: {
        agent_used: res.agent_used,
        audit: res.audit,
        error_code: 'SPECIALIST_MISMATCH',
        status: 'mismatch',
        suggested_agent: res.suggested_agent,
        routing: res.routing,
      },
    }
  }

  const invDetails = res.inventory_details || null
  // Digital Twin: only inventory answers drive the map behind the chat
  const uiCommand = res.agent_used === 'inventory_agent' && res.ui_command?.payload
    ? { ...res.ui_command, id: res.ui_command.id || `query-${id}`, query: text }
    : null
  // Order card heuristic belongs to the fulfillment UI and is kept as it was
  const hasOrder = text.includes('#4521') || res.response?.includes('#4521') || res.routing?.extracted_params?.order_id

  return {
    id,
    role: 'assistant',
    status: res.status || 'success',
    content: res.response || (res.status === 'error' && res.message)
      || 'Warehouse query coordinated and dispatched to specialist agent.',
    routing: res.routing || { target_agent: res.agent_used || 'coordinator' },
    inventory_details: invDetails,
    fulfillment_details: res.fulfillment_details || null,
    skuData: skuDataFromItem(invDetails?.items?.[0]),
    uiCommand,
    orderData: hasOrder ? {
      id: '#4521',
      status: 'In Transit — On Schedule',
      carrier: 'FreightExpress • Priority 1',
    } : null,
    metadata: { agent_used: res.agent_used, audit: res.audit, inventory_details: invDetails, fulfillment_details: res.fulfillment_details || null },
    timestamp,
    origin,
  }
}

export function toUserMessage(text, { senderName = 'Operator', id = nextId('u'), timestamp = new Date(), attachments = [] } = {}) {
  return { id, role: 'user', content: text, attachments, senderName, timestamp }
}

// GET /threads/:id messages → chat messages (history is never auto-played on the map)
export function storedToUiMessages(stored = [], senderName = 'Operator') {
  let lastUserText = ''
  return stored.map((m) => {
    const timestamp = m.created_at ? new Date(m.created_at) : new Date()
    if (m.role === 'user') {
      lastUserText = m.content || ''
      // Questions sent with files show the typed text + file chips, like when they were asked
      const { text, attachments } = splitAttachedQuery(m.content)
      return toUserMessage(text, { senderName, id: `m-${m.id}`, timestamp, attachments })
    }
    const meta = m.meta || {}
    const res = {
      status: m.status,
      error_code: meta.error_code,
      agent_used: m.agent_used || meta.agent_used,
      response: m.content,
      message: m.content,
      routing: meta.routing,
      inventory_details: meta.inventory_details,
      fulfillment_details: meta.fulfillment_details,
      ui_command: meta.ui_command,
    }
    return toAssistantMessage(res, { text: lastUserText, id: `m-${m.id}`, timestamp, origin: 'stored' })
  })
}

export function toThreadSummary(t) {
  return { id: t.id, title: t.title, timestamp: new Date(t.updated_at || t.created_at || Date.now()) }
}
