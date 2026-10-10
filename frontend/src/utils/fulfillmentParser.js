/**
 * Reusable utility for parsing and normalizing Fulfillment Agent response data.
 * Adheres strictly to backend data contracts without hallucinating or inventing data.
 */

/**
 * Parses raw fulfillment response text, structured details, and routing metadata.
 * @param {string} content - Assistant response text
 * @param {Object} fulfillmentDetails - Structured fulfillment payload (if any)
 * @param {Object} routing - Coordinator routing decision object
 * @returns {Object} Normalized fulfillment analysis fields
 */
export function parseFulfillmentContent(content = '', fulfillmentDetails = {}, routing = {}) {
  const text = String(content || '')
  const details = fulfillmentDetails || {}
  const route = routing || {}

  // 1. Order ID resolution: check structured field first, then strict regex
  let orderId = details?.order_id || route?.extracted_params?.order_id || null
  if (!orderId) {
    const match = text.match(/\b(ORD-\d+)\b/i)
    if (match) {
      orderId = match[1].toUpperCase()
    }
  }

  // 2. Intent resolution: structured intent or routing intent, fallback to ORDER_STATUS
  const intent = details?.intent || route?.intent || 'ORDER_STATUS'

  // 3. Special state flags
  const isNotFound = /not found in the system/i.test(text)
  const isMissingId = /provide a valid order ID/i.test(text)
  const isUnknownIntent =
    intent === 'UNKNOWN_FULFILLMENT' ||
    /could not confidently determine your fulfillment request/i.test(text)

  // 4. Real Status determination strictly from factual signals
  let status = details?.status || details?.order?.status || null
  if (isNotFound) {
    status = 'NOT_FOUND'
  } else if (isMissingId) {
    status = 'MISSING_ID'
  } else if (/is currently delayed/i.test(text) || /status: delayed/i.test(text) || /status:\s*delayed/i.test(text)) {
    status = 'DELAYED'
  } else if (/marked as shipped/i.test(text) || /is currently shipped/i.test(text) || /status: shipped/i.test(text) || /status:\s*shipped/i.test(text)) {
    status = 'SHIPPED'
  } else if (/is currently pending/i.test(text) || /status: pending/i.test(text) || /status:\s*pending/i.test(text)) {
    status = 'PENDING'
  } else if (/is currently cancelled/i.test(text) || /status: cancelled/i.test(text) || /status:\s*cancelled/i.test(text)) {
    status = 'CANCELLED'
  } else if (!status) {
    const statusMatch = text.match(/Status:\s*([A-Za-z_-]+)/i)
    if (statusMatch) {
      status = statusMatch[1].toUpperCase()
    }
  }

  // 5. Delay Analysis Fields (Only from factual text matches)
  let delayReason = null
  let carrierName = null
  let revisedDate = null

  const reasonMatch = text.match(/Reason:\s*([^.\n]+)/i)
  if (reasonMatch) {
    delayReason = reasonMatch[1].trim()
  }

  const carrierMatch = text.match(/Carrier:\s*([^.\n]+)/i)
  if (carrierMatch) {
    carrierName = carrierMatch[1].trim()
  }

  const dateMatch = text.match(/Revised delivery date:\s*([^.\n]+)/i)
  if (dateMatch) {
    revisedDate = dateMatch[1].trim()
  }

  const isOverdue = checkIsOverdue(revisedDate, status)

  // 6. Cross-Agent Inventory Investigation Detection (Strictly when genuine evidence exists)
  let crossAgent = null
  const skuMatch = text.match(/\b(SKU-\d+)\b/i)
  const isOutOfStock = /is currently out of stock/i.test(text) || /stock: 0/i.test(text) || /stock depleted/i.test(text)
  const isStockAvailable = /currently has stock available/i.test(text) || /units on hand/i.test(text)

  if (isOutOfStock && skuMatch) {
    crossAgent = {
      involved: true,
      sku: skuMatch[1].toUpperCase(),
      stockStatus: 'OUT_OF_STOCK',
      findings: `Inventory investigation confirmed zero stock on hand for ${skuMatch[1].toUpperCase()}. This stock depletion may be contributing to the order delay, but the order record itself does not contain an additional delay reason.`
    }
  } else if (isStockAvailable && skuMatch) {
    crossAgent = {
      involved: true,
      sku: skuMatch[1].toUpperCase(),
      stockStatus: 'IN_STOCK',
      findings: `Inventory investigation confirmed stock is available on hand for ${skuMatch[1].toUpperCase()}. The available inventory data alone does not explain the delay, and the order record does not specify an alternate reason.`
    }
  }

  // 7. Order Details Fields (When ORDER_DETAILS intent is queried)
  let orderDetails = null
  if (intent === 'ORDER_DETAILS' && !isNotFound) {
    const custMatch = text.match(/Customer:\s*([^\n]+)/i)
    const skuDetailMatch = text.match(/SKU:\s*([^\n]+)/i)
    const qtyMatch = text.match(/Quantity:\s*([^\n]+)/i)
    const statusDetailMatch = text.match(/Status:\s*([^\n]+)/i)
    const createdMatch = text.match(/Created At:\s*([^\n]+)/i)

    if (custMatch || skuDetailMatch || qtyMatch || statusDetailMatch || createdMatch) {
      orderDetails = {
        customer: custMatch ? custMatch[1].trim() : null,
        sku: skuDetailMatch ? skuDetailMatch[1].trim() : (skuMatch ? skuMatch[1].toUpperCase() : null),
        quantity: qtyMatch ? qtyMatch[1].trim() : null,
        status: statusDetailMatch ? statusDetailMatch[1].trim().toUpperCase() : status,
        createdAt: createdMatch ? createdMatch[1].trim().slice(0, 19) : null
      }
    }
  }

  // 8. Procedural Guidance & SOP Citations (Phase 2 & 3 RAG integration)
  const proceduralGuidance = details?.procedural_guidance || null
  const citations = Array.isArray(details?.citations) ? details.citations : []
  const informationReliability = details?.information_reliability || (proceduralGuidance ? 'procedural_guidance' : 'confirmed_facts')

  // Detect whether this is a pure procedural query (e.g. no order ID, but procedural guidance/intent exists)
  const isProcedural = intent === 'FULFILLMENT_PROCEDURE' || Boolean(proceduralGuidance || citations.length > 0)

  return {
    orderId,
    intent,
    status,
    isNotFound,
    isMissingId: isMissingId && !isProcedural, // Procedural questions without order ID are NOT missing ID errors
    isUnknownIntent,
    isProcedural,
    proceduralGuidance,
    citations,
    informationReliability,
    delayReason,
    carrierName,
    revisedDate,
    isOverdue,
    crossAgent,
    orderDetails,
    rawContent: text
  }
}

/**
 * Safely checks whether a revised delivery date has passed relative to the local calendar day.
 * - Compares calendar day parts safely (YYYY-MM-DD), avoiding timezone false positives.
 * - Does not mark today's date as overdue.
 * - Does not mark delivered or shipped orders as overdue.
 * - Returns false for missing or invalid date strings.
 *
 * @param {string} dateStr - Revised delivery date string (e.g., "2026-10-01")
 * @param {string} status - Current order status (e.g., "DELAYED", "SHIPPED")
 * @param {Date} [referenceDate] - Optional reference date for testing (defaults to current date)
 * @returns {boolean} True if strictly overdue
 */
export function checkIsOverdue(dateStr, status, referenceDate = null) {
  if (!dateStr || !status) return false
  const normStatus = String(status).toUpperCase()
  if (normStatus === 'DELIVERED' || normStatus === 'SHIPPED') return false

  const match = String(dateStr).match(/^(\d{4})-(\d{1,2})-(\d{1,2})/)
  if (!match) return false

  const revYear = parseInt(match[1], 10)
  const revMonth = parseInt(match[2], 10) - 1
  const revDay = parseInt(match[3], 10)

  // Validate calendar date bounds
  const revDateObj = new Date(revYear, revMonth, revDay)
  if (
    revDateObj.getFullYear() !== revYear ||
    revDateObj.getMonth() !== revMonth ||
    revDateObj.getDate() !== revDay
  ) {
    return false
  }

  const now = referenceDate instanceof Date ? referenceDate : new Date()
  const nowYear = now.getFullYear()
  const nowMonth = now.getMonth()
  const nowDay = now.getDate()

  if (revYear < nowYear) return true
  if (revYear > nowYear) return false
  if (revMonth < nowMonth) return true
  if (revMonth > nowMonth) return false
  return revDay < nowDay
}

/**
 * Generates context-aware follow-up suggestion queries.
 * @param {Object} parsed - Result of parseFulfillmentContent
 * @returns {Array<{label: string, query: string}>}
 */
export function getFulfillmentFollowUps(parsed) {
  if (!parsed) return []

  if (parsed.isProcedural && !parsed.orderId) {
    return [
      { label: 'Packing Procedure', query: 'What is the packing procedure?' },
      { label: 'Dispatch Checklist', query: 'What checks are required before dispatch?' },
      { label: 'Order Delay Guidance', query: 'What should I do when an order is delayed?' },
      { label: 'Check Status of ORD-1001', query: 'What is the status of ORD-1001?' }
    ]
  }

  if (!parsed.orderId || parsed.isNotFound || parsed.isMissingId) {
    return [
      { label: 'Check Status of ORD-1001', query: 'What is the status of ORD-1001?' },
      { label: 'Investigate Delay on ORD-1001', query: 'Why is ORD-1001 delayed?' },
      { label: 'Check Shipped Order ORD-1003', query: 'Has ORD-1003 shipped?' },
      { label: 'View Details of ORD-1002', query: 'Show me details for ORD-1002' }
    ]
  }

  const followUps = []
  const id = parsed.orderId

  if (parsed.intent !== 'ORDER_STATUS') {
    followUps.push({
      label: `Status for ${id}`,
      query: `What is the status of ${id}?`
    })
  }

  if (parsed.intent !== 'ORDER_DELAY') {
    followUps.push({
      label: `Investigate Delay (${id})`,
      query: `Why is ${id} delayed?`
    })
  }

  if (parsed.intent !== 'ORDER_DETAILS') {
    followUps.push({
      label: `Order Manifest Details (${id})`,
      query: `Show me details for ${id}`
    })
  }

  if (parsed.intent !== 'SHIPPING_STATUS') {
    followUps.push({
      label: `Check Dispatch / Shipping (${id})`,
      query: `Has ${id} shipped?`
    })
  }

  if (parsed.intent !== 'FULFILLMENT_PROGRESS') {
    followUps.push({
      label: `Track Fulfillment Progress (${id})`,
      query: `What is the fulfillment progress of ${id}?`
    })
  }

  return followUps.slice(0, 4)
}
