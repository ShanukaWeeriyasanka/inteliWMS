// Small, pure helpers for showing products: picture, stock level, search and
// relative time. Quantities always come from the database rows passed in.

// Picture for a product without an image_url: first matching rule wins.
const ART_RULES = [
  [/cable|usb/i, 'cable'],
  [/adapter|charger|power/i, 'plug'],
  [/bolt|nut/i, 'bolt'],
  [/screw/i, 'wrench'],
  [/drill/i, 'drill'],
  [/tape/i, 'tape'],
  [/box|carton|packag/i, 'box'],
  [/tea|coffee/i, 'cup'],
  [/milk|juice|drink/i, 'milk'],
  [/glove/i, 'hand'],
  [/helmet|hard hat/i, 'helmet'],
  [/bulb|led|lamp/i, 'bulb'],
]
const CATEGORY_ART = { Electronics: 'plug', Hardware: 'bolt', Tools: 'drill', Packaging: 'box', Food: 'cup', Safety: 'helmet' }
const CATEGORY_TONE = { Electronics: 'blue', Hardware: 'slate', Tools: 'amber', Packaging: 'sand', Food: 'green', Safety: 'orange' }

export function productArt(product) {
  const name = product?.name || ''
  const rule = ART_RULES.find(([re]) => re.test(name))
  return {
    art: rule ? rule[1] : CATEGORY_ART[product?.category] || 'box',
    tone: CATEGORY_TONE[product?.category] || 'slate',
  }
}

/** 'ok' | 'low' | 'out' | 'unknown' from v_product_totals flags. */
export function stockStatus(totals) {
  if (!totals) return 'unknown'
  if (totals.is_out_of_stock) return 'out'
  if (totals.is_low_stock) return 'low'
  return 'ok'
}

/**
 * Stock gauge 0–1. Full means "comfortably above the reorder point"
 * (three times it); at the reorder point the gauge sits at one third.
 */
export function stockGauge(totals) {
  if (!totals) return 0
  const comfortable = Math.max(1, (totals.reorder_point || 0) * 3)
  return Math.max(0, Math.min(1, totals.total_quantity / comfortable))
}

/** Search on ID, product number, SKU, name and aliases ("2", "#2", "prd-00002", "charger"). */
export function matchesProduct(product, query) {
  const q = (query || '').trim().toLowerCase()
  if (!q) return true
  const num = /^#?\s*(\d{1,7})$/.exec(q)
  if (num) return product.product_no === Number(num[1])
  const hay = [product.product_id, product.sku, product.name, product.category, ...(product.aliases || [])]
    .filter(Boolean).join(' ').toLowerCase()
  return q.split(/\s+/).every((w) => hay.includes(w))
}

export function timeAgo(iso, now = Date.now()) {
  if (!iso) return ''
  const s = Math.max(0, Math.round((now - new Date(iso).getTime()) / 1000))
  if (s < 60) return 'just now'
  if (s < 3600) return `${Math.round(s / 60)} min ago`
  if (s < 86400) return `${Math.round(s / 3600)} h ago`
  return `${Math.round(s / 86400)} d ago`
}

/** Sum `val` per `key` over rows → Map. */
export const sumBy = (rows, key, val = 'quantity') =>
  rows.reduce((m, r) => m.set(r[key], (m.get(r[key]) || 0) + r[val]), new Map())
