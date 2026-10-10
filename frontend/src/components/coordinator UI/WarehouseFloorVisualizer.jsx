import React, { useState, useEffect } from 'react'
import {
  Warehouse,
  Boxes,
  Cpu,
  Truck,
  AlertTriangle,
  FileText,
  TrendingDown,
  ShieldAlert,
  ArrowRightLeft,
  Wrench,
  Search,
  CheckCircle2,
  Clock,
  BatteryCharging,
  Thermometer,
  Weight,
  Sparkles,
  ChevronRight,
  ExternalLink,
  ShieldCheck,
  Send
} from 'lucide-react'

// Master warehouse catalog
const WAREHOUSE_ITEMS = [
  {
    sku: 'SKU-4521',
    name: 'Wireless Barcode Scanner',
    category: 'Electronics & Tech',
    aisle: 12,
    shelf: 'B3',
    tier: 'B',
    bay: 'Bay 04',
    zone: 'Zone B - Electronics & Tech',
    location: 'Aisle 12, Shelf B3, Bay 04',
    quantity: 340,
    available: 315,
    reserved: 25,
    safety_stock: 50,
    reorder_point: 80,
    reorder_qty: 200,
    unit: 'units',
    status: 'IN_STOCK',
    occupancy_pct: 78.5,
    weight_kg: 0.45,
    temperature: '20.2 °C (Climate Monitored)',
    cycle_count: 'Tomorrow, 08:00 AM',
    rack_color: '#f59e0b',
    burn_rate: 18.5,
    days_left: 18.4,
    lead_time: 3
  },
  {
    sku: 'SKU-7788',
    name: 'Thermal Label Printer',
    category: 'Dispatch Equipment',
    aisle: 5,
    shelf: 'A1',
    tier: 'A',
    bay: 'Bay 02',
    zone: 'Zone A - Dispatch Packing',
    location: 'Aisle 5, Shelf A1, Bay 02',
    quantity: 15,
    available: 10,
    reserved: 5,
    safety_stock: 10,
    reorder_point: 20,
    reorder_qty: 30,
    unit: 'units',
    status: 'LOW_STOCK',
    occupancy_pct: 45.0,
    weight_kg: 3.80,
    temperature: '21.0 °C (Ambient)',
    cycle_count: 'In 3 Days',
    rack_color: '#3b82f6',
    burn_rate: 6.2,
    days_left: 2.4,
    lead_time: 4
  },
  {
    sku: 'SKU-9012',
    name: 'Heavy Duty Pallet Wrap',
    category: 'Packaging Consumables',
    aisle: 3,
    shelf: 'C2',
    tier: 'C',
    bay: 'Bay 08',
    zone: 'Zone C - Bulk Pallet Storage',
    location: 'Aisle 3, Shelf C2, Bay 08',
    quantity: 5,
    available: 3,
    reserved: 2,
    safety_stock: 20,
    reorder_point: 25,
    reorder_qty: 100,
    unit: 'rolls',
    status: 'OUT_OF_STOCK',
    occupancy_pct: 12.0,
    weight_kg: 22.0,
    temperature: '18.5 °C (Standard)',
    cycle_count: 'Immediate Physical Audit',
    rack_color: '#ef4444',
    burn_rate: 32.0,
    days_left: 0.2,
    lead_time: 3
  },
  {
    sku: 'SKU-1088',
    name: 'Thermal Industrial Label Rolls',
    category: 'Consumables',
    aisle: 1,
    shelf: 'A3',
    tier: 'A',
    bay: 'Bay A-03',
    zone: 'Zone A - High Turn Consumables',
    location: 'Aisle 1, Bay A-03, Shelf A3',
    quantity: 120,
    available: 110,
    reserved: 10,
    safety_stock: 30,
    reorder_point: 50,
    reorder_qty: 150,
    unit: 'rolls',
    status: 'IN_STOCK',
    occupancy_pct: 85.0,
    weight_kg: 1.20,
    temperature: '20.5 °C (Climate Controlled)',
    cycle_count: 'Weekly, Friday',
    rack_color: '#10b981',
    burn_rate: 45.0,
    days_left: 2.7,
    lead_time: 2
  },
  {
    sku: 'SKU-2045',
    name: 'Heavy Duty Forklift Battery Lithium',
    category: 'Heavy Hazmat / Power',
    aisle: 4,
    shelf: 'B12',
    tier: 'B',
    bay: 'Bay B-12',
    zone: 'Zone D - Heavy Machinery & Batteries',
    location: 'Aisle 4, Bay B-12, Shelf B12',
    quantity: 42,
    available: 34,
    reserved: 8,
    safety_stock: 15,
    reorder_point: 25,
    reorder_qty: 30,
    unit: 'units',
    status: 'IN_STOCK',
    occupancy_pct: 68.0,
    weight_kg: 420.0,
    temperature: '19.0 °C (Hazmat Thermal Guarded)',
    cycle_count: 'Daily Shift Check',
    rack_color: '#8b5cf6',
    burn_rate: 4.5,
    days_left: 9.3,
    lead_time: 10
  }
]

export default function WarehouseFloorVisualizer({ selectedMessage, currentUser }) {
  // Navigation sub-tab inside Member 1 Inventory Hub
  const [subTab, setSubTab] = useState('map') // 'map' | 'doc_parser' | 'predictor' | 'anomalies' | 'transfers' | 'equipment'
  const [selectedSku, setSelectedSku] = useState('SKU-4521')
  const [searchFilter, setSearchFilter] = useState('')
  const [selectedAisle, setSelectedAisle] = useState(12)
  const [actionNotice, setActionNotice] = useState('')
  // Live item from the inventory agent's answer; its numbers win over the static catalog
  const [liveItem, setLiveItem] = useState(null)

  // Interactive Document Parser state
  const [docInputText, setDocInputText] = useState(
    'From: Apex Automotive Supplies <orders@apexauto.com>\nSubject: Inbound Manifest Confirmed PO-99214\nDispatched 150 units of Wireless Barcode Scanner (SKU-4521). Expected delivery date 2026-10-15.'
  )
  const [parsedDocState, setParsedDocState] = useState(null)

  // Interactive Equipment Health test input
  const [equipmentInput, setEquipmentInput] = useState('Forklift 3 mast grinding and vibration when raising heavy battery pack')
  const [healthAnalysisState, setHealthAnalysisState] = useState(null)

  // Synchronize when chat selects a message containing inventory details
  useEffect(() => {
    if (!selectedMessage) return

    // 1. Check direct inventory_details from backend
    const inv = selectedMessage.inventory_details || selectedMessage.metadata?.inventory_details
    if (inv) {
      if (inv.items && inv.items.length > 0) {
        const item = inv.items[0]
        setLiveItem(item)
        setSelectedSku(item.sku)
        if (item.aisle) setSelectedAisle(item.aisle)
      }
      if (inv.sub_intent) {
        if (inv.sub_intent === 'document_parser') setSubTab('doc_parser')
        else if (inv.sub_intent === 'equipment_health') setSubTab('equipment')
        else if (inv.sub_intent === 'anomaly_watcher') setSubTab('anomalies')
        else if (inv.sub_intent === 'transfer_advisor') setSubTab('transfers')
        else if (inv.sub_intent === 'reorder_predictor') setSubTab('predictor')
        else setSubTab('map')
      }
      if (inv.document_result) setParsedDocState(inv.document_result)
      if (inv.equipment_health_result) setHealthAnalysisState(inv.equipment_health_result)
      return
    }

    // 2. Check skuData fallback
    if (selectedMessage.skuData?.sku) {
      const match = WAREHOUSE_ITEMS.find((i) => i.sku === selectedMessage.skuData.sku)
      if (match) {
        setSelectedSku(match.sku)
        setSelectedAisle(match.aisle)
      }
    }
  }, [selectedMessage])

  // Current active item: the agent's live numbers for the selected SKU (never another SKU's data)
  const catalogItem = WAREHOUSE_ITEMS.find((i) => i.sku === selectedSku)
  const live = liveItem && liveItem.sku === selectedSku ? {
    sku: liveItem.sku,
    name: liveItem.name,
    category: liveItem.category,
    location: liveItem.location,
    ...(liveItem.aisle != null && { aisle: liveItem.aisle }),
    ...(liveItem.shelf && { shelf: liveItem.shelf }),
    ...(liveItem.tier && { tier: liveItem.tier }),
    ...(liveItem.bay && { bay: liveItem.bay }),
    quantity: liveItem.quantity_on_hand,
    available: liveItem.available_quantity,
    reserved: liveItem.reserved_quantity,
    safety_stock: liveItem.safety_stock,
    reorder_point: liveItem.reorder_point,
    reorder_qty: liveItem.reorder_quantity,
    unit: liveItem.unit,
    status: liveItem.status,
    ...(liveItem.occupancy_pct != null && { occupancy_pct: liveItem.occupancy_pct }),
    ...(liveItem.weight_kg != null && { weight_kg: liveItem.weight_kg }),
    ...(liveItem.temperature && { temperature: liveItem.temperature }),
  } : null
  const activeItem = live
    ? { ...(catalogItem || { zone: liveItem.category || '—', cycle_count: '—', rack_color: '#94a3b8',
                             occupancy_pct: null, temperature: '—', weight_kg: '—' }), ...live }
    : (catalogItem || WAREHOUSE_ITEMS[0])

  const handleSelectAisle = (aisleNum) => {
    setSelectedAisle(aisleNum)
    const itemInAisle = WAREHOUSE_ITEMS.find((i) => i.aisle === aisleNum)
    if (itemInAisle) {
      setSelectedSku(itemInAisle.sku)
    }
  }

  const handleSelectSku = (skuCode) => {
    setSelectedSku(skuCode)
    const match = WAREHOUSE_ITEMS.find((i) => i.sku === skuCode)
    if (match) setSelectedAisle(match.aisle)
  }

  const triggerActionFeedback = (text) => {
    setActionNotice(text)
    setTimeout(() => setActionNotice(''), 3000)
  }

  const handleTestDocumentParse = () => {
    // Deterministic simulation matching backend document_parser.py
    const isApex = docInputText.toLowerCase().includes('apex')
    const sku = docInputText.includes('SKU-4521') ? 'SKU-4521' : (docInputText.includes('SKU-7788') ? 'SKU-7788' : 'SKU-1088')
    const qty = docInputText.match(/\b(\d{2,4})\s*(?:units|rolls|printers|scanners)?\b/)?.[1] || 150
    setParsedDocState({
      document_type: 'supplier_email',
      supplier_name: isApex ? 'Apex Automotive Supplies' : 'Zebra Technologies Direct',
      extracted_sku: sku,
      extracted_quantity: parseInt(qty),
      extracted_delivery_date: '2026-10-15',
      po_reference: 'PO-99214',
      confidence: 0.98,
      draft_order: {
        draft_id: 'RST-88914',
        status: 'DRAFT_PENDING_APPROVAL',
        supplier_name: isApex ? 'Apex Automotive Supplies' : 'Zebra Technologies Direct',
        sku,
        quantity: parseInt(qty),
        promised_delivery_date: '2026-10-15'
      },
      raw_summary: `Parsed Supplier Email from Apex. Extracted SKU ${sku} (${qty} units), arriving 2026-10-15. Restock order RST-88914 drafted.`
    })
    triggerActionFeedback('Document parsed & Purchase Order draft created!')
  }

  const handleTestEquipmentAnalysis = () => {
    const isForklift = equipmentInput.toLowerCase().includes('forklift')
    setHealthAnalysisState({
      equipment_id: isForklift ? 'Forklift 3' : 'Conveyor A-02',
      equipment_type: isForklift ? 'Forklift' : 'Conveyor',
      reported_symptom: equipmentInput,
      detected_failure_mode: isForklift ? 'Mast Bearing / Pinion Gear Degradation' : 'Drive Belt Tension Loss / Pulley Glaze',
      breakdown_risk: 'HIGH',
      recurrence_count: 3,
      action_required: 'Immediate lubrication & bearing tolerance inspection. Do not lift loads > 1.5t.',
      scheduled_maintenance_window: 'Within 12 Hours'
    })
    triggerActionFeedback('Informal maintenance complaint analyzed!')
  }

  return (
    <div className="warehouse-visualizer-container">
      {/* Top Header & Live Metrics Banner (Inspired by user's design reference) */}
      <div className="wh-top-kpi-banner">
        <div className="wh-header-meta">
          <div className="wh-facility-pill">
            <Warehouse size={14} className="text-amber" />
            <span>Facility Alpha — Main Distribution</span>
          </div>
          <span className="wh-facility-id">ID: WH-412589015</span>
        </div>

        <div className="wh-stats-triad">
          <div className="wh-stat-chip">
            <div className="stat-chip-top">
              <span className="stat-num text-emerald">3</span>
              <span className="status-dot green" />
            </div>
            <span className="stat-desc">AGV Robots Online</span>
          </div>
          <div className="wh-stat-chip">
            <div className="stat-chip-top">
              <span className="stat-num text-blue">30</span>
              <span className="status-dot blue" />
            </div>
            <span className="stat-desc">Floor Associates</span>
          </div>
          <div className="wh-stat-chip">
            <div className="stat-chip-top">
              <span className="stat-num text-amber">345</span>
              <span className="status-dot amber" />
            </div>
            <span className="stat-desc">Hourly Throughput</span>
          </div>
        </div>
      </div>

      {/* Sub-Navigation for Member 1 Capabilities */}
      <div className="wh-subnav-strip">
        <button
          className={`wh-subnav-btn ${subTab === 'map' ? 'active' : ''}`}
          onClick={() => setSubTab('map')}
        >
          <Warehouse size={13} />
          <span>Floor & Bay Map</span>
        </button>
        <button
          className={`wh-subnav-btn ${subTab === 'doc_parser' ? 'active' : ''}`}
          onClick={() => setSubTab('doc_parser')}
        >
          <FileText size={13} />
          <span>Doc Parser</span>
        </button>
        <button
          className={`wh-subnav-btn ${subTab === 'predictor' ? 'active' : ''}`}
          onClick={() => setSubTab('predictor')}
        >
          <TrendingDown size={13} />
          <span>Depletion</span>
        </button>
        <button
          className={`wh-subnav-btn ${subTab === 'anomalies' ? 'active' : ''}`}
          onClick={() => setSubTab('anomalies')}
        >
          <ShieldAlert size={13} />
          <span>Shrinkage</span>
        </button>
        <button
          className={`wh-subnav-btn ${subTab === 'transfers' ? 'active' : ''}`}
          onClick={() => setSubTab('transfers')}
        >
          <ArrowRightLeft size={13} />
          <span>Transfers</span>
        </button>
        <button
          className={`wh-subnav-btn ${subTab === 'equipment' ? 'active' : ''}`}
          onClick={() => setSubTab('equipment')}
        >
          <Wrench size={13} />
          <span>Equipment</span>
        </button>
      </div>

      {actionNotice && (
        <div className="wh-toast-notice">
          <CheckCircle2 size={13} className="text-emerald" />
          <span>{actionNotice}</span>
        </div>
      )}

      {/* SUB-VIEW 1: INTERACTIVE FLOOR & BAY MAP */}
      {subTab === 'map' && (
        <div className="wh-tab-content map-view">
          {/* Search & Quick Selector */}
          <div className="wh-search-bar-row">
            <div className="wh-search-input-wrap">
              <Search size={13} className="search-icon" />
              <input
                type="text"
                placeholder="Search SKU or item (e.g. SKU-4521, scanner, battery)..."
                value={searchFilter}
                onChange={(e) => setSearchFilter(e.target.value)}
                className="wh-sku-search-input"
              />
            </div>
          </div>

          {/* Quick SKU Chips */}
          <div className="wh-sku-chips-row">
            {WAREHOUSE_ITEMS.filter(
              (item) =>
                !searchFilter ||
                item.sku.toLowerCase().includes(searchFilter.toLowerCase()) ||
                item.name.toLowerCase().includes(searchFilter.toLowerCase())
            ).map((item) => (
              <button
                key={item.sku}
                onClick={() => handleSelectSku(item.sku)}
                className={`wh-sku-chip ${selectedSku === item.sku ? 'active' : ''}`}
              >
                <span className="chip-sku">{item.sku}</span>
                <span className="chip-name">{item.name.split(' ')[0]}</span>
                <span className={`chip-badge ${item.status.toLowerCase()}`}>
                  {item.quantity}
                </span>
              </button>
            ))}
          </div>

          {/* High-Bay Isometric Storage Rack Floor Matrix */}
          <div className="wh-isometric-floor-card">
            <div className="floor-card-top">
              <div className="floor-heading">
                <span className="floor-title">Warehouse Floor Alpha — High-Bay Storage Racks</span>
                <span className="floor-sub">14 Aisles • 4 Vertical Tiers • Click an aisle to inspect</span>
              </div>
              <div className="zone-legend">
                <span className="legend-dot a" title="Zone A: Consumables" />
                <span className="legend-dot b" title="Zone B: Electronics" />
                <span className="legend-dot c" title="Zone C: Bulk" />
                <span className="legend-dot d" title="Zone D: Hazmat" />
              </div>
            </div>

            {/* Racks Visual Grid */}
            <div className="interactive-racks-grid">
              {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14].map((aisle) => {
                const isSelectedAisle = selectedAisle === aisle
                const hasActiveItem = activeItem.aisle === aisle
                const itemInAisle = WAREHOUSE_ITEMS.find((i) => i.aisle === aisle)

                return (
                  <div
                    key={aisle}
                    onClick={() => handleSelectAisle(aisle)}
                    className={`interactive-aisle-col ${isSelectedAisle ? 'selected-aisle' : ''} ${hasActiveItem ? 'active-target-aisle' : ''}`}
                    title={`Aisle ${aisle}${itemInAisle ? `: ${itemInAisle.name} (${itemInAisle.sku})` : ''}`}
                  >
                    <span className="aisle-tag">A{aisle < 10 ? `0${aisle}` : aisle}</span>

                    {/* Tier D: High-Bay Top Tier */}
                    <div className="rack-tier tier-d" />

                    {/* Tier C: Mid-High Tier */}
                    <div
                      className={`rack-tier tier-c ${hasActiveItem && activeItem.tier === 'C' ? 'target-glow-pin' : ''}`}
                    >
                      {hasActiveItem && activeItem.tier === 'C' && (
                        <div className="wh-pin-beacon" />
                      )}
                    </div>

                    {/* Tier B: Mid-Low Tier */}
                    <div
                      className={`rack-tier tier-b ${hasActiveItem && activeItem.tier === 'B' ? 'target-glow-pin' : ''}`}
                    >
                      {hasActiveItem && activeItem.tier === 'B' && (
                        <div className="wh-pin-beacon" />
                      )}
                    </div>

                    {/* Tier A: Ground Floor Tier */}
                    <div
                      className={`rack-tier tier-a ${hasActiveItem && activeItem.tier === 'A' ? 'target-glow-pin' : ''}`}
                    >
                      {hasActiveItem && activeItem.tier === 'A' && (
                        <div className="wh-pin-beacon" />
                      )}
                    </div>
                  </div>
                )
              })}
            </div>

            {/* AGV Fleet Transit Runway */}
            <div className="agv-transit-lane">
              <div className="lane-header">
                <span className="lane-label">AGV Transit Runway 03 (Automated Guided Vehicles)</span>
                <span className="lane-speed">1.2 m/s Autonomous Flow</span>
              </div>
              <div className="agv-units-row">
                <div className="agv-unit-chip active">
                  <span className="agv-icon">🤖</span>
                  <div className="agv-info">
                    <strong>AGV-01 (Haulix)</strong>
                    <span>En route Aisle 01 • Battery 72%</span>
                  </div>
                  <span className="agv-badge green">ACTIVE</span>
                </div>
                <div className="agv-unit-chip transit">
                  <span className="agv-icon">🤖</span>
                  <div className="agv-info">
                    <strong>AGV-04 (Haulix)</strong>
                    <span>Pick Aisle 12 • Battery 34%</span>
                  </div>
                  <span className="agv-badge blue">TRANSIT</span>
                </div>
                <div className="agv-unit-chip warning">
                  <span className="agv-icon">⚠️</span>
                  <div className="agv-info">
                    <strong>AGV-08 (Haulix)</strong>
                    <span>Runway 03 • Battery 19%</span>
                  </div>
                  <span className="agv-badge amber">SERVICE</span>
                </div>
              </div>
            </div>
          </div>

          {/* Detailed High-Bay Selected Item Inspector */}
          <div className="wh-bay-detail-inspector">
            <div className="inspector-header">
              <div className="inspector-title-group">
                <div
                  className="rack-color-indicator"
                  style={{ background: activeItem.rack_color }}
                />
                <div>
                  <h4>{activeItem.name}</h4>
                  <span className="inspector-sku-code">
                    {activeItem.sku} • {activeItem.category}
                  </span>
                  {!live && (
                    <span className="inspector-sample-note" title="Ask the inventory agent about this SKU for live stock">
                      Sample figures — ask the agent for live stock
                    </span>
                  )}
                </div>
              </div>
              <span className={`status-pill ${activeItem.status.toLowerCase()}`}>
                {activeItem.status.replace('_', ' ')}
              </span>
            </div>

            {/* Coordinates Grid */}
            <div className="inspector-coords-strip">
              <div className="coord-box">
                <span className="coord-lbl">AISLE</span>
                <span className="coord-val">Aisle {activeItem.aisle}</span>
              </div>
              <div className="coord-box">
                <span className="coord-lbl">SHELF / TIER</span>
                <span className="coord-val">Tier {activeItem.tier} ({activeItem.shelf})</span>
              </div>
              <div className="coord-box">
                <span className="coord-lbl">BAY LOCATOR</span>
                <span className="coord-val text-amber">{activeItem.bay}</span>
              </div>
              <div className="coord-box">
                <span className="coord-lbl">ZONE</span>
                <span className="coord-val">{activeItem.zone.split(' - ')[0]}</span>
              </div>
            </div>

            {/* Inventory Metrics */}
            <div className="inspector-quantities-row">
              <div className="qty-tile">
                <span className="qty-lbl">PHYSICAL ON-HAND</span>
                <span className="qty-num">{activeItem.quantity} {activeItem.unit}</span>
              </div>
              <div className="qty-tile">
                <span className="qty-lbl">AVAILABLE TO PICK</span>
                <span className="qty-num text-emerald">{activeItem.available} {activeItem.unit}</span>
              </div>
              <div className="qty-tile">
                <span className="qty-lbl">RESERVED ORDERS</span>
                <span className="qty-num text-blue">{activeItem.reserved} {activeItem.unit}</span>
              </div>
              <div className="qty-tile">
                <span className="qty-lbl">REORDER THRESHOLD</span>
                <span className="qty-num text-amber">{activeItem.reorder_point} {activeItem.unit}</span>
              </div>
            </div>

            {/* Volumetric Occupancy Progress Gauge */}
            <div className="occupancy-gauge-card">
              <div className="gauge-header">
                <span className="gauge-lbl">Bay Volumetric Fill Rate</span>
                <span className="gauge-val font-mono">{activeItem.occupancy_pct ?? '—'}% Occupied</span>
              </div>
              <div className="gauge-track">
                <div
                  className="gauge-fill"
                  style={{
                    width: `${activeItem.occupancy_pct}%`,
                    background: activeItem.occupancy_pct > 80 ? '#f59e0b' : (activeItem.occupancy_pct < 20 ? '#ef4444' : '#10b981')
                  }}
                />
              </div>
            </div>

            {/* Environmental & Cycle Count Metadata */}
            <div className="env-meta-grid">
              <div className="env-cell">
                <Thermometer size={13} className="text-amber" />
                <span>{activeItem.temperature}</span>
              </div>
              <div className="env-cell">
                <Weight size={13} className="text-blue" />
                <span>{activeItem.weight_kg} kg / unit</span>
              </div>
              <div className="env-cell">
                <Clock size={13} className="text-emerald" />
                <span>Cycle: {activeItem.cycle_count}</span>
              </div>
            </div>

            {/* Quick Interactive Actions */}
            <div className="inspector-actions-row">
              <button
                onClick={() => {
                  setSubTab('predictor')
                  triggerActionFeedback(`Loading depletion velocity for ${activeItem.sku}`)
                }}
                className="btn-wh-action"
              >
                <TrendingDown size={12} />
                <span>Depletion Forecast</span>
              </button>
              <button
                onClick={() => {
                  setSubTab('transfers')
                  triggerActionFeedback(`Scanning sibling warehouses for ${activeItem.sku}`)
                }}
                className="btn-wh-action"
              >
                <ArrowRightLeft size={12} />
                <span>Check Sibling Stock</span>
              </button>
              <button
                onClick={() => triggerActionFeedback(`Cycle count task scheduled for ${activeItem.location}`)}
                className="btn-wh-action primary"
              >
                <CheckCircle2 size={12} />
                <span>Audit Bay Now</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* SUB-VIEW 2: SUPPLIER DOCUMENT PARSER (NER) */}
      {subTab === 'doc_parser' && (
        <div className="wh-tab-content doc-parser-view">
          <div className="feature-intro-card">
            <div className="intro-title">
              <FileText size={16} className="text-amber" />
              <strong>Document Parser & Supplier NER (Member 1)</strong>
            </div>
            <p>
              Extracts SKU, quantity, and delivery date from unstructured supplier emails or PDF text,
              then automatically drafts restock requests to eliminate manual data entry.
            </p>
          </div>

          <div className="doc-tester-card">
            <div className="tester-header">
              <span className="lbl">Paste Unstructured Supplier Email or PDF Text:</span>
              <button
                onClick={() =>
                  setDocInputText(
                    'From: Zebra Technologies Direct <supply@zebra.com>\nSubject: Shipment Confirmation PO-33219\nDelivering 60 thermal label printers (SKU-7788) arriving tomorrow 09:00 AM.'
                  )
                }
                className="btn-mini-sample"
              >
                Load Sample 2
              </button>
            </div>
            <textarea
              className="doc-textarea"
              rows={4}
              value={docInputText}
              onChange={(e) => setDocInputText(e.target.value)}
            />
            <button onClick={handleTestDocumentParse} className="btn-wh-parse">
              <Sparkles size={13} />
              <span>Extract Entities & Draft Restock Order</span>
            </button>
          </div>

          {parsedDocState && (
            <div className="parsed-result-card">
              <div className="result-header">
                <strong>Extracted Entities (NER Engine)</strong>
                <span className="conf-pill">{(parsedDocState.confidence * 100).toFixed(0)}% Confidence</span>
              </div>

              <div className="entity-pills-matrix">
                <div className="ep-chip">
                  <span className="k">Target SKU:</span>
                  <span className="v text-amber">{parsedDocState.extracted_sku}</span>
                </div>
                <div className="ep-chip">
                  <span className="k">Inbound Quantity:</span>
                  <span className="v text-emerald">{parsedDocState.extracted_quantity} units</span>
                </div>
                <div className="ep-chip">
                  <span className="k">Promised Delivery:</span>
                  <span className="v text-blue">{parsedDocState.extracted_delivery_date}</span>
                </div>
                <div className="ep-chip">
                  <span className="k">Supplier Identity:</span>
                  <span className="v">{parsedDocState.supplier_name}</span>
                </div>
                <div className="ep-chip">
                  <span className="k">PO / Manifest Ref:</span>
                  <span className="v font-mono">{parsedDocState.po_reference}</span>
                </div>
              </div>

              {parsedDocState.draft_order && (
                <div className="draft-order-preview">
                  <div className="draft-title">
                    <CheckCircle2 size={14} className="text-emerald" />
                    <strong>Auto-Drafted Purchase Order: {parsedDocState.draft_order.draft_id}</strong>
                  </div>
                  <p>
                    Reorder of <strong>{parsedDocState.draft_order.quantity} units</strong> of{' '}
                    <strong>{parsedDocState.draft_order.sku}</strong> queued for Floor Manager sign-off.
                  </p>
                  <button
                    onClick={() => triggerActionFeedback(`Restock Order ${parsedDocState.draft_order.draft_id} Approved!`)}
                    className="btn-approve-po"
                  >
                    <span>Approve Restock Draft</span>
                    <ChevronRight size={13} />
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* SUB-VIEW 3: REORDER PREDICTOR (DEPLETION VELOCITY) */}
      {subTab === 'predictor' && (
        <div className="wh-tab-content predictor-view">
          <div className="feature-intro-card">
            <div className="intro-title">
              <TrendingDown size={16} className="text-amber" />
              <strong>Reorder Predictor & Stock Depletion Engine</strong>
            </div>
            <p>
              Watches daily stock-depletion trends and consumption velocity to proactively flag
              items about to run out before a physical stockout occurs.
            </p>
          </div>

          <div className="depletion-table-card">
            <table className="wh-table">
              <thead>
                <tr>
                  <th>Item / SKU</th>
                  <th>Current Stock</th>
                  <th>Daily Burn Rate</th>
                  <th>Days Left</th>
                  <th>Lead Time</th>
                  <th>Urgency</th>
                </tr>
              </thead>
              <tbody>
                {WAREHOUSE_ITEMS.map((item) => (
                  <tr key={item.sku} className={item.days_left <= item.lead_time ? 'critical-row' : ''}>
                    <td>
                      <div className="tbl-item-name">{item.name}</div>
                      <div className="tbl-item-sku">{item.sku}</div>
                    </td>
                    <td className="font-mono">{item.quantity} {item.unit}</td>
                    <td className="font-mono">{item.burn_rate} /day</td>
                    <td>
                      <span className={`days-badge ${item.days_left < 3 ? 'critical' : (item.days_left < 7 ? 'warning' : 'ok')}`}>
                        {item.days_left} days
                      </span>
                    </td>
                    <td className="font-mono">{item.lead_time} days</td>
                    <td>
                      <span className={`urgency-pill ${item.days_left <= item.lead_time ? 'critical' : 'normal'}`}>
                        {item.days_left <= item.lead_time ? 'CRITICAL' : 'STABLE'}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* SUB-VIEW 4: ANOMALY WATCHER (SHRINKAGE) */}
      {subTab === 'anomalies' && (
        <div className="wh-tab-content anomalies-view">
          <div className="feature-intro-card">
            <div className="intro-title">
              <ShieldAlert size={16} className="text-coral" />
              <strong>Anomaly Watcher & Loss Prevention (Member 1)</strong>
            </div>
            <p>
              Audits stock-movement patterns inconsistent with normal warehouse operations, detecting
              unexplained shrinkage, off-hours moves, and unauthorized manual inventory deltas.
            </p>
          </div>

          <div className="anomalies-list">
            <div className="anomaly-card high">
              <div className="anom-top">
                <span className="anom-badge high">HIGH SEVERITY</span>
                <span className="anom-id font-mono">ANOM-99218</span>
              </div>
              <h4>Unexplained Shrinkage: Heavy Duty Pallet Wrap (SKU-9012)</h4>
              <div className="anom-variance-grid">
                <div>Expected Count: <strong>25 rolls</strong></div>
                <div>Actual Count: <strong>5 rolls</strong></div>
                <div>Discrepancy: <strong className="text-coral">-20 rolls</strong></div>
                <div>Est. Exposure: <strong>$460.00</strong></div>
              </div>
              <p className="anom-desc">
                Discrepancy detected during morning cycle count. 20 rolls missing from Bay Aisle 3, Shelf C2 with no corresponding order fulfillment records.
              </p>
              <div className="anom-action">
                🛡️ <strong>Directive:</strong> Trigger physical bay audit on Aisle 3 & review CCTV footage between 22:00-05:00.
              </div>
            </div>

            <div className="anomaly-card critical">
              <div className="anom-top">
                <span className="anom-badge critical">CRITICAL SEVERITY</span>
                <span className="anom-id font-mono">ANOM-44102</span>
              </div>
              <h4>Repeated Manual Adjustments: Wireless Barcode Scanner (SKU-4521)</h4>
              <div className="anom-variance-grid">
                <div>Expected Count: <strong>350 units</strong></div>
                <div>Actual Count: <strong>340 units</strong></div>
                <div>Discrepancy: <strong className="text-coral">-10 units</strong></div>
                <div>Est. Exposure: <strong>$2,200.00</strong></div>
              </div>
              <p className="anom-desc">
                Multiple negative manual adjustments recorded by Shift 2 operator within 48 hours without supervisory sign-off.
              </p>
              <div className="anom-action">
                🛡️ <strong>Suggested next step:</strong> Supervisor to review the unapproved adjustments with Loss Prevention before any action — a signal to investigate, not a finding against a person.
              </div>
            </div>
          </div>
        </div>
      )}

      {/* SUB-VIEW 5: TRANSFER ADVISOR */}
      {subTab === 'transfers' && (
        <div className="wh-tab-content transfers-view">
          <div className="feature-intro-card">
            <div className="intro-title">
              <ArrowRightLeft size={16} className="text-amber" />
              <strong>Transfer Advisor (Sibling Warehouse Network)</strong>
            </div>
            <p>
              Checks sibling distribution centers for surplus stock before authorizing expensive
              external supplier purchase orders, optimizing multi-hub inventory allocation.
            </p>
          </div>

          <div className="sibling-network-grid">
            <div className="sibling-card recommended">
              <div className="sibling-badge">RECOMMENDED SOURCE</div>
              <h4>IntelliWMS East DC (WH-BETA-EAST)</h4>
              <span className="sibling-loc">Newark, NJ • 1 Day Transit</span>
              <div className="sibling-stat-row">
                <div>Surplus Available: <strong className="text-emerald">120 units</strong></div>
                <div>Transfer Freight: <strong>$2.50 / unit</strong></div>
              </div>
              <div className="savings-highlight">
                💰 Net Savings vs External PO: <strong>$10,875.00</strong>
              </div>
              <button
                onClick={() => triggerActionFeedback('Inter-facility Transfer Order Authorized for WH-BETA-EAST!')}
                className="btn-auth-transfer"
              >
                <span>Authorize Transfer of 50 Units</span>
                <ChevronRight size={13} />
              </button>
            </div>

            <div className="sibling-card">
              <h4>IntelliWMS Central Terminal (WH-DELTA-CENTRAL)</h4>
              <span className="sibling-loc">Chicago, IL • 1 Day Transit</span>
              <div className="sibling-stat-row">
                <div>Surplus Available: <strong>150 units</strong></div>
                <div>Transfer Freight: <strong>$2.20 / unit</strong></div>
              </div>
            </div>

            <div className="sibling-card">
              <h4>IntelliWMS South Hub (WH-GAMMA-SOUTH)</h4>
              <span className="sibling-loc">Atlanta, GA • 2 Days Transit</span>
              <div className="sibling-stat-row">
                <div>Surplus Available: <strong>10 units</strong></div>
                <div>Transfer Freight: <strong>$3.75 / unit</strong></div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* SUB-VIEW 6: EQUIPMENT HEALTH (STARRED DIFFERENTIATOR) */}
      {subTab === 'equipment' && (
        <div className="wh-tab-content equipment-view">
          <div className="feature-intro-card starred">
            <div className="intro-title">
              <Wrench size={16} className="text-amber" />
              <strong>★ Equipment Health (Member 1 Differentiator)</strong>
            </div>
            <p>
              Reads informal maintenance complaint logs (<em>"forklift 3 grinding"</em>, <em>"conveyor squealing"</em>)
              to spot recurring mechanical issues before a breakdown occurs — <strong>no sensors needed</strong>.
            </p>
          </div>

          <div className="equipment-input-card">
            <span className="lbl">Analyze Informal Operator Shift Complaint Log:</span>
            <div className="eq-input-row">
              <input
                type="text"
                value={equipmentInput}
                onChange={(e) => setEquipmentInput(e.target.value)}
                className="eq-input-field"
                placeholder="e.g. Forklift 3 mast grinding noise when lifting..."
              />
              <button onClick={handleTestEquipmentAnalysis} className="btn-wh-parse">
                <Wrench size={13} />
                <span>Analyze Symptom</span>
              </button>
            </div>
          </div>

          {healthAnalysisState && (
            <div className="equipment-health-report-card">
              <div className="report-header">
                <div>
                  <h4>{healthAnalysisState.equipment_id} ({healthAnalysisState.equipment_type})</h4>
                  <span className="symptom-text">"{healthAnalysisState.reported_symptom}"</span>
                </div>
                <span className={`risk-tag ${healthAnalysisState.breakdown_risk.toLowerCase()}`}>
                  {healthAnalysisState.breakdown_risk} BREAKDOWN RISK
                </span>
              </div>

              <div className="diagnosis-grid">
                <div className="diag-tile">
                  <span className="diag-k">Detected Failure Mode:</span>
                  <span className="diag-v text-amber">{healthAnalysisState.detected_failure_mode}</span>
                </div>
                <div className="diag-tile">
                  <span className="diag-k">Complaint Recurrence:</span>
                  <span className="diag-v">{healthAnalysisState.recurrence_count}x in past shift handoffs</span>
                </div>
                <div className="diag-tile">
                  <span className="diag-k">Preventative Window:</span>
                  <span className="diag-v text-emerald">{healthAnalysisState.scheduled_maintenance_window}</span>
                </div>
              </div>

              <div className="work-order-directive">
                <Wrench size={14} className="text-amber" />
                <div>
                  <strong>Prescribed Maintenance Work Order:</strong>
                  <p>{healthAnalysisState.action_required}</p>
                </div>
              </div>

              <button
                onClick={() => triggerActionFeedback(`Maintenance Work Order Dispatched for ${healthAnalysisState.equipment_id}`)}
                className="btn-dispatch-maintenance"
              >
                <span>Dispatch Preventative Maintenance</span>
                <ChevronRight size={13} />
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
