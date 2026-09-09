import React, { useState } from 'react'

export default function TokenInspectorDrawer({ token, currentUser }) {
  const [showTokenDetails, setShowTokenDetails] = useState(false)

  return (
    <div className="token-inspector-drawer">
      <button
        className="drawer-button"
        onClick={() => setShowTokenDetails(!showTokenDetails)}
      >
        {showTokenDetails
          ? '▼ Hide Cryptographic Security Claims'
          : '▶ Inspect Active Cryptographic JWT Claims & RBAC Matrix'}
      </button>

      {showTokenDetails && (
        <div className="drawer-panel">
          <div className="drawer-grid">
            <div>
              <h4 className="drawer-title">Active Bearer JWT Token:</h4>
              <textarea readOnly value={token} rows={3} />
            </div>
            <div>
              <h4 className="drawer-title">Decoded Claims & Identity:</h4>
              <pre>{JSON.stringify(currentUser, null, 2)}</pre>
            </div>
          </div>
          <div style={{ marginTop: '12px' }}>
            <h4 className="drawer-title">Granted Permissions Matrix:</h4>
            <div className="perm-chip-list">
              {currentUser.permissions?.map((p) => (
                <span key={p} className="perm-tag">
                  ✓ {p}
                </span>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
