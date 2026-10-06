import React from 'react'
import { stockStatus } from '../../lib/products'

export { stockStatus }

const LABEL = { ok: 'In stock', low: 'Low stock', out: 'Out of stock', over: 'Over capacity', unknown: '—' }

/** Status is never colour alone: every chip has a dot AND a word. */
export default function StatusChip({ status }) {
  return (
    <span className={`twin-status is-${status}`}>
      <span className="twin-status-dot" aria-hidden="true" />
      {LABEL[status]}
    </span>
  )
}
