import React, { useState } from 'react'

export default function ManagerDashboard({ currentUser, onExecuteAction, onSendQuery, actionLoading, queryLoading }) {
  const [queryText, setQueryText] = useState('')
  const [queryResponse, setQueryResponse] = useState(null)
  const [actionFeedback, setActionFeedback] = useState(null)

  const handleQuery = async () => {
    if (!queryText.trim()) return
    setQueryResponse(null)
    const res = await onSendQuery(queryText)
    if (!res.error) {
      setQueryResponse(res.data)
    }
  }

  const handleAction = async (actionName) => {
    setActionFeedback(null)
    const res = await onExecuteAction(actionName)
    setActionFeedback(res)
  }

  return (
    <div className="role-layout">
      {/* Role Banner */}
      <div className="role-banner manager-accent">
        <div className="role-banner-header">
          <span className="role-badge badge-mgr">SHIFT SUPERVISOR</span>
          <h3>Warehouse Operations & Approvals Hub</h3>
        </div>
        <p>
          Supervisor Portal: You have elevated privileges to authorize inventory restocking orders and inspect supply chain telemetry.
        </p>
      </div>

      <div className="content-grid">
        {/* Approvals Card */}
        <div className="editorial-card">
          <h3 className="card-headline">Pending Inventory Approvals</h3>
          <p className="card-desc">
            Requires Manager Authorization (RBAC Action: <code>approve_restock</code>).
          </p>

          <div className="approval-tile">
            <div className="tile-text">
              <strong>SKU-4521 — Heavy Duty Forklift Battery (Lithium)</strong>
              <span>Requested: +250 units • Supplier: Apex Power • Urgency: High</span>
            </div>
            <button
              className="btn-approve-action"
              onClick={() => handleAction('approve_restock')}
              disabled={actionLoading}
            >
              Authorize Restock
            </button>
          </div>

          <div className="approval-tile">
            <div className="tile-text">
              <strong>SKU-1088 — Thermal Industrial Label Rolls</strong>
              <span>Requested: +80 rolls • Supplier: Global Print • Urgency: Normal</span>
            </div>
            <button
              className="btn-approve-action"
              onClick={() => handleAction('approve_restock')}
              disabled={actionLoading}
            >
              Authorize Restock
            </button>
          </div>

          {actionFeedback && (
            <div className={`action-result-banner ${actionFeedback.status === 'allowed' ? 'res-allowed' : 'res-denied'}`}>
              <strong>{actionFeedback.status === 'allowed' ? '✅ AUTHORIZED' : '⛔ DENIED'}:</strong>
              <p>{actionFeedback.message}</p>
            </div>
          )}
        </div>

        {/* Warehouse Analytics Card */}
        <div className="editorial-card">
          <h3 className="card-headline">Shift Telemetry & Performance</h3>
          <p className="card-desc">
            Real-time metrics authorized under <code>view_analytics</code>.
          </p>

          <div className="metrics-grid">
            <div className="metric-cell">
              <span className="metric-number">99.2%</span>
              <span className="metric-caption">On-Time Fulfillment</span>
            </div>
            <div className="metric-cell">
              <span className="metric-number">16m</span>
              <span className="metric-caption">Avg Pick Duration</span>
            </div>
            <div className="metric-cell">
              <span className="metric-number">18</span>
              <span className="metric-caption">Active Pickers</span>
            </div>
          </div>

          <div style={{ marginTop: '16px' }}>
            <button
              className="rbac-btn allowed-btn"
              style={{ width: '100%' }}
              onClick={() => handleAction('view_vendor_performance')}
            >
              ✓ Review Vendor Reliability Matrix
            </button>
          </div>
        </div>
      </div>

      {/* Warehouse Query Assistant */}
      <div className="editorial-card" style={{ marginTop: '20px' }}>
        <h3 className="card-headline">Shift Coordination Assistant</h3>
        <div className="query-row">
          <input
            type="text"
            value={queryText}
            onChange={(e) => setQueryText(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleQuery()}
            placeholder="Ask shift coordination, stock thresholds, or supplier questions..."
          />
          <button className="btn-send" onClick={handleQuery} disabled={queryLoading}>
            {queryLoading ? 'Processing...' : 'Send'}
          </button>
        </div>
        {queryResponse && (
          <div className="alert-message success-alert">
            <pre>{JSON.stringify(queryResponse.routing || queryResponse, null, 2)}</pre>
          </div>
        )}
      </div>
    </div>
  )
}
