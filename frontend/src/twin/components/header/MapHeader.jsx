// Map header: building + floor picker on the left; product / rack / alert
// counters, live status and "back to chat" on the right.
import React, { useEffect, useRef, useState } from 'react'
import { ArrowLeft, Boxes, ChevronDown, CircleAlert, Layers, LayoutGrid, PanelLeft } from 'lucide-react'

function FloorPicker({ floors, floorId, targetFloors, onChange }) {
  const [open, setOpen] = useState(false)
  const ref = useRef(null)
  const current = floors.find((f) => f.id === floorId)
  useEffect(() => {
    if (!open) return undefined
    const close = (e) => { if (!ref.current?.contains(e.target)) setOpen(false) }
    window.addEventListener('pointerdown', close)
    return () => window.removeEventListener('pointerdown', close)
  }, [open])
  return (
    <div className="twin-floor-picker" ref={ref}>
      <button className="twin-floor-btn" onClick={() => setOpen((o) => !o)} aria-haspopup="listbox" aria-expanded={open}>
        <Layers size={14} />
        {current?.name}
        <ChevronDown size={13} />
      </button>
      {open && (
        <ul className="twin-menu" role="listbox" aria-label="Floor">
          {floors.map((f) => (
            <li key={f.id}>
              <button role="option" aria-selected={f.id === floorId} className={f.id === floorId ? 'is-on' : ''}
                onClick={() => { onChange(f.id); setOpen(false) }}>
                {f.name}
                <span className="twin-muted twin-mono">{f.id}</span>
                {targetFloors.has(f.id) && <span className="twin-floor-dot" aria-label="has the target" />}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

export default function MapHeader({
  warehouse, floors, floorId, targetFloors, onFloor, counts, live, alertsOn, onAlerts, onRacks, onProducts, onClose,
  onToggleList, listOpen,
}) {
  return (
    <header className="twin-map-head">
      <div className="twin-map-head-left">
        {onToggleList && (
          <button className={`twin-icon-btn is-boxed${listOpen ? ' is-on' : ''}`} onClick={onToggleList} aria-label="Inventory list">
            <PanelLeft size={15} />
          </button>
        )}
        <h1 className="twin-map-title" title={warehouse?.address}>{warehouse?.name}</h1>
        <FloorPicker floors={floors} floorId={floorId} targetFloors={targetFloors} onChange={onFloor} />
      </div>
      <div className="twin-map-head-right">
        <button className="twin-count-pill" onClick={onProducts} title="Products"><Boxes size={14} />{counts.products}</button>
        <button className="twin-count-pill" onClick={onRacks} title="Racks on this floor"><LayoutGrid size={14} />{counts.racks}</button>
        <button className={`twin-count-pill is-alert${alertsOn ? ' is-on' : ''}`} onClick={onAlerts} title="Open alerts">
          <CircleAlert size={14} />{counts.alerts}
        </button>
        <span className={`twin-live${live ? '' : ' is-paused'}`} role="status">
          <span className="twin-live-dot" />{live ? 'Live' : 'Paused'}
        </span>
        <button className="twin-back-btn" onClick={onClose}><ArrowLeft size={14} />Chat</button>
      </div>
    </header>
  )
}
