import { useState, useEffect } from 'react'
import { api } from './services/api'
import Topbar from './components/Topbar'
import TokenInspectorDrawer from './components/TokenInspectorDrawer'
import LoginPage from './pages/LoginPage'
import StaffDashboard from './pages/StaffDashboard'
import ManagerDashboard from './pages/ManagerDashboard'
import AdminDashboard from './pages/AdminDashboard'

function App() {
  // Session & Authentication State
  const [token, setToken] = useState(localStorage.getItem('token') || '')
  const [currentUser, setCurrentUser] = useState(null)
  const [authError, setAuthError] = useState('')
  const [authLoading, setAuthLoading] = useState(false)

  // Operational State
  const [actionLoading, setActionLoading] = useState(false)
  const [queryLoading, setQueryLoading] = useState(false)

  // Admin Telemetry & Audit
  const [auditLogs, setAuditLogs] = useState([])
  const [auditStats, setAuditStats] = useState(null)

  // Restore existing session on mount
  useEffect(() => {
    if (token) {
      restoreSession(token)
    }
  }, [])

  const restoreSession = async (authToken) => {
    try {
      const user = await api.fetchMe(authToken)
      setCurrentUser(user)
      if (user.role === 'admin') {
        fetchAuditData()
      }
    } catch (e) {
      console.warn('Session restoration failed or expired:', e.message)
      handleLogout()
    }
  }

  const handleLogin = async (username, password, role) => {
    setAuthLoading(true)
    setAuthError('')
    try {
      const data = await api.login(username, password, role)
      setToken(data.token)
      localStorage.setItem('token', data.token)
      setCurrentUser(data.user)
      if (data.user.role === 'admin') {
        fetchAuditData()
      }
    } catch (err) {
      setAuthError(err.response?.data?.detail || err.message || 'Authentication failed')
    } finally {
      setAuthLoading(false)
    }
  }

  const handleRegister = async (username, password, role, name) => {
    setAuthLoading(true)
    setAuthError('')
    try {
      const data = await api.register(username, password, role, name)
      setToken(data.token)
      localStorage.setItem('token', data.token)
      setCurrentUser(data.user)
    } catch (err) {
      setAuthError(err.response?.data?.detail || err.message || 'Registration failed')
    } finally {
      setAuthLoading(false)
    }
  }

  const handleLogout = () => {
    setToken('')
    setCurrentUser(null)
    localStorage.removeItem('token')
  }

  const handleExecuteAction = async (actionName) => {
    setActionLoading(true)
    try {
      const res = await api.executeAction(actionName, token)
      if (currentUser?.role === 'admin') {
        fetchAuditData()
      }
      return res
    } catch (err) {
      return {
        status: 'error',
        message: err.response?.data?.detail || err.message
      }
    } finally {
      setActionLoading(false)
    }
  }

  const handleSendQuery = async (queryText) => {
    setQueryLoading(true)
    try {
      const res = await api.sendQuery(queryText, token)
      if (currentUser?.role === 'admin') {
        fetchAuditData()
      }
      return { data: res }
    } catch (err) {
      return { error: `Request failed: ${err.message}` }
    } finally {
      setQueryLoading(false)
    }
  }

  const fetchAuditData = async () => {
    try {
      const data = await api.fetchAuditLogs()
      setAuditLogs(data.logs || [])
      setAuditStats(data.stats || null)
    } catch (e) {
      console.warn('Error loading audit logs:', e.message)
    }
  }

  const handleTestInjection = async (testText) => {
    try {
      const res = await api.testInjection(testText)
      fetchAuditData()
      return res
    } catch (e) {
      return { is_safe: false, reason: 'Error evaluating: ' + e.message }
    }
  }

  // View 1: Unauthenticated -> Modular Side-by-Side Login Screen
  if (!currentUser || !token) {
    return (
      <LoginPage
        onLogin={handleLogin}
        onRegister={handleRegister}
        authLoading={authLoading}
        authError={authError}
        setAuthError={setAuthError}
      />
    )
  }

  // View 2: Authenticated -> Role-Tailored Modular Application Shell
  return (
    <div className="app-shell">
      <Topbar currentUser={currentUser} onLogout={handleLogout} />

      <main className="dashboard-content">
        {currentUser.role === 'staff' && (
          <StaffDashboard
            currentUser={currentUser}
            onExecuteAction={handleExecuteAction}
            onSendQuery={handleSendQuery}
            actionLoading={actionLoading}
            queryLoading={queryLoading}
          />
        )}

        {currentUser.role === 'manager' && (
          <ManagerDashboard
            currentUser={currentUser}
            onExecuteAction={handleExecuteAction}
            onSendQuery={handleSendQuery}
            actionLoading={actionLoading}
            queryLoading={queryLoading}
          />
        )}

        {currentUser.role === 'admin' && (
          <AdminDashboard
            currentUser={currentUser}
            auditStats={auditStats}
            auditLogs={auditLogs}
            onRefreshAuditLogs={fetchAuditData}
            onTestInjection={handleTestInjection}
          />
        )}

        <TokenInspectorDrawer token={token} currentUser={currentUser} />
      </main>
    </div>
  )
}

export default App
