import React, { useState, useEffect, useRef } from 'react'
import {
  X,
  Check,
  ArrowRight,
} from 'lucide-react'
import './PricingModal.css'

export default function PricingModal({
  isOpen,
  onClose,
  initialPlan = 'professional',
  onSelectPlan
}) {
  const [selectedPlan, setSelectedPlan] = useState(initialPlan)
  const [hasChosenPlan, setHasChosenPlan] = useState(false)
  const dialogRef = useRef(null)

  // Close on Escape key
  useEffect(() => {
    if (!isOpen) return undefined
    const previousFocus = document.activeElement
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    dialogRef.current?.querySelector('button')?.focus({ preventScroll: true })
    const handleKeyDown = (e) => {
      if (e.key === 'Escape' && isOpen) {
        onClose()
      }
      if (e.key === 'Tab') {
        const controls = [...dialogRef.current.querySelectorAll('button, summary')]
          .filter((el) => el.getClientRects().length && !el.disabled)
        const first = controls[0]
        const last = controls.at(-1)
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault()
          last?.focus()
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault()
          first?.focus()
        }
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => {
      window.removeEventListener('keydown', handleKeyDown)
      document.body.style.overflow = previousOverflow
      previousFocus?.focus?.({ preventScroll: true })
    }
  }, [isOpen, onClose])

  if (!isOpen) return null

  const handleChoosePlan = (planKey) => {
    setSelectedPlan(planKey)
    setHasChosenPlan(true)
    if (onSelectPlan) {
      onSelectPlan(planKey)
    }
  }

  // 3 Pricing Tiers configuration
  const tiers = [
    {
      key: 'starter',
      name: 'Starter Plan',
      price: '50',
      priceFormatted: '$50/mo',
      period: '/ month',
      description: 'For Small Teams & Growing Operations',
      badge: null,
      bullets: [
        '100 GB storage processing limits',
        'Basic warehouse inventory & SKU tracking',
        'Core multi-agent query routing',
        'Limited AI tools & analytics',
        'Standard email & community support'
      ],
      ctaClass: 'card-cta-starter',
      checkClass: 'bullet-check-starter',
      cardClass: ''
    },
    {
      key: 'professional',
      name: 'Professional Plan',
      price: '80',
      priceFormatted: '$80/mo',
      period: '/ month',
      description: 'For Growing Centers & High-Velocity Fulfillment',
      badge: 'MOST POPULAR',
      bullets: [
        '600 GB high-throughput storage limits',
        'Multi-tenant warehouse keying',
        'Full advanced AI tools & analytics',
        'Real-time carrier webhook & dispatch ETA',
        '24/7 priority support & fast escalation'
      ],
      ctaClass: 'card-cta-pro',
      checkClass: 'bullet-check-pro',
      cardClass: 'featured-card'
    },
    {
      key: 'enterprise',
      name: 'Enterprise Plan',
      price: '180',
      priceFormatted: '$180/mo',
      period: '/ month',
      description: 'For Large Supply Networks & Industrial Warehouses',
      badge: 'ENTERPRISE',
      bullets: [
        '1 TB dedicated high-velocity storage',
        'Custom agent orchestration & SLAs',
        'Multi-tenant warehouse keying',
        'Dedicated 99.9% uptime SLA backing',
        'Tenant-isolated private vector RAG & key vault'
      ],
      ctaClass: 'card-cta-ent',
      checkClass: 'bullet-check-ent',
      cardClass: 'enterprise-card'
    }
  ]

  // A plan for every operation. rows
  const comparisonRows = [
    {
      featureName: 'Price',
      featureNote: 'Billed monthly per facility',
      starter: { type: 'text', val: '$50/mo', highlight: true },
      pro: { type: 'text', val: '$80/mo', highlight: true },
      enterprise: { type: 'text', val: '$180/mo', highlight: true }
    },
    {
      featureName: 'Basic features',
      featureNote: 'Inventory lookup, order tracking & coordinator triage',
      starter: { type: 'check', text: '✔️ Included' },
      pro: { type: 'check', text: '✔️ Included' },
      enterprise: { type: 'check', text: '✔️ Included' }
    },
    {
      featureName: 'Storage processing limits',
      featureNote: 'Operational SKU ledger & event stream volume',
      starter: { type: 'storage', val: '100 GB' },
      pro: { type: 'storage', val: '600 GB', highlight: true },
      enterprise: { type: 'storage', val: '1 TB', highlight: true }
    },
    {
      featureName: 'Advanced AI tools & analytics',
      featureNote: 'Predictive bottleneck detection & neural insights',
      starter: { type: 'ai', val: 'Limited' },
      pro: { type: 'ai', val: 'Full' },
      enterprise: { type: 'ai', val: 'Full' }
    },
    {
      featureName: 'Multi-tenant warehouse keying',
      featureNote: 'Partitioned warehouse_id isolation for multi-site hubs',
      starter: { type: 'cross', text: '❌' },
      pro: { type: 'check', text: '✔️' },
      enterprise: { type: 'check', text: '✔️' }
    },
    {
      featureName: 'Custom agent orchestration & SLAs',
      featureNote: 'Custom specialist hooks and 99.9% uptime SLA guarantees',
      starter: { type: 'cross', text: '❌' },
      pro: { type: 'cross', text: '❌' },
      enterprise: { type: 'check', text: '✔️' }
    }
  ]

  const renderCellValue = (cell) => {
    if (!cell) return null

    if (cell.type === 'check') {
      return (
        <span className="val-pill-check">
          <Check size={14} />
          <span>{cell.text}</span>
        </span>
      )
    }

    if (cell.type === 'cross') {
      return (
        <span className="val-pill-cross">
          <X size={14} />
          <span>{cell.text}</span>
        </span>
      )
    }

    if (cell.type === 'ai') {
      const isFull = cell.val.toLowerCase() === 'full'
      return (
        <span className={isFull ? 'val-ai-full' : 'val-ai-limited'}>
          {cell.val}
        </span>
      )
    }

    if (cell.type === 'storage') {
      return (
        <span className={`val-storage ${cell.highlight ? 'highlight-storage' : ''}`}>
          {cell.val}
        </span>
      )
    }

    return (
      <span className="val-price">
        {cell.val}
      </span>
    )
  }

  return (
    <div className="pricing-modal-backdrop" onClick={onClose}>
      <div
        className="pricing-modal-container"
        ref={dialogRef}
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label="Subscription plans"
      >
        <button type="button" className="pricing-close-btn" onClick={onClose} aria-label="Close pricing"><X size={18} /></button>

        {/* MODAL SCROLLABLE CONTENT */}
        <div className="pricing-modal-body">
          {/* 1. TOP SECTION — 3 PRICING TIERS */}
          <section className="pricing-tiers-section" id="pricing-plans">
            <h2 className="pricing-display-title">Pricing</h2>
            <div className="pricing-tiers-grid">
              {tiers.map((tier) => {
                const isSelected = selectedPlan === tier.key
                return (
                  <div
                    key={tier.key}
                    className={`pricing-card ${tier.cardClass} ${isSelected ? 'selected-card' : ''}`}
                    onClick={() => setSelectedPlan(tier.key)}
                  >
                    {tier.badge && (
                      <div className="card-badge-top">
                        <span className={`plan-pill ${tier.key === 'professional' ? 'pro' : 'ent'}`}>
                          {tier.badge}
                        </span>
                      </div>
                    )}

                    <div className="card-top-content">
                      <div className="card-header-row">
                        <h4 className="card-plan-title">{tier.name}</h4>
                      </div>

                      <p className="card-plan-desc">{tier.description}</p>

                      <div className="card-price-block">
                        <span className="price-currency">$</span>
                        <span className="price-value">{tier.price}</span>
                        <span className="price-frequency">/m</span>
                      </div>

                      <ul className="card-bullet-list">
                        {tier.bullets.map((bullet, idx) => (
                          <li key={idx}>
                            <Check size={15} className={`bullet-check-icon ${tier.checkClass}`} />
                            <span>{bullet}</span>
                          </li>
                        ))}
                      </ul>
                    </div>

                    <button
                      type="button"
                      className={`card-cta-btn ${tier.ctaClass}`}
                      onClick={(e) => {
                        e.stopPropagation()
                        handleChoosePlan(tier.key)
                      }}
                    >
                      <span>{hasChosenPlan && isSelected ? 'Selected' : 'Get Started'}</span>
                      <ArrowRight size={15} className="btn-arrow-icon" />
                    </button>
                  </div>
                )
              })}
            </div>
          </section>

          {/* 2. BOTTOM SECTION — FEATURE COMPARISON TABLE */}
          <section className="comparison-section" id="pricing-comparison">
            <div className="comparison-table-card">
              <table className="feature-matrix-table">
                <thead>
                  <tr>
                    <th className="col-feature">Feature / Dimension</th>
                    <th className="col-tier">
                      <span>Starter</span>
                    </th>
                    <th className="col-tier">
                      <span>Professional</span>
                      <span className="tier-th-badge badge-pro">PRO</span>
                    </th>
                    <th className="col-tier">
                      <span>Enterprise</span>
                      <span className="tier-th-badge badge-ent">ENT</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {comparisonRows.map((row, index) => (
                    <tr key={index}>
                      <td>
                        <div className="feature-cell-title">
                          <strong>{row.featureName}</strong>
                          {row.featureNote && <span>{row.featureNote}</span>}
                        </div>
                      </td>
                      <td className="matrix-val-cell">
                        {renderCellValue(row.starter)}
                      </td>
                      <td className="matrix-val-cell">
                        {renderCellValue(row.pro)}
                      </td>
                      <td className="matrix-val-cell">
                        {renderCellValue(row.enterprise)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </div>

      </div>
    </div>
  )
}
