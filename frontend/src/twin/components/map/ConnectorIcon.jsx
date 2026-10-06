// Markers for lifts, stairs, entrance, dock and charging bays, with their label.
import React from 'react'
import MapText from './MapText'

const BOLT = 'M0.1 -0.48 L-0.27 0.07 L-0.02 0.07 L-0.1 0.48 L0.27 -0.07 L0.02 -0.07 Z'
const GLYPH = { lift: '⇅', stairs: '≡', entrance: '→', dock: '▭' }

export default function ConnectorIcon({ node }) {
  const dark = node.type !== 'entrance' && node.type !== 'dock'
  return (
    <g className={`twin-connector${dark ? ' is-dark' : ''}`} transform={`translate(${node.x} ${node.y})`}>
      <title>{node.label}</title>
      <rect x={-0.72} y={-0.72} width={1.44} height={1.44} rx={0.34} filter="url(#twin-shadow)" />
      {node.type === 'charging'
        ? <path d={BOLT} className="twin-connector-bolt" />
        : <MapText x={0} y={0.04} size={0.82}>{GLYPH[node.type] || '•'}</MapText>}
      {node.label && <MapText className="twin-connector-label" x={0} y={1.35} size={0.5}>{node.label}</MapText>}
    </g>
  )
}
