import React, { useState } from 'react'
import './LoginPage.css'

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
      // Only staff accounts can be self-registered
      onRegister(username, password, 'staff', fullName)
    } else {
      onLogin(username, password, role)
    }
  }

  return (
    <div className="logistics-frame">
      {/* Background Video from logistics showcase */}
      <video
        className="logistics-bg-video"
        autoPlay
        muted
        loop
        playsInline
        disablePictureInPicture
        aria-label="Aerial view of a container freight train crossing black coal terrain"
        src="https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20261005_115944_095d91d4-030f-4e82-b42b-a388c0816d24.mp4"
      />

      {/* Atmospheric Overlays */}
      <div className="logistics-tint" />
      <div className="logistics-overlay-glow" />

      {/* Main Centered Stage */}
      <main className="logistics-stage-centered">
        {/* TOP: CENTERED HERO HEADLINE */}
        <header className="logistics-hero-header">
          <p className="logistics-eyebrow">
            <span className="eyebrow-badge">INTELIWMS</span>
            <span>WHY US · AGENTIC FULFILLMENT</span>
          </p>

          <h1 className="logistics-headline-centered">
            <span className="hl-line hl1">LOGISTICS</span>
            <span className="hl-line hl2">THAT WORKS</span>
            <span className="hl-line hl3">AS HARD AS</span>
            <span className="hl-line hl4">YOU DO.</span>
          </h1>
        </header>

        {/* CENTER: INTEGRATED FROSTED GLASS LOGIN TERMINAL */}
        <section className="logistics-auth-card-centered">
          {/* Brand Header */}
          <div className="auth-card-header">
            <img
              src="/intelliwms_logo.png"
              alt="InteliWMS Emblem"
              className="auth-card-emblem"
            />
            <div className="auth-card-titles">
              <h2 className="auth-brand-name">InteliWMS</h2>
              <p className="auth-brand-subtitle">Operations Access Terminal</p>
            </div>
          </div>

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
            <span className="or-line" />
            <span className="or-label">OR WITH CREDENTIALS</span>
            <span className="or-line" />
          </div>

          {/* Mode Switch Tabs */}
          <div className="auth-tab-row">
            <button
              type="button"
              className={`tab-link ${!isRegisterMode ? 'active' : ''}`}
              onClick={() => {
                setIsRegisterMode(false)
                setAuthError('')
              }}
            >
              Sign In
            </button>
            <button
              type="button"
              className={`tab-link ${isRegisterMode ? 'active' : ''}`}
              onClick={() => {
                setIsRegisterMode(true)
                setRole('staff')
                setAuthError('')
              }}
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
              <select
                id="role"
                value={isRegisterMode ? 'staff' : role}
                onChange={(e) => setRole(e.target.value)}
                aria-describedby={isRegisterMode ? 'role-register-note' : undefined}
              >
                <option value="staff">Staff — Floor Operations & Picking</option>
                <option value="manager" disabled={isRegisterMode}>
                  Manager — Shift Supervisor & Approvals
                </option>
                <option value="admin" disabled={isRegisterMode}>
                  Admin — System & Security SOC
                </option>
              </select>
              {isRegisterMode && (
                <span id="role-register-note" className="field-hint">
                  Manager and admin accounts are created by an administrator.
                </span>
              )}
            </div>

            {authError && <div className="error-banner">{authError}</div>}

            <button
              type="submit"
              className="primary-white-btn"
              disabled={authLoading}
            >
              {authLoading
                ? 'Authenticating...'
                : isRegisterMode
                ? 'Create Account & Continue'
                : 'Continue to Operations'}
            </button>
          </form>
        </section>

        {/* BOTTOM: SYMMETRICAL MARK & FEATURES FLANKING CENTER */}
        <section className="logistics-bottom-section">
          {/* Centered Circular Mark */}
          <svg className="logistics-mark-centered" viewBox="0 0 52 52" fill="none" aria-hidden="true">
            <circle
              cx="26"
              cy="26"
              r="23"
              stroke="#D6523A"
              strokeWidth="1.6"
              strokeDasharray="98.3 46.3"
              transform="rotate(2.5 26 26)"
            />
            <g stroke="#D6523A" strokeWidth="1.6" strokeLinecap="round">
              <circle cx="26.5" cy="26.1" r="2.3" />
              <path d="M28.9 27.6C31.6 29 32.9 31.2 31.8 33.3 30.7 35.4 27.2 36.1 24.2 35.1" />
            </g>
          </svg>

          {/* Features Grid Flanking Center */}
          <div className="logistics-bottom-features">
            {/* Feature Left: One point of contact */}
            <article className="feature-side left">
              <svg className="feature-icon-svg" viewBox="0 0 35 34" width="35" height="34" aria-hidden="true">
                <defs>
                  <clipPath id="gclip">
                    <circle cx="17.5" cy="17" r="9.80" />
                  </clipPath>
                </defs>
                <circle cx="17.5" cy="17" r="16.5" stroke="#F9F9F9" strokeWidth="1.9" strokeDasharray="3.6 3" fill="none" />
                <circle cx="17.5" cy="17" r="9.80" fill="#F9F9F9" />
                <path
                  d="M11.90 7.20 V26.80 M17.5 7.20 V26.80 M23.10 7.20 V26.80 M7.70 11.40 H27.30 M7.70 17 H27.30 M7.70 22.60 H27.30"
                  stroke="#101215"
                  strokeWidth="0.90"
                  clipPath="url(#gclip)"
                />
              </svg>
              <h2 className="feature-title-text">One point of contact</h2>
              <p className="feature-desc-text">
                No more chasing multiple vendors. One intelligent platform manages your entire end-to-end warehouse flow origin to destination.
              </p>
            </article>

            {/* Feature Right: Full supply chain visibility */}
            <article className="feature-side right">
              <svg className="feature-icon-svg" viewBox="0 0 35 38" width="35" height="38" aria-hidden="true">
                <rect x="0.5" y="0.5" width="17" height="9.6" rx="0.5" fill="#F9F9F9" />
                <rect x="10.5" y="13.5" width="13.5" height="10.9" rx="0.5" fill="#F9F9F9" />
                <rect x="17.5" y="28.3" width="17" height="9.7" rx="0.5" fill="#F9F9F9" />
                <g fill="#101215">
                  <rect x="2.50" y="2.50" width="1.10" height="1.90" />
                  <rect x="5.60" y="2.50" width="1.10" height="1.90" />
                  <rect x="8.70" y="2.50" width="1.10" height="1.90" />
                  <rect x="11.80" y="2.50" width="1.10" height="1.90" />
                  <rect x="14.90" y="2.50" width="1.10" height="1.90" />
                  <rect x="2.50" y="6.50" width="1.10" height="1.90" />
                  <rect x="5.60" y="6.50" width="1.10" height="1.90" />
                  <rect x="8.70" y="6.50" width="1.10" height="1.90" />
                  <rect x="11.80" y="6.50" width="1.10" height="1.90" />
                  <rect x="14.90" y="6.50" width="1.10" height="1.90" />
                  <rect x="12.50" y="15.20" width="1.10" height="1.90" />
                  <rect x="15.60" y="15.20" width="1.10" height="1.90" />
                  <rect x="18.70" y="15.20" width="1.10" height="1.90" />
                  <rect x="21.80" y="15.20" width="1.10" height="1.90" />
                  <rect x="12.50" y="20.40" width="1.10" height="1.90" />
                  <rect x="15.60" y="20.40" width="1.10" height="1.90" />
                  <rect x="18.70" y="20.40" width="1.10" height="1.90" />
                  <rect x="21.80" y="20.40" width="1.10" height="1.90" />
                  <rect x="19.50" y="30.30" width="1.10" height="1.90" />
                  <rect x="22.60" y="30.30" width="1.10" height="1.90" />
                  <rect x="25.70" y="30.30" width="1.10" height="1.90" />
                  <rect x="28.80" y="30.30" width="1.10" height="1.90" />
                  <rect x="31.90" y="30.30" width="1.10" height="1.90" />
                  <rect x="19.50" y="34.40" width="1.10" height="1.90" />
                  <rect x="22.60" y="34.40" width="1.10" height="1.90" />
                  <rect x="25.70" y="34.40" width="1.10" height="1.90" />
                  <rect x="28.80" y="34.40" width="1.10" height="1.90" />
                  <rect x="31.90" y="34.40" width="1.10" height="1.90" />
                </g>
              </svg>
              <h2 className="feature-title-text">Full supply chain visibility</h2>
              <p className="feature-desc-text">
                Track your freight in real time and get proactive updates before issues become delays.
              </p>
            </article>
          </div>
        </section>
      </main>
    </div>
  )
}
