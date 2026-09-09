import React, { useState } from 'react'

export default function StaffDashboard({ currentUser, onExecuteAction, onSendQuery, actionLoading, queryLoading }) {
  const [queryText, setQueryText] = useState('')
  const [queryResponse, setQueryResponse] = useState(null)
  const [queryError, setQueryError] = useState('')
  const [actionFeedback, setActionFeedback] = useState(null)

  const handleQuery = async (preset) => {
    const textToSend = preset !== undefined ? preset : queryText
    if (!textToSend.trim()) return

    setQueryError('')
    setQueryResponse(null)
    const res = await onSendQuery(textToSend)
    if (res.error) {
      setQueryError(res.error)
    } else {
      if (res.data?.status === 'blocked') {
        setQueryError(res.data.message)
      }
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
      <div className="role-banner staff-accent">
        <div className="role-banner-header">
          <span className="role-badge">STAFF OPERATIONS</span>
          <h3>Warehouse Floor & Picking Station</h3>
        </div>
        <p>
          Welcome, {currentUser.name || currentUser.username}. You are authorized for SKU location lookups, order tracking, and shift damage reporting.
        </p>
      </div>

      <div className="content-grid">
        {/* Floor Query Assistant */}
        <div className="editorial-card">
          <h3 className="card-headline">Warehouse Location & SKU Query</h3>
          <p className="card-desc">Messages are cryptographically validated, sanitized against injection, and routed.</p>

          <div className="preset-pill-row">
            <span>Quick Actions:</span>
            <button onClick={() => { setQueryText('Where is SKU-4521 located?'); handleQuery('Where is SKU-4521 located?') }}>
              📍 Where is SKU-4521?
            </button>
            <button onClick={() => { setQueryText("What's the status of order #4521?"); handleQuery("What's the status of order #4521?") }}>
              📦 Track Order #4521
            </button>
            <button onClick={() => { setQueryText('Report item damaged in aisle 3'); handleQuery('Report item damaged in aisle 3') }}>
              ⚠️ Report Damage
            </button>
          </div>

          <div className="query-row">
            <input
              type="text"
              value={queryText}
              onChange={(e) => setQueryText(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleQuery()}
              placeholder="Ask warehouse assistant (e.g. Where is SKU-4521?)..."
              disabled={queryLoading}
            />
            <button className="btn-send" onClick={() => handleQuery()} disabled={queryLoading}>
              {queryLoading ? 'Routing...' : 'Send'}
            </button>
          </div>

          {queryError && (
            <div className="alert-message error-alert">
              <strong>Security Shield Block:</strong> {queryError}
            </div>
          )}

          {queryResponse && (
            <div className="alert-message success-alert">
              <strong>Coordinator Response:</strong>
              <pre>{JSON.stringify(queryResponse.routing || queryResponse, null, 2)}</pre>
            </div>
          )}
        </div>

        {/* RBAC Simulation Card for Staff */}
        <div className="editorial-card">
          <h3 className="card-headline">Permission Enforcement (RBAC)</h3>
          <p className="card-desc">Demonstrates zero-trust access control: attempting manager/admin actions is strictly blocked.</p>

          <div className="action-stack">
            <button
              className="rbac-btn allowed-btn"
              onClick={() => handleAction('query_location')}
              disabled={actionLoading}
            >
              ✓ Query Location (Staff Allowed)
            </button>
            <button
              className="rbac-btn allowed-btn"
              onClick={() => handleAction('track_order')}
              disabled={actionLoading}
            >
              ✓ Track Order (Staff Allowed)
            </button>
            <button
              className="rbac-btn restricted-btn"
              onClick={() => handleAction('approve_restock')}
              disabled={actionLoading}
            >
              🔒 Approve Restock (Restricted to Manager)
            </button>
            <button
              className="rbac-btn restricted-btn"
              onClick={() => handleAction('view_analytics')}
              disabled={actionLoading}
            >
              🔒 View Analytics (Restricted to Manager)
            </button>
          </div>

          {actionFeedback && (
            <div className={`action-result-banner ${actionFeedback.status === 'allowed' ? 'res-allowed' : 'res-denied'}`}>
              <strong>{actionFeedback.status === 'allowed' ? '✅ AUTHORIZED' : '⛔ ACCESS DENIED (RBAC)'}:</strong>
              <p>{actionFeedback.message}</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
