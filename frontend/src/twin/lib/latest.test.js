import { describe, expect, it } from 'vitest'
import { latestRequest } from './latest'

describe('inventory responses', () => {
  it('keeps the newer snapshot when requests complete out of order', async () => {
    const request=latestRequest(), accepted=[]
    let resolveOld
    const old=request.run(() => new Promise((r) => { resolveOld=r }), (v) => accepted.push(v))
    await request.run(async () => ({ product:'B',quantity:7 }), (v) => accepted.push(v))
    resolveOld({ product:'A',quantity:9 })
    await old
    expect(accepted).toEqual([{ product:'B',quantity:7 }])
  })
  it('rejects a response after selection or component invalidation', async () => {
    const request=latestRequest(), accepted=[]
    let resolve
    const pending=request.run(() => new Promise((r) => { resolve=r }), (v) => accepted.push(v))
    request.invalidate()
    resolve('old product')
    await pending
    expect(accepted).toEqual([])
  })
})
