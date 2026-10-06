// Left panel: the warehouse's products, the racks on this floor and open
// alerts, as clickable cards (like a fleet list). Search matches ID, number,
// SKU, name and aliases.
import React, { useMemo } from 'react'
import { ChevronDown, MapPin, MoreHorizontal, Search, X } from 'lucide-react'
import ProductArt from './ProductArt'
import StatusChip from './StatusChip'
import LevelBars, { Gauge } from './LevelBars'
import { matchesProduct, stockGauge, stockStatus, timeAgo } from '../../lib/products'
import { shortBinLabel } from '../../lib/ids'

const TABS = [['products', 'Products'], ['racks', 'Racks'], ['alerts', 'Alerts']]

function ProductCard({ product, rows, selected, onClick }) {
  const status = stockStatus(product)
  const best = rows?.[0]
  const floors = new Set((rows || []).map((r) => r.floor_id)).size
  return (
    <button className={`twin-card${selected ? ' is-selected' : ''}`} onClick={onClick} aria-pressed={selected}>
      <div className="twin-card-top">
        <ProductArt product={product} />
        <strong className="twin-card-id">{product.product_id}</strong>
        <StatusChip status={status} />
      </div>
      <div className="twin-card-grid">
        <span className="twin-label">Product</span>
        <span className="twin-label">Location</span>
        <span className="twin-value" title={product.name}>{product.name}</span>
        <span className="twin-value">
          <LevelBars value={stockGauge(product)} status={status} />
          {best ? shortBinLabel(best.bin_id, best.rack_name) : 'Not stored'}
        </span>
      </div>
      <div className="twin-card-chips">
        <span className="twin-chip">{product.category || 'General'}</span>
        <span className="twin-chip">{product.bin_count} bin{product.bin_count === 1 ? '' : 's'}{floors > 1 ? ` · ${floors} floors` : ''}</span>
        <span className="twin-chip is-gauge">
          <Gauge value={stockGauge(product)} status={status} />
          {product.total_quantity} {product.unit}
        </span>
      </div>
    </button>
  )
}

function RackCard({ rack, zone, fill, selected, onClick }) {
  const ratio = fill?.fill_ratio || 0
  return (
    <button className={`twin-card is-compact${selected ? ' is-selected' : ''}`} onClick={onClick} aria-pressed={selected}>
      <div className="twin-card-top">
        <span className={`twin-rack-swatch is-${rack.type}`} aria-hidden="true" />
        <strong className="twin-card-id">{rack.name}</strong>
        <span className="twin-muted twin-mono">{rack.id.split('-').slice(2).join('-')}</span>
      </div>
      <div className="twin-card-row">
        <span className="twin-muted">{zone?.name}</span>
      </div>
      <div className="twin-card-chips">
        <span className="twin-chip is-gauge"><Gauge value={ratio} status={ratio > 0.85 ? 'low' : 'ok'} />{Math.round(ratio * 100)}% full</span>
        <span className="twin-chip">{fill?.total_units || 0} units</span>
        <span className="twin-chip">{fill?.distinct_products || 0} products</span>
      </div>
    </button>
  )
}

function AlertCard({ alert, onClick }) {
  return (
    <button className={`twin-card is-compact is-alert-${alert.level}`} onClick={onClick}>
      <div className="twin-card-top">
        <span className="twin-alert-icon" aria-hidden="true">!</span>
        <strong className="twin-card-id">{alert.product_name || alert.bin_id}</strong>
        <span className="twin-muted">{timeAgo(alert.created_at)}</span>
      </div>
      <p className="twin-card-text">{alert.message}</p>
    </button>
  )
}

export default function InventoryPanel({
  data, floorId, tab, onTab, query, onQuery, selection, onSelectProduct, onSelectRack, onSelectAlert, onClose,
}) {
  const { layout, products, locationsByProduct, fillByRack, alerts } = data
  const warehouse = layout.raw.warehouses[0]
  const floorRacks = layout.racksByFloor.get(floorId) || []
  const shown = useMemo(() => products.filter((p) => matchesProduct(p, query)), [products, query])
  const counts = { products: products.length, racks: floorRacks.length, alerts: alerts.length }
  const selProduct = selection?.kind === 'product' ? selection.id : null
  const selRack = selection?.kind === 'rack' ? selection.id : null

  return (
    <aside className="twin-panel twin-inventory" aria-label="Inventory">
      <div className="twin-panel-head">
        <h2>Inventory</h2>
        {onClose
          ? <button className="twin-icon-btn" onClick={onClose} aria-label="Hide inventory list"><X size={15} /></button>
          : <span className="twin-icon-btn is-static" aria-hidden="true"><MoreHorizontal size={15} /></span>}
      </div>

      <div className="twin-site" title={warehouse?.address}>
        <span className="twin-site-pin"><MapPin size={14} /></span>
        <span className="twin-site-name">{warehouse?.name}{warehouse?.address ? `, ${warehouse.address}` : ''}</span>
        <ChevronDown size={14} />
      </div>

      <div className="twin-tabs" role="tablist">
        {TABS.map(([key, label]) => (
          <button key={key} role="tab" aria-selected={tab === key} className={tab === key ? 'is-on' : ''} onClick={() => onTab(key)}>
            {tab === key && <span className="twin-tab-dot" />}
            {label}
            <span className="twin-tab-count">{counts[key]}</span>
          </button>
        ))}
      </div>

      {tab === 'products' && (
        <label className="twin-search">
          <Search size={14} />
          <input value={query} onChange={(e) => onQuery(e.target.value)} placeholder="Search ID, number, SKU or name" />
          {query && <button className="twin-icon-btn" onClick={() => onQuery('')} aria-label="Clear search"><X size={12} /></button>}
        </label>
      )}

      <div className="twin-list">
        {tab === 'products' && shown.map((p) => (
          <ProductCard key={p.product_id} product={p} rows={locationsByProduct.get(p.product_id)}
            selected={selProduct === p.product_id} onClick={() => onSelectProduct(p.product_id)} />
        ))}
        {tab === 'products' && !shown.length && <p className="twin-empty">No product matches “{query}”.</p>}

        {tab === 'racks' && floorRacks.map((r) => (
          <RackCard key={r.id} rack={r} zone={layout.zonesById.get(r.zone_id)} fill={fillByRack.get(r.id)}
            selected={selRack === r.id} onClick={() => onSelectRack(r.id)} />
        ))}

        {tab === 'alerts' && alerts.map((a) => <AlertCard key={a.id} alert={a} onClick={() => onSelectAlert(a)} />)}
        {tab === 'alerts' && !alerts.length && <p className="twin-empty">No open alerts. Stock is healthy.</p>}
      </div>
    </aside>
  )
}
