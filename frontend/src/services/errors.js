// Human-readable text for a failed API call. The backend answers errors with
// {status: "error", error_code, message, audit}; `detail` is the older FastAPI shape.
export function apiErrorMessage(err, fallback = 'Something went wrong. Please try again.') {
  const data = err?.response?.data
  if (data && typeof data === 'object') {
    if (typeof data.message === 'string' && data.message.trim()) return data.message
    if (typeof data.detail === 'string' && data.detail.trim()) return data.detail
    if (Array.isArray(data.detail)) {
      const parts = data.detail.map((d) => d?.msg).filter(Boolean)
      if (parts.length) return parts.join('; ')
    }
  }
  return err?.message || fallback
}

export const apiErrorCode = (err) => err?.response?.data?.error_code || null
