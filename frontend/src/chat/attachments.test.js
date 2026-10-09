import { describe, expect, it } from 'vitest'
import {
  CHAT_MAX_CHARS,
  TRUNCATION_NOTE,
  charCounterLabel,
  composeQuery,
  isReadableTextFile,
  splitAttachedQuery,
  unsupportedFileNotice,
} from './attachments'

describe('isReadableTextFile', () => {
  it('accepts text mime types and known text extensions', () => {
    expect(isReadableTextFile({ name: 'notes', type: 'text/plain' })).toBe(true)
    expect(isReadableTextFile({ name: 'supplier.EML', type: '' })).toBe(true)
    for (const ext of ['txt', 'csv', 'md', 'json', 'log', 'tsv']) {
      expect(isReadableTextFile({ name: `file.${ext}`, type: 'application/octet-stream' })).toBe(true)
    }
  })

  it('rejects images, PDFs and other binaries', () => {
    expect(isReadableTextFile({ name: 'photo.jpg', type: 'image/jpeg' })).toBe(false)
    expect(isReadableTextFile({ name: 'manifest.pdf', type: 'application/pdf' })).toBe(false)
    expect(isReadableTextFile({ name: '.txt', type: '' })).toBe(false)
    expect(unsupportedFileNotice('photo.jpg'))
      .toBe("photo.jpg can't be read here — only text files (.txt, .csv, .eml, .md) are supported.")
  })
})

describe('composeQuery', () => {
  it('appends each file after the typed text', () => {
    const { query, truncated, omitted } = composeQuery('Check this order', [
      { name: 'a.txt', content: 'alpha' },
      { name: 'b.csv', content: 'sku,qty\nSKU-1,3' },
    ])
    expect(query).toBe('Check this order\n\n[Attached file: a.txt]\nalpha\n\n[Attached file: b.csv]\nsku,qty\nSKU-1,3')
    expect(truncated).toEqual([])
    expect(omitted).toEqual([])
  })

  it('sends a file on its own when nothing was typed', () => {
    expect(composeQuery('  ', [{ name: 'supplier.eml', content: 'Subject: delay' }]).query)
      .toBe('[Attached file: supplier.eml]\nSubject: delay')
  })

  it('never exceeds the limit and marks cut files', () => {
    const big = 'x'.repeat(10000)
    const { query, truncated } = composeQuery('hello', [{ name: 'big.log', content: big }])
    expect(query.length).toBe(CHAT_MAX_CHARS)
    expect(query.startsWith('hello\n\n[Attached file: big.log]\nxxx')).toBe(true)
    expect(query.endsWith(TRUNCATION_NOTE)).toBe(true)
    expect(truncated).toEqual(['big.log'])
  })

  it('marks files that were only partly read even if the start fits', () => {
    const { query, truncated } = composeQuery('', [{ name: 'huge.csv', content: 'a,b', truncated: true }])
    expect(query).toBe(`[Attached file: huge.csv]\na,b${TRUNCATION_NOTE}`)
    expect(truncated).toEqual(['huge.csv'])
  })

  it('reports files that no longer fit at all', () => {
    const typed = 'q'.repeat(CHAT_MAX_CHARS - 10)
    const { query, omitted } = composeQuery(typed, [{ name: 'late.txt', content: 'zzz' }])
    expect(query).toBe(typed)
    expect(omitted).toEqual(['late.txt'])
  })

  it('does not split an emoji when cutting', () => {
    const content = `${'a'.repeat(30)}${'📦'.repeat(20)}`
    const { query } = composeQuery('', [{ name: 'e.txt', content }], 30 + '[Attached file: e.txt]\n'.length + TRUNCATION_NOTE.length + 1)
    expect(query).toBe(`[Attached file: e.txt]\n${'a'.repeat(30)}${TRUNCATION_NOTE}`)
  })
})

describe('splitAttachedQuery', () => {
  it('turns a saved question back into typed text + file chips', () => {
    const { query } = composeQuery('Is this late?', [{ name: 'a.eml', content: 'body' }, { name: 'b.txt', content: 'more' }])
    expect(splitAttachedQuery(query)).toEqual({ text: 'Is this late?', attachments: [{ name: 'a.eml' }, { name: 'b.txt' }] })
    expect(splitAttachedQuery('[Attached file: only.txt]\nbody')).toEqual({ text: '', attachments: [{ name: 'only.txt' }] })
    expect(splitAttachedQuery('plain question')).toEqual({ text: 'plain question', attachments: [] })
  })
})

describe('charCounterLabel', () => {
  it('appears only near the limit', () => {
    expect(charCounterLabel(120)).toBeNull()
    expect(charCounterLabel(3500)).toBeNull()
    expect(charCounterLabel(3812)).toBe('3,812 / 4,000')
  })
})
