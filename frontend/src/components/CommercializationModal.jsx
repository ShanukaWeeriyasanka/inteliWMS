import React, { useState } from 'react'
import {
  X,
  Crown,
  Sparkles,
  Check,
  ShieldCheck,
  Truck,
  Zap,
  Building2,
  Lock,
  Package,
  PackageCheck,
  ArrowRight,
  ChevronDown,
  ChevronUp,
  CheckCircle2,
  Layers,
  Database,
  Cpu,
  Workflow
} from 'lucide-react'

export default function CommercializationModal({
  isOpen,
  onClose,
  isTrialActive,
  onStartTrial
}) {
  const [trialStarted, setTrialStarted] = useState(isTrialActive || false)
  const [selectedTier, setSelectedTier] = useState('enterprise')
  const [showComparison, setShowComparison] = useState(false)

  if (!isOpen) return null

  const handleStartTrial = () => {
    setTrialStarted(true)
    if (onStartTrial) {
      onStartTrial()
    }
  }

  const comparisonRows = [
    {
      category: 'Architecture & Multi-Tenancy',
      feature: 'Warehouse Partitioning',
      starter: 'Single Facility (SQLite/PG)',
      pro: 'Multi-Warehouse Keying (warehouse_id)',
      enterprise: 'Multi-Tenant Isolated VPC'
    },
    {
      category: 'Agent Orchestration',
      feature: 'Coordinator & Specialist Triage',
      starter: 'In-Process Regex Fast-Path (<1ms)',
      pro: 'Cross-Agent Delay Investigation',
      enterprise: 'Custom Agent Toolhooks & Workflows'
    },
    {
      category: 'Relational Schema',
      feature: 'Order Data Model',
      starter: 'Single SKU per Order string',
      pro: 'Partitioned Orders + Carrier Fields',
      enterprise: '1:N Relational order_items Schema'
    },
    {
      category: 'Dispatch & Carrier Tracking',
      feature: 'Delay Root-Cause Diagnostics',
      starter: 'Stock Out-of-Stock Inference only',
      pro: 'Live Carrier Webhooks & ETA Sync',
      enterprise: 'Predictive Transit SLA & Auto Door Dispatch'
    },
    {
      category: 'Knowledge & Vector RAG',
      feature: 'SOP Document Embeddings',
      starter: 'Shared ChromaDB Collection',
      pro: 'Zone & Category Filtered Vector Search',
      enterprise: 'Tenant-Isolated Private ChromaDB Collections'
    },
    {
      category: 'Security & Compliance',
      feature: 'Authentication & Audit Logs',
      starter: '13-Pattern Injection Defense',
      pro: 'Adaptive bcrypt + SOC Event Streaming',
      enterprise: 'Zero-Trust RBAC + Dedicated LLM Key Vault'
    },
    {
      category: 'Capacity & Support',
      feature: 'Monthly Operational Quota',
      starter: '5,000 queries / mo • Standard',
      pro: '25,000 queries / mo • 24/7 Priority',
      enterprise: 'Unlimited Queries • Dedicated SLA 99.9%'
    }
  ]

  return (
    <div className="commercial-modal-backdrop" onClick={onClose}>
      <div className="commercial-modal-box" onClick={(e) => e.stopPropagation()}>
        {/* 1. MODAL HEADER */}
        <div className="commercial-modal-header">
          <div className="commercial-header-left">
            <div className="commercial-header-icon-wrap">
              <Crown size={22} className="commercial-crown-icon" />
            </div>
            <div>
              <div className="commercial-title-row">
                <h2 className="commercial-modal-title">IntelliWMS Commercialization Plan</h2>
                <span className="commercial-header-pill">ENTERPRISE SAAS</span>
              </div>
              <p className="commercial-modal-subtitle">
                Scalable Multi-Agent Autonomous Warehouse Architecture & Tiered Deployment Plans
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="commercial-close-btn"
            title="Close modal"
          >
            <X size={18} />
          </button>
        </div>

        {/* 2. TRIAL NOTIFICATION BANNER */}
        {trialStarted && (
          <div className="commercial-trial-banner">
            <CheckCircle2 size={18} className="trial-check-icon" />
            <div className="trial-banner-text">
              <strong>Enterprise 14-Day Trial Active</strong>
              <span>Full multi-tenant keying, carrier webhooks, and private RAG simulation unlocked.</span>
            </div>
          </div>
        )}

        {/* 3. MODAL CONTENT GRID (TWO MAIN COLUMNS) */}
        <div className="commercial-modal-body">
          {/* LEFT COLUMN: PLATFORM TIERS */}
          <div className="commercial-column">
            <div className="column-header">
              <Building2 size={16} className="col-header-icon" />
              <h3>Platform Tiers</h3>
              <span className="column-count">3 Options</span>
            </div>

            <div className="tier-cards-list">
              {/* STARTER (CURRENT PLAN) */}
              <div
                className={`commercial-tier-card ${selectedTier === 'starter' ? 'tier-selected' : ''}`}
                onClick={() => setSelectedTier('starter')}
              >
                <div className="tier-card-header">
                  <div className="tier-name-group">
                    <span className="tier-name">Starter</span>
                    <span className="tier-badge-current">Current Plan</span>
                  </div>
                  <div className="tier-price">
                    <span className="price-amount">$499</span>
                    <span className="price-cycle">/ facility / mo</span>
                  </div>
                </div>
                <p className="tier-desc">Single facility operations & small 3PL logistics hubs.</p>
                <ul className="tier-features-list">
                  <li>
                    <Check size={14} className="feature-check" />
                    <span>Single warehouse deployment (SQLite / PostgreSQL)</span>
                  </li>
                  <li>
                    <Check size={14} className="feature-check" />
                    <span>Core multi-agent triage (Coordinator, Inventory, Fulfillment, Knowledge)</span>
                  </li>
                  <li>
                    <Check size={14} className="feature-check" />
                    <span>Basic SOP vector RAG retrieval with ChromaDB</span>
                  </li>
                  <li>
                    <Check size={14} className="feature-check" />
                    <span>Deterministic regex fast-path triage (&lt;1ms latency)</span>
                  </li>
                </ul>
              </div>

              {/* PROFESSIONAL [NEW] */}
              <div
                className={`commercial-tier-card ${selectedTier === 'pro' ? 'tier-selected' : ''}`}
                onClick={() => setSelectedTier('pro')}
              >
                <div className="tier-card-header">
                  <div className="tier-name-group">
                    <span className="tier-name">Professional</span>
                    <span className="tier-badge-new">NEW</span>
                  </div>
                  <div className="tier-price">
                    <span className="price-amount">$1,499</span>
                    <span className="price-cycle">/ facility / mo</span>
                  </div>
                </div>
                <p className="tier-desc">Growing distribution centers & high-velocity D2C fulfillment.</p>
                <ul className="tier-features-list">
                  <li>
                    <Check size={14} className="feature-check feature-check-pro" />
                    <span><strong>Multi-tenant & multi-warehouse keying</strong> (<code>warehouse_id</code> partitioning)</span>
                  </li>
                  <li>
                    <Check size={14} className="feature-check feature-check-pro" />
                    <span><strong>Live carrier integration</strong> with dispatch ETA monitoring</span>
                  </li>
                  <li>
                    <Check size={14} className="feature-check feature-check-pro" />
                    <span>Advanced SOC monitoring with security audit log streaming</span>
                  </li>
                  <li>
                    <Check size={14} className="feature-check feature-check-pro" />
                    <span>Autonomous cross-agent delay investigation & stock checks</span>
                  </li>
                </ul>
              </div>

              {/* ENTERPRISE [RECOMMENDED] */}
              <div
                className={`commercial-tier-card ${selectedTier === 'enterprise' ? 'tier-selected tier-featured' : ''}`}
                onClick={() => setSelectedTier('enterprise')}
              >
                <div className="tier-card-header">
                  <div className="tier-name-group">
                    <span className="tier-name">Enterprise</span>
                    <span className="tier-badge-enterprise">RECOMMENDED</span>
                  </div>
                  <div className="tier-price">
                    <span className="price-amount">$3,500+</span>
                    <span className="price-cycle">/ custom quote</span>
                  </div>
                </div>
                <p className="tier-desc">Large-scale supply networks & high-volume industrial warehouses.</p>
                <ul className="tier-features-list">
                  <li>
                    <Check size={14} className="feature-check feature-check-ent" />
                    <span><strong>Custom SOP private RAG</strong> with isolated tenant vector collections</span>
                  </li>
                  <li>
                    <Check size={14} className="feature-check feature-check-ent" />
                    <span><strong>1:N relational order line items</strong> (<code>order_items</code> database schema)</span>
                  </li>
                  <li>
                    <Check size={14} className="feature-check feature-check-ent" />
                    <span>Custom agent orchestration, toolhooks & on-premise VPC options</span>
                  </li>
                  <li>
                    <Check size={14} className="feature-check feature-check-ent" />
                    <span>99.9% SLA-backed uptime, dedicated LLM keys & priority routing</span>
                  </li>
                </ul>
              </div>
            </div>
          </div>

          {/* RIGHT COLUMN: UPGRADE EXPANSION PACKS */}
          <div className="commercial-column">
            <div className="column-header">
              <Zap size={16} className="col-header-icon" />
              <h3>Upgrade Expansion Packs</h3>
              <span className="column-count">Modular Add-ons</span>
            </div>

            <div className="pack-cards-list">
              {/* SECURITY & COMPLIANCE PACK */}
              <div className="commercial-pack-card">
                <div className="pack-card-top">
                  <div className="pack-icon-wrap icon-cyan">
                    <Lock size={18} />
                  </div>
                  <div>
                    <h4 className="pack-title">Security & Compliance Pack</h4>
                    <span className="pack-tag">Zero-Trust Architecture</span>
                  </div>
                </div>
                <p className="pack-desc">
                  Hardened security foundation tailored for enterprise audit standards and data governance.
                </p>
                <div className="pack-highlights">
                  <div className="highlight-item">
                    <ShieldCheck size={14} className="highlight-icon" />
                    <span>Adaptive password hashing with <strong>bcrypt / Argon2</strong></span>
                  </div>
                  <div className="highlight-item">
                    <ShieldCheck size={14} className="highlight-icon" />
                    <span>Complete conversation & audit trail logging in PostgreSQL (<code>conversation_logs</code>)</span>
                  </div>
                  <div className="highlight-item">
                    <ShieldCheck size={14} className="highlight-icon" />
                    <span>Elimination of development fallback JWT secrets with rotation</span>
                  </div>
                </div>
              </div>

              {/* CARRIER INTEGRATION PACK */}
              <div className="commercial-pack-card">
                <div className="pack-card-top">
                  <div className="pack-icon-wrap icon-blue">
                    <Truck size={18} />
                  </div>
                  <div>
                    <h4 className="pack-title">Carrier Integration Pack</h4>
                    <span className="pack-tag">Real-Time Dispatch Sync</span>
                  </div>
                </div>
                <p className="pack-desc">
                  Live webhook pipelines connecting warehouse fulfillment directly to international freight carriers.
                </p>
                <div className="pack-highlights">
                  <div className="highlight-item">
                    <Truck size={14} className="highlight-icon" />
                    <span>Live tracking webhooks for <strong>FedEx, DHL, UPS & FreightExpress</strong></span>
                  </div>
                  <div className="highlight-item">
                    <Truck size={14} className="highlight-icon" />
                    <span>Automated dispatch delay reason capture (<code>delay_reason</code> & <code>carrier_code</code>)</span>
                  </div>
                  <div className="highlight-item">
                    <Truck size={14} className="highlight-icon" />
                    <span>Predictive transit ETA calculation and courier door allocation</span>
                  </div>
                </div>
              </div>

              {/* COMMERCIAL TOOLS PACK */}
              <div className="commercial-pack-card">
                <div className="pack-card-top">
                  <div className="pack-icon-wrap icon-purple">
                    <Workflow size={18} />
                  </div>
                  <div>
                    <h4 className="pack-title">Commercial Tools Pack</h4>
                    <span className="pack-tag">Autonomous Supply Chain</span>
                  </div>
                </div>
                <p className="pack-desc">
                  Automated replenishment protocols directly bridging inventory depletion to vendor ordering.
                </p>
                <div className="pack-highlights">
                  <div className="highlight-item">
                    <Zap size={14} className="highlight-icon" />
                    <span>Direct automated vendor reorder integration via EDI and REST APIs</span>
                  </div>
                  <div className="highlight-item">
                    <Zap size={14} className="highlight-icon" />
                    <span>Reorder threshold triggers with supervisor approval workflows</span>
                  </div>
                  <div className="highlight-item">
                    <Zap size={14} className="highlight-icon" />
                    <span>Supplier lead-time tracking and automated purchase order generation</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* 4. OPTIONAL TOGGLE: FULL FEATURE COMPARISON TABLE */}
        <div className="commercial-comparison-toggle-section">
          <button
            onClick={() => setShowComparison(!showComparison)}
            className="btn-toggle-comparison"
          >
            <span>{showComparison ? 'Hide Feature Comparison' : 'View Full Feature Comparison Matrix'}</span>
            {showComparison ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
          </button>

          {showComparison && (
            <div className="comparison-table-wrapper">
              <table className="comparison-table">
                <thead>
                  <tr>
                    <th>Capability / Dimension</th>
                    <th>Starter ($499)</th>
                    <th>Professional ($1,499)</th>
                    <th>Enterprise ($3,500+)</th>
                  </tr>
                </thead>
                <tbody>
                  {comparisonRows.map((row, idx) => (
                    <tr key={idx}>
                      <td className="comp-feature-name">
                        <span className="comp-category">{row.category}</span>
                        <strong>{row.feature}</strong>
                      </td>
                      <td className="comp-starter">{row.starter}</td>
                      <td className="comp-pro">{row.pro}</td>
                      <td className="comp-ent">{row.enterprise}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* 5. MODAL FOOTER & ACTION BUTTONS */}
        <div className="commercial-modal-footer">
          <div className="footer-meta-info">
            <span className="spec-doc-label">Based on Specification:</span>
            <span className="spec-doc-name">SCHEMA_AND_COMMERCIALIZATION_PLAN.md (v1.0.0)</span>
          </div>

          <div className="footer-actions">
            <button
              onClick={onClose}
              className="btn-modal-secondary"
            >
              Close
            </button>
            <button
              onClick={handleStartTrial}
              className="btn-modal-trial"
              disabled={trialStarted}
            >
              <Sparkles size={16} className="btn-sparkle-icon" />
              <span>{trialStarted ? 'Enterprise Trial Active' : 'Start 14-Day Enterprise Trial →'}</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
