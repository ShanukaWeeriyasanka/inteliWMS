import React, { useState } from 'react'
import {
  Boxes,
  Package,
  Truck,
  Building2,
  CheckCircle2,
  AlertTriangle,
  Clock,
  Info,
  Layers,
  Sparkles,
  Search
} from 'lucide-react'
import './WarehouseScene.css'

/**
 * High-definition Isometric 3D Warehouse Scene with interactive hotspot overlays.
 * Features Storage Racks, Conveyor Line, Packing Workstations, Loading Docks & Fleet, and Control Office.
 */
export default function WarehouseScene({
  selectedZone = 'storage_racks',
  onSelectZone,
  parsed = {},
  orderStatus
}) {
  const [hoveredZone, setHoveredZone] = useState(null)

  const isDelayed = parsed.status === 'DELAYED' || parsed.intent === 'ORDER_DELAY'
  const isShipped = parsed.status === 'SHIPPED'
  const hasInventoryCheck = !!parsed.crossAgent?.involved

  return (
    <div className="fc-scene-card">
      {/* Scene Header & Zone Selection Toolbar */}
      <div className="fc-scene-toolbar">
        <div className="fc-scene-toolbar-left">
          <div className="fc-live-pulse-dot" />
          <span className="fc-scene-title">Isometric Warehouse Operations Center</span>
          <span className="fc-scene-model-pill" title="Illustrative 3D operational visualizer">
            <Info size={12} />
            <span>Operational Model</span>
          </span>
        </div>

        {/* Quick Zone Selector Buttons */}
        <div className="fc-scene-zone-pills">
          <button
            type="button"
            className={`fc-zone-tab-btn ${selectedZone === 'storage_racks' ? 'active' : ''}`}
            onClick={() => onSelectZone('storage_racks')}
            title="Inspect Storage Racks & Inventory Stock"
          >
            <Boxes size={13} />
            <span>1. Storage Racks</span>
            {hasInventoryCheck && (
              <span className={`fc-tag-mini ${parsed.crossAgent?.stockStatus === 'OUT_OF_STOCK' ? 'tag-coral' : 'tag-emerald'}`}>
                {parsed.crossAgent?.stockStatus === 'OUT_OF_STOCK' ? 'STOCK: 0' : 'IN STOCK'}
              </span>
            )}
          </button>

          <button
            type="button"
            className={`fc-zone-tab-btn ${selectedZone === 'packing_area' ? 'active' : ''}`}
            onClick={() => onSelectZone('packing_area')}
            title="Inspect Packing Stations & Manifest Staging"
          >
            <Package size={13} />
            <span>2. Packing Area</span>
          </button>

          <button
            type="button"
            className={`fc-zone-tab-btn ${selectedZone === 'loading_docks' ? 'active' : ''}`}
            onClick={() => onSelectZone('loading_docks')}
            title="Inspect Loading Docks & Logistics Carrier Fleet"
          >
            <Truck size={13} />
            <span>3. Loading Docks</span>
            {isDelayed && <span className="fc-tag-mini tag-coral">DELAY</span>}
            {isShipped && <span className="fc-tag-mini tag-emerald">SHIPPED</span>}
          </button>

          <button
            type="button"
            className={`fc-zone-tab-btn ${selectedZone === 'control_office' ? 'active' : ''}`}
            onClick={() => onSelectZone('control_office')}
            title="Inspect Operations Control Office & Routing Telemetry"
          >
            <Building2 size={13} />
            <span>4. Control Office</span>
          </button>
        </div>
      </div>

      {/* 3D Warehouse Canvas with Hotspot Overlays */}
      <div className="fc-scene-canvas-wrapper">
        <div className="fc-canvas-inner">
          <img
            src="/isometric_warehouse_operations.jpg"
            alt="IntelliWMS Isometric 3D Warehouse Operations"
            className="fc-warehouse-img"
          />

          {/* ── HOTSPOT 1: HIGH-BAY STORAGE RACKS (TOP LEFT: 20% left, 35% top) ── */}
          <div
            className={`fc-hotspot-pin hotspot-racks ${selectedZone === 'storage_racks' ? 'active-pin' : ''}`}
            style={{ left: '22%', top: '30%' }}
            onClick={() => onSelectZone('storage_racks')}
            onMouseEnter={() => setHoveredZone('storage_racks')}
            onMouseLeave={() => setHoveredZone(null)}
            role="button"
            tabIndex={0}
            title="Click to inspect High-Bay Storage Racks"
          >
            <div className="fc-pin-beacon" />
            <div className="fc-pin-pill">
              <Boxes size={13} className="fc-pin-icon" />
              <span className="fc-pin-text">1. High-Bay Storage Racks</span>
              {hasInventoryCheck && (
                <span className={`fc-pin-badge ${parsed.crossAgent?.stockStatus === 'OUT_OF_STOCK' ? 'badge-coral' : 'badge-emerald'}`}>
                  {parsed.crossAgent?.stockStatus === 'OUT_OF_STOCK' ? 'DEPLETED' : 'VERIFIED'}
                </span>
              )}
            </div>
          </div>

          {/* ── HOTSPOT 2: PACKING & SORTING WORKSTATIONS (BOTTOM-CENTER: 35% left, 72% top) ── */}
          <div
            className={`fc-hotspot-pin hotspot-packing ${selectedZone === 'packing_area' ? 'active-pin' : ''}`}
            style={{ left: '36%', top: '74%' }}
            onClick={() => onSelectZone('packing_area')}
            onMouseEnter={() => setHoveredZone('packing_area')}
            onMouseLeave={() => setHoveredZone(null)}
            role="button"
            tabIndex={0}
            title="Click to inspect Packing & Sorting Area"
          >
            <div className="fc-pin-beacon" />
            <div className="fc-pin-pill">
              <Package size={13} className="fc-pin-icon" />
              <span className="fc-pin-text">2. Packing & Staging Area</span>
            </div>
          </div>

          {/* ── HOTSPOT 3: LOADING DOCKS & DELIVERY FLEET (RIGHT DOCKS: 80% left, 62% top) ── */}
          <div
            className={`fc-hotspot-pin hotspot-docks ${selectedZone === 'loading_docks' ? 'active-pin' : ''}`}
            style={{ left: '80%', top: '64%' }}
            onClick={() => onSelectZone('loading_docks')}
            onMouseEnter={() => setHoveredZone('loading_docks')}
            onMouseLeave={() => setHoveredZone(null)}
            role="button"
            tabIndex={0}
            title="Click to inspect Loading Docks & Logistics Carrier Fleet"
          >
            <div className={`fc-pin-beacon ${isDelayed ? 'beacon-coral' : isShipped ? 'beacon-emerald' : ''}`} />
            <div className="fc-pin-pill">
              <Truck size={13} className="fc-pin-icon" />
              <span className="fc-pin-text">3. Loading Docks & Fleet</span>
              {isDelayed && <span className="fc-pin-badge badge-coral">DELAY</span>}
              {isShipped && <span className="fc-pin-badge badge-emerald">DISPATCH</span>}
            </div>
          </div>

          {/* ── HOTSPOT 4: OPERATIONS CONTROL ROOM (TOP RIGHT MEZZANINE: 72% left, 28% top) ── */}
          <div
            className={`fc-hotspot-pin hotspot-office ${selectedZone === 'control_office' ? 'active-pin' : ''}`}
            style={{ left: '72%', top: '28%' }}
            onClick={() => onSelectZone('control_office')}
            onMouseEnter={() => setHoveredZone('control_office')}
            onMouseLeave={() => setHoveredZone(null)}
            role="button"
            tabIndex={0}
            title="Click to inspect Operations Control Office"
          >
            <div className="fc-pin-beacon" />
            <div className="fc-pin-pill">
              <Building2 size={13} className="fc-pin-icon" />
              <span className="fc-pin-text">4. Operations Control Office</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
