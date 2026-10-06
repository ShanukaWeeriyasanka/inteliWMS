// Hierarchical twin IDs. A child ID always starts with its parent's ID:
//   WH1 › WH1-F2 › WH1-F2-Z01 › WH1-F2-Z01-R02 › …-S03 (shelf, S01 = bottom) › …-B04 (bin, B01 = left)
// Nav nodes: WH1-F2-N009. Products: PRD-00002.
// Highlighting is ALWAYS a lookup by these exact strings — never by name or index.

const LOCATION_RE = /^(WH\d+)(?:-(F\d+)(?:-(Z\d{2})(?:-(R\d{2})(?:-(S\d{2})(?:-(B\d{2}))?)?)?)?)?$/
const NAV_NODE_RE = /^(WH\d+)-(F\d+)-(N\d{3})$/
const PRODUCT_RE = /^PRD-\d{5}$/

const LEVELS = ['warehouse', 'floor', 'zone', 'rack', 'shelf', 'bin']

export const isProductId = (id) => typeof id === 'string' && PRODUCT_RE.test(id)
export const isNavNodeId = (id) => typeof id === 'string' && NAV_NODE_RE.test(id)
export const isLocationId = (id) => typeof id === 'string' && LOCATION_RE.test(id)

/**
 * Split a location or nav-node ID into its parts.
 * Returns null for anything that is not a well-formed twin ID.
 *   parseLocationId('WH1-F2-Z01-R02-S03-B04') →
 *   { id, level: 'bin', warehouseId: 'WH1', floorId: 'WH1-F2', zoneId: 'WH1-F2-Z01',
 *     rackId: 'WH1-F2-Z01-R02', shelfId: 'WH1-F2-Z01-R02-S03', binId: …, floorLevel: 2,
 *     shelfLevel: 3, binPosition: 4 }
 */
export function parseLocationId(id) {
  if (typeof id !== 'string') return null
  const node = NAV_NODE_RE.exec(id)
  if (node) {
    const [, wh, f, n] = node
    return {
      id, level: 'nav_node', warehouseId: wh, floorId: `${wh}-${f}`,
      zoneId: null, rackId: null, shelfId: null, binId: null,
      floorLevel: Number(f.slice(1)), nodeNumber: Number(n.slice(1)),
      shelfLevel: null, binPosition: null,
    }
  }
  const m = LOCATION_RE.exec(id)
  if (!m) return null
  const parts = m.slice(1).filter(Boolean)
  const prefix = (n) => (parts.length >= n ? parts.slice(0, n).join('-') : null)
  return {
    id,
    level: LEVELS[parts.length - 1],
    warehouseId: prefix(1),
    floorId: prefix(2),
    zoneId: prefix(3),
    rackId: prefix(4),
    shelfId: prefix(5),
    binId: prefix(6),
    floorLevel: m[2] ? Number(m[2].slice(1)) : null,
    shelfLevel: m[5] ? Number(m[5].slice(1)) : null,
    binPosition: m[6] ? Number(m[6].slice(1)) : null,
  }
}

/** Parent ID one level up ('WH1-F2-Z01-R02-S03' → 'WH1-F2-Z01-R02'); null at the top. */
export function parentId(id) {
  const p = parseLocationId(id)
  if (!p || p.level === 'warehouse') return null
  if (p.level === 'nav_node') return p.floorId
  return id.split('-').slice(0, -1).join('-')
}

export const floorOf = (id) => parseLocationId(id)?.floorId ?? null
export const rackOf = (id) => parseLocationId(id)?.rackId ?? null

/** True when `id` is `ancestor` or lies inside it (pure prefix rule on whole segments). */
export function isWithin(id, ancestor) {
  return id === ancestor || (typeof id === 'string' && id.startsWith(`${ancestor}-`))
}

/** Compact label for tables: 'F2 · Rack 2 · S3 · B4' (rack name, not its index, so it matches the map). */
export function shortBinLabel(binId, rackName) {
  const p = parseLocationId(binId)
  if (!p) return binId
  const bits = [`F${p.floorLevel}`, rackName || p.rackId?.split('-').pop()]
  if (p.shelfLevel) bits.push(`S${p.shelfLevel}`)
  if (p.binPosition) bits.push(`B${p.binPosition}`)
  return bits.join(' · ')
}
