// Loads the static layout once, keeps stock / fill / alerts fresh, and listens
// to the live stream. Everything the map shows comes from here (fetched by ID),
// never from an agent's text.
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { openTwinStream } from '../lib/stream'
import { rackOf } from '../lib/ids'
import { latestRequest } from '../lib/latest'

function indexLayout(layout) {
  const by = (rows, key) => {
    const m = new Map()
    for (const r of rows) {
      if (!m.has(r[key])) m.set(r[key], [])
      m.get(r[key]).push(r)
    }
    return m
  }
  const floors = [...layout.floors].sort((a, b) => a.level - b.level)
  const ids = new Set()
  for (const t of ['warehouses', 'floors', 'zones', 'racks', 'shelves', 'bins', 'nav_nodes']) {
    for (const r of layout[t]) ids.add(r.id)
  }
  const shelvesByRack = by(layout.shelves, 'rack_id')
  const binsByShelf = by(layout.bins, 'shelf_id')
  const rackGrid = new Map()
  for (const rack of layout.racks) {
    const shelves = (shelvesByRack.get(rack.id) || []).sort((a, b) => a.level_index - b.level_index)
    const cols = Math.max(0, ...shelves.map((s) => (binsByShelf.get(s.id) || []).length))
    rackGrid.set(rack.id, { levels: shelves.length, cols, shelves })
  }
  return {
    raw: layout,
    ids,
    floors,
    floorsById: new Map(floors.map((f) => [f.id, f])),
    zonesByFloor: by(layout.zones, 'floor_id'),
    zonesById: new Map(layout.zones.map((z) => [z.id, z])),
    racksById: new Map(layout.racks.map((r) => [r.id, r])),
    racksByFloor: by(layout.racks, 'floor_id'),
    nodesById: new Map(layout.nav_nodes.map((n) => [n.id, n])),
    nodesByFloor: by(layout.nav_nodes, 'floor_id'),
    shelvesByRack,
    binsByShelf,
    rackGrid,
  }
}

export function useTwinData(api, { sessionId, enabled = true, handlers }) {
  const [status, setStatus] = useState('loading') // loading | ready | error | disabled
  const [error, setError] = useState(null)
  const [layout, setLayout] = useState(null)
  const [edges, setEdges] = useState([])
  const [snapshot, setSnapshot] = useState({ products: [], rack_fill: [], alerts: [], locations: [], as_of: null })
  const { products, rack_fill: rackFill, alerts, locations, as_of: asOf } = snapshot
  const pendingStock = useRef(latestRequest())
  const loadVersion = useRef(0)
  const [live, setLive] = useState(false)
  const [stockVersion, setStockVersion] = useState(0)
  const handlersRef = useRef(handlers)
  handlersRef.current = handlers

  const refreshStock = useCallback(async () => {
    // Every stock row (v_product_locations) — a few dozen for the demo — drives bin shading and markers.
    await pendingStock.current.run(() => api.snapshot(), (value) => {
      setSnapshot(value)
      setError(null)
      setStockVersion((v) => v + 1)
    }, (e) => setError(e.message))
  }, [api])

  const load = useCallback(async () => {
    const version = ++loadVersion.current
    setStatus('loading')
    setError(null)
    try {
      const st = await api.status()
      if (version !== loadVersion.current) return
      if (!st.enabled) {
        setStatus('disabled')
        return
      }
      const lay = await api.layout()
      if (version !== loadVersion.current) return
      setLayout(indexLayout(lay))
      setEdges(lay.nav_edges)
      await refreshStock()
      if (version !== loadVersion.current) return
      setStatus('ready')
    } catch (e) {
      if (version !== loadVersion.current) return
      setError(e.message)
      setStatus('error')
    }
  }, [api, refreshStock])

  useEffect(() => {
    if (enabled) load()
    return () => { pendingStock.current.invalidate(); loadVersion.current += 1 }
  }, [enabled, load])

  // Live stream: refetch by ID on every change (debounced), never trust event numbers for display.
  useEffect(() => {
    if (!enabled || status !== 'ready') return undefined
    let timer = null
    const scheduleRefresh = () => {
      clearTimeout(timer)
      timer = setTimeout(() => refreshStock().catch(() => {}), 120)
    }
    const close = openTwinStream(api.streamUrl(sessionId), {
      onLive: (connected) => { setLive(connected); if (connected) scheduleRefresh() },
      onCommand: (ev) => {
        if (ev.op === 'INSERT') handlersRef.current?.onCommand?.({ id: ev.row.id, payload: ev.row.payload, query: ev.row.query_text, source: 'realtime' })
      },
      onChange: (ev) => {
        if (ev.table === 'stock_locations') {
          scheduleRefresh()
          handlersRef.current?.onStockChange?.(rackOf(ev.row.bin_id), ev.row)
        } else if (ev.table === 'products' || ev.table === 'unplaced_stock') {
          scheduleRefresh()
        } else if (ev.table === 'alerts') {
          scheduleRefresh()
          if (ev.op === 'INSERT' && !ev.row.resolved_at) handlersRef.current?.onAlert?.(ev.row)
        } else if (ev.table === 'nav_edges') {
          api.navEdges().then((e) => {
            setEdges(e)
            handlersRef.current?.onEdgeChange?.(ev.row)
          }).catch(() => {})
        }
      },
    })
    return () => {
      clearTimeout(timer)
      close()
    }
  }, [api, enabled, status, sessionId, refreshStock])

  // Notifications are hints. Poll and refresh after reconnect to recover events missed in a gap.
  useEffect(() => {
    if (!enabled || status !== 'ready') return undefined
    const timer = setInterval(() => refreshStock().catch(() => {}), 15000)
    return () => clearInterval(timer)
  }, [enabled, status, refreshStock])

  const productsById = useMemo(() => new Map(products.map((p) => [p.product_id, p])), [products])
  const fillByRack = useMemo(() => new Map(rackFill.map((f) => [f.rack_id, f])), [rackFill])
  const index = useMemo(() => {
    const byProduct = new Map()
    const byRack = new Map()
    const binQty = new Map()
    for (const r of locations) {
      if (!byProduct.has(r.product_id)) byProduct.set(r.product_id, [])
      byProduct.get(r.product_id).push(r)
      if (!byRack.has(r.rack_id)) byRack.set(r.rack_id, [])
      byRack.get(r.rack_id).push(r)
      binQty.set(r.bin_id, (binQty.get(r.bin_id) || 0) + r.quantity)
    }
    return { byProduct, byRack, binQty }
  }, [locations])

  return {
    status, error, reload: load, layout, edges, products, productsById, rackFill, fillByRack,
    alerts, live, stockVersion, refreshStock, locations, asOf,
    locationsByProduct: index.byProduct, locationsByRack: index.byRack, binQty: index.binQty,
  }
}
