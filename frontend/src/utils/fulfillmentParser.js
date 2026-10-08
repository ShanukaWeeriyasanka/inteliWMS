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
  let status = null
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
    orderDetails,
    rawContent: text
  }
}

/**
 * Generates context-aware follow-up suggestion queries.
 * @param {Object} parsed - Result of parseFulfillmentContent
 * @returns {Array<{label: string, query: string}>}
 */
export function getFulfillmentFollowUps(parsed) {
  if (!parsed) return []

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
