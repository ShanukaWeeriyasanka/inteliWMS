import React from 'react'

export default function Topbar({ currentUser, onLogout }) {
  const getAvatar = (role) => {
    switch (role) {
      case 'staff':
        return '👷'
      case 'manager':
        return '👩‍💼'
      case 'admin':
        return '⚙️'
      default:
        return '👤'
    }
  }

  return (
    <header className="topbar">
      <div className="topbar-brand">
        <img src="/intelliwms_logo.png" alt="InteliWMS Logo" className="brand-logo-glow" />
        <div>
          <h2 className="topbar-title">InteliWMS</h2>
          <p className="topbar-subtitle">Supply Chain Intelligence Portal</p>
        </div>
      </div>

      <div className="topbar-user">
        <div className={`user-chip chip-${currentUser.role}`}>
          <span className="chip-avatar">{getAvatar(currentUser.role)}</span>
          <div className="chip-info">
            <span className="chip-name">{currentUser.name || currentUser.username}</span>
            <span className="chip-role-tag">{currentUser.role.toUpperCase()}</span>
          </div>
        </div>
        <button className="signout-btn" onClick={onLogout} title="Sign Out">
          Sign Out
        </button>
      </div>
    </header>
  )
}
