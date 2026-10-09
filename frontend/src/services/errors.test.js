import { describe, expect, it } from 'vitest'
import { apiErrorCode, apiErrorMessage } from './errors'

const axiosError = (status, data) => Object.assign(new Error(`Request failed with status code ${status}`), {
  response: { status, data },
})

describe('apiErrorMessage', () => {
  it('reads the error envelope message', () => {
    const err = axiosError(401, { status: 'error', error_code: 'UNAUTHORIZED', message: "not authorized for role 'admin'", audit: {} })
    expect(apiErrorMessage(err)).toBe("not authorized for role 'admin'")
    expect(apiErrorCode(err)).toBe('UNAUTHORIZED')
  })

  it('falls back to detail, then the axios message, then the fallback', () => {
    expect(apiErrorMessage(axiosError(400, { detail: "Unknown role 'x'" }))).toBe("Unknown role 'x'")
    expect(apiErrorMessage(axiosError(422, { detail: [{ msg: 'field required' }] }))).toBe('field required')
    expect(apiErrorMessage(axiosError(500, '<html>'))).toBe('Request failed with status code 500')
    expect(apiErrorMessage(null, 'Login failed')).toBe('Login failed')
  })
})
