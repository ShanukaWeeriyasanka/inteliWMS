import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import InventorySuggestions from '../components/coordinator UI/InventorySuggestions'
import AgentDock from '../twin/components/AgentDock'
import PromptCapsule from '../components/coordinator UI/PromptCapsule'

const items = [
  { text: 'What is the current stock of Wireless Barcode Scanner (SKU-1004)?', kind: 'product', sku: 'SKU-1004' },
  { text: 'Which products are low on stock?', kind: 'generic' },
]

describe('InventorySuggestions', () => {
  it('renders an accessible listbox with the highlighted option selected', () => {
    const html = renderToStaticMarkup(
      <InventorySuggestions id="inv-list" items={items} activeIndex={1} onSelect={() => {}} />,
    )
    expect(html).toContain('role="listbox"')
    expect(html).toContain('aria-label="Inventory question suggestions"')
    expect(html).toContain('id="inv-list-opt-0"')
    expect(html).toMatch(/id="inv-list-opt-1" role="option" aria-selected="true"/)
    expect(html).toMatch(/id="inv-list-opt-0" role="option" aria-selected="false"/)
    expect(html).toContain('inv-suggest--dark')
    expect(html).toContain('2 inventory question suggestions')
  })

  it('has a light variant for the map dock', () => {
    const html = renderToStaticMarkup(<InventorySuggestions id="x" items={items} variant="light" onSelect={() => {}} />)
    expect(html).toContain('inv-suggest--light')
  })

  it('renders no list (only an empty live region) when there is nothing to suggest', () => {
    const html = renderToStaticMarkup(<InventorySuggestions id="x" items={[]} onSelect={() => {}} />)
    expect(html).not.toContain('role="listbox"')
    expect(html).toContain('aria-live="polite"')
  })
})

describe('chat inputs expose the suggestions as a combobox', () => {
  it('PromptCapsule keeps its send button and quick chips while closed', () => {
    const html = renderToStaticMarkup(<PromptCapsule onSend={() => {}} isLoading={false} authToken="t" />)
    expect(html).toContain('role="combobox"')
    expect(html).toContain('aria-expanded="false"')
    expect(html).toContain('aria-autocomplete="list"')
    expect(html).toContain('capsule-send-btn')
    expect(html).toContain('prompt-quick-chips-row')
  })

  it('AgentDock input is a combobox too', () => {
    const html = renderToStaticMarkup(
      <AgentDock reply="" busy={false} value="" onChange={() => {}} onSend={() => {}} token="t" />,
    )
    expect(html).toContain('role="combobox"')
    expect(html).toContain('aria-expanded="false"')
  })
})
