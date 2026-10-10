import { describe, expect, it } from 'vitest'
import { normalizeSpokenText, LOGISTICS_VOCABULARY_BOOSTS } from './voiceNormalizer'
import { cleanTextForSpeech } from './useSpeechSynthesis'

describe('voiceNormalizer', () => {
  it('corrects common phonetic misrecognitions in warehouse speech', () => {
    expect(normalizeSpokenText('where is the cold ball located')).toBe('Where is the cold vault located')
    expect(normalizeSpokenText('call the fork lift driver')).toBe('Call the forklift driver')
    expect(normalizeSpokenText('check the safety socks level')).toBe('Check the safety stock level')
    expect(normalizeSpokenText('we need a cycle count today')).toBe('We need a cycle count today')
  })

  it('normalizes spoken SKU sequences into uppercase hyphenated SKUs', () => {
    expect(normalizeSpokenText('check stock for sku one zero zero four')).toBe('Check stock for SKU-1004')
    expect(normalizeSpokenText('where is sku four five two one')).toBe('Where is SKU-4521')
    expect(normalizeSpokenText('status of order four five two one')).toBe('Status of ORD-4521')
  })

  it('normalizes location bays', () => {
    expect(normalizeSpokenText('go to bay bee twelve')).toBe('Go to bay B-12')
    expect(normalizeSpokenText('check bay a four')).toBe('Check bay A-04')
  })

  it('handles empty or blank inputs cleanly', () => {
    expect(normalizeSpokenText('')).toBe('')
    expect(normalizeSpokenText(null)).toBe('')
  })
})

describe('cleanTextForSpeech', () => {
  it('strips markdown formatting so text sounds natural when spoken', () => {
    const markdown = '**Alert**: SKU-1004 is located in `Bay B-12`! [View Map](file:///loc).'
    const cleaned = cleanTextForSpeech(markdown)
    expect(cleaned).toContain('Alert: SKU-1004 is located in Bay B-12! View Map.')
    expect(cleaned).not.toContain('**')
    expect(cleaned).not.toContain('`')
    expect(cleaned).not.toContain('[')
  })

  it('strips markdown table syntax cleanly', () => {
    const tableMarkdown = `
| SKU | Location | Qty |
| --- | --- | --- |
| SKU-1004 | B-12 | 150 |
`
    const cleaned = cleanTextForSpeech(tableMarkdown)
    expect(cleaned).not.toContain('|')
    expect(cleaned).not.toContain('---')
  })
})
