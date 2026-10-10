import React from 'react'
import { Boxes, ScanBarcode } from 'lucide-react'
import { suggestionOptionId } from '../../chat/inventorySuggestions'

// Listbox of suggested Inventory Agent questions, driven by the input's keyboard (aria-activedescendant).
// Options take the mouse without stealing focus from the input; picking one only fills the input.
export default function InventorySuggestions({ id, items, activeIndex = -1, onSelect, onHighlight, variant = 'dark' }) {
  const count = items?.length || 0
  return (
    <>
      <span className="inv-suggest-status" role="status" aria-live="polite">
        {count ? `${count} inventory question suggestion${count === 1 ? '' : 's'}. Use up and down arrows to choose.` : ''}
      </span>
      {count > 0 && (
        <div className={`inv-suggest inv-suggest--${variant}`}>
          <div className="inv-suggest-head" aria-hidden="true">Inventory questions</div>
          <ul id={id} role="listbox" aria-label="Inventory question suggestions" className="inv-suggest-list">
            {items.map((item, i) => {
              const Icon = item.kind === 'product' ? ScanBarcode : Boxes
              return (
                <li
                  key={item.text}
                  id={suggestionOptionId(id, i)}
                  role="option"
                  aria-selected={i === activeIndex}
                  className={`inv-suggest-option${i === activeIndex ? ' is-active' : ''}`}
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={() => onSelect(item, i)}
                  onMouseEnter={() => onHighlight?.(i)}
                >
                  <Icon size={13} className="inv-suggest-icon" aria-hidden="true" />
                  <span className="inv-suggest-text">{item.text}</span>
                </li>
              )
            })}
          </ul>
        </div>
      )}
    </>
  )
}
