/**
 * Real-time Speech Normalizer & Logistics Terminology Booster
 * Cleans speech-to-text transcriptions, formats SKUs/Order IDs,
 * corrects common acoustic speech misunderstandings, and prepares clean queries.
 */

// Common acoustic mishearings in warehouse speech -> canonical term
const PHONETIC_WAREHOUSE_MAP = {
  'cold ball': 'cold vault',
  'cold bowl': 'cold vault',
  'cold world': 'cold vault',
  'call vault': 'cold vault',
  'coal vault': 'cold vault',
  'fork lift': 'forklift',
  'four lift': 'forklift',
  'for lift': 'forklift',
  'froklift': 'forklift',
  'ware house': 'warehouse',
  'stock out': 'stockout',
  'stck': 'stock',
  'stoxk': 'stock',
  'safety socks': 'safety stock',
  'safety sock': 'safety stock',
  'quck': 'quick',
  'qiuck': 'quick',
  'qwick': 'quick',
  'invenory': 'inventory',
  'ivnentory': 'inventory',
  'fulfilment': 'fulfillment',
  'pal let': 'pallet',
  'pallete': 'pallet',
  'haz mat': 'hazmat',
  'bar code': 'barcode',
  'r f i d': 'RFID',
  's o p': 'SOP',
  'sops': 'SOPs',
  'r m a': 'RMA',
}

// Spoken number words to digits
const NUMBER_WORDS = {
  zero: '0',
  one: '1',
  two: '2',
  three: '3',
  four: '4',
  five: '5',
  six: '6',
  seven: '7',
  eight: '8',
  nine: '9',
  ten: '10'
}

/**
 * Normalizes speech text into standard logistics query format.
 * - Converts "sku one zero zero four" or "sku 1004" -> "SKU-1004"
 * - Converts "order four five two one" or "order 4521" -> "ORD-4521"
 * - Replaces common phonetic speech engine misrecognitions
 */
export function normalizeSpokenText(raw) {
  if (!raw || typeof raw !== 'string') return ''

  let text = raw.trim()

  // 1. Phonetic warehouse term replacements (case-insensitive)
  Object.entries(PHONETIC_WAREHOUSE_MAP).forEach(([misheard, correct]) => {
    const reg = new RegExp(`\\b${misheard}\\b`, 'gi')
    text = text.replace(reg, correct)
  })

  // 2. Normalize spoken number sequences for SKUs/Orders (e.g. "sku one zero zero four" -> "sku 1004")
  text = text.replace(/\b(sku|order|ord|prd|wh|building|bld)\s+((?:(?:zero|one|two|three|four|five|six|seven|eight|nine|\d+)\s*)+)/gi, (match, prefix, numbersStr) => {
    let digits = numbersStr
      .toLowerCase()
      .split(/\s+/)
      .map(w => NUMBER_WORDS[w] || w)
      .join('')
      .replace(/[^\d]/g, '')

    const pLower = prefix.toLowerCase()
    if (pLower === 'sku') return `SKU-${digits}`
    if (pLower === 'order' || pLower === 'ord') return `ORD-${digits}`
    if (pLower === 'prd') return `PRD-${digits.padStart(5, '0')}`
    if (pLower === 'building' || pLower === 'bld') return `Building ${digits}`
    if (pLower === 'wh') return `WH${digits}`
    return `${prefix} ${digits}`
  })

  // 3. Format standalone "sku 4521" or "sku-4521" -> "SKU-4521"
  text = text.replace(/\bsku[-\s]?(\d{3,6})\b/gi, 'SKU-$1')

  // 4. Format standalone "order 4521" or "ord 4521" -> "ORD-$1"
  text = text.replace(/\b(?:order|ord)[-\s]?#?(\d{3,6})\b/gi, 'ORD-$1')

  // 5. Bay normalization (e.g. "bay bee twelve" -> "bay B-12", "bay a four" -> "bay A-04")
  const EXTENDED_NUMBERS = {
    ...NUMBER_WORDS,
    eleven: '11',
    twelve: '12',
    thirteen: '13',
    fourteen: '14',
    fifteen: '15',
    sixteen: '16',
    seventeen: '17',
    eighteen: '18',
    nineteen: '19',
    twenty: '20'
  }
  const LETTER_SOUNDS = {
    bee: 'B', b: 'B',
    see: 'C', c: 'C',
    dee: 'D', d: 'D',
    ay: 'A', a: 'A',
    ee: 'E', e: 'E',
    eff: 'F', f: 'F'
  }
  text = text.replace(/\bbay\s+(bee|see|dee|ay|[a-f])\s*[-]?\s*([a-z\d]+)\b/gi, (match, letterPart, numPart) => {
    const l = LETTER_SOUNDS[letterPart.toLowerCase()] || letterPart.toUpperCase()
    const n = EXTENDED_NUMBERS[numPart.toLowerCase()] || numPart
    const numInt = parseInt(n, 10)
    if (!isNaN(numInt)) {
      return `bay ${l}-${numInt < 10 ? '0' + numInt : numInt}`
    }
    return match
  })

  // 5. Clean extra spaces
  text = text.replace(/\s+/g, ' ').trim()

  // 6. Ensure initial capital
  if (text.length > 0) {
    text = text.charAt(0).toUpperCase() + text.slice(1)
  }

  return text
}
