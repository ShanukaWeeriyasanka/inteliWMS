// Turns /query responses and stored thread messages into chat UI messages.
// Live answers and reloaded history go through the same mapping, so a conversation
// looks the same after a refresh. Inventory cards are built only from the items the
// backend returned — never from placeholder values.

let seq = 0
const nextId = (prefix) => `${prefix}-${Date.now()}-${(seq += 1)}`

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
    content: res.response || 'Warehouse query coordinated and dispatched to specialist agent.',
    routing: res.routing || { target_agent: res.agent_used || 'coordinator' },
    inventory_details: invDetails,
    skuData: skuDataFromItem(invDetails?.items?.[0]),
    uiCommand,
    orderData: hasOrder ? {
      id: '#4521',
      status: 'In Transit — On Schedule',
      carrier: 'FreightExpress • Priority 1',
    } : null,
    metadata: { agent_used: res.agent_used, audit: res.audit, inventory_details: invDetails },
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
      return toUserMessage(m.content, { senderName, id: `m-${m.id}`, timestamp })
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
      ui_command: meta.ui_command,
    }
    return toAssistantMessage(res, { text: lastUserText, id: `m-${m.id}`, timestamp, origin: 'stored' })
  })
}

export function toThreadSummary(t) {
  return { id: t.id, title: t.title, timestamp: new Date(t.updated_at || t.created_at || Date.now()) }
}
