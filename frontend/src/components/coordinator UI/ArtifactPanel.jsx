import React, { useState, useEffect, useRef } from 'react'
import {
  X,
  Compass,
  Warehouse,
  Maximize2,
  Minimize2,
  ZoomIn,
  ZoomOut,
  RotateCcw,
  Building2,
  Boxes,
  Layers,
  Truck,
  Navigation,
  Check,
  ExternalLink,
  ChevronRight,
  ShieldCheck,
  AlertTriangle,
  Clock,
  Sparkles
} from 'lucide-react'

// ── Multi-Building Warehouse Complex Data ─────────────────────────────────────
export const WAREHOUSE_COMPLEX_DATA = {
  complex: {
    id: 'CMP-01',
    name: 'Colombo Logistics Complex',
    hubCode: 'NORTH-HUB',
    gateOrigin: { x: 55, y: 155, name: 'Gate 1' }
  },
  buildings: [
    {
      id: 'BLD-01',
      number: '1',
      name: 'Building 1 — High-Bay Hub',
      title: '1 · High-Bay Hub',
      category: 'Automated Pallet High-Bay',
      color: '#3B7BF6',
      status: '94% Operational',
      statusTone: 'is-ok',
      rect: { x: 50, y: 28, w: 125, h: 80 },
      capacity: '2,400 Pallet Bays',
      lots: '150 Stored Lots',
      mhe: '2 Forklifts Active',
      dockY: 108
    },
    {
      id: 'BLD-02',
      number: '2',
      name: 'Building 2 — Bulk Distribution',
      title: '2 · Bulk Distribution',
      category: 'Bulk Storage & Outbound',
      color: '#8B5CF6',
      status: '78% Operational',
      statusTone: 'is-ok',
      rect: { x: 195, y: 28, w: 115, h: 80 },
      capacity: '1,600 Pallet Bays',
      lots: '95 Stored Lots',
      mhe: '1 Shunt Truck',
      dockY: 108
    },
    {
      id: 'BLD-06',
      number: '6',
      name: 'Building 6 — MHE Fleet Depot',
      title: '6 · Fleet Depot',
      category: 'Fleet Maintenance & Chargers',
      color: '#FF7A1A',
      status: '8 Charging Bays',
      statusTone: 'is-ok',
      rect: { x: 330, y: 28, w: 105, h: 80 },
      capacity: '8 Fast Chargers',
      lots: '4 Vehicles Parked',
      mhe: '100% Ready',
      dockY: 108
    },
    {
      id: 'BLD-07',
      number: '7',
      name: 'Building 7 — Gatehouse & Scale',
      title: '7 · Gatehouse & Scale',
      category: 'Security & Weighbridge',
      color: '#1E293B',
      status: 'Online 24/7',
      statusTone: 'is-ok',
      rect: { x: 50, y: 130, w: 75, h: 70 },
      capacity: '60T Scale',
      lots: 'Inbound / Outbound',
      mhe: '1 AGV Station',
      dockY: 130
    },
    {
      id: 'BLD-03',
      number: '3',
      name: 'Building 3 — Tech Mezzanine',
      title: '3 · Tech Mezzanine',
      category: 'Cleanroom ESD Electronics',
      color: '#06B6D4',
      status: 'Regulated ESD',
      statusTone: 'is-ok',
      rect: { x: 145, y: 130, w: 115, h: 70 },
      capacity: '950 Electronics Bins',
      lots: '42 Stored Lots',
      mhe: '2.5T Freight Lift',
      dockY: 130
    },
    {
      id: 'BLD-04',
      number: '4',
      name: 'Building 4 — Cold Vault',
      title: '4 · Cold Vault',
      category: 'Pharma Cold-Chain (2°–4°C)',
      color: '#0284C7',
      status: 'Chilled Vault Active',
      statusTone: 'is-ok',
      rect: { x: 280, y: 130, w: 80, h: 70 },
      capacity: '320 Chilled Bays',
      lots: '50 Vaccine Lots',
      mhe: 'Airlock Port',
      dockY: 130
    },
    {
      id: 'BLD-05',
      number: '5',
      name: 'Building 5 — Quarantine Yard',
      title: '5 · Quarantine Yard',
      category: 'Hazmat & Returns Hold',
      color: '#E5484D',
      status: 'Restricted Access',
      statusTone: 'is-low',
      rect: { x: 380, y: 130, w: 55, h: 70 },
      capacity: '80 RMA Lots',
      lots: '14 Hold Lots',
      mhe: 'Spill Berm OK',
      dockY: 130
    }
  ],
  vehicles: [
    { id: 'FL-01', name: 'Forklift 1', coords: { x: 70, y: 96 }, color: '#22C55E', status: 'Active Picking' },
    { id: 'RT-01', name: 'Reach 1', coords: { x: 140, y: 96 }, color: '#22C55E', status: 'High-Bay Stacking' },
    { id: 'PJ-01', name: 'Pallet Jack', coords: { x: 215, y: 96 }, color: '#22C55E', status: 'Dock Transfer' },
    { id: 'AGV-01', name: 'Tugger AGV', coords: { x: 325, y: 120 }, color: '#22C55E', status: 'Transit Highway' },
    { id: 'RT-02', name: 'Reach 2 (Charging)', coords: { x: 370, y: 65 }, color: '#F59E0B', status: 'Fast Charger Bay 2' }
  ]
}

// ── Master Warehouse Inventory Catalog ────────────────────────────────────────
export const WAREHOUSE_INVENTORY_ITEMS = [
  {
    sku: 'SKU-4521',
    name: 'Wireless Barcode Scanner',
    category: 'Electronics & Tech',
    aisle: 12,
    shelf: 'B3',
    tier: 'B',
    bay: 'Bay 04',
    location: 'Aisle 12, Shelf B3, Bay 04',
    quantity: 340,
    available: 315,
    reserved: 25,
    reorder_point: 80,
    unit: 'units',
    status: 'IN_STOCK',
    statusLabel: 'In Stock',
    rack_color: '#f59e0b',
    burn_rate: 18.5,
    days_left: 18.4
  },
  {
    sku: 'SKU-7788',
    name: 'Thermal Label Printer',
    category: 'Dispatch Equipment',
    aisle: 5,
    shelf: 'A1',
    tier: 'A',
    bay: 'Bay 02',
    location: 'Aisle 5, Shelf A1, Bay 02',
    quantity: 15,
    available: 10,
    reserved: 5,
    reorder_point: 20,
    unit: 'units',
    status: 'LOW_STOCK',
    statusLabel: 'Low Stock',
    rack_color: '#3b82f6',
    burn_rate: 6.2,
    days_left: 2.4
  },
  {
    sku: 'SKU-9012',
    name: 'Heavy Duty Pallet Wrap',
    category: 'Packaging Consumables',
    aisle: 3,
    shelf: 'C2',
    tier: 'C',
    bay: 'Bay 08',
    location: 'Aisle 3, Shelf C2, Bay 08',
    quantity: 5,
    available: 3,
    reserved: 2,
    reorder_point: 25,
    unit: 'rolls',
    status: 'REORDER',
    statusLabel: 'Reorder Level',
    rack_color: '#ef4444',
    burn_rate: 4.8,
    days_left: 1.0
  },
  {
    sku: 'SKU-1088',
    name: 'Thermal Industrial Label Rolls',
    category: 'Packaging & Labels',
    aisle: 1,
    shelf: 'A3',
    tier: 'A',
    bay: 'Bay A-03',
    location: 'Aisle 1, Bay A-03, Shelf A3',
    quantity: 120,
    available: 110,
    reserved: 10,
    reorder_point: 50,
    unit: 'rolls',
    status: 'IN_STOCK',
    statusLabel: 'In Stock',
    rack_color: '#10b981',
    burn_rate: 12.0,
    days_left: 10.0
  },
  {
    sku: 'SKU-2045',
    name: 'Heavy Duty Forklift Battery Lithium',
    category: 'Heavy Hazmat / Power',
    aisle: 4,
    shelf: 'B12',
    tier: 'B',
    bay: 'Bay B-12',
    location: 'Aisle 4, Bay B-12, Shelf B12',
    quantity: 42,
    available: 38,
    reserved: 4,
    reorder_point: 15,
    unit: 'units',
    status: 'IN_STOCK',
    statusLabel: 'In Stock',
    rack_color: '#8b5cf6',
    burn_rate: 2.1,
    days_left: 20.0
  }
]

export default function ArtifactPanel({
  isOpen,
  onClose,
  activeTab = 'site_plan',
  setActiveTab,
  selectedMessage,
  onOpenFullscreenMap
}) {
  // ── UI States ──────────────────────────────────────────────────────────────
  const [isExpanded, setIsExpanded] = useState(false)
  
  // Site Plan State
  const [selectedBuilding, setSelectedBuilding] = useState(WAREHOUSE_COMPLEX_DATA.buildings[0])
  const [hoveredBuilding, setHoveredBuilding] = useState(null)
  const [routeLine, setRouteLine] = useState(null)
  const DEFAULT_SITE_VB = { x: 26, y: 12, w: 424, h: 200 }
  const [siteVb, setSiteVb] = useState(DEFAULT_SITE_VB)
  const siteSvgRef = useRef(null)

  // Floor Map State
  const [selectedProduct, setSelectedProduct] = useState(WAREHOUSE_INVENTORY_ITEMS[0])
  const [activeAisle, setActiveAisle] = useState(12)

  // ── Auto-Sync With Message Context ─────────────────────────────────────────
  useEffect(() => {
    if (!selectedMessage) return
    const text = `${selectedMessage.content || ''} ${JSON.stringify(selectedMessage.knowledge_details || {})} ${JSON.stringify(selectedMessage.inventory_details || {})}`

    // 1. Detect Building / Facility Mention
    const bldMatch = text.match(/BLD-0[1-7]|Building\s*[1-7]|Cold Vault|Quarantine Yard|High-Bay Hub|Bulk Distribution|Tech Mezzanine|Fleet Depot|Gatehouse/i)
    if (bldMatch) {
      const matchStr = bldMatch[0].toLowerCase()
      const found = WAREHOUSE_COMPLEX_DATA.buildings.find(b => 
        b.id.toLowerCase() === matchStr ||
        b.name.toLowerCase().includes(matchStr) ||
        matchStr.includes(b.number)
      )
      if (found) {
        setSelectedBuilding(found)
        traceRouteTo(found.rect.x + found.rect.w / 2, found.dockY || (found.rect.y + found.rect.h / 2))
      }
    }

    // 2. Detect SKU Mention
    const skuMatch = text.match(/SKU-\d{4}/i)
    if (skuMatch) {
      const skuStr = skuMatch[0].toUpperCase()
      const foundProduct = WAREHOUSE_INVENTORY_ITEMS.find(p => p.sku === skuStr)
      if (foundProduct) {
        setSelectedProduct(foundProduct)
        setActiveAisle(foundProduct.aisle)
      }
    }
  }, [selectedMessage])

  if (!isOpen) return null

  // ── Route Tracing from Gate 1 ──────────────────────────────────────────────
  const traceRouteTo = (destX, destY) => {
    const origin = WAREHOUSE_COMPLEX_DATA.complex.gateOrigin
    const corridorY = 120
    setRouteLine([
      [origin.x, origin.y],
      [origin.x, corridorY],
      [destX, corridorY],
      [destX, destY]
    ])
  }

  const handleSelectBuilding = (bld) => {
    setSelectedBuilding(bld)
    traceRouteTo(bld.rect.x + bld.rect.w / 2, bld.dockY || (bld.rect.y + bld.rect.h / 2))
  }

  const handleZoomSite = (factor) => {
    setSiteVb((prev) => {
      const nw = prev.w * factor
      const nh = prev.h * factor
      const dx = (nw - prev.w) / 2
      const dy = (nh - prev.h) / 2
      return { x: prev.x - dx, y: prev.y - dy, w: nw, h: nh }
    })
  }

  const handleResetSite = () => {
    setSiteVb(DEFAULT_SITE_VB)
    setRouteLine(null)
  }

  const handleSelectProduct = (prod) => {
    setSelectedProduct(prod)
    setActiveAisle(prod.aisle)
  }

  return (
    <aside className={`claude-artifact-panel ${isExpanded ? 'is-expanded' : ''}`} style={isExpanded ? { width: '740px', minWidth: '680px' } : { width: '540px', minWidth: '500px' }}>
      
      {/* ── Top Header ──────────────────────────────────────────────────────── */}
      <div className="artifact-panel-header">
        <div className="artifact-header-left">
          <div className="artifact-title-row">
            <Warehouse size={18} className="text-amber" />
            <h3 className="artifact-title">Warehouse Spatial Intelligence</h3>
          </div>
          <span className="artifact-subtitle">Interactive floor plans & multi-facility site plan</span>
        </div>

        <div className="flex items-center gap-2">
          {/* Toggle Panel Expand */}
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="artifact-close-btn"
            title={isExpanded ? "Collapse Width" : "Expand Width"}
          >
            {isExpanded ? <Minimize2 size={15} /> : <Maximize2 size={15} />}
          </button>

          {/* Close Panel */}
          <button onClick={onClose} className="artifact-close-btn" title="Close Panel">
            <X size={16} />
          </button>
        </div>
      </div>

      {/* ── Tabs Navigation ─────────────────────────────────────────────────── */}
      <div className="artifact-tabs-bar">
        <button
          className={`artifact-tab-btn ${activeTab === 'site_plan' ? 'active' : ''}`}
          onClick={() => setActiveTab('site_plan')}
        >
          <Compass size={14} className={activeTab === 'site_plan' ? 'text-blue' : ''} />
          <span>Warehouse Site Plan</span>
        </button>

        <button
          className={`artifact-tab-btn ${activeTab === 'floor_map' ? 'active' : ''}`}
          onClick={() => setActiveTab('floor_map')}
        >
          <Layers size={14} className={activeTab === 'floor_map' ? 'text-amber' : ''} />
          <span>Warehouse Floor Map</span>
        </button>

        {onOpenFullscreenMap && (
          <button
            className="artifact-tab-btn ml-auto hover:text-white"
            onClick={onOpenFullscreenMap}
            title="Open in full screen workspace"
            style={{ marginLeft: 'auto', background: 'rgba(255,255,255,0.06)' }}
          >
            <ExternalLink size={12} />
            <span>Fullscreen Twin</span>
          </button>
        )}
      </div>

      {/* ── Panel Scrollable Content Body ───────────────────────────────────── */}
      <div className="artifact-panel-content p-4 space-y-4" style={{ overflowY: 'auto', flex: 1 }}>

        {/* ═════════════════════════════════════════════════════════════════════ */}
        {/* TAB 1: WAREHOUSE SITE PLAN (MULTI-BUILDING COMPLEX)                   */}
        {/* ═════════════════════════════════════════════════════════════════════ */}
        {activeTab === 'site_plan' && (
          <div className="site-plan-tab-view space-y-4">
            
            {/* Header Status Strip */}
            <div className="flex items-center justify-between bg-slate-900/70 border border-slate-800 rounded-xl px-3.5 py-2.5">
              <div>
                <div className="text-xs font-semibold text-white tracking-wide">
                  {WAREHOUSE_COMPLEX_DATA.complex.name}
                </div>
                <div className="text-[11px] text-slate-400">
                  7 Facilities · Live Fleet Tracking · Gate 1 Entry
                </div>
              </div>
              
              <div className="flex items-center gap-1.5">
                <button
                  onClick={() => handleZoomSite(0.85)}
                  className="p-1 rounded hover:bg-slate-800 text-slate-300"
                  title="Zoom In"
                >
                  <ZoomIn size={14} />
                </button>
                <button
                  onClick={() => handleZoomSite(1.15)}
                  className="p-1 rounded hover:bg-slate-800 text-slate-300"
                  title="Zoom Out"
                >
                  <ZoomOut size={14} />
                </button>
                <button
                  onClick={handleResetSite}
                  className="p-1 rounded hover:bg-slate-800 text-slate-300"
                  title="Reset Fit"
                >
                  <RotateCcw size={14} />
                </button>
              </div>
            </div>

            {/* Quick Facility Selector Pills */}
            <div className="flex flex-wrap gap-1.5 pb-1">
              {WAREHOUSE_COMPLEX_DATA.buildings.map((b) => {
                const isSelected = selectedBuilding?.id === b.id
                return (
                  <button
                    key={b.id}
                    onClick={() => handleSelectBuilding(b)}
                    className={`text-xs px-2.5 py-1 rounded-full font-medium transition border flex items-center gap-1.5 ${
                      isSelected
                        ? 'bg-blue-600/30 text-white border-blue-500 shadow-sm'
                        : 'bg-slate-900/60 text-slate-400 border-slate-800 hover:border-slate-700 hover:text-slate-200'
                    }`}
                  >
                    <span
                      className="w-2 h-2 rounded-full flex-shrink-0"
                      style={{ backgroundColor: b.color }}
                    />
                    <span>{b.title}</span>
                  </button>
                )
              })}
            </div>

            {/* Interactive SVG Site Plan Container */}
            <div className="relative bg-slate-950 rounded-2xl border border-slate-800/90 overflow-hidden shadow-inner p-1.5">
              <svg
                ref={siteSvgRef}
                viewBox={`${siteVb.x} ${siteVb.y} ${siteVb.w} ${siteVb.h}`}
                className="w-full h-64 select-none"
                style={{ display: 'block', background: '#090D16' }}
              >
                <defs>
                  <filter id="cleanShadowArtifact" x="-10%" y="-10%" width="120%" height="120%">
                    <feDropShadow dx="0" dy="1" stdDeviation="1" floodColor="#000000" floodOpacity="0.4" />
                  </filter>
                </defs>

                {/* 1. Perimeter Container */}
                <rect
                  x="32"
                  y="15"
                  width="416"
                  height="194"
                  rx="10"
                  fill="#0F172A"
                  stroke="#1E293B"
                  strokeWidth="1.2"
                />

                {/* Gate 1 Entrance Tag */}
                <g transform="translate(34, 155)">
                  <rect x="0" y="-6" width="14" height="12" rx="2" fill="#2563EB" />
                  <text x="7" y="1.5" fontSize="2.8" fontWeight="bold" fill="#FFFFFF" textAnchor="middle">GATE 1</text>
                </g>

                {/* 2. Logistics Roadways */}
                <g>
                  {/* Central Highway */}
                  <rect x="36" y="113" width="404" height="14" rx="2" fill="#1E293B" opacity="0.6" />
                  <line x1="38" y1="120" x2="438" y2="120" stroke="#334155" strokeWidth="0.8" strokeDasharray="4 4" />

                  {/* North-South Corridors */}
                  <rect x="178" y="22" width="12" height="180" rx="2" fill="#1E293B" opacity="0.4" />
                  <line x1="184" y1="24" x2="184" y2="200" stroke="#334155" strokeWidth="0.6" strokeDasharray="3 3" />

                  <rect x="313" y="22" width="12" height="180" rx="2" fill="#1E293B" opacity="0.4" />
                  <line x1="319" y1="24" x2="319" y2="200" stroke="#334155" strokeWidth="0.6" strokeDasharray="3 3" />
                </g>

                {/* 3. Parked Trucks at Loading Docks */}
                <g>
                  <rect x="71" y="108" width="8" height="14" rx="1.5" fill="#334155" stroke="#475569" strokeWidth="0.5" />
                  <rect x="126" y="108" width="8" height="14" rx="1.5" fill="#1E40AF" stroke="#3B82F6" strokeWidth="0.5" />
                  <rect x="236" y="108" width="8" height="14" rx="1.5" fill="#6D28D9" stroke="#8B5CF6" strokeWidth="0.5" />
                </g>

                {/* 4. Active Route Tracing */}
                {routeLine && routeLine.length > 1 && (
                  <path
                    d={`M ${routeLine.map((p) => p.join(',')).join(' L ')}`}
                    fill="none"
                    stroke="#22C55E"
                    strokeWidth="2.4"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeDasharray="4 2"
                    style={{ animation: 'dash 1.2s linear infinite' }}
                  />
                )}

                {/* 5. Buildings */}
                {WAREHOUSE_COMPLEX_DATA.buildings.map((b) => {
                  const isSelected = selectedBuilding?.id === b.id
                  const isHovered = hoveredBuilding?.id === b.id

                  return (
                    <g
                      key={b.id}
                      onClick={() => handleSelectBuilding(b)}
                      onMouseEnter={() => setHoveredBuilding(b)}
                      onMouseLeave={() => setHoveredBuilding(null)}
                      style={{ cursor: 'pointer' }}
                    >
                      {/* Building Footprint */}
                      <rect
                        x={b.rect.x}
                        y={b.rect.y}
                        width={b.rect.w}
                        height={b.rect.h}
                        rx="6"
                        fill={isSelected ? '#1E293B' : '#141E33'}
                        stroke={isSelected ? b.color : isHovered ? '#64748B' : '#334155'}
                        strokeWidth={isSelected ? '2' : '1'}
                      />

                      {/* Number Header Badge */}
                      <rect
                        x={b.rect.x + 4}
                        y={b.rect.y + 4}
                        width="11"
                        height="10"
                        rx="2"
                        fill={b.color}
                      />
                      <text
                        x={b.rect.x + 9.5}
                        y={b.rect.y + 11}
                        fontSize="6"
                        fontWeight="bold"
                        fill="#FFFFFF"
                        textAnchor="middle"
                      >
                        {b.number}
                      </text>

                      {/* Building Name */}
                      <text
                        x={b.rect.x + 19}
                        y={b.rect.y + 11}
                        fontSize="4.8"
                        fontWeight="600"
                        fill="#FFFFFF"
                      >
                        {b.title.split('·')[1]?.trim() || b.name}
                      </text>

                      {/* Category Label */}
                      <text
                        x={b.rect.x + 6}
                        y={b.rect.y + 24}
                        fontSize="3.8"
                        fill="#94A3B8"
                      >
                        {b.category}
                      </text>

                      {/* Capacity / Lots */}
                      <text
                        x={b.rect.x + 6}
                        y={b.rect.y + 36}
                        fontSize="3.6"
                        fill="#CBD5E1"
                        fontWeight="500"
                      >
                        {b.capacity} · {b.lots}
                      </text>

                      {/* Live Status Pill */}
                      <g transform={`translate(${b.rect.x + b.rect.w - 18}, ${b.rect.y + 5})`}>
                        <circle cx="2" cy="2" r="1.8" fill={b.statusTone === 'is-ok' ? '#22C55E' : '#E5484D'} />
                      </g>
                    </g>
                  )
                })}

                {/* 6. Fleet Vehicles */}
                {WAREHOUSE_COMPLEX_DATA.vehicles.map((v) => (
                  <g key={v.id} transform={`translate(${v.coords.x}, ${v.coords.y})`}>
                    <circle cx="0" cy="0" r="4.5" fill={v.color} fillOpacity="0.3" />
                    <circle cx="0" cy="0" r="2.8" fill={v.color} stroke="#FFFFFF" strokeWidth="0.6" />
                    <rect x="-8" y="4.5" width="16" height="5.5" rx="1.2" fill="#0F172A" stroke="#334155" strokeWidth="0.4" />
                    <text x="0" y="8.5" fontSize="2.8" fontWeight="bold" fill="#F8FAFC" textAnchor="middle">{v.id}</text>
                  </g>
                ))}
              </svg>
            </div>

            {/* Selected Facility Inspector Card */}
            {selectedBuilding && (
              <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-3.5 space-y-3">
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-2">
                    <span
                      className="w-6 h-6 rounded flex items-center justify-center font-bold text-white text-xs"
                      style={{ backgroundColor: selectedBuilding.color }}
                    >
                      {selectedBuilding.number}
                    </span>
                    <div>
                      <div className="font-semibold text-white text-sm">
                        {selectedBuilding.name}
                      </div>
                      <div className="text-xs text-slate-400">
                        {selectedBuilding.category}
                      </div>
                    </div>
                  </div>

                  <span className="text-[11px] px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 font-medium border border-emerald-500/20">
                    {selectedBuilding.status}
                  </span>
                </div>

                <div className="grid grid-cols-3 gap-2 pt-1 border-t border-slate-800/80 text-xs">
                  <div>
                    <span className="block text-slate-400 text-[10px] uppercase font-semibold">Capacity</span>
                    <span className="font-medium text-slate-200">{selectedBuilding.capacity}</span>
                  </div>
                  <div>
                    <span className="block text-slate-400 text-[10px] uppercase font-semibold">Active Lots</span>
                    <span className="font-medium text-slate-200">{selectedBuilding.lots}</span>
                  </div>
                  <div>
                    <span className="block text-slate-400 text-[10px] uppercase font-semibold">MHE Fleet</span>
                    <span className="font-medium text-slate-200">{selectedBuilding.mhe}</span>
                  </div>
                </div>

                <div className="flex items-center gap-2 pt-1">
                  <button
                    onClick={() => traceRouteTo(selectedBuilding.rect.x + selectedBuilding.rect.w / 2, selectedBuilding.dockY || selectedBuilding.rect.y + selectedBuilding.rect.h / 2)}
                    className="flex-1 text-xs py-1.5 px-3 rounded-lg bg-blue-600/20 text-blue-300 border border-blue-500/30 hover:bg-blue-600/30 font-medium transition flex items-center justify-center gap-1.5"
                  >
                    <Navigation size={13} />
                    <span>Trace Route from Gate 1</span>
                  </button>

                  <button
                    onClick={() => setActiveTab('floor_map')}
                    className="flex-1 text-xs py-1.5 px-3 rounded-lg bg-slate-800 text-slate-200 border border-slate-700 hover:bg-slate-700 font-medium transition flex items-center justify-center gap-1.5"
                  >
                    <Layers size={13} />
                    <span>View Floor Map ➔</span>
                  </button>
                </div>
              </div>
            )}
          </div>
        )}

        {/* ═════════════════════════════════════════════════════════════════════ */}
        {/* TAB 2: WAREHOUSE FLOOR MAP (HIGH-BAY INVENTORY DIGITAL TWIN)          */}
        {/* ═════════════════════════════════════════════════════════════════════ */}
        {activeTab === 'floor_map' && (
          <div className="floor-map-tab-view space-y-4">
            
            {/* Header Status Strip */}
            <div className="flex items-center justify-between bg-slate-900/70 border border-slate-800 rounded-xl px-3.5 py-2.5">
              <div>
                <div className="text-xs font-semibold text-white tracking-wide">
                  Warehouse Floor Alpha — High-Bay Storage
                </div>
                <div className="text-[11px] text-slate-400">
                  14 Aisles · 4 Vertical Tiers · Live AGV Pick Line
                </div>
              </div>

              <span className="text-[11px] px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 font-medium border border-emerald-500/20">
                Aisle {activeAisle} Selected
              </span>
            </div>

            {/* Quick SKU Selector Pills */}
            <div>
              <div className="text-[11px] text-slate-400 font-semibold mb-1.5 uppercase tracking-wider">
                Fast SKU Inspector
              </div>
              <div className="flex flex-wrap gap-1.5">
                {WAREHOUSE_INVENTORY_ITEMS.map((item) => {
                  const isSelected = selectedProduct?.sku === item.sku
                  return (
                    <button
                      key={item.sku}
                      onClick={() => handleSelectProduct(item)}
                      className={`text-xs px-2.5 py-1 rounded-full font-medium transition border flex items-center gap-1.5 ${
                        isSelected
                          ? 'bg-amber-500/30 text-amber-200 border-amber-500 shadow-sm'
                          : 'bg-slate-900/60 text-slate-400 border-slate-800 hover:border-slate-700 hover:text-slate-200'
                      }`}
                    >
                      <span
                        className="w-2 h-2 rounded-full flex-shrink-0"
                        style={{ backgroundColor: item.rack_color }}
                      />
                      <span>{item.sku}</span>
                      <span className="text-[10px] opacity-75 font-mono">{item.quantity}</span>
                    </button>
                  )
                })}
              </div>
            </div>

            {/* High-Bay Storage Racks Grid (Aisle 1 to 14) */}
            <div className="bg-slate-950 rounded-2xl border border-slate-800/90 p-3 shadow-inner space-y-2">
              <div className="flex items-center justify-between text-[11px] text-slate-400 font-mono">
                <span>RACK TIERS (D · C · B · A)</span>
                <span className="text-amber-400">Target: Aisle {activeAisle} · Shelf {selectedProduct.shelf}</span>
              </div>

              {/* 14 Aisles Floor Layout */}
              <div className="grid grid-cols-7 sm:grid-cols-14 gap-1 pt-1">
                {Array.from({ length: 14 }, (_, i) => i + 1).map((aisleNum) => {
                  const isAisleActive = aisleNum === activeAisle
                  return (
                    <button
                      key={aisleNum}
                      onClick={() => {
                        setActiveAisle(aisleNum)
                        const matching = WAREHOUSE_INVENTORY_ITEMS.find(p => p.aisle === aisleNum)
                        if (matching) setSelectedProduct(matching)
                      }}
                      className={`flex flex-col items-center p-1 rounded-lg border transition ${
                        isAisleActive
                          ? 'bg-amber-500/20 border-amber-500 shadow-sm'
                          : 'bg-slate-900/80 border-slate-800 hover:border-slate-700'
                      }`}
                    >
                      <span className={`text-[10px] font-mono font-bold mb-1 ${isAisleActive ? 'text-amber-300' : 'text-slate-400'}`}>
                        A{String(aisleNum).padStart(2, '0')}
                      </span>

                      {/* 4 Vertical Tiers per Rack */}
                      {['D', 'C', 'B', 'A'].map((tier) => {
                        const isCellTarget = isAisleActive && selectedProduct.tier === tier
                        return (
                          <div
                            key={tier}
                            className={`w-full h-3.5 my-0.5 rounded-sm flex items-center justify-center transition ${
                              isCellTarget
                                ? 'bg-amber-400 shadow-md animate-pulse'
                                : isAisleActive
                                  ? 'bg-amber-900/40 border border-amber-600/30'
                                  : 'bg-slate-800/60 border border-slate-700/40'
                            }`}
                          >
                            {isCellTarget && (
                              <div className="w-1.5 h-1.5 bg-black rounded-full" />
                            )}
                          </div>
                        )
                      })}
                    </button>
                  )
                })}
              </div>

              {/* AGV Transit Runway Strip */}
              <div className="mt-2 pt-2 border-t border-slate-800/80 flex items-center justify-between text-[11px] text-slate-400">
                <div className="flex items-center gap-1.5">
                  <div className="w-2 h-2 rounded-full bg-emerald-400 animate-ping" />
                  <span>AGV Transit Runway 05 (Automated Guided Vehicles)</span>
                </div>
                <span className="font-mono text-emerald-400 text-[10px]">1.2 m/s Autonomous Flow</span>
              </div>
            </div>

            {/* Selected Product Inventory Details Card */}
            {selectedProduct && (
              <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-3.5 space-y-3">
                <div className="flex items-start justify-between">
                  <div>
                    <div className="font-bold text-white text-sm">
                      {selectedProduct.name}
                    </div>
                    <div className="text-xs text-slate-400 font-mono">
                      {selectedProduct.sku} · {selectedProduct.category}
                    </div>
                  </div>

                  <span className={`text-[11px] px-2.5 py-0.5 rounded-full font-medium border ${
                    selectedProduct.status === 'IN_STOCK'
                      ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                      : selectedProduct.status === 'LOW_STOCK'
                        ? 'bg-blue-500/10 text-blue-400 border-blue-500/20'
                        : 'bg-rose-500/10 text-rose-400 border-rose-500/20'
                  }`}>
                    {selectedProduct.statusLabel}
                  </span>
                </div>

                <div className="grid grid-cols-4 gap-2 pt-1 border-t border-slate-800/80 text-xs">
                  <div>
                    <span className="block text-slate-400 text-[10px] uppercase font-semibold">Aisle</span>
                    <span className="font-medium text-slate-200">Aisle {selectedProduct.aisle}</span>
                  </div>
                  <div>
                    <span className="block text-slate-400 text-[10px] uppercase font-semibold">Shelf / Tier</span>
                    <span className="font-medium text-slate-200">{selectedProduct.shelf} (Tier {selectedProduct.tier})</span>
                  </div>
                  <div>
                    <span className="block text-slate-400 text-[10px] uppercase font-semibold">Bay</span>
                    <span className="font-medium text-slate-200">{selectedProduct.bay}</span>
                  </div>
                  <div>
                    <span className="block text-slate-400 text-[10px] uppercase font-semibold">Available</span>
                    <span className="font-medium text-emerald-400 font-mono">{selectedProduct.available} {selectedProduct.unit}</span>
                  </div>
                </div>

                <div className="grid grid-cols-3 gap-2 pt-1 border-t border-slate-800/80 text-xs">
                  <div>
                    <span className="block text-slate-400 text-[10px] uppercase font-semibold">On-Hand Total</span>
                    <span className="font-mono text-white">{selectedProduct.quantity} {selectedProduct.unit}</span>
                  </div>
                  <div>
                    <span className="block text-slate-400 text-[10px] uppercase font-semibold">Reserved Orders</span>
                    <span className="font-mono text-amber-300">{selectedProduct.reserved} {selectedProduct.unit}</span>
                  </div>
                  <div>
                    <span className="block text-slate-400 text-[10px] uppercase font-semibold">Reorder Threshold</span>
                    <span className="font-mono text-slate-300">{selectedProduct.reorder_point} {selectedProduct.unit}</span>
                  </div>
                </div>

                {/* Switch to Site Plan */}
                <div className="pt-1">
                  <button
                    onClick={() => setActiveTab('site_plan')}
                    className="w-full text-xs py-1.5 px-3 rounded-lg bg-slate-800 text-slate-200 border border-slate-700 hover:bg-slate-700 font-medium transition flex items-center justify-center gap-1.5"
                  >
                    <Compass size={13} className="text-blue-400" />
                    <span>View Building on Warehouse Site Plan ➔</span>
                  </button>
                </div>
              </div>
            )}
          </div>
        )}

      </div>
    </aside>
  )
}
