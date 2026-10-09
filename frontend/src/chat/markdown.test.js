import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { parseInline, parseMarkdown } from './markdown'
import MarkdownText from '../components/coordinator UI/MarkdownText'

const text = (value) => ({ type: 'text', value })
const render = (md) => renderToStaticMarkup(React.createElement(MarkdownText, { text: md }))

describe('parseInline', () => {
  it('parses bold, italic and inline code', () => {
    expect(parseInline('We have **330** units of `SKU-4521`, *roughly* full')).toEqual([
      text('We have '),
      { type: 'strong', children: [text('330')] },
      text(' units of '),
      { type: 'code', value: 'SKU-4521' },
      text(', '),
      { type: 'em', children: [text('roughly')] },
      text(' full'),
    ])
  })

  it('nests italic and code inside bold', () => {
    expect(parseInline('**Rack *A* `R-12`**')).toEqual([
      { type: 'strong', children: [text('Rack '), { type: 'em', children: [text('A')] }, text(' '), { type: 'code', value: 'R-12' }] },
    ])
  })

  it('leaves unmatched or spaced markers as text', () => {
    expect(parseInline('5 * 3 = 15')).toEqual([text('5 * 3 = 15')])
    expect(parseInline('**not closed')).toEqual([text('**not closed')])
    expect(parseInline('a ` b')).toEqual([text('a ` b')])
    expect(parseInline('\\*literal\\*')).toEqual([text('*literal*')])
  })

  it('keeps code content literal', () => {
    expect(parseInline('`**x**`')).toEqual([{ type: 'code', value: '**x**' }])
  })
})

describe('parseMarkdown', () => {
  it('splits paragraphs on blank lines and keeps single line breaks', () => {
    expect(parseMarkdown('Line one\nLine two\n\nNext 📦')).toEqual([
      { type: 'paragraph', children: [text('Line one'), { type: 'br' }, text('Line two')] },
      { type: 'paragraph', children: [text('Next 📦')] },
    ])
  })

  it('builds bullet lists from "• ", "- " and "* " lines', () => {
    const blocks = parseMarkdown('Low stock:\n• **SKU-1** — 3 left\n- SKU-2\n* SKU-3')
    expect(blocks[0]).toEqual({ type: 'paragraph', children: [text('Low stock:')] })
    expect(blocks[1].type).toBe('list')
    expect(blocks[1].ordered).toBe(false)
    expect(blocks[1].items).toHaveLength(3)
    expect(blocks[1].items[0]).toEqual([{ type: 'strong', children: [text('SKU-1')] }, text(' — 3 left')])
  })

  it('builds numbered lists and keeps the first number', () => {
    const [list] = parseMarkdown('3. Pick\n4. Pack\n   carefully')
    expect(list).toMatchObject({ type: 'list', ordered: true, start: 3 })
    expect(list.items[1]).toEqual([text('Pack'), { type: 'br' }, text('carefully')])
  })

  it('handles CRLF, empty and missing input', () => {
    expect(parseMarkdown('a\r\nb')).toEqual([{ type: 'paragraph', children: [text('a'), { type: 'br' }, text('b')] }])
    expect(parseMarkdown('')).toEqual([])
    expect(parseMarkdown(undefined)).toEqual([])
  })
})

describe('MarkdownText', () => {
  it('renders elements, not raw markdown', () => {
    const html = render('**330** units of `SKU-4521`\n\n• one\n• two\n\n1. first')
    expect(html).toContain('<strong>330</strong>')
    expect(html).toContain('<code class="md-code">SKU-4521</code>')
    expect(html).toContain('<ul class="md-list"><li>one</li><li>two</li></ul>')
    expect(html).toContain('<ol class="md-list"><li>first</li></ol>')
    expect(html).not.toContain('**')
  })

  it('never interprets HTML in the text', () => {
    const html = render('<img src=x onerror="alert(1)"> **<b>bold</b>**')
    expect(html).not.toContain('<img')
    expect(html).not.toContain('<b>')
    expect(html).toContain('&lt;img src=x onerror=&quot;alert(1)&quot;&gt;')
    expect(html).toContain('<strong>&lt;b&gt;bold&lt;/b&gt;</strong>')
  })
})
