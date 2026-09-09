import React, { useState } from 'react'

export default function LoginPage({ onLogin, onRegister, authLoading, authError, setAuthError }) {
  const [isRegisterMode, setIsRegisterMode] = useState(false)
  const [username, setUsername] = useState('john_staff')
  const [password, setPassword] = useState('pass123')
  const [role, setRole] = useState('staff')
  const [fullName, setFullName] = useState('')

  const handleQuickLogin = (u, p, r) => {
    setUsername(u)
    setPassword(p)
    setRole(r)
    onLogin(u, p, r)
  }

  const handleSubmit = (e) => {
    e.preventDefault()
    if (isRegisterMode) {
      onRegister(username, password, role, fullName)
    } else {
      onLogin(username, password, role)
    }
  }

  return (
    <div className="login-screen-wrapper side-by-side-mode">
      <div className="login-split-container">
        {/* LEFT SIDE: AUTHENTICATION CONTENT */}
        <div className="auth-left-column">
          <div className="login-header-text">
            <h1 className="editorial-heading">Coordinate what’s next</h1>
            <p className="editorial-subtitle">Your intelligent agentic partner for warehouse & supply chain operations</p>
          </div>

          <div className="claude-auth-box">
            {/* Quick 1-Click Demo Profiles */}
            <div className="quick-access-section">
              <span className="section-label">Quick 1-Click Demo Profiles</span>
              <div className="quick-oauth-row">
                <button
                  type="button"
                  className="oauth-btn"
                  onClick={() => handleQuickLogin('john_staff', 'pass123', 'staff')}
                  title="Login as Warehouse Staff"
                >
                  <span className="oauth-icon">👷</span>
                  <span className="oauth-text">Staff (John)</span>
                </button>

                <button
                  type="button"
                  className="oauth-btn"
                  onClick={() => handleQuickLogin('sarah_manager', 'pass456', 'manager')}
                  title="Login as Shift Supervisor"
                >
                  <span className="oauth-icon">👩‍💼</span>
                  <span className="oauth-text">Manager (Sarah)</span>
                </button>

                <button
                  type="button"
                  className="oauth-btn"
                  onClick={() => handleQuickLogin('admin_user', 'admin123', 'admin')}
                  title="Login as System Admin"
                >
                  <span className="oauth-icon">⚙️</span>
                  <span className="oauth-text">Admin (Alex)</span>
                </button>
              </div>
            </div>

            {/* OR Divider */}
            <div className="or-separator">
              <span className="or-line"></span>
              <span className="or-label">OR WITH CREDENTIALS</span>
              <span className="or-line"></span>
            </div>

            {/* Mode Switch Tabs */}
            <div className="auth-tab-row">
              <button
                type="button"
                className={`tab-link ${!isRegisterMode ? 'active' : ''}`}
                onClick={() => { setIsRegisterMode(false); setAuthError('') }}
              >
                Sign In
              </button>
              <button
                type="button"
                className={`tab-link ${isRegisterMode ? 'active' : ''}`}
                onClick={() => { setIsRegisterMode(true); setAuthError('') }}
              >
                Register Account
              </button>
            </div>

            {/* Form */}
            <form onSubmit={handleSubmit} className="credential-form">
              {isRegisterMode && (
                <div className="input-group">
                  <label className="field-label" htmlFor="fullName">Full Name</label>
                  <input
                    id="fullName"
                    type="text"
                    placeholder="e.g. Alex Morgan"
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    required
                  />
                </div>
              )}

              <div className="input-group">
                <label className="field-label" htmlFor="username">Username or Warehouse ID</label>
                <input
                  id="username"
                  type="text"
                  placeholder="e.g. john_staff"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  required
                />
              </div>

              <div className="input-group">
                <label className="field-label" htmlFor="password">Password</label>
                <input
                  id="password"
                  type="password"
                  placeholder="Enter your secure password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                />
              </div>

              <div className="input-group">
                <label className="field-label" htmlFor="role">Warehouse Operational Role</label>
                <select id="role" value={role} onChange={(e) => setRole(e.target.value)}>
                  <option value="staff">Staff — Floor Operations & Picking</option>
                  <option value="manager">Manager — Shift Supervisor & Approvals</option>
                  <option value="admin">Admin — System & Security SOC</option>
                </select>
              </div>

              {authError && <div className="error-banner">{authError}</div>}

              <button type="submit" className="primary-white-btn" disabled={authLoading}>
                {authLoading
                  ? 'Authenticating...'
                  : isRegisterMode
                  ? 'Create Account & Continue'
                  : 'Continue to Operations'}
              </button>
            </form>
          </div>
        </div>

        {/* RIGHT SIDE: INTELIWMS EMBLEM SHOWCASE */}
        <div className="brand-right-column">
          <div className="emblem-card-frame">
            <div className="emblem-glow-wrapper">
              <img
                src="/intelliwms_logo.png"
                alt="InteliWMS Official Emblem"
                className="showcase-emblem"
              />
            </div>

            <div className="brand-showcase-text">
              <h2 className="showcase-title">InteliWMS</h2>
              <p className="showcase-tagline">Intelligent Agentic Warehouse Management System</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
