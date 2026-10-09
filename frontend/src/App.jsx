import React, { useState, useEffect, useRef, useReducer, useCallback } from 'react'
import axios from 'axios'
import { api } from './services/api'
import { apiErrorMessage } from './services/errors'
import { composeQuery } from './chat/attachments'
import { chatReducer, initialChatState, DRAFT } from './chat/chatState'
import { storedToUiMessages, toAssistantMessage, toThreadSummary, toUserMessage, isFulfillmentMessage } from './chat/messageMapping'
import { threadNavigator, useThreadRoute } from './chat/useThreadRoute'
import {
  Sidebar,
  PromptCapsule,
  ChatMessage,
  ArtifactPanel,
  OperationalModal,
  WarehouseThinkingAnimation
} from './components/coordinator UI'
import CommercializationModal from './components/CommercializationModal'
import PricingModal from './components/PricingModal'
import SplineScene from './components/SplineScene'
import LoginPage from './pages/LoginPage'
import FulfillmentDashboard from './pages/FulfillmentDashboard'
import WarehouseTwin from './twin/WarehouseTwin'
import {
  Menu,
  Layers,
  Sparkles,
  ShieldCheck,
  Cpu,
  Database,
  RefreshCw,
  LogOut,
  Crown
} from 'lucide-react'


// One twin session per browser tab: agent map commands are addressed to it.
const getTwinSessionId = () => {
  try {
    const existing = sessionStorage.getItem('twin_session_id')
    if (existing) return existing
    const id = crypto.randomUUID ? crypto.randomUUID() : `s-${Date.now()}-${Math.random().toString(16).slice(2)}`
    sessionStorage.setItem('twin_session_id', id)
    return id
  } catch {
    return `s-${Date.now()}`
  }
}

// A new map session for the next user on this tab (map commands are addressed per session)
const newTwinSessionId = () => {
  try {
    sessionStorage.removeItem('twin_session_id')
  } catch {
    // storage unavailable: getTwinSessionId falls back to a fresh id
  }
  return getTwinSessionId()
}

// Only managers and admins may read the security audit stream (decided by the server-issued role)
const canViewAuditLog = (role) => role === 'manager' || role === 'admin'

// Width of the centre stage -> layout mode for the floating topbar items
const stageModeFor = (width) => (width < 560 ? 'is-narrow is-compact' : width < 1180 ? 'is-narrow' : '')

// Up to this width the expanded sidebar floats over the page (index.css, MOBILE RESPONSIVENESS)
const OVERLAY_SIDEBAR_QUERY = '(max-width: 1024px)'
const isOverlaySidebar = () => typeof window !== 'undefined' && window.matchMedia?.(OVERLAY_SIDEBAR_QUERY).matches

function useOverlaySidebar() {
  const [overlay, setOverlay] = useState(isOverlaySidebar)
  useEffect(() => {
    const mq = window.matchMedia?.(OVERLAY_SIDEBAR_QUERY)
    if (!mq) return undefined
    const onChange = () => setOverlay(mq.matches)
    mq.addEventListener('change', onChange)
    return () => mq.removeEventListener('change', onChange)
  }, [])
  return overlay
}

export default function App() {
  // Session & Authentication
  const [token, setToken] = useState(localStorage.getItem('token') || '')
  const [currentUser, setCurrentUser] = useState(null)
  // Role the server issued the token for ("Switch Simulated Role" only changes currentUser.role)
  const [authRole, setAuthRole] = useState(null)
  const [authError, setAuthError] = useState('')
  const [authLoading, setAuthLoading] = useState(false)

  // Layout & Navigation State
  // Up to 1024px the sidebar overlays the page (index.css), so it starts collapsed there
  const [sidebarOpen, setSidebarOpen] = useState(window.innerWidth > 1024)
  const overlaySidebar = useOverlaySidebar()
  const [artifactOpen, setArtifactOpen] = useState(false)
  const [artifactTab, setArtifactTab] = useState('telemetry')
  const [selectedArtifactMessage, setSelectedArtifactMessage] = useState(null)
  const [operationalModal, setOperationalModal] = useState(null) // null | 'approvals' | 'injection_sandbox'
  const [isPricingModalOpen, setIsPricingModalOpen] = useState(false)
  const [isCommercializationOpen, setIsCommercializationOpen] = useState(false)
  const [isEnterpriseTrial, setIsEnterpriseTrial] = useState(false)
  const [actionLoading, setActionLoading] = useState(false)

  // Chat & Operational Query State — one saved conversation (thread) at a time, chosen by the URL
  const [chat, dispatchChat] = useReducer(chatReducer, initialChatState)
  const route = useThreadRoute()
  const chatRef = useRef(chat)
  chatRef.current = chat
  const messages = chat.messages
  const isLoading = !!chat.pending[chat.activeKey]
  const [lastUserQuery, setLastUserQuery] = useState('')
  const [selectedAgent, setSelectedAgent] = useState('auto')
  const sessionEpochRef = useRef(0) // bumps on logout: late answers from the old session are dropped
  const lastAskKeyRef = useRef(null) // conversation of the most recent question (map commands follow it)

  // Warehouse Digital Twin: shown behind the chat when the inventory agent answers
  const [twinSessionId, setTwinSessionId] = useState(getTwinSessionId)
  const [twinActive, setTwinActive] = useState(false)
  const [twinCommand, setTwinCommand] = useState(null)

  // Security SOC Telemetry
  const [auditLogs, setAuditLogs] = useState([])
  const [auditStats, setAuditStats] = useState(null)
  const [auditError, setAuditError] = useState('')
  // Latest token / role for calls made from async callbacks
  const tokenRef = useRef(token)
  tokenRef.current = token
  const authRoleRef = useRef(authRole)
  authRoleRef.current = authRole

  // Centre stage width: narrow stages move the floating map button into the top row
  const [stageMode, setStageMode] = useState('')
  const stageRef = useCallback((el) => {
    if (!el || typeof ResizeObserver === 'undefined') return undefined
    const observer = new ResizeObserver(([entry]) => setStageMode(stageModeFor(entry.contentRect.width)))
    observer.observe(el)
    return () => observer.disconnect()
  }, [])

  const messagesEndRef = useRef(null)

  // Auto-scroll chat
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isLoading])

  // Restore session on mount
  useEffect(() => {
    if (token) {
      restoreSession(token)
    }
  }, [])

  // A narrow window can't fit sidebar + chat + artifact panel: make room for the chat
  useEffect(() => {
    if (artifactOpen && window.innerWidth < 1200) setSidebarOpen(false)
  }, [artifactOpen])

  // Where the sidebar floats over the page, the map gets the whole stage when it opens
  useEffect(() => {
    if (twinActive && overlaySidebar) setSidebarOpen(false)
  }, [twinActive, overlaySidebar])

  const restoreSession = async (authToken) => {
    try {
      const user = await api.fetchMe(authToken)
      setCurrentUser(user)
      setAuthRole(user.role || null)
      fetchAuditData({ authToken, role: user.role })
    } catch (e) {
      console.warn('Session restoration failed:', e.message)
      // Keep /chat/<id> so the conversation reopens after signing in again
      handleLogout({ keepUrl: true })
    }
  }

  const senderName = currentUser?.name || currentUser?.username || 'Operator'

  // ── Conversations (threads) ──────────────────────────────────────────────

  // Shown in place of a conversation that can't be opened
  const showNotice = (text) => {
    dispatchChat({
      type: 'NEW_DRAFT',
      messages: [{ id: `n-${Date.now()}`, role: 'assistant', status: 'error', content: text, timestamp: new Date() }]
    })
  }

  const resetWorkspace = () => {
    setTwinCommand(null)
    setSelectedArtifactMessage(null)
    setArtifactOpen(false)
  }

  const loadThreads = async () => {
    const epoch = sessionEpochRef.current
    try {
      const threads = await api.listThreads(token)
      if (epoch === sessionEpochRef.current) {
        dispatchChat({ type: 'THREADS_LOADED', threads: threads.map(toThreadSummary) })
      }
    } catch (e) {
      console.warn('Could not load conversations:', e.message)
    }
  }

  useEffect(() => {
    if (currentUser && token) loadThreads()
  }, [currentUser, token])

  // URL → active conversation (sidebar clicks, refresh, browser back / forward)
  useEffect(() => {
    if (!currentUser || !token) return
    if (route.invalidThreadId) {
      showNotice('That conversation link is not valid, so a new chat was started.')
      threadNavigator.replace({ threadId: null })
      return
    }
    const key = route.threadId || DRAFT
    if (key === chatRef.current.activeKey) return
    resetWorkspace()
    dispatchChat({ type: 'ROUTE_CHANGED', key })
  }, [route.threadId, route.invalidThreadId, currentUser, token])

  // Load the selected conversation's history (stale loads are aborted / ignored)
  useEffect(() => {
    if (!currentUser || !token) return
    const key = chat.activeKey
    if (key === DRAFT || chat.loadedKey === key) return
    const controller = new AbortController()
    dispatchChat({ type: 'LOAD_START', key })
    api.getThread(token, key, { signal: controller.signal })
      .then((data) => dispatchChat({ type: 'LOAD_OK', key, messages: storedToUiMessages(data.messages, senderName) }))
      .catch((err) => {
        if (axios.isCancel(err)) return
        const status = err.response?.status
        if (status === 401) {
          handleLogout({ keepUrl: true })
        } else if (status === 404 || status === 400) {
          showNotice('That conversation could not be found (it may have been deleted), so a new chat was started.')
          threadNavigator.replace({ threadId: null })
        } else {
          dispatchChat({
            type: 'LOAD_OK',
            key,
            messages: [{ id: `n-${Date.now()}`, role: 'assistant', status: 'error', timestamp: new Date(),
              content: `Could not load this conversation: ${err.message}. Refresh to try again.` }]
          })
        }
      })
    return () => controller.abort()
  }, [chat.activeKey, chat.loadedKey, currentUser, token])

  // The map follows the URL (?view=map), so browser Back closes it and refresh keeps it open
  useEffect(() => {
    setTwinActive(route.view === 'map')
  }, [route.view])

  const openMap = () => {
    setTwinActive(true)
    const current = threadNavigator.current()
    if (current.view !== 'map') threadNavigator.push({ threadId: current.threadId, view: 'map' }, { mapPushed: true })
  }

  const closeMap = ({ userAction = false } = {}) => {
    setTwinActive(false)
    const current = threadNavigator.current()
    if (current.view !== 'map') return
    if (userAction && threadNavigator.pushedWith('mapPushed')) threadNavigator.back()
    else threadNavigator.replace({ threadId: current.threadId, view: null })
  }

  const fetchAuditData = async ({ authToken = tokenRef.current, role = authRoleRef.current } = {}) => {
    if (!authToken || !canViewAuditLog(role)) {
      // Staff never ask: the panel explains the stream is for managers and admins
      setAuditLogs([])
      setAuditStats(null)
      setAuditError('')
      return
    }
    try {
      const data = await api.fetchAuditLogs(authToken)
      setAuditLogs(data.logs || [])
      setAuditStats(data.stats || null)
      setAuditError('')
    } catch (e) {
      console.warn('Could not fetch audit logs:', e.message)
      setAuditError(apiErrorMessage(e, 'Could not load the security audit stream.'))
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
      setAuthRole(data.user?.role || null)
      fetchAuditData({ authToken: data.token, role: data.user?.role })
    } catch (err) {
      setAuthError(apiErrorMessage(err, 'Authentication failed'))
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
      setAuthRole(data.user?.role || null)
      fetchAuditData({ authToken: data.token, role: data.user?.role })
    } catch (err) {
      setAuthError(apiErrorMessage(err, 'Registration failed'))
    } finally {
      setAuthLoading(false)
    }
  }

  const handleLogout = ({ keepUrl = false } = {}) => {
    sessionEpochRef.current += 1
    setToken('')
    setCurrentUser(null)
    setAuthRole(null)
    setAuditLogs([])
    setAuditStats(null)
    setAuditError('')
    localStorage.removeItem('token')
    // Nothing from this user's session may leak into the next sign-in on this tab
    dispatchChat({ type: 'RESET' })
    resetWorkspace()
    setTwinActive(false)
    setTwinSessionId(newTwinSessionId())
    if (keepUrl !== true) threadNavigator.replace({ threadId: null })
  }

  const handleSwitchRoleQuick = (newRole) => {
    // Demo role switcher for testing RBAC matrix live
    if (!currentUser) return
    setCurrentUser({
      ...currentUser,
      role: newRole
    })
  }

  // Handle Query Submission through Coordinator API Gateway
  const handleSendMessage = async ({ text = '', attachments = [], mode, targetAgent }) => {
    const typed = (text || '').trim()
    if (!typed && attachments.length === 0) return
    // Text files travel inside the question (cut to the 4,000-character limit)
    const { query } = composeQuery(typed, attachments)
    if (!query.trim()) return

    // The question belongs to the conversation on screen when it is asked
    const key = chatRef.current.activeKey
    if (chatRef.current.pending[key]) return // one question at a time per conversation
    const epoch = sessionEpochRef.current
    const threadId = key === DRAFT ? null : key
    lastAskKeyRef.current = key

    setLastUserQuery(typed || attachments.map((a) => a.name).join(', '))
    // The bubble shows what was typed plus file chips, not the file bodies
    const chips = attachments.map(({ name, size }) => ({ name, size }))
    dispatchChat({ type: 'SEND', key, message: toUserMessage(typed, { senderName, attachments: chips }) })

    let res = null
    let assistantMsg
    try {
      // Execute query through real backend Coordinator API Gateway (same thread_id for the whole conversation)
      res = await api.sendQuery(query, token, twinSessionId, threadId)
      assistantMsg = toAssistantMessage(res, { text: query })
    } catch (err) {
      if (err.response?.status === 401 && epoch === sessionEpochRef.current) {
        handleLogout({ keepUrl: true })
        return
      }
      const code = err.response?.data?.error_code
      // This tab's map session belongs to another user: start a fresh one for the next question
      if (code === 'TWIN_SESSION_FORBIDDEN' && epoch === sessionEpochRef.current) {
        setTwinSessionId(newTwinSessionId())
      }
      assistantMsg = {
        id: `e-${Date.now()}`,
        role: 'assistant',
        status: 'error',
        content: code === 'THREAD_NOT_FOUND'
          ? 'This conversation no longer exists (it may have been deleted). Start a new chat to continue.'
          : code === 'TWIN_SESSION_FORBIDDEN'
            ? 'The map session was reset — please ask again.'
            : `Error contacting Coordinator Agent: ${apiErrorMessage(err)}`,
        timestamp: new Date()
      }
    }

    if (epoch !== sessionEpochRef.current) return // signed out while waiting
    const stillOnScreen = chatRef.current.activeKey === key
    dispatchChat({ type: 'RESPONSE', key, message: assistantMsg, threadId: res?.thread_id || null })
    if (!res) return

    // First answer of a new conversation: the URL now names its thread (no reload, no new history entry)
    if (key === DRAFT && res.thread_id && stillOnScreen) {
      threadNavigator.replace({ threadId: res.thread_id, view: threadNavigator.current().view })
    }
    if (res.thread_id) loadThreads()
    if (!stillOnScreen) return // saved in its own conversation; leave the current screen alone

    setSelectedArtifactMessage(assistantMsg)

    // Check if backend returned security block
    if (assistantMsg.status === 'blocked') {
      fetchAuditData()
      return
    }

    const uiCommand = assistantMsg.uiCommand
    if (uiCommand) {
      setTwinCommand(uiCommand)
      setArtifactOpen(false)
      openMap()
    } else {
      closeMap()
    }

    // Auto open visualizer for classic SKU inventory inquiries
    const isInventory = res.agent_used === 'inventory_agent' || !!res.inventory_details
    if (!uiCommand && (isInventory || assistantMsg.skuData)) {
      setArtifactTab('bay_visualizer')
      setArtifactOpen(true)
    }

    fetchAuditData()
  }

  // Handle Role Actions (e.g. approve_restock)
  const handleExecuteRoleAction = async (actionName) => {
    setActionLoading(true)
    try {
      const res = await api.executeAction(actionName, token)
      fetchAuditData()
      return res
    } catch (err) {
      // A denied action is HTTP 403 {error_code: "FORBIDDEN", message}
      fetchAuditData()
      return {
        status: 'denied',
        message: apiErrorMessage(err, 'This action is not allowed for your role.')
      }
    } finally {
      setActionLoading(false)
    }
  }

  // Handle Injection Testing
  const handleTestInjection = async (testText) => {
    try {
      const res = await api.testInjection(testText, token)
      fetchAuditData()
      return res
    } catch (e) {
      return { is_safe: false, reason: apiErrorMessage(e) }
    }
  }

  // New Chat: an empty conversation at "/"; its thread is created with the first answer
  const handleNewChat = () => {
    const { activeKey, messages: current } = chatRef.current
    if (activeKey === DRAFT && current.length === 0 && !route.view) return
    resetWorkspace()
    dispatchChat({ type: 'NEW_DRAFT' })
    threadNavigator.push({ threadId: null })
  }

  // Select Chat from History: the URL changes, the route effect loads that thread's messages
  const handleSelectChat = (chatId) => {
    if (chatId === chatRef.current.activeKey && !route.view) return
    threadNavigator.push({ threadId: chatId })
  }

  const handleClearHistory = async () => {
    if (!window.confirm('Delete all saved conversations? This cannot be undone.')) return
    try {
      await api.clearThreads(token)
    } catch (err) {
      if (err.response?.status === 401) handleLogout({ keepUrl: true })
      else console.warn('Could not clear conversations:', err.message)
      return
    }
    dispatchChat({ type: 'THREADS_LOADED', threads: [] })
    resetWorkspace()
    dispatchChat({ type: 'NEW_DRAFT' })
    threadNavigator.replace({ threadId: null })
  }

  const handleOpenArtifactTab = (tabName) => {
    if (tabName === 'order_timeline') {
      openFulfillmentDashboard()
      return
    }
    setArtifactTab(tabName)
    setArtifactOpen(true)
  }

  const openFulfillmentDashboard = (message) => {
    setArtifactOpen(false)
    const current = threadNavigator.current()
    const index = message ? messages.findIndex((m) => m.id === message.id) : -1
    threadNavigator.push({ threadId: current.threadId, view: 'fulfillment', messageIndex: index >= 0 ? index : null },
      { fulfillmentPushed: true })
  }

  const closeFulfillmentDashboard = () => {
    if (threadNavigator.pushedWith('fulfillmentPushed')) threadNavigator.back()
    else threadNavigator.replace({ threadId: threadNavigator.current().threadId })
  }

  // View 1: Unauthenticated Session
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

  // View 2: Authenticated Claude.ai Operational Interface
  const showHero = messages.length === 0 && !chat.loadingHistory

  return (
    <div className="claude-app-layout">
      {route.view === 'fulfillment' && !chat.loadingHistory && chat.activeKey === (route.threadId || DRAFT) && (
        <FulfillmentDashboard
          selectedMessage={isFulfillmentMessage(messages[route.messageIndex])
            ? messages[route.messageIndex] : [...messages].reverse().find(isFulfillmentMessage)}
          currentUser={currentUser}
          onBackToChat={closeFulfillmentDashboard}
        />
      )}
      {/* Collapsible Left Sidebar */}
      {/* Small screens: the expanded sidebar floats over the page; tapping outside closes it */}
      {overlaySidebar && sidebarOpen && (
        <div className="sidebar-scrim" onClick={() => setSidebarOpen(false)} aria-hidden="true" />
      )}

      <Sidebar
        isOpen={sidebarOpen}
        onToggle={() => setSidebarOpen(!sidebarOpen)}
        chatHistory={chat.threads}
        activeChatId={route.threadId}
        onSelectChat={handleSelectChat}
        onNewChat={handleNewChat}
        onClearHistory={handleClearHistory}
        currentUser={currentUser}
        onLogout={handleLogout}
        onOpenArtifactTab={handleOpenArtifactTab}
        onSwitchRoleQuick={handleSwitchRoleQuick}
        onOpenPricingModal={() => setIsPricingModalOpen(true)}
        onOpenCommercializationModal={() => setIsPricingModalOpen(true)}
      />

      {/* Main Center Canvas */}
      <div className={`claude-main-stage ${stageMode}`.trim()} ref={stageRef}>
        {/* Floating Minimalist Topbar: Sidebar Icon & Who Logged In */}
        <header className="claude-topbar floating-minimal-topbar">
          <div className="topbar-left">
            <button
              onClick={() => setSidebarOpen(!sidebarOpen)}
              className="topbar-icon-btn"
              title="Toggle Sidebar"
            >
              <Menu size={18} />
            </button>
          </div>

          <div className="topbar-right">
            {/* Enterprise Trial Active Pill */}
            {isEnterpriseTrial && (
              <div
                className="topbar-trial-pill"
                onClick={() => setIsPricingModalOpen(true)}
                title="SaaS Pricing & Plans • Feature Comparison"
              >
                <Crown size={12} className="trial-crown-icon" />
                <span>ENTERPRISE TRIAL</span>
              </div>
            )}

            {/* Who Logged In */}
            <div className="topbar-logged-user-pill">
              <div className="topbar-user-avatar">
                {currentUser.name ? currentUser.name[0].toUpperCase() : (currentUser.username ? currentUser.username[0].toUpperCase() : 'U')}
              </div>
              <span className="topbar-user-name" title={currentUser.name || currentUser.username || 'Signed-in user'}>
                {currentUser.name || currentUser.username || 'Signed-in user'}
              </span>
              <span className={`role-badge-pill role-${currentUser.role || 'staff'}`}>
                <ShieldCheck size={12} />
                <span>{currentUser.role?.toUpperCase() || 'STAFF'}</span>
              </span>
            </div>
          </div>
        </header>

        {/* Center Conversation / Hero Canvas */}
        <main className={`claude-center-canvas spline-active-canvas${twinActive ? ' twin-bg-active' : ''}`}>
          {/* Ambient Lighting & Micro-Grid Atmosphere */}
          <div className="ambient-canvas-glow" />

          {/* Warehouse Digital Twin — interactive map workspace for inventory answers */}
          <WarehouseTwin
            token={token}
            sessionId={twinSessionId}
            command={twinCommand}
            visible={twinActive}
            onActivate={(clickEvent) => {
              // The launcher button passes its click event; live map commands (SSE) pass nothing and
              // only open the map while the conversation that asked for them is still on screen.
              if (clickEvent || lastAskKeyRef.current === chatRef.current.activeKey) openMap()
            }}
            onClose={() => closeMap({ userAction: true })}
            onAsk={(text) => handleSendMessage({ text, attachments: [], targetAgent: selectedAgent })}
            agentReply={[...messages].reverse().find((m) => m.role === 'assistant')?.content}
            agentBusy={isLoading}
          />

          {/* Spline 3D Scene: only on the empty / hero screen. Behind the chat or the map it is
              covered, and a hidden WebGL scene keeps rendering into an empty framebuffer. */}
          {!twinActive && showHero && <SplineScene isChatActive={false} />}

          {showHero ? (
            /* Pure 3D Scene + Floating Chat Box */
            <div className="spline-hero-chat-container">
              <div className="spline-capsule-floating-wrapper">
                <PromptCapsule
                  onSend={handleSendMessage}
                  isLoading={isLoading}
                  currentUser={currentUser}
                  selectedAgent={selectedAgent}
                  setSelectedAgent={setSelectedAgent}
                  onOpenOperationalModal={(type) => setOperationalModal(type)}
                />
              </div>
            </div>
          ) : (
            /* ACTIVE CHAT STREAM */
            <div className="claude-chat-stream-container">
              <div className="chat-messages-scroll-area">
                {messages.map((msg) => (
                  <ChatMessage
                    key={msg.id}
                    message={msg}
                    onOpenFulfillmentDashboard={openFulfillmentDashboard}
                    onOpenArtifact={(m) => {
                      setSelectedArtifactMessage(m)
                      setArtifactTab('telemetry')
                      setArtifactOpen(true)
                    }}
                    onInspectLocation={() => {
                      // The Bay Map shows this answer's live numbers (not the visualizer's sample catalog)
                      setSelectedArtifactMessage(msg)
                      setArtifactTab('bay_visualizer')
                      setArtifactOpen(true)
                    }}
                    onInspectOrder={() => {
                      openFulfillmentDashboard(msg)
                    }}
                    onShowOnMap={(m) => {
                      // Replay the stored command (new id so the twin plays it again)
                      setTwinCommand({ ...m.uiCommand, id: `replay-${Date.now()}` })
                      openMap()
                    }}
                  />
                ))}

                {isLoading && (
                  <div className="chat-message-row assistant-row loading-row">
                    <div className="message-avatar-container">
                      <div className="assistant-msg-avatar warehouse-avatar-glow">
                        <img src="/intelliwms_logo.png" alt="IntelliWMS" className="assistant-logo-icon pulse" />
                      </div>
                    </div>
                    <div className="message-bubble-wrapper" style={{ width: '100%', maxWidth: '620px' }}>
                      <WarehouseThinkingAnimation queryText={lastUserQuery} />
                    </div>
                  </div>
                )}
                <div ref={messagesEndRef} />
              </div>

              {/* Bottom Sticky Prompt Capsule */}
              <div className="bottom-sticky-prompt-bar">
                <PromptCapsule
                  onSend={handleSendMessage}
                  isLoading={isLoading}
                  currentUser={currentUser}
                  selectedAgent={selectedAgent}
                  setSelectedAgent={setSelectedAgent}
                  onOpenOperationalModal={(type) => setOperationalModal(type)}
                />
              </div>
            </div>
          )}
        </main>
      </div>

      {/* Right Slide-out Artifact & Telemetry Drawer */}
      <ArtifactPanel
        isOpen={artifactOpen}
        onClose={() => setArtifactOpen(false)}
        activeTab={artifactTab}
        setActiveTab={setArtifactTab}
        selectedMessage={selectedArtifactMessage}
        token={token}
        currentUser={currentUser}
        auditLogs={auditLogs}
        auditStats={auditStats}
        auditAccess={canViewAuditLog(authRole)}
        auditError={auditError}
        onRefreshAuditLogs={() => fetchAuditData()}
      />

      {/* Operational Modal for Approvals and Sandbox */}
      <OperationalModal
        isOpen={!!operationalModal}
        modalType={operationalModal}
        onClose={() => setOperationalModal(null)}
        currentUser={currentUser}
        onExecuteAction={handleExecuteRoleAction}
        onTestInjection={handleTestInjection}
        actionLoading={actionLoading}
      />

      {/* SaaS Pricing & Feature Comparison Modal */}
      <PricingModal
        isOpen={isPricingModalOpen || isCommercializationOpen}
        onClose={() => {
          setIsPricingModalOpen(false)
          setIsCommercializationOpen(false)
        }}
      />
    </div>
  )
}
