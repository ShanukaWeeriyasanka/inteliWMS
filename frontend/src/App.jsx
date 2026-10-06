import React, { useState, useEffect, useRef, useReducer } from 'react'
import axios from 'axios'
import { api } from './services/api'
import { chatReducer, initialChatState, DRAFT } from './chat/chatState'
import { storedToUiMessages, toAssistantMessage, toThreadSummary, toUserMessage } from './chat/messageMapping'
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

export default function App() {
  // Session & Authentication
  const [token, setToken] = useState(localStorage.getItem('token') || '')
  const [currentUser, setCurrentUser] = useState(null)
  const [authError, setAuthError] = useState('')
  const [authLoading, setAuthLoading] = useState(false)

  // Layout & Navigation State
  const [sidebarOpen, setSidebarOpen] = useState(window.innerWidth >= 1024)
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

  const restoreSession = async (authToken) => {
    try {
      const user = await api.fetchMe(authToken)
      setCurrentUser(user)
      fetchAuditData()
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

  const fetchAuditData = async () => {
    try {
      const data = await api.fetchAuditLogs()
      setAuditLogs(data.logs || [])
      setAuditStats(data.stats || null)
    } catch (e) {
      console.warn('Could not fetch audit logs:', e.message)
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
      fetchAuditData()
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
      fetchAuditData()
    } catch (err) {
      setAuthError(err.response?.data?.detail || err.message || 'Registration failed')
    } finally {
      setAuthLoading(false)
    }
  }

  const handleLogout = ({ keepUrl = false } = {}) => {
    sessionEpochRef.current += 1
    setToken('')
    setCurrentUser(null)
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
  const handleSendMessage = async ({ text, attachments = [], mode, targetAgent }) => {
    if (!text.trim() && attachments.length === 0) return

    // The question belongs to the conversation on screen when it is asked
    const key = chatRef.current.activeKey
    if (chatRef.current.pending[key]) return // one question at a time per conversation
    const epoch = sessionEpochRef.current
    const threadId = key === DRAFT ? null : key
    lastAskKeyRef.current = key

    setLastUserQuery(text)
    dispatchChat({ type: 'SEND', key, message: toUserMessage(text, { senderName, attachments }) })

    let res = null
    let assistantMsg
    try {
      // Execute query through real backend Coordinator API Gateway (same thread_id for the whole conversation)
      res = await api.sendQuery(text, token, twinSessionId, threadId)
      assistantMsg = toAssistantMessage(res, { text })
    } catch (err) {
      if (err.response?.status === 401 && epoch === sessionEpochRef.current) {
        handleLogout({ keepUrl: true })
        return
      }
      const code = err.response?.data?.error_code
      assistantMsg = {
        id: `e-${Date.now()}`,
        role: 'assistant',
        status: 'error',
        content: code === 'THREAD_NOT_FOUND'
          ? 'This conversation no longer exists (it may have been deleted). Start a new chat to continue.'
          : `Error contacting Coordinator Agent: ${err.response?.data?.message || err.response?.data?.detail || err.message}`,
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
      return {
        status: 'denied',
        message: err.response?.data?.detail || err.message
      }
    } finally {
      setActionLoading(false)
    }
  }

  // Handle Injection Testing
  const handleTestInjection = async (testText) => {
    try {
      const res = await api.testInjection(testText)
      fetchAuditData()
      return res
    } catch (e) {
      return { is_safe: false, reason: e.message }
    }
  }

  // New Chat: an empty conversation at "/"; its thread is created with the first answer
  const handleNewChat = () => {
    const { activeKey, messages: current } = chatRef.current
    if (activeKey === DRAFT && current.length === 0) return
    resetWorkspace()
    dispatchChat({ type: 'NEW_DRAFT' })
    threadNavigator.push({ threadId: null })
  }

  // Select Chat from History: the URL changes, the route effect loads that thread's messages
  const handleSelectChat = (chatId) => {
    if (chatId === chatRef.current.activeKey) return
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
    setArtifactTab(tabName)
    setArtifactOpen(true)
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
  return (
    <div className="claude-app-layout">
      {/* Collapsible Left Sidebar */}
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
      <div className="claude-main-stage">
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
              <span className="topbar-user-name">{currentUser.name || currentUser.username}</span>
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

          {/* Spline 3D Scene */}
          {!twinActive && <SplineScene isChatActive={messages.length > 0} />}

          {messages.length === 0 && !chat.loadingHistory ? (
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
                    onOpenArtifact={(m) => {
                      setSelectedArtifactMessage(m)
                      setArtifactTab('telemetry')
                      setArtifactOpen(true)
                    }}
                    onInspectLocation={() => {
                      setArtifactTab('bay_visualizer')
                      setArtifactOpen(true)
                    }}
                    onInspectOrder={() => {
                      setArtifactTab('order_timeline')
                      setArtifactOpen(true)
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
        onRefreshAuditLogs={fetchAuditData}
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
