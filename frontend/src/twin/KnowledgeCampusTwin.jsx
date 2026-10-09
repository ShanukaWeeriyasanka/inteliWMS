// =========================================================================
// Knowledge Agent — Multi-Building Campus Spatial Digital Twin
// Clean, Fast, User-Friendly Map: Bold visual buildings, instant locating,
// zero label clutter (no "pallets", "3.2°C", etc. labels on the map).
// Scoped pure CSS (twin.css).
// =========================================================================
import React, { useState, useRef } from 'react'
import {
  Building2,
  ArrowLeft,
  Plus,
  Minus,
  Maximize2,
  X,
  ExternalLink,
  Compass
} from 'lucide-react'
import './twin.css'

// ── Campus Master Plan Dataset ───────────────────────────────────────────────
export const CAMPUS_DATA = {
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
    { id: 'FL-01', name: 'Forklift 1', coords: { x: 70, y: 96 }, color: '#22C55E' },
    { id: 'RT-01', name: 'Reach 1', coords: { x: 140, y: 96 }, color: '#22C55E' },
    { id: 'PJ-01', name: 'Pallet Jack', coords: { x: 215, y: 96 }, color: '#22C55E' },
    { id: 'AGV-01', name: 'Tugger AGV', coords: { x: 325, y: 120 }, color: '#22C55E' },
    { id: 'RT-02', name: 'Charger Bay 2', coords: { x: 370, y: 65 }, color: '#F59E0B' }
  ]
}

export default function KnowledgeCampusTwin({
  visible = true,
  onClose,
  onSwitchToInventoryTwin
}) {
  const [selectedBuilding, setSelectedBuilding] = useState(null)
  const [hoveredBuilding, setHoveredBuilding] = useState(null)
  const [routeLine, setRouteLine] = useState(null)

  // Full panoramic site bounds framing all 7 facilities perfectly
  const DEFAULT_VB = { x: 26, y: 12, w: 424, h: 200 }
  const [vb, setVb] = useState(DEFAULT_VB)
  const isDraggingRef = useRef(false)
  const lastMouseRef = useRef({ x: 0, y: 0 })
  const svgRef = useRef(null)

  // Fast, smooth locate handler: highlights building and traces route without extreme cutoffs
  const handleSelectBuilding = (bld) => {
    setSelectedBuilding(bld)
    const cx = bld.rect.x + bld.rect.w / 2
    const cy = bld.rect.y + bld.rect.h / 2
    traceRouteTo(cx, bld.dockY || cy)
  }

  // Smooth orthogonal route from Gate 1 to building loading dock
  const traceRouteTo = (destX, destY) => {
    const origin = CAMPUS_DATA.complex.gateOrigin
    const corridorY = 120 // Central transit avenue
    const path = [
      [origin.x, origin.y],
      [origin.x, corridorY],
      [destX, corridorY],
      [destX, destY]
    ]
    setRouteLine(path)
  }

  // Zoom / Pan handlers
  const handleZoom = (factor) => {
    setVb((prev) => {
      const nw = prev.w * factor
      const nh = prev.h * factor
      const dx = (nw - prev.w) / 2
      const dy = (nh - prev.h) / 2
      return { x: prev.x - dx, y: prev.y - dy, w: nw, h: nh }
    })
  }

  const handleResetFit = () => {
    setVb(DEFAULT_VB)
    setSelectedBuilding(null)
    setRouteLine(null)
  }

  const onMouseDown = (e) => {
    if (e.button !== 0) return
    isDraggingRef.current = true
    lastMouseRef.current = { x: e.clientX, y: e.clientY }
  }

  const onMouseMove = (e) => {
    if (!isDraggingRef.current) return
    const dx = e.clientX - lastMouseRef.current.x
    const dy = e.clientY - lastMouseRef.current.y
    lastMouseRef.current = { x: e.clientX, y: e.clientY }

    const scale = vb.w / (svgRef.current?.clientWidth || 900)
    setVb((prev) => ({
      ...prev,
      x: prev.x - dx * scale,
      y: prev.y - dy * scale
    }))
  }

  const onMouseUp = () => {
    isDraggingRef.current = false
  }

  const onWheel = (e) => {
    e.preventDefault()
    const factor = e.deltaY < 0 ? 0.9 : 1.12
    handleZoom(factor)
  }

  if (!visible) return null

  return (
    <div className="twin-root is-workspace">
      
      {/* ── Main Hero Logistics Campus Site Map ───────────────────────────── */}
      <section className="twin-map-card">
        
        {/* Clean, Streamlined Header (Zero Button Overload) */}
        <header className="twin-map-head">
          <div className="twin-map-head-left">
            <Compass size={18} style={{ color: '#3B7BF6' }} />
            <h1 className="twin-map-title">Colombo Logistics Complex · Campus Site Plan</h1>
            <span className="twin-tag">7 Facilities · Live Fleet</span>
          </div>

          <div className="twin-map-head-right">
            {/* Quick Switch to Warehouse 1 Floor Map */}
            <button
              className="twin-floor-btn"
              onClick={onSwitchToInventoryTwin}
              title="Open Warehouse 1 Floor Map"
              style={{ fontWeight: 600, color: '#0F172A' }}
            >
              <Building2 size={14} style={{ color: '#3B7BF6' }} />
              <span>Warehouse 1 Floor Map ➔</span>
            </button>

            {/* Fit Campus View */}
            <button
              className="twin-floor-btn"
              onClick={handleResetFit}
              title="Fit Entire Campus Map"
            >
              <Maximize2 size={13} />
              <span>Fit Campus</span>
            </button>

            {/* Live Indicator */}
            <span className="twin-live" role="status" title="Live Campus Telemetry">
              <span className="twin-live-dot" />
              <span className="twin-head-text">Live</span>
            </span>

            {/* Back to Chat */}
            <button className="twin-back-btn" onClick={onClose} title="Back to Chat">
              <ArrowLeft size={14} />
              <span className="twin-head-text">Chat</span>
            </button>
          </div>
        </header>

        {/* ── Architectural Vector Site Map Canvas Viewport ────────────────── */}
        <div
          className="twin-map-viewport"
          onMouseDown={onMouseDown}
          onMouseMove={onMouseMove}
          onMouseUp={onMouseUp}
          onWheel={onWheel}
          style={{ cursor: isDraggingRef.current ? 'grabbing' : 'grab' }}
        >
          <svg
            ref={svgRef}
            className="twin-svg"
            viewBox={`${vb.x} ${vb.y} ${vb.w} ${vb.h}`}
            preserveAspectRatio="xMidYMid meet"
          >
            <defs>
              <filter id="cleanShadow" x="-20%" y="-20%" width="140%" height="140%">
                <feDropShadow dx="0" dy="1.4" stdDeviation="1.8" floodColor="#0F172A" floodOpacity="0.08" />
              </filter>
            </defs>

            {/* ── 1. CAMPUS PERIMETER BOUNDARY CONTAINER ────────────────────── */}
            <rect
              className="twin-building"
              x="32"
              y="15"
              width="416"
              height="194"
              rx="14"
              fill="#FFFFFF"
              stroke="#CBD5E1"
              strokeWidth="1.2"
              filter="url(#cleanShadow)"
            />

            {/* Perimeter Notches (Door / Gate entrances) */}
            <rect className="twin-notch is-door" x="30.8" y="146" width="2.6" height="18" rx="0.6" fill="#1E293B" />
            <rect className="twin-notch" x="120" y="14" width="18" height="2" rx="0.5" fill="#CBD5E1" />
            <rect className="twin-notch" x="260" y="14" width="18" height="2" rx="0.5" fill="#CBD5E1" />
            <rect className="twin-notch" x="120" y="207.8" width="18" height="2" rx="0.5" fill="#CBD5E1" />
            <rect className="twin-notch" x="260" y="207.8" width="18" height="2" rx="0.5" fill="#CBD5E1" />

            {/* Gate 1 Entrance Tag */}
            <g transform="translate(34, 155)">
              <rect x="0" y="-6" width="13" height="12" rx="2" fill="#1E293B" />
              <text x="6.5" y="1.2" fontSize="2.8" fontWeight="bold" fill="#FFFFFF" textAnchor="middle">GATE 1</text>
            </g>

            {/* ── 2. LOGISTICS TRANSIT ROADWAYS ─────────────────────────────── */}
            <g className="twin-roadways">
              {/* Central Main Logistics Highway */}
              <rect x="36" y="113" width="404" height="14" rx="2" fill="#F1F5F9" />
              <line x1="38" y1="120" x2="438" y2="120" stroke="#CBD5E1" strokeWidth="0.9" strokeDasharray="4 4" />

              {/* North-South Transit Corridors */}
              <rect x="178" y="22" width="12" height="180" rx="2" fill="#F8FAFC" />
              <line x1="184" y1="24" x2="184" y2="200" stroke="#E2E8F0" strokeWidth="0.7" strokeDasharray="3 3" />

              <rect x="313" y="22" width="12" height="180" rx="2" fill="#F8FAFC" />
              <line x1="319" y1="24" x2="319" y2="200" stroke="#E2E8F0" strokeWidth="0.7" strokeDasharray="3 3" />

              {/* Junction Nodes */}
              <circle cx="184" cy="120" r="2.2" fill="#FFFFFF" stroke="#94A3B8" strokeWidth="0.8" />
              <circle cx="319" cy="120" r="2.2" fill="#FFFFFF" stroke="#94A3B8" strokeWidth="0.8" />
            </g>

            {/* ── 3. PARKED LOGISTICS TRAILERS AT DOCKS ─────────────────────── */}
            <g className="twin-trucks">
              {/* Truck at BLD-01 */}
              <g transform="translate(75, 108)">
                <rect x="-4" y="0" width="8" height="14" rx="1.2" fill="#FFFFFF" stroke="#64748B" strokeWidth="0.5" />
                <rect x="-3.5" y="10.5" width="7" height="3" rx="0.8" fill="#1E293B" />
              </g>

              {/* Truck at BLD-01 Dock 2 */}
              <g transform="translate(130, 108)">
                <rect x="-4" y="0" width="8" height="14" rx="1.2" fill="#FFFFFF" stroke="#3B7BF6" strokeWidth="0.5" />
                <rect x="-3.5" y="10.5" width="7" height="3" rx="0.8" fill="#1E40AF" />
              </g>

              {/* Express Truck at BLD-02 */}
              <g transform="translate(240, 108)">
                <rect x="-4" y="0" width="8" height="14" rx="1.2" fill="#FFFFFF" stroke="#8B5CF6" strokeWidth="0.5" />
                <rect x="-3.5" y="10.5" width="7" height="3" rx="0.8" fill="#6D28D9" />
              </g>
            </g>

            {/* ── 4. WAYFINDING ACTIVE ROUTE ─────────────────────────────────── */}
            {routeLine && routeLine.length > 1 && (
              <g className="twin-route" aria-hidden="true">
                <path
                  d={`M ${routeLine.map((p) => `${p[0]} ${p[1]}`).join(' L ')}`}
                  fill="none"
                  stroke="rgba(70, 168, 94, 0.3)"
                  strokeWidth="4.2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
                <path
                  d={`M ${routeLine.map((p) => `${p[0]} ${p[1]}`).join(' L ')}`}
                  fill="none"
                  stroke="#3E9A57"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
                <circle cx={routeLine[0][0]} cy={routeLine[0][1]} r="2" fill="#3B7BF6" stroke="#FFFFFF" strokeWidth="0.8" />
              </g>
            )}

            {/* ── 5. SEVEN BUILDINGS (CLEAN, BOLD, ZERO LABEL CLUTTER) ───────── */}
            {CAMPUS_DATA.buildings.map((b) => {
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
                  {/* Building Outer Card Shell */}
                  <rect
                    x={b.rect.x}
                    y={b.rect.y}
                    width={b.rect.w}
                    height={b.rect.h}
                    rx="9"
                    fill={isHovered ? '#FAFCFF' : '#FFFFFF'}
                    stroke={isSelected ? b.color : isHovered ? '#94A3B8' : '#CBD5E1'}
                    strokeWidth={isSelected ? '2.8' : isHovered ? '1.5' : '1'}
                    filter="url(#cleanShadow)"
                  />

                  {/* Exterior Loading Dock Bumpers facing Roadway */}
                  {b.dockY === 108 && (
                    <>
                      <rect x={b.rect.x + 18} y={b.rect.y + b.rect.h - 1.5} width="16" height="2.5" rx="0.6" fill="#F59E0B" />
                      <rect x={b.rect.x + b.rect.w - 34} y={b.rect.y + b.rect.h - 1.5} width="16" height="2.5" rx="0.6" fill="#F59E0B" />
                    </>
                  )}

                  {/* Prominent Building Header Title (Clean, Bold, Crisp) */}
                  <g transform={`translate(${b.rect.x + 8}, ${b.rect.y + 7})`}>
                    <circle cx="2.5" cy="4" r="2.5" fill={b.color} />
                    <text x="8" y="7" fontSize="4.6" fontWeight="bold" fill="#0F172A" fontFamily="Inter, sans-serif">
                      {b.title}
                    </text>
                  </g>

                  {/* ── Visual Storage Architecture (Graphic Blocks, Zero Label Clutter) ── */}
                  <g className="twin-interior-graphics">
                    {/* BLD-01: High-Bay Pallet Racks (Blue Storage Blocks) */}
                    {b.id === 'BLD-01' && (
                      <g transform={`translate(${b.rect.x + 8}, ${b.rect.y + 18})`}>
                        {[0, 1, 2, 3].map((col) => (
                          <g key={col} transform={`translate(${col * 27.5}, 0)`}>
                            <rect x="0" y="0" width="24" height="46" rx="2" fill="#F8FAFC" stroke="#CBD5E1" strokeWidth="0.6" />
                            {[0, 1, 2, 3].map((row) => (
                              <React.Fragment key={row}>
                                <rect
                                  x="2"
                                  y={2 + row * 11}
                                  width="9.5"
                                  height="9.5"
                                  rx="1.2"
                                  fill={col === 0 && row < 2 ? '#3B7BF6' : '#DBEAFE'}
                                  stroke="#93C5FD"
                                  strokeWidth="0.4"
                                />
                                <rect
                                  x="12.5"
                                  y={2 + row * 11}
                                  width="9.5"
                                  height="9.5"
                                  rx="1.2"
                                  fill={col === 1 && row === 1 ? '#3B7BF6' : '#DBEAFE'}
                                  stroke="#93C5FD"
                                  strokeWidth="0.4"
                                />
                              </React.Fragment>
                            ))}
                          </g>
                        ))}
                      </g>
                    )}

                    {/* BLD-02: Bulk Distribution (Purple Storage Blocks) */}
                    {b.id === 'BLD-02' && (
                      <g transform={`translate(${b.rect.x + 8}, ${b.rect.y + 18})`}>
                        {[0, 1, 2].map((col) => (
                          <g key={col} transform={`translate(${col * 33.5}, 0)`}>
                            <rect x="0" y="0" width="30" height="46" rx="2" fill="#FAF5FF" stroke="#D8B4FE" strokeWidth="0.6" />
                            {[0, 1, 2].map((row) => (
                              <React.Fragment key={row}>
                                <rect x="2.5" y={2.5 + row * 14} width="12" height="12" rx="1.5" fill={col === 0 && row === 0 ? '#8B5CF6' : '#F3E8FF'} />
                                <rect x="15.5" y={2.5 + row * 14} width="12" height="12" rx="1.5" fill="#F3E8FF" />
                              </React.Fragment>
                            ))}
                          </g>
                        ))}
                      </g>
                    )}

                    {/* BLD-03: Tech Mezzanine (Green Cleanroom Crates) */}
                    {b.id === 'BLD-03' && (
                      <g transform={`translate(${b.rect.x + 8}, ${b.rect.y + 18})`}>
                        <rect x="0" y="0" width="99" height="38" rx="2" fill="#ECFEFF" stroke="#A5F3FC" strokeWidth="0.6" />
                        {[0, 1, 2].map((col) => (
                          <g key={col} transform={`translate(${col * 24 + 4}, 4)`}>
                            <rect x="0" y="0" width="20" height="30" rx="1.5" fill="#FFFFFF" stroke="#86EFAC" strokeWidth="0.5" />
                            {[0, 1, 2].map((r) => (
                              <rect key={r} x="2" y={2 + r * 9} width="16" height="8" rx="1" fill={col === 1 && r === 0 ? '#10B981' : '#DCFCE7'} />
                            ))}
                          </g>
                        ))}
                        {/* Freight Lift Shaft */}
                        <g transform="translate(78, 6)">
                          <rect x="0" y="0" width="16" height="26" rx="2" fill="#0F172A" />
                        </g>
                      </g>
                    )}

                    {/* BLD-04: Cold Vault (Insulated Freezer Chamber) */}
                    {b.id === 'BLD-04' && (
                      <g transform={`translate(${b.rect.x + 7}, ${b.rect.y + 18})`}>
                        <rect x="0" y="0" width="66" height="38" rx="2" fill="#F0F9FF" stroke="#7DD3FC" strokeWidth="0.8" />
                        <rect x="3" y="3" width="28" height="32" rx="1.5" fill="#E0F2FE" stroke="#38BDF8" strokeWidth="0.5" />
                        <rect x="35" y="3" width="28" height="32" rx="1.5" fill="#BAE6FD" stroke="#38BDF8" strokeWidth="0.5" />
                      </g>
                    )}

                    {/* BLD-05: Quarantine Yard (Hazard Red Hatch) */}
                    {b.id === 'BLD-05' && (
                      <g transform={`translate(${b.rect.x + 6}, ${b.rect.y + 18})`}>
                        <rect x="0" y="0" width="43" height="38" rx="2" fill="#FEF2F2" stroke="#EF4444" strokeWidth="1.2" strokeDasharray="3 2" />
                      </g>
                    )}

                    {/* BLD-06: MHE Fleet Fast Charging (Orange Bays) */}
                    {b.id === 'BLD-06' && (
                      <g transform={`translate(${b.rect.x + 7}, ${b.rect.y + 18})`}>
                        {[0, 1, 2, 3].map((bay) => (
                          <g key={bay} transform={`translate(${bay * 22.5}, 0)`}>
                            <rect x="0" y="0" width="20" height="42" rx="2" fill="#FFF7ED" stroke="#FDBA74" strokeWidth="0.6" />
                            <circle cx="10" cy="9" r="3.2" fill="#FFEDD5" stroke="#EA580C" strokeWidth="0.6" />
                            <text x="10" y="11" fontSize="3" fontWeight="bold" fill="#EA580C" textAnchor="middle">⚡</text>
                            <rect x="2.5" y="18" width="15" height="18" rx="1.5" fill="#FED7AA" />
                          </g>
                        ))}
                      </g>
                    )}

                    {/* BLD-07: Gatehouse Weighbridge Scale Platform */}
                    {b.id === 'BLD-07' && (
                      <g transform={`translate(${b.rect.x + 7}, ${b.rect.y + 18})`}>
                        <rect x="0" y="0" width="61" height="38" rx="2" fill="#F8FAFC" stroke="#CBD5E1" strokeWidth="0.8" />
                        <rect x="8" y="9" width="45" height="20" rx="2" fill="#E2E8F0" stroke="#64748B" strokeWidth="0.8" />
                        <line x1="8" y1="19" x2="53" y2="19" stroke="#94A3B8" strokeWidth="0.6" strokeDasharray="2 2" />
                      </g>
                    )}
                  </g>
                </g>
              )
            })}

            {/* ── 6. LIVE VEHICLE FLEET POSITIONS (CLEAN GLOWING DOTS) ──────── */}
            {CAMPUS_DATA.vehicles.map((v) => (
              <g
                key={v.id}
                transform={`translate(${v.coords.x}, ${v.coords.y})`}
                style={{ cursor: 'pointer' }}
              >
                <circle cx="0" cy="0" r="4.2" fill="#22272D" stroke="#FFFFFF" strokeWidth="1" />
                <circle cx="0" cy="0" r="2" fill={v.color} />
              </g>
            ))}

            {/* ── 7. ACTIVE BEACON SPOTLIGHT ─────────────────────────────────── */}
            {selectedBuilding && (
              <g transform={`translate(${selectedBuilding.rect.x + selectedBuilding.rect.w / 2}, ${selectedBuilding.rect.y + selectedBuilding.rect.h / 2})`}>
                <circle cx="0" cy="0" r="16" fill="none" stroke={selectedBuilding.color} strokeWidth="0.9" strokeDasharray="3 2" opacity="0.6">
                  <animate attributeName="r" values="10;20;10" dur="2.4s" repeatCount="indefinite" />
                  <animate attributeName="opacity" values="0.8;0.2;0.8" dur="2.4s" repeatCount="indefinite" />
                </circle>
                <circle cx="0" cy="0" r="7" fill="none" stroke={selectedBuilding.color} strokeWidth="1.8" />
                <circle cx="0" cy="0" r="3" fill={selectedBuilding.color} />

                {/* Clean ID Callout Badge (Zero text clipping) */}
                <g transform="translate(0, -13)">
                  <rect x="-18" y="-8" width="36" height="9" rx="3.5" fill="#1E293B" stroke="#FFFFFF" strokeWidth="0.8" />
                  <text x="0" y="-2" fontSize="3.2" fontWeight="bold" fill="#FFFFFF" textAnchor="middle">
                    📍 {selectedBuilding.id}
                  </text>
                </g>
              </g>
            )}
          </svg>

          {/* ── Floating Hover Card (Instant 0.2s glance, clean metrics) ────── */}
          {hoveredBuilding && !selectedBuilding && (
            <div
              className="twin-hover"
              style={{
                left: '20px',
                top: '16px',
                maxWidth: '260px',
                pointerEvents: 'none',
                boxShadow: 'var(--tw-shadow-lg)'
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                <span style={{ width: 8, height: 8, borderRadius: '50%', backgroundColor: hoveredBuilding.color }} />
                <strong style={{ fontSize: 13.5 }}>{hoveredBuilding.name}</strong>
              </div>
              <span className="twin-muted" style={{ fontSize: 11.5 }}>
                {hoveredBuilding.category}
              </span>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 6 }}>
                <span className="twin-chip is-light">{hoveredBuilding.capacity}</span>
                <span className="twin-chip is-light">{hoveredBuilding.lots}</span>
              </div>
            </div>
          )}

          {/* ── Bottom Right Clean Zoom Controls ─────────────────────────────── */}
          <div className="twin-controls-right">
            <button className="twin-zoom-btn" onClick={() => handleZoom(0.85)} title="Zoom In">
              <Plus size={15} />
            </button>
            <button className="twin-zoom-btn" onClick={() => handleZoom(1.18)} title="Zoom Out">
              <Minus size={15} />
            </button>
            <button className="twin-zoom-btn" onClick={handleResetFit} title="Fit Site">
              <Maximize2 size={14} />
            </button>
          </div>

          {/* ── FAST-ACTION BOTTOM QUICK CARD (Pure Scoped CSS) ──────────────── */}
          {selectedBuilding && (
            <div className="twin-quick-card">
              <div
                className="twin-quick-card-icon"
                style={{ backgroundColor: selectedBuilding.color }}
              >
                <Building2 size={20} />
              </div>

              <div className="twin-quick-card-info">
                <div className="twin-quick-card-top">
                  <span className="twin-quick-card-title">{selectedBuilding.name}</span>
                  <span className={`twin-status ${selectedBuilding.statusTone}`}>
                    <span className="twin-status-dot" />
                    {selectedBuilding.status}
                  </span>
                </div>

                <div className="twin-quick-card-badges">
                  <span className="twin-chip">{selectedBuilding.capacity}</span>
                  <span className="twin-chip">{selectedBuilding.lots}</span>
                  <span className="twin-chip">{selectedBuilding.mhe}</span>
                </div>
              </div>

              <div className="twin-quick-card-actions">
                <button
                  className="twin-quick-btn"
                  onClick={onSwitchToInventoryTwin}
                  title="Open Interior Floor Plan"
                >
                  <span>Open Interior</span>
                  <ExternalLink size={12} />
                </button>

                <button
                  className="twin-quick-close"
                  onClick={() => setSelectedBuilding(null)}
                  title="Close Card"
                  aria-label="Close building card"
                >
                  <X size={15} />
                </button>
              </div>
            </div>
          )}
        </div>
      </section>
    </div>
  )
}
