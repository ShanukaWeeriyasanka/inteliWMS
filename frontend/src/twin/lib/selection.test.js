import { describe, it, expect } from 'vitest'
import { productHighlightRows } from './selection'

const bins = new Map([
  ['PRD-00001', [{bin_id:'WH1-F1-Z01-R01-S01-B01',quantity:5},
                 {bin_id:'WH1-F2-Z01-R01-S01-B01',quantity:8}]],
  ['PRD-00002', [{bin_id:'WH1-F1-Z01-R02-S01-B01',quantity:2},
                 {bin_id:'WH1-F1-Z01-R02-S01-B02',quantity:0}]],
])
describe('inventory result selection', () => {
  it('highlights every stocked box for multiple returned products', () => {
    expect(productHighlightRows({kind:'product',id:'PRD-00001',highlightProductIds:['PRD-00001','PRD-00002']},bins)).toHaveLength(3)
  })
  it('respects complete location boundaries and excludes zero stock', () => {
    const selection={kind:'product',id:'PRD-00001',highlightProductIds:['PRD-00001','PRD-00002'],locationScopes:['WH1-F1']}
    expect(productHighlightRows(selection,bins).map((r) => r.bin_id)).toEqual([
      'WH1-F1-Z01-R01-S01-B01','WH1-F1-Z01-R02-S01-B01'])
    expect(productHighlightRows({...selection,locationScopes:['WH1-F10']},bins)).toEqual([])
  })
  it('a fresh product selection clears previous report scopes and product IDs', () => {
    expect(productHighlightRows({kind:'product',id:'PRD-00001'},bins)).toHaveLength(2)
    expect(productHighlightRows({kind:'rack',id:'WH1-F1-Z01-R01'},bins)).toEqual([])
  })
})
