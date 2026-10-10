// Warehouse Digital Twin — interactive map workspace for the Inventory Agent.
// Opens over the chat when the inventory agent answers (or from the "Warehouse
// map" button): inventory list on the left, floor plan in the middle, details
// of the selected product / rack on the right, and a prompt bar to keep asking.
//
// Accuracy rules: commands are zod-validated; every ID must exist in the layout
// we fetched and is looked up by exact ID on the map; quantities, labels and
// routes come from database queries, never from the agent's text.
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useReducedMotion } from 'framer-motion'
import { Map as MapIcon, RefreshCw } from 'lucide-react'
import { createTwinApi } from './lib/api'
import { commandIds, validateCommand } from './lib/commands'
import { floorOf, isProductId, isWithin, parseLocationId, rackOf } from './lib/ids'
import { formatMetric, heatColor } from './lib/heat'
import { frameView, growBox, unionBox, zoomAt } from './lib/viewport'
import { sumBy } from './lib/products'
import { productHighlightRows } from './lib/selection'
import { useTwinData } from './hooks/useTwinData'
import { useRoute } from './hooks/useRoute'
import { useRoutePlayback } from './hooks/useRoutePlayback'
import { useViewport } from './hooks/useViewport'
import FloorMap from './components/map/FloorMap'
import MapControls from './components/map/MapControls'
import HoverCard from './components/map/HoverCard'
import MapHeader from './components/header/MapHeader'
import InventoryPanel from './components/panels/InventoryPanel'
import { ClarifyDetail, CountDetail, GroupDetail, ProductDetail, RackDetail } from './components/panels/DetailPanel'
import AgentDock from './components/AgentDock'
import Toasts from './components/Toasts'
import './twin.css'

const RACK_KIND = { shelf_unit: 'shelf units', pallet_grid: 'pallet racks', crate_rack: 'crate racks', cabinet: 'cold cabinets' }
const DETAIL_W = 344 // px — keep in sync with .twin-detail in twin.css
const NARROW_W = 1080 // below this the inventory list becomes a drawer
let localSeq = 0
const localId = () => `local-${Date.now()}-${++localSeq}`
const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v))

// Everything drawn for a rack that must stay in view when the map frames it (metres): the
// halo, the count badge above it, its name below, and the stock marker on the aisle in front
// (icon, pulse and number) — see RackShape and StockMarker.
function rackFootprint(rack, layout) {
  const body = growBox({ x: rack.x, y: rack.y, w: rack.width_m, h: rack.depth_m },
    { left: 0.6, right: 0.6, top: 1.5, bottom: 1.4 })
  const node = layout?.nodesById.get(rack.access_node_id)
  // pulse r 1.5, count on the right, and the rack name on the left when the marker is right below
  const marker = node && { x: node.x - 4.2, y: node.y - 1.6, w: 7.0, h: 3.2 }
  return unionBox([body, marker])
}

/** Stable callback ref that reports an element's width. */
function useWidth() {
  const [width, setWidth] = useState(0)
  const ro = useRef(null)
  const ref = useCallback((el) => {
    ro.current?.disconnect()
    if (!el) return
    ro.current = new ResizeObserver(([e]) => setWidth(e.contentRect.width))
    ro.current.observe(el)
  }, [])
  return [ref, width]
}

export default function WarehouseTwin({
  token, sessionId, command, visible = true, onActivate, onClose, onAsk, agentReply, agentBusy, onScopeChange,
}) {
  const reducedMotion = !!useReducedMotion()
  const api = useMemo(() => createTwinApi(token), [token])
  const svgRef = useRef(null)
  const mapEl = useRef(null)
  const inputRef = useRef(null)
  const registry = useRef(new Map())
  const [rootRef, rootW] = useWidth()
  const vp = useViewport({ reducedMotion })

  const [floorId, setFloorId] = useState(null)
  const [selection, setSelection] = useState(null)
  const [badges, setBadges] = useState(() => new Map())
  const [layer, setLayer] = useState('map')
  const [heatCfg, setHeatCfg] = useState({ metric: 'fill_ratio', values: null })
  const [tab, setTab] = useState('products')
  const [query, setQuery] = useState('')
  const [listOpen, setListOpen] = useState(false)
  const [rackView, setRackView] = useState(true)
  const [movementState, setMovementState] = useState({ productId: null, rows: [] })
  const [hover, setHover] = useState(null)
  const [focusReq, setFocusReq] = useState(null) // { floorId, box | null, key }
  const [flash, setFlash] = useState(() => new Map())
  const [routeReq, setRouteReq] = useState(null)
  const [routeVersion, setRouteVersion] = useState(0)
  const [toasts, setToasts] = useState([])
  const [ask, setAsk] = useState('')
  const narrow = rootW > 0 && rootW < NARROW_W

  // ── toasts ──
  const dismissToast = useCallback((id) => setToasts((t) => t.filter((x) => x.id !== id)), [])
  const toast = useCallback((text, tone = 'info') => {
    const id = localId()
    setToasts((t) => [...t.slice(-2), { id, text, tone }])
    setTimeout(() => dismissToast(id), tone === 'error' ? 8000 : 5000)
  }, [dismissToast])

  // ── live data ──
  const enqueueRef = useRef(null)
  const pendingEdge = useRef(null)
  const handlers = useMemo(() => ({
    onCommand: (item) => { enqueueRef.current?.(item); onActivate?.() },
    onStockChange: (rackId) => { if (rackId) setFlash((m) => new Map(m).set(rackId, (m.get(rackId) || 0) + 1)) },
    onAlert: (row) => toast(row.message, 'warn'),
    onEdgeChange: (row) => {
      pendingEdge.current = row
      setRouteReq((r) => r && { ...r, autoplay: false })
      setRouteVersion((v) => v + 1)
    },
  }), [toast, onActivate])

  const data = useTwinData(api, { sessionId, enabled: true, handlers })
  const { layout } = data
  const dataRef = useRef(data)
  dataRef.current = data

  const currentFloor = floorId || layout?.floors[0]?.id
  const floorRef = useRef(currentFloor)
  floorRef.current = currentFloor
  const floor = layout?.floorsById.get(currentFloor)
  const switchFloor = useCallback((fid) => { if (fid) setFloorId(fid) }, [])
  const focusOn = useCallback((fid, racks) => {
    const layoutNow = dataRef.current?.layout
    const box = racks?.length ? unionBox(racks.filter(Boolean).map((r) => rackFootprint(r, layoutNow))) : null
    setFocusReq({ floorId: fid, box, key: localId() })
  }, [])
  const fitFloor = useCallback((fid) => setFocusReq({ floorId: fid || floorRef.current, box: null, key: localId() }), [])

  // ── viewport: frame the requested racks (or the whole floor) in the part of the map that
  //    the detail panel, the agent reply and the controls leave visible ──
  const panelOpen = !!selection
  const userMoved = useRef(false) // the user panned / zoomed since the last framing: don't undo it

  // Pixels of the map covered by floating UI, measured from the DOM
  const coveredInsets = () => {
    const host = mapEl.current
    if (!host) return {}
    const map = host.getBoundingClientRect()
    const insets = { top: 12, right: 12, bottom: 60, left: 12 } // bottom: zoom / layer controls
    const panelEl = host.querySelector('.twin-detail')
    if (panelEl) {
      const p = panelEl.getBoundingClientRect()
      if (p.top > map.top + map.height * 0.2) insets.bottom = Math.max(insets.bottom, map.bottom - p.top + 12) // bottom sheet
      else insets.right = Math.max(insets.right, map.right - p.left + 12)
    } else if (panelOpen && map.width > 700) {
      insets.right = DETAIL_W + 28 // opening this render
    }
    const dockWrap = host.querySelector('.twin-dock-wrap')
    if (dockWrap && getComputedStyle(dockWrap).display !== 'none') {
      const dock = dockWrap.firstElementChild?.getBoundingClientRect()
      if (dock?.height) insets.bottom = Math.max(insets.bottom, map.bottom - dock.top + 12)
    }
    return insets
  }

  const frameNow = () => {
    if (!floor || !vp.aspect) return
    const req = focusReq && focusReq.floorId === currentFloor ? focusReq : null
    const opts = { insets: coveredInsets() }
    const target = req?.box
      ? frameView(req.box, vp.size, { ...opts, scale: 1.6, minVisibleW: 18, maxW: floor.width_m + 8 })
      : frameView({ x: -2, y: -2, w: floor.width_m + 4, h: floor.height_m + 4 }, vp.size, opts)
    if (vp.vb) vp.animateTo(target)
    else vp.set(target)
  }

  // A new request or another floor: frame it, and forget the user's own pan / zoom
  useEffect(() => {
    userMoved.current = false
    frameNow()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentFloor, focusReq, vp.aspect > 0, floor?.id])

  // The visible part changed (panel opened or closed, the agent replied, the window was resized):
  // frame the same target again so it is not left under the panel — unless the user moved the map
  const sizeKey = `${Math.round(vp.size.w / 40)}x${Math.round(vp.size.h / 40)}`
  useEffect(() => {
    if (!userMoved.current) frameNow()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [panelOpen, sizeKey, !!agentReply])

  const toMetres = (clientX, clientY) => {
    const svg = svgRef.current
    const m = svg?.getScreenCTM()
    if (!m) return null
    const p = svg.createSVGPoint()
    p.x = clientX
    p.y = clientY
    return p.matrixTransform(m.inverse())
  }
  const zoomLimits = { maxW: (floor?.width_m || 60) * 2 }
  const onPan = (dx, dy) => {
    userMoved.current = true
    vp.set((v) => v && { ...v, x: v.x - dx * (v.w / vp.size.w), y: v.y - dy * (v.w / vp.size.w) })
  }
  const onZoom = (factor, clientX, clientY) => {
    const pt = toMetres(clientX, clientY)
    userMoved.current = true
    if (pt) vp.set((v) => v && zoomAt(v, factor, pt.x, pt.y, zoomLimits))
  }
  const zoomCentre = (factor) => {
    userMoved.current = true
    if (vp.vb) vp.animateTo(zoomAt(vp.vb, factor, vp.vb.x + vp.vb.w / 2, vp.vb.y + vp.vb.h / 2, zoomLimits))
  }

  // ── route + playback ──
  const route = useRoute(api, routeReq, routeVersion)
  const playKey = routeReq && route.data ? `${routeReq.key}-${route.data.path.map((p) => p.node_id).join('|')}` : null
  const targetFloorRef = useRef(null)
  const waiters = useRef([])
  const playback = useRoutePlayback(route.segments, {
    reducedMotion,
    playKey,
    autoplay: !!routeReq?.autoplay && !reducedMotion,
    onFloor: (fid) => { switchFloor(fid); fitFloor(fid) },
    onDone: () => {
      if (targetFloorRef.current) { switchFloor(targetFloorRef.current); fitFloor(targetFloorRef.current) }
      waiters.current.splice(0).forEach((r) => r())
    },
  })

  // A live aisle / lift change that alters the shown route gets a short notice.
  const prevPath = useRef(null)
  useEffect(() => {
    if (!route.data) return
    const sig = route.data.path.map((p) => p.node_id).join('|')
    const edge = pendingEdge.current
    if (edge && prevPath.current && prevPath.current !== sig) {
      const closed = edge.edge_type === 'walk' ? 'an aisle' : (dataRef.current.layout?.nodesById.get(edge.from_node_id)?.label || edge.edge_type)
      const using = [...new Set(route.segments.filter((s) => s.connectorLabel).map((s) => s.connectorLabel))].join(', ')
      toast(`Route updated: ${closed} is ${edge.blocked ? 'closed' : 'open again'}${using ? `, using ${using}` : ''}`, 'warn')
    }
    pendingEdge.current = null
    prevPath.current = sig
  }, [route.data, route.segments, toast])
  useEffect(() => { if (route.errorStep) toast(route.errorStep.instruction, 'error') }, [route.errorStep, toast])

  const routeStarted = useRef(false)
  const startRoute = useCallback((req) => {
    routeStarted.current = true
    pendingEdge.current = null
    prevPath.current = null
    targetFloorRef.current = req.targetFloor || null
    setRouteReq({ ...req, prefer: req.prefer || 'lift', key: localId() })
  }, [])

  // ── selection ──
  const selectProduct = useCallback((pid, { floorId: want, rackId, binId, highlightProductIds, locationScopes } = {}) => {
    const d = dataRef.current
    const rows = d.locationsByProduct.get(pid) || []
    const floors = new Set(rows.map((r) => r.floor_id))
    const fid = (want && floors.has(want) && want) || rows[0]?.floor_id || floorRef.current
    const floorRows = rows.filter((r) => r.floor_id === fid)
    const rid = (rackId && floorRows.some((r) => r.rack_id === rackId) && rackId) || floorRows[0]?.rack_id || null
    setSelection({ kind: 'product', id: pid, rackId: rid, binId: binId || null,
      highlightProductIds, locationScopes })
    switchFloor(fid)
    if (rid) focusOn(fid, [d.layout.racksById.get(rid)])
  }, [focusOn, switchFloor])

  const selectRack = useCallback((rid, { targetBins = [], targetShelves = [] } = {}) => {
    const rack = dataRef.current.layout.racksById.get(rid)
    if (!rack) return
    setSelection({ kind: 'rack', id: rid, targetBins: new Set(targetBins), targetShelves: new Set(targetShelves) })
    switchFloor(rack.floor_id)
    focusOn(rack.floor_id, [rack])
  }, [focusOn, switchFloor])

  const clearSelection = useCallback(() => {
    interactionVersion.current += 1
    setSelection(null)
    setBadges(new Map())
    setRouteReq(null)
  }, [])

  const userSelectProduct = (pid, rackId) => {
    interactionVersion.current += 1
    setRouteReq(null)
    setBadges(new Map())
    selectProduct(pid, { rackId, floorId: rackId ? floorOf(rackId) : undefined })
    if (narrow) setListOpen(false)
  }
  const userSelectRack = (rid) => {
    interactionVersion.current += 1
    setRouteReq(null)
    setBadges(new Map())
    selectRack(rid)
    if (narrow) setListOpen(false)
  }
  const onMarker = (rid) => {
    interactionVersion.current += 1
    if (selection?.kind === 'product' && (data.locationsByRack.get(rid) || []).some((r) => r.product_id === selection.id)) {
      setSelection((s) => ({ ...s, rackId: rid }))
      focusOn(floorOf(rid), [layout.racksById.get(rid)])
    } else userSelectRack(rid)
  }
  const onSelectAlert = (a) => {
    if (a.product_id) userSelectProduct(a.product_id, a.rack_id || undefined)
    else if (a.rack_id) { setRouteReq(null); selectRack(a.rack_id, { targetBins: a.bin_id ? [a.bin_id] : [] }) }
  }

  // ── agent commands → map ──
  const activeCmd = useRef(null)
  const interactionVersion = useRef(0)
  const knownId = (id) => (isProductId(id) ? dataRef.current.productsById.has(id) : dataRef.current.layout.ids.has(id))

  const run = useCallback(async (cmd, { refresh = false } = {}) => {
    const interaction = ++interactionVersion.current
    const d = dataRef.current
    const L = d.layout
    const bad = refresh ? [] : commandIds(cmd).filter((id) => !knownId(id))
    for (const id of bad) toast(`Unknown ID ${id} — nothing highlighted for it.`, 'error')
    const ok = (id) => !bad.includes(id)
    const floorName = (fid) => L.floorsById.get(fid)?.name || fid

    if (!refresh && !['clarify', 'not_found'].includes(cmd.action)) {
      setRouteReq(null)
      setBadges(new Map())
      targetFloorRef.current = null
      if (cmd.action !== 'heatmap') setLayer('map')
    }

    switch (cmd.action) {
      case 'clear':
        setSelection(null)
        fitFloor()
        return
      case 'not_found':
        toast(cmd.answer_text)
        return
      case 'clarify':
        setSelection({ kind: 'clarify', text: cmd.answer_text, candidates: cmd.candidates })
        return
      case 'locate_product': {
        const pids = cmd.product_ids.filter(ok)
        if (!pids.length) return
        let rows = await api.productLocations(pids)
        if (interaction !== interactionVersion.current) return
        const locFilter = (cmd.location_ids || []).filter(ok)
        if (locFilter.length) rows = rows.filter((r) => locFilter.some((l) => isWithin(r.bin_id, l)))
        const want = (cmd.floor_id && rows.some((r) => r.floor_id === cmd.floor_id) && cmd.floor_id) || rows[0]?.floor_id
        const best = rows.find((r) => r.floor_id === want)
        selectProduct(pids[0], { floorId: want, rackId: best?.rack_id,
          highlightProductIds: pids, locationScopes: locFilter })
        if (!rows.some((r) => r.quantity > 0)) {
          const product = d.productsById.get(pids[0])
          toast(product?.unplaced_quantity > 0
            ? `${product.name}: stock is awaiting a verified bin assignment.`
            : `${product?.name || pids[0]} has no stock in the selected locations.`)
        }
        if (!refresh && cmd.route && rows.length) {
          startRoute({ toId: cmd.route.to_id || pids[0], fromId: cmd.route.from_id, prefer: cmd.route.prefer, autoplay: true, targetFloor: want })
        }
        return
      }
      case 'show_location': {
        const ids = cmd.location_ids.filter(ok)
        if (!ids.length) return
        const first = ids[0]
        const p = parseLocationId(first)
        if (ids.length > 1) {
          const rackIds = [...new Set(ids.map(rackOf).filter(Boolean))]
          const racks = rackIds.map((id) => L.racksById.get(id))
          const fid = (cmd.floor_id && ok(cmd.floor_id) && cmd.floor_id) || p.floorId
          setSelection({ kind: 'group', ids: rackIds, title: `${racks.length} ${RACK_KIND[racks[0]?.type] || 'racks'}`,
            sub: [...new Set(racks.map((r) => floorName(r.floor_id)))].join(' and ') })
          switchFloor(fid)
          focusOn(fid, racks.filter((r) => r.floor_id === fid))
          return
        }
        if (p.level === 'floor' || p.level === 'warehouse') {
          setSelection(null)
          switchFloor(p.floorId || floorRef.current)
          fitFloor(p.floorId)
          return
        }
        if (p.level === 'zone') {
          const zoneRacks = (L.racksByFloor.get(p.floorId) || []).filter((r) => r.zone_id === first)
          setSelection({ kind: 'group', ids: zoneRacks.map((r) => r.id), zoneId: first,
            title: L.zonesById.get(first)?.name || first, sub: floorName(p.floorId) })
          switchFloor(p.floorId)
          focusOn(p.floorId, zoneRacks)
        } else {
          selectRack(p.rackId, {
            targetBins: p.binId ? [p.binId] : [],
            targetShelves: p.shelfId && !p.binId ? [p.shelfId] : [],
          })
        }
        if (!refresh && cmd.route) {
          startRoute({ toId: cmd.route.to_id || first, fromId: cmd.route.from_id, prefer: cmd.route.prefer, autoplay: true, targetFloor: p.floorId })
        }
        return
      }
      case 'navigate': {
        const to = cmd.route.to_id
        if (!ok(to)) return
        let targetFloor = floorOf(to)
        if (isProductId(to)) {
          const [row] = await api.productLocations([to])
          if (interaction !== interactionVersion.current) return
          selectProduct(to, row ? { floorId: row.floor_id, rackId: row.rack_id } : {})
          targetFloor = row?.floor_id
        } else {
          const p = parseLocationId(to)
          if (p?.rackId) selectRack(p.rackId, { targetBins: p.binId ? [p.binId] : [], targetShelves: p.shelfId && !p.binId ? [p.shelfId] : [] })
          else if (p?.level === 'zone') {
            const zoneRacks = (L.racksByFloor.get(p.floorId) || []).filter((r) => r.zone_id === to)
            setSelection({ kind: 'group', ids: zoneRacks.map((r) => r.id), zoneId: to, title: L.zonesById.get(to)?.name, sub: floorName(p.floorId) })
          }
        }
        if (!refresh) startRoute({ toId: to, fromId: cmd.route.from_id, prefer: cmd.route.prefer, autoplay: true, targetFloor })
        return
      }
      case 'count': {
        const sp = parseLocationId(cmd.scope.id)
        const prefix = sp?.level === 'warehouse' ? null : cmd.scope.id
        const pids = (cmd.product_ids || []).filter(ok)
        const rows = await api.productLocations(pids, prefix)
        if (interaction !== interactionVersion.current) return
        const fid = sp?.floorId || cmd.floor_id || rows[0]?.floor_id || floorRef.current
        const racksInScope = (L.racksByFloor.get(fid) || []).filter((r) => !prefix || isWithin(r.id, prefix) || isWithin(prefix, r.id))
        const perRack = sumBy(rows, 'rack_id')
        const total = !prefix
          ? d.products.filter((p) => !pids.length || pids.includes(p.product_id)).reduce((s,p) => s+p.total_quantity,0)
          : rows.reduce((s, r) => s + r.quantity, 0)
        const product = pids[0] ? d.productsById.get(pids[0]) : null
        const scopeName = sp?.rackId ? L.racksById.get(sp.rackId)?.name : sp?.level === 'zone' ? L.zonesById.get(cmd.scope.id)?.name
          : sp?.level === 'floor' ? floorName(cmd.scope.id) : 'the warehouse'
        setBadges(new Map(racksInScope.map((r) => [r.id, `${perRack.get(r.id) || 0}`])))
        setSelection({
          kind: 'count', title: product ? product.name : 'Units in stock', total, unit: product?.unit || 'units',
          sub: `in ${scopeName}${sp?.rackId ? ` · ${floorName(fid)}` : ''}${sp?.level === 'warehouse' ? ` · showing ${floorName(fid)}` : ''}`,
          perRack: racksInScope.map((r) => ({ rackId: r.id, qty: perRack.get(r.id) || 0 })).sort((a, b) => b.qty - a.qty),
        })
        switchFloor(fid)
        if (!refresh) {
          if (sp?.rackId || sp?.level === 'zone') focusOn(fid, racksInScope)
          else fitFloor(fid)
        }
        return
      }
      case 'heatmap': {
        const fid = ok(cmd.floor_id) ? cmd.floor_id : floorRef.current
        const metric = cmd.metric || 'total_units'
        const values = metric === 'product_quantity' && cmd.product_ids?.length
          ? sumBy(await api.productLocations(cmd.product_ids.filter(ok)), 'rack_id') : null
        if (interaction !== interactionVersion.current) return
        setSelection(null)
        setHeatCfg({ metric, values })
        setLayer('heat')
        switchFloor(fid)
        fitFloor(fid)
        return
      }
      case 'show_alerts': {
        const types = cmd.alert_types?.length ? cmd.alert_types : ['low_stock', 'out_of_stock', 'bin_over_capacity']
        const list = d.alerts.filter((a) => types.includes(a.type))
        setSelection(null)
        setTab('alerts')
        setListOpen(true)
        const fid = list.find((a) => a.floor_id)?.floor_id || floorRef.current
        switchFloor(fid)
        fitFloor(fid)
        return
      }
      default:
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [api, fitFloor, focusOn, selectProduct, selectRack, startRoute, switchFloor, toast])

  // ── command queue (in order, de-duplicated by ui_commands.id) ──
  const queue = useRef([])
  const seen = useRef(new Set())
  const busy = useRef(false)

  const process = useCallback(async (item) => {
    const res = validateCommand(item.payload)
    if (!res.ok) { toast(res.error, 'error'); return }
    activeCmd.current = res.command
    routeStarted.current = false
    try {
      await run(res.command)
    } catch (e) {
      toast(`Could not show that on the map: ${e.message}`, 'error')
      return
    }
    // Hold the queue while a route plays, so commands never trample each other.
    await (routeStarted.current && !reducedMotion
      ? new Promise((r) => { waiters.current.push(r); setTimeout(r, 8000) })
      : new Promise((r) => setTimeout(r, reducedMotion ? 0 : 400)))
  }, [run, toast, reducedMotion])

  const pump = useCallback(async () => {
    if (busy.current || dataRef.current.status !== 'ready') return
    const next = queue.current.shift()
    if (!next) return
    busy.current = true
    try { await process(next) } finally { busy.current = false; pump() }
  }, [process])

  const enqueue = useCallback((item) => {
    if (!item?.payload) return
    if (item.id) {
      if (seen.current.has(item.id)) return
      seen.current.add(item.id)
    }
    queue.current.push(item)
    pump()
  }, [pump])
  enqueueRef.current = enqueue

  useEffect(() => { if (data.status === 'ready') pump() }, [data.status, pump])
  useEffect(() => { if (command) enqueue(command) }, [command, enqueue])

  // Live stock: a shown count is recomputed in place (product/rack panels read live rows directly).
  const firstStock = useRef(true)
  useEffect(() => {
    if (firstStock.current) { firstStock.current = false; return }
    if (activeCmd.current?.action === 'count' && selection?.kind === 'count') run(activeCmd.current, { refresh: true }).catch(() => {})
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data.stockVersion])

  const selPid = selection?.kind === 'product' ? selection.id : null
  const movements = movementState.productId === selPid ? movementState.rows : []
  useEffect(() => {
    setMovementState({ productId: selPid, rows: [] })
    if (!selPid) return undefined
    let cancelled = false
    api.movements(selPid, 6).then((m) => { if (!cancelled) setMovementState({ productId: selPid, rows: m }) }).catch(() => {})
    return () => { cancelled = true }
  }, [api, selPid, data.stockVersion])

  // Esc: close the detail panel first, then the map.
  useEffect(() => {
    if (!visible) return undefined
    const onKey = (e) => {
      if (e.key !== 'Escape') return
      if (e.target instanceof HTMLInputElement && e.target.value) return
      if (selection) clearSelection()
      else onClose?.()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [visible, onClose, selection, clearSelection])

  // ── what the map shows ──
  const view = useMemo(() => {
    const highlight = new Set()
    const targetBins = new Set()
    let targetShelves = new Set()
    let zoneId = null
    let selectedRackId = null
    const s = selection
    if (s?.kind === 'product') {
      for (const r of productHighlightRows(s, data.locationsByProduct)) {
        highlight.add(r.rack_id); targetBins.add(r.bin_id)
      }
      selectedRackId = s.rackId
    } else if (s?.kind === 'rack') {
      highlight.add(s.id)
      selectedRackId = s.id
      s.targetBins.forEach((b) => targetBins.add(b))
      targetShelves = s.targetShelves
    } else if (s?.kind === 'group') {
      s.ids.forEach((id) => highlight.add(id))
      zoneId = s.zoneId || null
    } else if (s?.kind === 'count') {
      s.perRack.forEach((r) => highlight.add(r.rackId))
    }
    let heat = null
    let shownBadges = badges
    if (layer === 'heat' && layout) {
      const racks = layout.racksByFloor.get(currentFloor) || []
      const metric = heatCfg.metric === 'product_quantity' && !heatCfg.values ? 'total_units' : heatCfg.metric
      const values = new Map(racks.map((r) => [r.id, metric === 'product_quantity'
        ? heatCfg.values.get(r.id) || 0 : data.fillByRack.get(r.id)?.[metric] ?? 0]))
      const max = metric === 'fill_ratio' ? 1 : Math.max(1, ...values.values())
      heat = new Map(racks.map((r) => [r.id, heatColor(values.get(r.id), max)]))
      shownBadges = new Map(racks.map((r) => [r.id, formatMetric(metric, values.get(r.id))]))
    }
    const alertRacks = new Set(data.alerts.map((a) => a.rack_id).filter(Boolean))
    return { highlight, targetBins, targetShelves, zoneId, selectedRackId, heat, badges: shownBadges, alertRacks, flash }
  }, [selection, data.locationsByProduct, data.fillByRack, data.alerts, badges, layer, heatCfg, layout, currentFloor, flash])

  const markers = useMemo(() => {
    if (!layout || !currentFloor || layer === 'heat') return []
    const out = []
    for (const r of layout.racksByFloor.get(currentFloor) || []) {
      const units = data.fillByRack.get(r.id)?.total_units || 0
      const mine = selPid ? (data.locationsByRack.get(r.id) || []).filter((x) => x.product_id === selPid)
        .reduce((s, x) => s + x.quantity, 0) : 0
      const isSel = view.selectedRackId === r.id
      if (!units && !isSel) continue
      const node = layout.nodesById.get(r.access_node_id)
      const pos = node ? { x: node.x, y: node.y } : { x: r.x + r.width_m / 2, y: r.y + r.depth_m + 1 }
      let tone = 'default'
      let label = units
      if (selPid) {
        tone = mine ? (isSel ? 'selected' : 'target') : 'dim'
        label = mine || units
      } else if (isSel) tone = 'selected'
      else if (view.highlight.size && !view.highlight.has(r.id)) tone = 'dim'
      out.push({ rackId: r.id, ...pos, label, tone })
    }
    return out
  }, [layout, currentFloor, layer, data.fillByRack, data.locationsByRack, selPid, view.selectedRackId, view.highlight])

  const targetFloors = useMemo(() => {
    const s = selection
    if (s?.kind === 'product') return new Set((data.locationsByProduct.get(s.id) || []).map((r) => r.floor_id))
    if (s?.kind === 'rack') return new Set([floorOf(s.id)])
    if (s?.kind === 'group' || s?.kind === 'count') {
      return new Set((s.ids || s.perRack.map((r) => r.rackId)).map(floorOf))
    }
    return new Set()
  }, [selection, data.locationsByProduct])

  const onHover = (h) => {
    if (!h) { setHover(null); return }
    const rect = mapEl.current?.getBoundingClientRect()
    if (!rect) return
    setHover({ id: h.id, x: clamp(h.clientX - rect.left + 16, 8, rect.width - 250), y: clamp(h.clientY - rect.top + 16, 8, rect.height - 120) })
  }
  const setMapEl = useCallback((el) => { mapEl.current = el; vp.containerRef(el) }, [vp.containerRef])
  const askAgent = (text) => { setAsk(text); setTimeout(() => inputRef.current?.focus(), 0) }
  const send = (text) => { onAsk?.(text); setAsk('') }

  // ── render ──
  if (data.status === 'disabled') return null
  const ready = data.status === 'ready' && layout && currentFloor
  const launcher = !visible && ready && (
    <button className="twin-launcher" onClick={onActivate} title="Warehouse map" aria-label="Warehouse map">
      <MapIcon size={14} /><span className="twin-launcher-label">Warehouse map</span>
    </button>
  )
  if (!ready) {
    if (!visible) return null
    return (
      <div className="twin-root" ref={rootRef}>
        <div className="twin-state-card">
          {data.status === 'error' ? (
            <>
              <strong>The warehouse map could not load</strong>
              <p className="twin-muted">{data.error}</p>
              <div className="twin-state-actions">
                <button className="twin-back-btn" onClick={data.reload}><RefreshCw size={14} />Try again</button>
                <button className="twin-back-btn is-light" onClick={onClose}>Back to chat</button>
              </div>
            </>
          ) : <><span className="twin-spinner" /><span className="twin-muted">Loading the warehouse…</span></>}
        </div>
      </div>
    )
  }

  const routeFor = (match) => (routeReq && match ? route : null)
  let panel = null
  const panelProps = { onClose: clearSelection, reducedMotion }
  if (selection?.kind === 'product' && data.productsById.get(selection.id)) {
    panel = (
      <ProductDetail {...panelProps} product={data.productsById.get(selection.id)}
        rows={data.locationsByProduct.get(selection.id) || []} focusRackId={selection.rackId} focusBinId={selection.binId} layout={layout}
        movements={movements} route={routeFor(routeReq?.toId === selection.id)} rackView={rackView}
        onToggleRackView={() => setRackView((v) => !v)}
        onDirections={() => startRoute({ toId: selection.id, autoplay: true, targetFloor: floorOf(selection.rackId) })}
        onAsk={askAgent}
        onFocusRow={(r) => { interactionVersion.current += 1; selectProduct(selection.id, { floorId: r.floor_id, rackId: r.rack_id, binId: r.bin_id }) }} />
    )
  } else if (selection?.kind === 'rack' && layout.racksById.get(selection.id)) {
    const target = [...selection.targetBins][0] || [...selection.targetShelves][0] || selection.id
    panel = (
      <RackDetail {...panelProps} rack={layout.racksById.get(selection.id)} layout={layout}
        fill={data.fillByRack.get(selection.id)} rows={data.locationsByRack.get(selection.id) || []}
        productsById={data.productsById} targetBins={selection.targetBins} targetShelves={selection.targetShelves}
        route={routeFor(routeReq && rackOf(routeReq.toId) === selection.id)}
        onSelectProduct={(pid, rid) => userSelectProduct(pid, rid)}
        onDirections={() => startRoute({ toId: target, autoplay: true, targetFloor: floorOf(selection.id) })}
        onHeat={() => { setHeatCfg({ metric: 'fill_ratio', values: null }); setLayer('heat') }}
        onAsk={askAgent} />
    )
  } else if (selection?.kind === 'count') {
    panel = <CountDetail {...panelProps} result={selection} layout={layout} onSelectRack={userSelectRack} />
  } else if (selection?.kind === 'group') {
    panel = <GroupDetail {...panelProps} title={selection.title} sub={selection.sub} rackIds={selection.ids} data={data} onSelectRack={userSelectRack} />
  } else if (selection?.kind === 'clarify') {
    panel = (
      <ClarifyDetail {...panelProps} text={selection.text} candidates={selection.candidates}
        onPick={(c) => enqueue({ id: localId(), payload: c.product_id
          ? { version: '1.1', action: 'locate_product', answer_text: c.label, product_ids: [c.product_id] }
          : { version: '1.1', action: 'show_location', answer_text: c.label, location_ids: [c.location_id] } })} />
    )
  }

  const transfer = playback.transfer
  const showList = !narrow || listOpen
  const counts = { products: data.products.length, racks: (layout.racksByFloor.get(currentFloor) || []).length, alerts: data.alerts.length }

  return (
    <>
      <div className={`twin-root is-workspace${visible ? '' : ' is-hidden'}${narrow ? ' is-narrow' : ''}`} ref={rootRef}>
        {showList && (
          <InventoryPanel data={data} floorId={currentFloor} tab={tab} onTab={setTab} query={query} onQuery={setQuery}
            selection={selection} onSelectProduct={(pid) => userSelectProduct(pid)} onSelectRack={userSelectRack}
            onSelectAlert={onSelectAlert} onClose={narrow ? () => setListOpen(false) : null} />
        )}

        <section className="twin-map-card">
          <MapHeader warehouse={layout.raw.warehouses.find((w) => w.id === floor?.warehouse_id)} floors={layout.floors} floorId={currentFloor} targetFloors={targetFloors}
            onFloor={(fid) => { interactionVersion.current += 1; onScopeChange?.(fid); switchFloor(fid); fitFloor(fid) }} counts={counts} live={data.live}
            alertsOn={tab === 'alerts' && showList}
            onProducts={() => { setTab('products'); setListOpen(true) }}
            onRacks={() => { setTab('racks'); setListOpen(true) }}
            onAlerts={() => { setTab('alerts'); setListOpen(true) }}
            onClose={onClose} onToggleList={narrow ? () => setListOpen((o) => !o) : null} listOpen={listOpen} />

          <div className="twin-muted" role="status">Data checked {data.asOf || 'unknown'}{data.error ? ` · Refresh failed: ${data.error}` : ''}</div>
          <div className={`twin-map-viewport${panel ? ' has-panel' : ''}`} ref={setMapEl}>
            <FloorMap svgRef={svgRef} layout={layout} edges={data.edges} floorId={currentFloor} vb={vp.vb}
              view={view} markers={markers} binQty={data.binQty} route={route} playback={playback}
              reducedMotion={reducedMotion} registry={registry}
              onRack={(rid) => (selection?.kind === 'product' && view.highlight.has(rid) ? onMarker(rid) : userSelectRack(rid))}
              onMarker={onMarker} onHover={onHover} onPan={onPan} onZoom={onZoom} />

            <HoverCard hover={hover} data={data} selectedProductId={selPid} />

            {transfer && (
              <span className="twin-transfer" role="status">
                {transfer.label} {transfer.up ? '↑' : '↓'} {layout.floorsById.get(transfer.toFloorId)?.name}
              </span>
            )}

            <MapControls mpp={vp.mpp} layer={layer} heatMetric={heatCfg.metric}
              onLayer={(l) => { setLayer(l); if (l === 'heat' && heatCfg.metric === 'product_quantity' && !heatCfg.values) setHeatCfg({ metric: 'fill_ratio', values: null }) }}
              onZoomIn={() => zoomCentre(1.4)} onZoomOut={() => zoomCentre(1 / 1.4)} onFit={() => fitFloor()} />

            {panel}

            <div className="twin-dock-wrap">
              <AgentDock reply={agentReply} busy={agentBusy} value={ask} onChange={setAsk} onSend={send} inputRef={inputRef} token={token} />
            </div>

            <Toasts toasts={toasts} onDismiss={dismissToast} />
          </div>
        </section>
      </div>
      {launcher}
    </>
  )
}
