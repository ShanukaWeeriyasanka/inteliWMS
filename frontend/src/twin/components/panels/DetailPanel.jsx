// Right panel: details of whatever is selected on the map — a product, a
// rack, a count result, a group of racks or a "which one did you mean?"
// question from the agent. Every number comes from database rows.
import React from 'react'
import { motion } from 'framer-motion'
import {
  ArrowDownLeft, ArrowRightLeft, ArrowUpRight, Check, Copy, Flame, LayoutGrid, MessageSquare, Route, SlidersHorizontal, X,
} from 'lucide-react'
import ProductArt from './ProductArt'
import StatusChip from './StatusChip'
import RackElevation from './RackElevation'
import { Gauge } from './LevelBars'
import { parseLocationId, rackOf, shortBinLabel } from '../../lib/ids'
import { stockGauge, stockStatus, sumBy, timeAgo } from '../../lib/products'

const MOVE_ICON = { receive: ArrowDownLeft, pick: ArrowUpRight, transfer: ArrowRightLeft, adjust: SlidersHorizontal }
const MOVE_VERB = { receive: 'Received', pick: 'Picked', transfer: 'Moved', adjust: 'Adjusted' }
const STEP_DOT = { start: 'is-start', arrive: 'is-arrive', floor_change: 'is-floor', error: 'is-error', note: 'is-note' }

function Shell({ title, sub, aside, onClose, children, reducedMotion }) {
  return (
    <motion.aside className="twin-panel twin-detail" aria-label={`${title} details`}
      initial={reducedMotion ? false : { opacity: 0, x: 24 }} animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.22, ease: 'easeOut' }}>
      <div className="twin-detail-head">
        <div className="twin-detail-title">
          <h2>{title}</h2>
          {aside}
        </div>
        <button className="twin-icon-btn" onClick={onClose} aria-label="Close details"><X size={16} /></button>
      </div>
      {sub && <div className="twin-detail-sub">{sub}</div>}
      <div className="twin-detail-body">{children}</div>
    </motion.aside>
  )
}

function Actions({ items }) {
  return (
    <div className="twin-actions">
      {items.map(({ icon: Icon, label, onClick, on, disabled }) => (
        <button key={label} className={`twin-action${on ? ' is-on' : ''}`} onClick={onClick} disabled={disabled}>
          <span className="twin-action-icon"><Icon size={16} /></span>
          {label}
        </button>
      ))}
    </div>
  )
}

function Directions({ route }) {
  if (!route) return null
  if (route.loading) return <section className="twin-section"><h3>Directions</h3><p className="twin-muted">Finding the route…</p></section>
  if (route.error) return <section className="twin-section"><h3>Directions</h3><p className="twin-error">{route.error}</p></section>
  const steps = route.data?.directions || []
  if (!steps.length) return null
  return (
    <section className="twin-section">
      <div className="twin-section-head"><h3>Directions</h3>{route.summary && <span className="twin-muted">{route.summary}</span>}</div>
      <ol className="twin-steps">
        {steps.map((s) => (
          <li key={s.step} className={STEP_DOT[s.kind] || ''}>
            <span className="twin-step-dot" aria-hidden="true" />
            <span>{s.instruction}</span>
          </li>
        ))}
      </ol>
    </section>
  )
}

/** Hierarchical ID as stops: WH1 › F2 › Z01 › R02 › S03 › B04 (the last one is "here"). */
function IdPath({ id }) {
  const [copied, setCopied] = React.useState(false)
  const parts = id.split('-')
  const copy = () => {
    navigator.clipboard?.writeText(id).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 1400)
    }).catch(() => {})
  }
  return (
    <section className="twin-section">
      <div className="twin-section-head">
        <h3>Location ID</h3>
        <button className="twin-link-btn" onClick={copy}>
          {copied ? <Check size={13} /> : <Copy size={13} />}{copied ? 'Copied' : id}
        </button>
      </div>
      <div className="twin-stops">
        {parts.map((p, i) => (
          <span key={p} className={`twin-stop${i === parts.length - 1 ? ' is-here' : ''}`} title={parts.slice(0, i + 1).join('-')}>{p}</span>
        ))}
      </div>
    </section>
  )
}

export function ProductDetail({
  product, rows, focusRackId, focusBinId, layout, movements, route, rackView, onToggleRackView, onDirections, onAsk, onFocusRow,
  onClose, reducedMotion,
}) {
  const status = stockStatus(product)
  const focus = rows.find((r) => r.bin_id === focusBinId) || rows.find((r) => r.rack_id === focusRackId) || rows[0]
  const floors = new Set(rows.map((r) => r.floor_id))
  const maxQty = Math.max(1, ...rows.map((r) => r.quantity))
  const updated = product.updated_at || rows.reduce((m, r) => (r.updated_at > m ? r.updated_at : m), '')
  let position = null
  if (focus) {
    const cols = layout.rackGrid.get(focus.rack_id)?.cols || 1
    const shelf = layout.rackGrid.get(focus.rack_id)?.shelves.find((s) => s.id === focus.shelf_id)
    position = {
      x: focus.rack_x + ((focus.position_index - 0.5) * focus.rack_width_m) / cols,
      y: focus.rack_y + focus.rack_depth_m / 2,
      z: ((focus.level_index - 1) * (shelf?.height_cm || 45)) / 100,
    }
  }
  const focusRack = focus && layout.racksById.get(focus.rack_id)

  return (
    <Shell reducedMotion={reducedMotion} onClose={onClose} title={product.product_id}
      aside={<span className="twin-tag">#{product.product_no}</span>}
      sub={<><StatusChip status={status} /><span className="twin-muted">SKU {product.sku}</span>{updated && <span className="twin-muted">· updated {timeAgo(updated)}</span>}</>}>

      <div className="twin-hero">
        <span className="twin-muted">Source: {product.data_source || 'unverified'} · Updated: {updated || 'unknown'}</span>
        <div className="twin-hero-chips">
          <span className="twin-chip is-light">{product.total_quantity} {product.unit}</span>
          <span className="twin-chip is-light">{product.category || 'General'}</span>
        </div>
        <ProductArt product={product} size="lg" />
        <div className="twin-hero-name">
          <strong>{product.name}</strong>
          {product.aliases?.length > 0 && <span className="twin-muted">also “{product.aliases.join('”, “')}”</span>}
        </div>
      </div>

      <div className="twin-stat-card">
        <div>
          <span className="twin-label">Stock level</span>
          <div className="twin-big">{product.total_quantity}<small> {product.unit}</small></div>
          <span className="twin-muted">Reorder at {product.reorder_point}</span>
          <div className="twin-muted">Available {product.available_quantity ?? product.total_quantity} · Reserved {product.reserved_quantity ?? 0} · Quarantined {product.quarantined_quantity ?? 0}</div>
          <Gauge value={stockGauge(product)} status={status} />
        </div>
        <div className="twin-bars" aria-label="Units per bin">
          {rows.slice(0, 10).map((r) => (
            <i key={r.bin_id} title={`${shortBinLabel(r.bin_id, r.rack_name)}: ${r.quantity}`}
              className={r.bin_id === focus?.bin_id ? 'is-on' : ''} style={{ height: `${Math.max(10, (r.quantity / maxQty) * 100)}%` }} />
          ))}
        </div>
        <div className="twin-stat-side">
          <span><strong>{rows.length}</strong> bin{rows.length === 1 ? '' : 's'}</span>
          <span><strong>{floors.size}</strong> floor{floors.size === 1 ? '' : 's'}</span>
        </div>
      </div>

      <Actions items={[
        { icon: Route, label: 'Directions', onClick: onDirections, disabled: !rows.length, on: !!route },
        { icon: LayoutGrid, label: 'Rack view', onClick: onToggleRackView, disabled: !focus, on: rackView },
        { icon: MessageSquare, label: 'Ask agent', onClick: () => onAsk(`How many ${product.name} do we have left?`) },
      ]} />
      {product.unplaced_quantity > 0 && <p className="twin-empty">{product.unplaced_quantity} {product.unit} have no verified box assignment.</p>}

      {focus ? (
        <section className="twin-section twin-position">
          <div className="twin-kv"><span className="twin-label">Position</span>
            <span className="twin-mono">{position.x.toFixed(2)} m / {position.y.toFixed(2)} m / {position.z.toFixed(2)} m</span></div>
          <div className="twin-kv"><span className="twin-label">Location</span>
            <span>{focus.location_label}</span></div>
          <div className="twin-kv"><span className="twin-label">Here</span>
            <span><strong>{focus.quantity}</strong> {product.unit} · bin holds {focus.capacity_units}</span></div>
        </section>
      ) : <p className="twin-empty">No verified bin assignment for {product.name}.</p>}

      {rackView && focusRack && (
        <section className="twin-section">
          <div className="twin-section-head"><h3>{focusRack.name} · front view</h3><span className="twin-muted">S1 = floor level</span></div>
          <RackElevation rack={focusRack} layout={layout}
            targetBins={new Set(rows.filter((r) => r.rack_id === focusRack.id).map((r) => r.bin_id))}
            binLabels={sumBy(rows.filter((r) => r.rack_id === focusRack.id), 'bin_id')} />
        </section>
      )}

      <Directions route={route} />

      {rows.length > 0 && (
        <section className="twin-section">
          <div className="twin-section-head"><h3>Stock locations</h3><span className="twin-muted">{rows.length}</span></div>
          <div className="twin-rows">
            {rows.map((r) => (
              <button key={r.bin_id} className={`twin-row${r.bin_id === focus?.bin_id ? ' is-on' : ''}`} onClick={() => onFocusRow(r)}>
                <span className="twin-row-main">
                  <strong>{shortBinLabel(r.bin_id, r.rack_name)}</strong>
                  <span className="twin-muted">{r.location_label}</span>
                  <span className="twin-muted">{r.bin_id} · Updated {r.updated_at}</span>
                </span>
                <span className="twin-row-side">
                  <span>{r.quantity} {product.unit}</span>
                  <span className="twin-muted">{r.available_quantity} available · {r.reserved_quantity} reserved · {r.quarantined_quantity} quarantined</span>
                  <Gauge value={r.quantity / Math.max(1, r.capacity_units)} />
                </span>
              </button>
            ))}
          </div>
        </section>
      )}

      {movements?.length > 0 && (
        <section className="twin-section">
          <div className="twin-section-head"><h3>Recent movements</h3></div>
          <ul className="twin-moves">
            {movements.map((m) => {
              const Icon = MOVE_ICON[m.type] || ArrowRightLeft
              const bin = m.to_bin_id || m.from_bin_id
              return (
                <li key={m.id}>
                  <span className={`twin-move-icon is-${m.type}`}><Icon size={13} /></span>
                  <span className="twin-move-text">
                    <strong>{MOVE_VERB[m.type] || m.type} {m.quantity}</strong>
                    <span className="twin-muted">{bin ? shortBinLabel(bin, layout.racksById.get(rackOf(bin))?.name) : ''}{m.actor ? ` · ${m.actor}` : ''}</span>
                  </span>
                  <span className="twin-muted">{timeAgo(m.created_at)}</span>
                </li>
              )
            })}
          </ul>
        </section>
      )}

      {focus && <IdPath id={focus.bin_id} />}
    </Shell>
  )
}

export function RackDetail({
  rack, layout, fill, rows, productsById, targetBins, targetShelves, route, onSelectProduct, onDirections, onHeat, onAsk,
  onClose, reducedMotion,
}) {
  const zone = layout.zonesById.get(rack.zone_id)
  const floor = layout.floorsById.get(rack.floor_id)
  const ratio = fill?.fill_ratio || 0
  const perProduct = [...sumBy(rows, 'product_id')].sort((a, b) => b[1] - a[1])
  const target = [...(targetBins || []), ...(targetShelves || [])][0]
  const p = target && parseLocationId(target)

  return (
    <Shell reducedMotion={reducedMotion} onClose={onClose} title={rack.name}
      aside={<span className="twin-tag twin-mono">{rack.id.split('-').slice(2).join('-')}</span>}
      sub={<span className="twin-muted">{zone?.name} · {floor?.name}</span>}>

      <div className="twin-stat-card">
        <div>
          <span className="twin-label">Rack fill</span>
          <div className="twin-big">{Math.round(ratio * 100)}<small>%</small></div>
          <Gauge value={ratio} status={ratio > 0.85 ? 'low' : 'ok'} />
        </div>
        <div className="twin-stat-side">
          <span><strong>{fill?.total_units || 0}</strong> units</span>
          <span><strong>{fill?.distinct_products || 0}</strong> products</span>
          <span><strong>{fill?.capacity_units || 0}</strong> capacity</span>
        </div>
      </div>

      <Actions items={[
        { icon: Route, label: 'Directions', onClick: onDirections, on: !!route },
        { icon: Flame, label: 'Heatmap', onClick: onHeat },
        { icon: MessageSquare, label: 'Ask agent', onClick: () => onAsk(`How many products are in ${rack.name} on ${floor?.name}?`) },
      ]} />

      {p && (
        <section className="twin-section twin-position">
          <div className="twin-kv"><span className="twin-label">Target</span>
            <span>Shelf {p.shelfLevel}{p.binPosition ? ` · Bin ${p.binPosition}` : ''}</span></div>
        </section>
      )}

      <section className="twin-section">
        <div className="twin-section-head"><h3>Front view</h3><span className="twin-muted">S1 = floor level · B1 = left</span></div>
        <RackElevation rack={rack} layout={layout} targetBins={targetBins} targetShelves={targetShelves}
          binLabels={sumBy(rows, 'bin_id')} />
      </section>

      <Directions route={route} />

      <section className="twin-section">
        <div className="twin-section-head"><h3>Products here</h3><span className="twin-muted">{perProduct.length}</span></div>
        {!perProduct.length && <p className="twin-empty">This rack is empty.</p>}
        <div className="twin-rows">
          {perProduct.map(([pid, qty]) => {
            const prod = productsById.get(pid)
            const bins = rows.filter((r) => r.product_id === pid)
            return (
              <button key={pid} className="twin-row" onClick={() => onSelectProduct(pid, rack.id)}>
                <ProductArt product={prod} />
                <span className="twin-row-main">
                  <strong>{prod?.name || pid}</strong>
                  <span className="twin-muted">{pid} · {bins.map((b) => `S${b.level_index}·B${b.position_index}`).join(', ')}</span>
                </span>
                <span className="twin-row-side"><span>{qty} {prod?.unit || ''}</span></span>
              </button>
            )
          })}
        </div>
      </section>

      <IdPath id={rack.id} />
    </Shell>
  )
}

export function CountDetail({ result, layout, onSelectRack, onClose, reducedMotion }) {
  const max = Math.max(1, ...result.perRack.map((r) => r.qty))
  return (
    <Shell reducedMotion={reducedMotion} onClose={onClose} title={result.title} sub={<span className="twin-muted">{result.sub}</span>}>
      <div className="twin-stat-card">
        <div>
          <span className="twin-label">Total</span>
          <div className="twin-big">{result.total}<small> {result.unit}</small></div>
        </div>
        <div className="twin-stat-side">
          <span><strong>{result.perRack.filter((r) => r.qty > 0).length}</strong> racks with stock</span>
        </div>
      </div>
      <section className="twin-section">
        <div className="twin-section-head"><h3>Per rack</h3></div>
        <div className="twin-rows">
          {result.perRack.map(({ rackId, qty }) => (
            <button key={rackId} className="twin-row" onClick={() => onSelectRack(rackId)}>
              <span className="twin-row-main">
                <strong>{layout.racksById.get(rackId)?.name}</strong>
                <span className="twin-muted">{layout.zonesById.get(layout.racksById.get(rackId)?.zone_id)?.name}</span>
              </span>
              <span className="twin-row-side"><span>{qty}</span><Gauge value={qty / max} /></span>
            </button>
          ))}
        </div>
      </section>
    </Shell>
  )
}

export function GroupDetail({ title, sub, rackIds, data, onSelectRack, onClose, reducedMotion }) {
  return (
    <Shell reducedMotion={reducedMotion} onClose={onClose} title={title} sub={<span className="twin-muted">{sub}</span>}>
      <div className="twin-rows">
        {rackIds.map((id) => {
          const rack = data.layout.racksById.get(id)
          const fill = data.fillByRack.get(id)
          return (
            <button key={id} className="twin-row" onClick={() => onSelectRack(id)}>
              <span className={`twin-rack-swatch is-${rack?.type}`} aria-hidden="true" />
              <span className="twin-row-main">
                <strong>{rack?.name}</strong>
                <span className="twin-muted">{data.layout.floorsById.get(rack?.floor_id)?.name} · {fill?.total_units || 0} units</span>
              </span>
              <span className="twin-row-side"><Gauge value={fill?.fill_ratio || 0} /></span>
            </button>
          )
        })}
      </div>
    </Shell>
  )
}

export function ClarifyDetail({ text, candidates, onPick, onClose, reducedMotion }) {
  return (
    <Shell reducedMotion={reducedMotion} onClose={onClose} title="Which one?" sub={<span className="twin-muted">{text}</span>}>
      <div className="twin-rows">
        {candidates.map((c) => (
          <button key={c.product_id || c.location_id} className="twin-row" onClick={() => onPick(c)}>
            <span className="twin-row-main">
              <strong>{c.label}</strong>
              <span className="twin-muted twin-mono">{c.product_id || c.location_id}</span>
            </span>
            <span className="twin-row-side twin-muted">Show</span>
          </button>
        ))}
      </div>
    </Shell>
  )
}
