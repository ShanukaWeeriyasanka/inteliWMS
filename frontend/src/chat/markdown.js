// Tiny Markdown subset for agent replies → a plain tree that MarkdownText turns into
// React elements. Supported: **bold**, *italic*, `code`, bullet lines ("• ", "- ", "* "),
// numbered lines ("1. "), line breaks and blank-line paragraphs. Nothing here is ever
// treated as HTML: text like <img onerror=…> stays text (React escapes it).
//
// Blocks:  { type: 'paragraph', children: Inline[] }
//          { type: 'list', ordered: boolean, start: number, items: Inline[][] }
// Inline:  { type: 'text', value } | { type: 'code', value } | { type: 'br' }
//          { type: 'strong', children } | { type: 'em', children }

const BULLET = /^\s*[•\-*]\s+(.*)$/
const NUMBERED = /^\s*(\d{1,3})[.)]\s+(.*)$/
const ESCAPABLE = new Set(['*', '`', '\\'])

const isSpace = (ch) => ch === undefined || /\s/.test(ch)

// Closing "**" for a bold run that opened at `from` (content must not be empty or start/end with a space)
function findBoldClose(src, from) {
  let end = src.indexOf('**', from)
  while (end !== -1) {
    if (end > from && !isSpace(src[end - 1])) return end
    end = src.indexOf('**', end + 1)
  }
  return -1
}

// Closing "*" for an italic run: not part of "**", not preceded by a space
function findItalicClose(src, from) {
  for (let j = from; j < src.length; j += 1) {
    if (src[j] === '\\') { j += 1; continue }
    if (src[j] === '`') {
      const codeEnd = src.indexOf('`', j + 1)
      if (codeEnd !== -1) { j = codeEnd; continue }
    }
    if (src[j] === '*' && src[j + 1] !== '*' && src[j - 1] !== '*' && j > from && !isSpace(src[j - 1])) return j
  }
  return -1
}

export function parseInline(src = '') {
  const out = []
  let buf = ''
  const flush = () => {
    if (buf) out.push({ type: 'text', value: buf })
    buf = ''
  }

  let i = 0
  while (i < src.length) {
    const ch = src[i]

    if (ch === '\\' && ESCAPABLE.has(src[i + 1])) {
      buf += src[i + 1]
      i += 2
      continue
    }

    if (ch === '`') {
      const end = src.indexOf('`', i + 1)
      if (end > i + 1) {
        flush()
        out.push({ type: 'code', value: src.slice(i + 1, end) })
        i = end + 1
        continue
      }
    }

    if (ch === '*' && src[i + 1] === '*' && !isSpace(src[i + 2])) {
      const end = findBoldClose(src, i + 2)
      if (end !== -1) {
        flush()
        out.push({ type: 'strong', children: parseInline(src.slice(i + 2, end)) })
        i = end + 2
        continue
      }
    }

    if (ch === '*' && src[i + 1] !== '*' && !isSpace(src[i + 1])) {
      const end = findItalicClose(src, i + 1)
      if (end !== -1) {
        flush()
        out.push({ type: 'em', children: parseInline(src.slice(i + 1, end)) })
        i = end + 1
        continue
      }
    }

    buf += ch
    i += 1
  }
  flush()
  return out
}

// Joins lines of one block with explicit line breaks
const withBreaks = (lines) => lines.flatMap((line, idx) => (idx === 0 ? parseInline(line) : [{ type: 'br' }, ...parseInline(line)]))

const tableCells = (line) => line.trim().replace(/^\|/, '').replace(/\|$/, '')
  .split(/(?<!\\)\|/).map((cell) => cell.trim().replace(/\\\|/g, '|'))

export function parseMarkdown(text = '', { allowTables = false } = {}) {
  const lines = String(text ?? '').replace(/\r\n?/g, '\n').split('\n')
  const blocks = []
  let para = null // lines of the current paragraph
  let list = null // { ordered, start, items: string[][] }

  const closePara = () => {
    if (para) blocks.push({ type: 'paragraph', children: withBreaks(para) })
    para = null
  }
  const closeList = () => {
    if (list) blocks.push({ type: 'list', ordered: list.ordered, start: list.start, items: list.items.map(withBreaks) })
    list = null
  }

  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index]
    if (allowTables && line.trim().startsWith('|') && lines[index + 1]?.trim().startsWith('|')) {
      const header = tableCells(line)
      const divider = tableCells(lines[index + 1])
      if (header.length === divider.length && divider.every((cell) => /^:?-{3,}:?$/.test(cell))) {
        closePara()
        closeList()
        const rows = []
        index += 1
        while (lines[index + 1]?.trim().startsWith('|')) {
          const row = tableCells(lines[index + 1])
          if (row.length !== header.length) break
          rows.push(row.map(parseInline))
          index += 1
        }
        blocks.push({ type: 'table', header: header.map(parseInline), rows })
        continue
      }
    }
    if (!line.trim()) {
      closePara()
      closeList()
      continue
    }

    const bullet = line.match(BULLET)
    const numbered = bullet ? null : line.match(NUMBERED)
    if (bullet || numbered) {
      const ordered = !!numbered
      closePara()
      if (list && list.ordered !== ordered) closeList()
      if (!list) list = { ordered, start: ordered ? Number(numbered[1]) : 1, items: [] }
      list.items.push([ordered ? numbered[2] : bullet[1]])
      continue
    }

    // An indented line right after a list item continues that item
    if (list && /^\s+/.test(line)) {
      list.items[list.items.length - 1].push(line.trim())
      continue
    }

    closeList()
    if (!para) para = []
    para.push(line)
  }
  closePara()
  closeList()
  return blocks
}
