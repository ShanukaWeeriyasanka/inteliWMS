import React, { useEffect, useRef } from 'react'

/**
 * Toast notification component.
 * Props:
 *   toasts  – array of { id, type, title, message }
 *   remove  – fn(id) to remove a toast
 */
export default function ToastContainer({ toasts, remove }) {
  return (
    <div className="toast-container" aria-live="assertive">
      {toasts.map((t) => (
        <Toast key={t.id} toast={t} onRemove={remove} />
      ))}
    </div>
  )
}

function Toast({ toast, onRemove }) {
  const timerRef = useRef(null)

  useEffect(() => {
    timerRef.current = setTimeout(() => onRemove(toast.id), 6000)
    return () => clearTimeout(timerRef.current)
  }, [toast.id, onRemove])

  const icons = {
    error:   '🔴',
    warning: '🟡',
    success: '🟢',
    info:    '🔵',
  }

  return (
    <div className={`toast toast-${toast.type || 'error'}`} role="alert">
      <span className="toast-icon">{icons[toast.type] || '🔴'}</span>
      <div className="toast-body">
        {toast.title && <p className="toast-title">{toast.title}</p>}
        <p className="toast-message">{toast.message}</p>
      </div>
      <button className="toast-close" onClick={() => onRemove(toast.id)} aria-label="Dismiss">✕</button>
    </div>
  )
}
