import React, { useState, useEffect } from 'react'
import {
  Warehouse,
  Boxes,
  Truck,
  ScanBarcode,
  Bot,
  ShieldCheck,
  Cpu,
  Sparkles,
  Layers,
  Activity
} from 'lucide-react'

export default function WarehouseThinkingAnimation({ queryText }) {
  const [currentStep, setCurrentStep] = useState(0)

  // Determine which domain the query likely targets for contextual animation
  const qLower = (queryText || '').toLowerCase()
  const isOrder = qLower.includes('order') || qLower.includes('#') || qLower.includes('track') || qLower.includes('carrier')
  const isInjection = qLower.includes('ignore') || qLower.includes('drop') || qLower.includes('prompt') || qLower.includes('leak')
  const isSop = qLower.includes('sop') || qLower.includes('hazard') || qLower.includes('damage') || qLower.includes('spill')

  const steps = isInjection
    ? [
        { label: 'Inspecting Cryptographic JWT claims...', icon: ShieldCheck, color: 'text-emerald' },
        { label: 'Scanning syntax with security/sanitizer.py...', icon: ShieldCheck, color: 'text-coral' },
        { label: 'Harmful query shield evaluating payload...', icon: Activity, color: 'text-coral' }
      ]
    : isOrder
    ? [
        { label: 'Parsing consignment & tracking ID...', icon: ScanBarcode, color: 'text-amber' },
        { label: 'Connecting to Fulfillment Agent via MCP...', icon: Bot, color: 'text-blue' },
        { label: 'Querying Freight carrier & dispatch telemetry...', icon: Truck, color: 'text-emerald' }
      ]
    : isSop
    ? [
        { label: 'Evaluating operational safety domain...', icon: ShieldCheck, color: 'text-amber' },
        { label: 'Routing to Knowledge Specialist Agent...', icon: Bot, color: 'text-blue' },
        { label: 'Retrieving Standard Operating Procedures...', icon: Warehouse, color: 'text-emerald' }
      ]
    : [
        { label: 'Sanitizing input & verifying HS256 claims...', icon: ShieldCheck, color: 'text-emerald' },
        { label: 'Classifying intent & extracting SKU coordinates...', icon: ScanBarcode, color: 'text-amber' },
        { label: 'Automated AGV locating High-Bay Storage...', icon: Warehouse, color: 'text-blue' },
        { label: 'Delegating to Inventory Agent via MCP...', icon: Boxes, color: 'text-emerald' }
      ]

  useEffect(() => {
    const interval = setInterval(() => {
      setCurrentStep((prev) => (prev < steps.length - 1 ? prev + 1 : prev))
    }, 450)
    return () => clearInterval(interval)
  }, [steps.length])

  const StepIcon = steps[currentStep]?.icon || Warehouse

  return (
    <div className="warehouse-thinking-card">
      {/* Top Header Row with High-Tech AGV Scanner */}
      <div className="thinking-card-header">
        <div className="thinking-brand-left">
          <div className="thinking-pulse-emblem">
            <img src="/intelliwms_logo.png" alt="IntelliWMS" className="thinking-logo-img" />
          </div>
          <div>
            <div className="thinking-title-line">
              <span className="thinking-title">Autonomous Coordination in Progress</span>
              <span className="thinking-badge-live">LIVE MCP</span>
            </div>
            <span className="thinking-subtitle">
              IntelliWMS Multi-Agent routing engine active
            </span>
          </div>
        </div>

        <div className="thinking-telemetry-pill">
          <Activity size={12} className="text-amber pulse" />
          <span>AGV_SCANNER_v2.4</span>
        </div>
      </div>

      {/* Holographic Warehouse Floor Scanner Visualizer */}
      <div className="hologram-scanner-viewport">
        {/* Animated Laser Beam */}
        <div className="laser-scan-line" />

        {/* Mini Warehouse Bay Shelves */}
        <div className="scanner-aisle-racks">
          <div className="scan-bay-cell" data-bay="A12-01">
            <div className="bay-stock-indicator filled" />
            <span>01</span>
          </div>
          <div className="scan-bay-cell" data-bay="A12-02">
            <div className="bay-stock-indicator filled" />
            <span>02</span>
          </div>
          <div className="scan-bay-cell active-target" data-bay="A12-03">
            <div className="bay-stock-indicator target-glow" />
            <div className="agv-beacon-dot" />
            <span>B3</span>
          </div>
          <div className="scan-bay-cell" data-bay="A12-04">
            <div className="bay-stock-indicator filled" />
            <span>04</span>
          </div>
          <div className="scan-bay-cell" data-bay="A12-05">
            <div className="bay-stock-indicator" />
            <span>05</span>
          </div>
          <div className="scan-bay-cell" data-bay="A12-06">
            <div className="bay-stock-indicator filled" />
            <span>06</span>
          </div>
        </div>

        {/* Runway Track with AGV Robot Shuttle */}
        <div className="agv-transit-track">
          <div className="agv-shuttle-robot">
            <div className="agv-sensor-light" />
            <span className="agv-tag">AGV-08</span>
          </div>
          <div className="track-rail-line" />
        </div>
      </div>

      {/* Dynamic Agent Coordination Progress Steps */}
      <div className="thinking-step-indicator">
        <div className="step-icon-wrap">
          <StepIcon size={14} className={steps[currentStep]?.color || 'text-amber'} />
        </div>
        <div className="step-text-wrap">
          <span className="step-label">{steps[currentStep]?.label}</span>
          <div className="step-progress-mini">
            {steps.map((_, idx) => (
              <div
                key={idx}
                className={`step-tick ${idx <= currentStep ? 'active' : ''}`}
              />
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
