// Chat message limits and text-file attachments.
// Files are read in the browser and sent as part of the question text, e.g.
//   "check this order\n\n[Attached file: supplier.eml]\n<file text>"
// The whole question must fit the backend's limit (CHAT_MAX_CHARS), so file text is cut to fit.

export const CHAT_MAX_CHARS = 4000 // keep in sync with the backend's CHAT_MAX_MESSAGE_CHARS
export const CHAR_COUNTER_FROM = 3500 // show "3,812 / 4,000" from here on
export const TEXT_FILE_EXTENSIONS = ['txt', 'csv', 'md', 'eml', 'json', 'log', 'tsv']
export const TEXT_FILE_ACCEPT = `${TEXT_FILE_EXTENSIONS.map((ext) => `.${ext}`).join(',')},text/*`
export const TRUNCATION_NOTE = '\n[… file truncated]'
// Bytes read from a file: always more characters than can be sent (a character is at most 4 bytes)
export const READ_LIMIT_BYTES = CHAT_MAX_CHARS * 4

const ATTACHED_MARKER = /(^|\n\n)\[Attached file: ([^\]\n]+)\]\n/g

const formatNumber = (n) => n.toLocaleString('en-US')

export function fileExtension(name = '') {
  const dot = name.lastIndexOf('.')
  return dot > 0 ? name.slice(dot + 1).toLowerCase() : ''
}

export function isReadableTextFile({ name = '', type = '' } = {}) {
  return type.startsWith('text/') || TEXT_FILE_EXTENSIONS.includes(fileExtension(name))
}

export function unsupportedFileNotice(name) {
  return `${name} can't be read here — only text files (.txt, .csv, .eml, .md) are supported.`
}

export function omittedFileNotice(name, maxChars = CHAT_MAX_CHARS) {
  return `${name} was not sent — the message is already at the ${formatNumber(maxChars)}-character limit.`
}

export function formatFileSize(bytes = 0) {
  return bytes < 1024 * 1024 ? `${(bytes / 1024).toFixed(1)} KB` : `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

// "3,812 / 4,000" once the text is long enough to matter, otherwise null
export function charCounterLabel(length, maxChars = CHAT_MAX_CHARS, from = CHAR_COUNTER_FROM) {
  return length > from ? `${formatNumber(length)} / ${formatNumber(maxChars)}` : null
}

// Typed text + each attachment as "[Attached file: NAME]" and its text, never longer than maxChars.
// attachments: [{ name, content, truncated? }] (truncated = only the start of the file was read)
// Returns the query plus the names of files that were cut short or could not be included at all.
export function composeQuery(text = '', attachments = [], maxChars = CHAT_MAX_CHARS) {
  let query = String(text || '').trim()
  const truncated = []
  const omitted = []

  for (const att of attachments) {
    const header = `${query ? '\n\n' : ''}[Attached file: ${att.name}]\n`
    const content = String(att.content || '')
    const room = maxChars - query.length - header.length

    if (!att.truncated && content.length <= room) {
      query += header + content
      continue
    }

    let keep = Math.min(content.length, room - TRUNCATION_NOTE.length)
    // never split an emoji / surrogate pair in half
    if (keep > 0 && /[\uD800-\uDBFF]/.test(content[keep - 1])) keep -= 1
    if (keep <= 0) {
      omitted.push(att.name)
      continue
    }
    query += header + content.slice(0, keep) + TRUNCATION_NOTE
    truncated.push(att.name)
  }

  return { query, truncated, omitted }
}

// A saved question → the typed text and attachment chips (so reloaded history shows the
// question as it was asked, not the whole file body)
export function splitAttachedQuery(content = '') {
  const source = String(content || '')
  const matches = [...source.matchAll(ATTACHED_MARKER)]
  if (matches.length === 0) return { text: source, attachments: [] }
  return {
    text: source.slice(0, matches[0].index).trim(),
    attachments: matches.map((m) => ({ name: m[2] })),
  }
}
