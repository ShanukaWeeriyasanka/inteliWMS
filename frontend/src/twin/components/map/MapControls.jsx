// Bottom map controls: scale bar + layer switch (left), zoom (right), and the
// heatmap legend when the heat layer is on.
import React from 'react'
import { Flame, Layers, Maximize2, Minus, Plus } from 'lucide-react'
import { scaleBar } from '../../lib/viewport'
import { HEAT_STEPS } from '../../lib/heat'

const METRIC_LABEL = {
  fill_ratio: 'Rack fill', total_units: 'Units per rack', product_quantity: 'Units of this product',
  distinct_products: 'Products per rack',
}

export default function MapControls({ mpp, layer, onLayer, heatMetric, onZoomIn, onZoomOut, onFit }) {
  const bar = mpp > 0 ? scaleBar(mpp) : null
  return (
    <>
      <div className="twin-controls-left">
        {bar && (
          <div className="twin-scale" aria-label={`Scale: ${bar.metres} metres`}>
            <span style={{ width: bar.px }}>{bar.metres} m</span>
            <span style={{ width: bar.px }}>{bar.feet} ft</span>
          </div>
        )}
        <div className="twin-layer-switch" role="radiogroup" aria-label="Map layer">
          <button role="radio" aria-checked={layer === 'map'} className={layer === 'map' ? 'is-on' : ''}
            onClick={() => onLayer('map')} title="Stock map"><Layers size={14} /></button>
          <button role="radio" aria-checked={layer === 'heat'} className={layer === 'heat' ? 'is-on' : ''}
            onClick={() => onLayer('heat')} title="Heatmap"><Flame size={14} /></button>
        </div>
        {layer === 'heat' && (
          <div className="twin-legend">
            <span>{METRIC_LABEL[heatMetric] || 'Rack fill'}</span>
            <span className="twin-legend-ramp">{HEAT_STEPS.map((c) => <i key={c} style={{ background: c }} />)}</span>
            <span className="twin-muted">low → high</span>
          </div>
        )}
      </div>
      <div className="twin-controls-right">
        <button className="twin-zoom-btn" onClick={onZoomIn} aria-label="Zoom in"><Plus size={15} /></button>
        <button className="twin-zoom-btn" onClick={onZoomOut} aria-label="Zoom out"><Minus size={15} /></button>
        <button className="twin-zoom-btn" onClick={onFit} aria-label="Fit floor"><Maximize2 size={14} /></button>
      </div>
    </>
  )
}
