import { describe, expect, it } from 'vitest'
import { parseLocationId, parentId, isWithin, shortBinLabel, isProductId, isNavNodeId } from './ids'
import { splitRouteByFloor, routeSummary, pointAlong } from './route'
import { validateCommand, commandIds } from './commands'
import { fitView, focusView, frameView, growBox, racksBox, scaleBar, unionBox, zoomAt } from './viewport'
import { rackNamePlacement, ringRuns } from '../components/map/RackShape'
import { zoneLabelY } from '../components/map/FloorMap'
import { matchesProduct, productArt, stockGauge, stockStatus, sumBy, timeAgo } from './products'
import uiCommandSchema from '../../../../database/twin/ui_command.schema.json'

describe('viewport maths', () => {
  const floor = { width_m: 60, height_m: 34 }

  it('fits the whole floor with a margin, centred, at the container aspect', () => {
    const v = fitView(floor, 2)
    expect(v.w / v.h).toBeCloseTo(2)
    expect(v.x).toBeLessThanOrEqual(-3)
    expect(v.x + v.w).toBeGreaterThanOrEqual(63)
    expect(v.y).toBeLessThanOrEqual(-3)
    expect(v.y + v.h).toBeGreaterThanOrEqual(37)
  })

  it('zooms around the cursor point and respects limits', () => {
    const v = { x: 0, y: 0, w: 40, h: 20 }
    const z = zoomAt(v, 2, 10, 5)
    expect(z.w).toBe(20)
    // the point under the cursor stays at the same fraction of the view
    expect((10 - z.x) / z.w).toBeCloseTo((10 - v.x) / v.w)
    expect(zoomAt(v, 100, 0, 0).w).toBe(10) // MIN_VIEW_W
  })

  it('frames a rack and keeps it clear of the right panel', () => {
    const rack = { x: 20, y: 3, width_m: 8, depth_m: 6 }
    const box = racksBox([rack])
    expect(box).toEqual({ x: 20, y: 3, w: 8, h: 6 })
    const free = focusView(box, 2, { occludeRight: 0 })
    const covered = focusView(box, 2, { occludeRight: 0.4 })
    const centre = 24
    expect((centre - free.x) / free.w).toBeCloseTo(0.5)
    expect((centre - covered.x) / covered.w).toBeCloseTo(0.3) // middle of the visible 60 %
  })

  it('frames a box in the part of the map that floating UI leaves visible', () => {
    const size = { w: 1000, h: 600 }
    const box = { x: 40, y: 20, w: 6, h: 4 } // centre (43, 22)
    const insets = { right: 372, bottom: 170, top: 12, left: 12 }
    const v = frameView(box, size, { insets, scale: 1.6, minVisibleW: 18 })
    const mpp = v.w / size.w
    const toPx = (mx, my) => ({ x: (mx - v.x) / mpp, y: (my - v.y) / mpp })
    // the box centre sits in the middle of the uncovered rectangle (12..628 × 12..430)
    const c = toPx(43, 22)
    expect(c.x).toBeCloseTo((12 + 628) / 2)
    expect(c.y).toBeCloseTo((12 + 430) / 2)
    // and the whole box is inside it, clear of the panel and the agent reply
    const tl = toPx(box.x, box.y)
    const br = toPx(box.x + box.w, box.y + box.h)
    expect(tl.x).toBeGreaterThan(12)
    expect(br.x).toBeLessThan(628)
    expect(tl.y).toBeGreaterThan(12)
    expect(br.y).toBeLessThan(430)
    // at least 18 m stay visible for context
    expect(616 * mpp).toBeGreaterThanOrEqual(18 - 1e-9)
    expect(v.w / v.h).toBeCloseTo(size.w / size.h)
  })

  it('never lets floating UI take more than three quarters of the map when framing', () => {
    const v = frameView({ x: 0, y: 0, w: 10, h: 10 }, { w: 400, h: 400 }, { insets: { bottom: 380 } })
    const mpp = v.w / 400
    expect((5 - v.y) / mpp).toBeCloseTo(50) // centred in the top 100 px that stay visible
  })

  it('grows and unions boxes', () => {
    expect(growBox({ x: 1, y: 1, w: 2, h: 2 }, { left: 1, top: 0.5, bottom: 1 })).toEqual({ x: 0, y: 0.5, w: 3, h: 3.5 })
    expect(unionBox([{ x: 0, y: 0, w: 1, h: 1 }, null, { x: 3, y: -1, w: 1, h: 1 }])).toEqual({ x: 0, y: -1, w: 4, h: 2 })
    expect(unionBox([])).toBeNull()
  })

  it('picks a round scale-bar length', () => {
    expect(scaleBar(0.1).metres).toBe(5)
    expect(scaleBar(0.05).metres).toBe(5)
    expect(scaleBar(0.2).metres).toBe(10)
  })
})

describe('zone names', () => {
  const zone = { id: 'Z1', y: 10 }
  it('stay in the zone corner when racks start lower down', () => {
    expect(zoneLabelY(zone, [{ zone_id: 'Z1', y: 13 }])).toBeCloseTo(10.75)
  })
  it('lift above a rack that starts near the zone edge, clear of its highlight outline', () => {
    const y = zoneLabelY(zone, [{ zone_id: 'Z1', y: 10.8 }, { zone_id: 'Z2', y: 9 }])
    expect(y + 0.3).toBeLessThanOrEqual(10.8 - 0.45) // label bottom above the outline's top edge
  })
})

describe('rack names', () => {
  const rack = { x: 10, y: 5, width_m: 8, depth_m: 6 } // bottom edge at y = 11
  it('go under the rack, below the highlight outline when there is one', () => {
    expect(rackNamePlacement(rack, 'normal', null)).toEqual({ x: 14, y: 11.6, anchor: 'middle' })
    expect(rackNamePlacement(rack, 'selected', null).y).toBeCloseTo(11.95)
    // a marker above the rack (aisle on the other side) leaves the name where it was
    expect(rackNamePlacement(rack, 'selected', { x: 14, y: 3 }).anchor).toBe('middle')
  })
  it('go beside the stock marker when the marker sits right under the rack', () => {
    const p = rackNamePlacement(rack, 'selected', { x: 14, y: 13 })
    expect(p).toEqual({ x: 13, y: 13.02, anchor: 'end' }) // left of the 1.44 m icon, level with it
  })
})

describe('target bin outlines', () => {
  const geo = { y: 1, cw: 1, ch: 0.8, gap: 0.11 }
  const overlaps = (a, b) => a.x < b.x + b.width && b.x < a.x + a.width && a.y < b.y + b.height && b.y < a.y + a.height
  const cell = (col) => ({ col, x: 0.2 + (col - 1) * (geo.cw + geo.gap) })

  it('draws one outline around neighbouring target bins', () => {
    const runs = ringRuns([cell(3), cell(2)], geo)
    expect(runs).toHaveLength(1)
    expect(runs[0].x).toBeLessThan(cell(2).x)
    expect(runs[0].x + runs[0].width).toBeGreaterThan(cell(3).x + geo.cw)
  })

  it('keeps outlines of separate bins and of adjacent shelves from crossing', () => {
    const [a, b] = ringRuns([cell(1), cell(3)], geo)
    expect(overlaps(a, b)).toBe(false)
    // the shelf below starts one cell height + gap lower; with the ring stroke the outlines still don't meet
    const below = ringRuns([cell(1)], { ...geo, y: geo.y + geo.ch + geo.gap })[0]
    const stroke = 0.09
    expect(a.y + a.height + stroke / 2).toBeLessThan(below.y - stroke / 2 + 1e-9)
  })
})

describe('product helpers', () => {
  const charger = { product_id: 'PRD-00002', product_no: 2, sku: 'EL-PWR-65W', name: 'Power Adapter 65W',
    category: 'Electronics', aliases: ['charger', '65w adapter'], total_quantity: 50, reorder_point: 25,
    is_low_stock: false, is_out_of_stock: false }

  it('searches by number, ID, SKU, name and alias', () => {
    for (const q of ['2', '#2', 'prd-00002', 'el-pwr', 'power adapter', 'charger', '']) expect(matchesProduct(charger, q)).toBe(true)
    for (const q of ['3', 'drill', 'charger blue']) expect(matchesProduct(charger, q)).toBe(false)
  })

  it('reads stock status from the database flags', () => {
    expect(stockStatus(charger)).toBe('ok')
    expect(stockStatus({ ...charger, is_low_stock: true })).toBe('low')
    expect(stockStatus({ ...charger, is_out_of_stock: true, is_low_stock: true })).toBe('out')
    expect(stockStatus(null)).toBe('unknown')
  })

  it('scales the stock gauge so the reorder point sits at one third', () => {
    expect(stockGauge({ total_quantity: 25, reorder_point: 25 })).toBeCloseTo(1 / 3)
    expect(stockGauge({ total_quantity: 500, reorder_point: 25 })).toBe(1)
    expect(stockGauge({ total_quantity: 0, reorder_point: 0 })).toBe(0)
  })

  it('chooses a picture from the name first, then the category', () => {
    expect(productArt(charger).art).toBe('plug')
    expect(productArt({ name: 'Hex Bolt M8', category: 'Hardware' }).art).toBe('bolt')
    expect(productArt({ name: 'Mystery item', category: 'Food' })).toEqual({ art: 'cup', tone: 'green' })
  })

  it('sums quantities per key and formats relative time', () => {
    const rows = [{ rack_id: 'A', quantity: 2 }, { rack_id: 'B', quantity: 3 }, { rack_id: 'A', quantity: 5 }]
    expect([...sumBy(rows, 'rack_id')]).toEqual([['A', 7], ['B', 3]])
    const now = Date.parse('2026-10-05T12:00:00Z')
    expect(timeAgo('2026-10-05T11:59:30Z', now)).toBe('just now')
    expect(timeAgo('2026-10-05T11:30:00Z', now)).toBe('30 min ago')
    expect(timeAgo('2026-10-03T12:00:00Z', now)).toBe('2 d ago')
  })
})

describe('parseLocationId', () => {
  it('splits a bin into every ancestor', () => {
    expect(parseLocationId('WH1-F2-Z01-R02-S03-B04')).toEqual({
      id: 'WH1-F2-Z01-R02-S03-B04', level: 'bin', warehouseId: 'WH1', floorId: 'WH1-F2',
      zoneId: 'WH1-F2-Z01', rackId: 'WH1-F2-Z01-R02', shelfId: 'WH1-F2-Z01-R02-S03',
      binId: 'WH1-F2-Z01-R02-S03-B04', floorLevel: 2, shelfLevel: 3, binPosition: 4,
    })
  })

  it('knows every level', () => {
    expect(parseLocationId('WH1').level).toBe('warehouse')
    expect(parseLocationId('WH1-F3').level).toBe('floor')
    expect(parseLocationId('WH1-F3-Z01').level).toBe('zone')
    expect(parseLocationId('WH1-F3-Z01-R03').level).toBe('rack')
    expect(parseLocationId('WH1-F3-Z01-R03-S02').level).toBe('shelf')
  })

  it('parses nav nodes, including lifts that share a number across floors', () => {
    const lift = parseLocationId('WH1-F2-N020')
    expect(lift).toMatchObject({ level: 'nav_node', floorId: 'WH1-F2', floorLevel: 2, nodeNumber: 20 })
    expect(isNavNodeId('WH1-F2-N020')).toBe(true)
  })

  it('rejects malformed IDs instead of guessing', () => {
    for (const bad of ['WH1-F2-R02', 'wh1-f2', 'WH1-F2-Z1', 'WH1-F2-Z01-R02-B04', 'PRD-00002', '', null, 42]) {
      expect(parseLocationId(bad)).toBeNull()
    }
    expect(isProductId('PRD-00002')).toBe(true)
    expect(isProductId('PRD-2')).toBe(false)
  })

  it('derives parents by trimming segments', () => {
    expect(parentId('WH1-F2-Z01-R02-S03-B04')).toBe('WH1-F2-Z01-R02-S03')
    expect(parentId('WH1-F2-Z01')).toBe('WH1-F2')
    expect(parentId('WH1-F2-N009')).toBe('WH1-F2')
    expect(parentId('WH1')).toBeNull()
    // NB: the rack is the first FOUR segments; slice(0, 5) would be the shelf.
    expect('WH1-F2-Z01-R02-S03-B04'.split('-').slice(0, 4).join('-')).toBe(parseLocationId('WH1-F2-Z01-R02-S03-B04').rackId)
  })

  it('checks containment on whole segments only', () => {
    expect(isWithin('WH1-F2-Z01-R02-S03', 'WH1-F2-Z01-R02')).toBe(true)
    expect(isWithin('WH1-F2-Z01-R02', 'WH1-F2-Z01-R02')).toBe(true)
    expect(isWithin('WH1-F12-Z01', 'WH1-F1')).toBe(false)
  })

  it('formats a short bin label with the rack name', () => {
    expect(shortBinLabel('WH1-F2-Z03-R03-S01-B02', 'Crate 4')).toBe('F2 · Crate 4 · S1 · B2')
  })
})

// find_route output for "Main entrance → Rack 2 on Floor 2" (acceptance test 1)
const pathToRack2F2 = [
  { seq: 1, node_id: 'WH1-F1-N001', floor_id: 'WH1-F1', floor_level: 1, x: 2, y: 15, label: 'Main entrance', via: null, total_m: 0, total_s: 0 },
  { seq: 2, node_id: 'WH1-F1-N020', floor_id: 'WH1-F1', floor_level: 1, x: 2, y: 9, label: 'Lift A', via: 'walk', total_m: 6, total_s: 5 },
  { seq: 3, node_id: 'WH1-F2-N020', floor_id: 'WH1-F2', floor_level: 2, x: 2, y: 9, label: 'Lift A', via: 'lift', total_m: 6, total_s: 30 },
  { seq: 4, node_id: 'WH1-F2-N001', floor_id: 'WH1-F2', floor_level: 2, x: 2, y: 15, label: 'Lift lobby', via: 'walk', total_m: 12, total_s: 35 },
  { seq: 5, node_id: 'WH1-F2-N003', floor_id: 'WH1-F2', floor_level: 2, x: 10, y: 15, label: null, via: 'walk', total_m: 20, total_s: 42 },
  { seq: 6, node_id: 'WH1-F2-N004', floor_id: 'WH1-F2', floor_level: 2, x: 24, y: 15, label: null, via: 'walk', total_m: 34, total_s: 53 },
  { seq: 7, node_id: 'WH1-F2-N009', floor_id: 'WH1-F2', floor_level: 2, x: 24, y: 11, label: null, via: 'walk', total_m: 38, total_s: 57 },
]

describe('splitRouteByFloor', () => {
  it('starts a new segment at every lift or stairs arrival', () => {
    const segs = splitRouteByFloor(pathToRack2F2)
    expect(segs.map((s) => [s.floorId, s.points.length, s.arrivedVia, s.connectorLabel])).toEqual([
      ['WH1-F1', 2, null, null],
      ['WH1-F2', 5, 'lift', 'Lift A'],
    ])
  })

  it('marks floors the lift only passes through', () => {
    const path = [
      { node_id: 'WH1-F1-N020', floor_id: 'WH1-F1', floor_level: 1, label: 'Lift A', via: null },
      { node_id: 'WH1-F2-N020', floor_id: 'WH1-F2', floor_level: 2, label: 'Lift A', via: 'lift' },
      { node_id: 'WH1-F3-N020', floor_id: 'WH1-F3', floor_level: 3, label: 'Lift A', via: 'lift' },
      { node_id: 'WH1-F3-N001', floor_id: 'WH1-F3', floor_level: 3, label: 'Lift lobby', via: 'walk' },
    ]
    const segs = splitRouteByFloor(path)
    expect(segs.map((s) => [s.floorId, s.passThrough])).toEqual([
      ['WH1-F1', false], ['WH1-F2', true], ['WH1-F3', false],
    ])
  })

  it('handles empty and single-floor routes', () => {
    expect(splitRouteByFloor([])).toEqual([])
    expect(splitRouteByFloor(pathToRack2F2.slice(0, 2))).toHaveLength(1)
  })

  it('summarises distance, time and connector', () => {
    const segs = splitRouteByFloor(pathToRack2F2)
    expect(routeSummary(pathToRack2F2, segs)).toBe('38 m · about 57 s · via Lift A')
  })

  it('interpolates along a polyline', () => {
    expect(pointAlong([{ x: 0, y: 0 }, { x: 10, y: 0 }], 0.5)).toEqual({ x: 5, y: 0 })
  })
})

describe('validateCommand', () => {
  it('accepts every example in ui_command.schema.json', () => {
    for (const ex of uiCommandSchema.examples) expect(validateCommand(ex)).toMatchObject({ ok: true })
  })

  it('rejects bad IDs with a message that names the field', () => {
    const res = validateCommand({ version: '1.1', action: 'show_location', answer_text: 'x', location_ids: ['WH1-F9-R01'] })
    expect(res.ok).toBe(false)
    expect(res.error).toContain('location_ids.0')
  })

  it('enforces per-action requirements', () => {
    expect(validateCommand({ version: '1.1', action: 'locate_product', answer_text: 'x' }).ok).toBe(false)
    expect(validateCommand({ version: '1.1', action: 'heatmap', answer_text: 'x' }).ok).toBe(false)
    expect(validateCommand({ version: '1.1', action: 'navigate', answer_text: 'x', route: {} }).ok).toBe(false)
    expect(validateCommand({ version: '1.1', action: 'clarify', answer_text: 'x',
      candidates: [{ label: 'a', product_id: 'PRD-00001' }] }).ok).toBe(false)
    expect(validateCommand({ version: '1.1', action: 'clear', answer_text: 'x', extra: true }).ok).toBe(false)
  })

  it('lists every ID a command refers to', () => {
    expect(commandIds({ product_ids: ['PRD-00002'], route: { to_id: 'WH1-F3-Z01-R03' }, floor_id: 'WH1-F3' }))
      .toEqual(['PRD-00002', 'WH1-F3', 'WH1-F3-Z01-R03'])
  })
})
