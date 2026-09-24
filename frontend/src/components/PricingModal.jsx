import React, { useState, useEffect } from 'react'
import {
  X,
  Crown,
  Check,
  CheckCircle2,
  ArrowRight,
  Shield,
  Zap,
  Building2,
  Sparkles,
  Info
} from 'lucide-react'
import './PricingModal.css'

export default function PricingModal({
  isOpen,
  onClose,
  initialPlan = 'professional',
  onSelectPlan
}) {
  const [selectedPlan, setSelectedPlan] = useState(initialPlan)
  const [activeNotification, setActiveNotification] = useState(null)

  // Close on Escape key
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape' && isOpen) {
        onClose()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isOpen, onClose])

  if (!isOpen) return null

  const handleChoosePlan = (planKey, planName, planPrice) => {
    setSelectedPlan(planKey)
    setActiveNotification(`${planName} (${planPrice}/month) selected! Your operational workspace is ready.`)
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

  // Feature Comparison Matrix rows
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
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="pricing-modal-title"
      >
        {/* MODAL HEADER */}
        <header className="pricing-modal-header">
          <div className="pricing-header-left">
            <div className="pricing-header-icon-wrap">
              <Crown size={22} />
            </div>
            <div>
              <div className="pricing-title-row">
                <h2 id="pricing-modal-title" className="pricing-modal-title">
                  IntelliWMS SaaS Pricing & Plans
                </h2>
                <span className="pricing-header-badge">COMMERCIAL PLANS</span>
              </div>
              <p className="pricing-modal-subtitle">
                Flexible tiers designed for small hubs, growing fulfillment centers, and enterprise logistics networks.
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="pricing-close-btn"
            title="Close modal (Esc)"
            aria-label="Close modal"
          >
            <X size={18} />
          </button>
        </header>

        {/* NOTIFICATION BANNER */}
        {activeNotification && (
          <div className="pricing-alert-banner">
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <CheckCircle2 size={16} color="#34d399" />
              <span>{activeNotification}</span>
            </div>
            <button
              onClick={() => setActiveNotification(null)}
              className="pricing-alert-dismiss"
            >
              Dismiss
            </button>
          </div>
        )}

        {/* MODAL SCROLLABLE CONTENT */}
        <div className="pricing-modal-body">
          {/* 1. TOP SECTION — 3 PRICING TIERS */}
          <section className="pricing-tiers-section">
            <div className="section-headline-group">
              <span className="section-label">
                <Sparkles size={14} /> Tiered Deployment Options
              </span>
              <h3 className="section-title">Select the Ideal Tier for Your Warehouse</h3>
              <p className="section-desc">
                Transparent monthly pricing with instant multi-agent orchestration setup.
              </p>
            </div>

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
                        <span className="price-frequency">{tier.period}</span>
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
                        handleChoosePlan(tier.key, tier.name, `$${tier.price}`)
                      }}
                    >
                      <span>{isSelected ? 'Current Selection' : 'Get Started'}</span>
                      <ArrowRight size={15} className="btn-arrow-icon" />
                    </button>
                  </div>
                )
              })}
            </div>
          </section>

          {/* 2. BOTTOM SECTION — FEATURE COMPARISON TABLE */}
          <section className="comparison-section">
            <div className="section-headline-group">
              <span className="section-label">
                <Building2 size={14} /> Detailed Breakdown
              </span>
              <h3 className="section-title">Feature Comparison Matrix</h3>
              <p className="section-desc">
                Side-by-side comparison across Starter, Professional, and Enterprise plans.
              </p>
            </div>

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

        {/* MODAL FOOTER */}
        <footer className="pricing-modal-footer">
          <div className="footer-info-text">
            <Info size={15} className="footer-info-icon" />
            <span>All tiers include autonomous agent triage, audit logging, and continuous deployment updates.</span>
          </div>
          <button
            onClick={onClose}
            className="pricing-btn-close"
          >
            Close
          </button>
        </footer>
      </div>
    </div>
  )
}
