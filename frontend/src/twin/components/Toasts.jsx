import React from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { X } from 'lucide-react'

export default function Toasts({ toasts, onDismiss }) {
  return (
    <div className="twin-toasts" aria-live="polite">
      <AnimatePresence>
        {toasts.map((t) => (
          <motion.div key={t.id} className={`twin-toast is-${t.tone || 'info'}`} role={t.tone === 'error' ? 'alert' : 'status'}
            initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 12 }}>
            <span>{t.text}</span>
            {t.action && <button className="twin-link" onClick={() => { t.action.run(); onDismiss(t.id) }}>{t.action.label}</button>}
            <button className="twin-icon-btn" onClick={() => onDismiss(t.id)} aria-label="Dismiss"><X size={13} /></button>
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  )
}
