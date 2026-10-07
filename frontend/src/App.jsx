import React, { useState, useEffect, useRef, useCallback } from 'react'
import { api } from './services/api'
import ToastContainer from './components/Toast'
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

  // Chat & Operational Query State
  const [messages, setMessages] = useState([])
  const [lastUserQuery, setLastUserQuery] = useState('')
  const [chatHistory, setChatHistory] = useState([
    { id: 1, title: 'SKU-4521 Bay Location & Stock', timestamp: new Date(Date.now() - 3600000) },
    { id: 2, title: 'Consignment #4521 Carrier Dispatch', timestamp: new Date(Date.now() - 7200000) },
    { id: 3, title: 'Hazmat Spill Response Manual', timestamp: new Date(Date.now() - 86400000) }
  ])
  const [activeChatId, setActiveChatId] = useState(1)
  const [isLoading, setIsLoading] = useState(false)
  const [selectedAgent, setSelectedAgent] = useState('auto')

  // Security SOC Telemetry
  const [auditLogs, setAuditLogs] = useState([])
  const [auditStats, setAuditStats] = useState(null)

  // Toast Notifications
  const [toasts, setToasts] = useState([])
  const addToast = useCallback((toast) => {
    const id = Date.now() + Math.random()
    setToasts((prev) => [...prev, { id, ...toast }])
  }, [])
  const removeToast = useCallback((id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
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

  const restoreSession = async (authToken) => {
    try {
      const user = await api.fetchMe(authToken)
      setCurrentUser(user)
      fetchAuditData()
    } catch (e) {
      console.warn('Session restoration failed:', e.message)
      handleLogout()
    }
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

  const handleLogout = () => {
    setToken('')
    setCurrentUser(null)
    localStorage.removeItem('token')
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
  const handleSendMessage = async ({ text, attachments, mode, targetAgent }) => {
    if (!text.trim() && attachments.length === 0) return

    setLastUserQuery(text)

    const userMsg = {
      id: Date.now(),
      role: 'user',
      content: text,
      attachments,
      senderName: currentUser?.name || currentUser?.username || 'Operator',
      timestamp: new Date()
    }

    setMessages((prev) => [...prev, userMsg])
    setIsLoading(true)

    try {
      // Execute query through real backend Coordinator API Gateway
      const res = await api.sendQuery(text, token)
      
      // Update history if first message
      if (messages.length === 0) {
        const newHistItem = {
          id: Date.now(),
          title: text.slice(0, 32) + (text.length > 32 ? '...' : ''),
          timestamp: new Date()
        }
        setChatHistory((prev) => [newHistItem, ...prev])
        setActiveChatId(newHistItem.id)
      }

      // Check if backend returned security block
      if (res.status === 'error' && res.error_code === 'PROMPT_INJECTION_DETECTED') {
        const blockMsg = {
          id: Date.now() + 1,
          role: 'assistant',
          status: 'blocked',
          content: res.message || 'Prompt injection attempt detected and neutralized by security shield.',
          routing: {
            status: 'blocked',
            target_agent: 'security_sanitizer',
            rule: res.message
          },
          timestamp: new Date()
        }
        setMessages((prev) => [...prev, blockMsg])
        setSelectedArtifactMessage(blockMsg)
        fetchAuditData()
        return
      }

      // Helper parser for SKU or Order cards
      const invDetails = res.inventory_details || null
      const firstItem = invDetails?.items?.[0] || null
      const isInventory = res.agent_used === 'inventory_agent' || !!invDetails
      const hasSku = !!firstItem || text.toUpperCase().includes('SKU-') || res.response?.includes('SKU-') || (res.routing?.extracted_params?.sku)
      const hasOrder = text.includes('#4521') || res.response?.includes('#4521') || (res.routing?.extracted_params?.order_id)

      const skuData = firstItem ? {
        sku: firstItem.sku,
        name: firstItem.name,
        location: firstItem.location,
        aisle: firstItem.aisle || 12,
        shelf: firstItem.shelf || 'B3',
        tier: firstItem.tier || 'B',
        bay: firstItem.bay || 'Bay 04',
        stock: `${firstItem.quantity_on_hand} ${firstItem.unit} (${firstItem.status.replace('_', ' ')})`,
        available: firstItem.available_quantity,
        status: firstItem.status,
        rawItem: firstItem
      } : (hasSku ? {
        sku: res.routing?.extracted_params?.sku || 'SKU-4521',
        name: 'Warehouse Stock Item',
        location: 'Aisle 12, Shelf B3, Bay 04',
        aisle: 12,
        shelf: 'B3',
        tier: 'B',
        bay: 'Bay 04',
        stock: '340 units available'
      } : null)

      const fulfillmentDetails = res.fulfillment_details || null

      const assistantMsg = {
        id: Date.now() + 1,
        role: 'assistant',
        content: res.response || 'Warehouse query coordinated and dispatched to specialist agent.',
        routing: res.routing || {
          target_agent: res.agent_used || 'coordinator',
          confidence: 0.95,
          latency_ms: 28
        },
        inventory_details: invDetails,
        fulfillment_details: fulfillmentDetails,
        skuData,
        metadata: {
          agent_used: res.agent_used,
          audit: res.audit,
          inventory_details: invDetails,
          fulfillment_details: fulfillmentDetails
        },
        timestamp: new Date()
      }

      setMessages((prev) => [...prev, assistantMsg])
      setSelectedArtifactMessage(assistantMsg)
      
      // Auto open visualizer for inventory inquiries
      if (isInventory || skuData) {
        setArtifactTab('bay_visualizer')
        setArtifactOpen(true)
      }
      
      fetchAuditData()
    } catch (err) {
      const rawMsg = err.response?.data?.detail || err.message || ''
      const isQuotaError = (
        err.response?.status === 429 ||
        /quota|resource_exhausted|rate.?limit|api.?key|tokens?.?limit|exceeded/i.test(rawMsg)
      )

      if (isQuotaError) {
        addToast({
          type: 'error',
          title: 'API Key Quota Exhausted',
          message: 'The LLM API key has run out of tokens or hit its rate limit. Check your GEMINI_API_KEY or GROQ_API_KEY in the .env file and retry.',
        })
      } else if (err.response?.status === 401) {
        addToast({
          type: 'warning',
          title: 'Session Expired',
          message: 'Your login session has expired. Please log out and log back in.',
        })
      } else {
        addToast({
          type: 'error',
          title: 'Agent Error',
          message: rawMsg || 'Could not reach the Coordinator Agent. Make sure the backend is running on port 8000.',
        })
      }

      const errorMsg = {
        id: Date.now() + 1,
        role: 'assistant',
        status: 'error',
        content: isQuotaError
          ? 'API key quota exhausted. The LLM could not respond. Please check your API key limits.'
          : `Error contacting Coordinator Agent: ${rawMsg}`,
        timestamp: new Date()
      }
      setMessages((prev) => [...prev, errorMsg])
    } finally {
      setIsLoading(false)
    }
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

  // New Chat
  const handleNewChat = () => {
    setMessages([])
    setActiveChatId(null)
  }

  // Select Chat from History
  const handleSelectChat = (chatId) => {
    setActiveChatId(chatId)
    const chat = chatHistory.find((c) => c.id === chatId)
    if (chat) {
      setMessages([
        {
          id: Date.now(),
          role: 'user',
          content: chat.title,
          senderName: currentUser?.name || 'Operator',
          timestamp: chat.timestamp
        },
        {
          id: Date.now() + 1,
          role: 'assistant',
          content: `Reopened session: ${chat.title}. All warehouse telemetry and specialist routing decisions restored.`,
          routing: {
            target_agent: chat.title.includes('SKU') ? 'inventory_agent' : chat.title.includes('Order') ? 'fulfillment_agent' : 'knowledge_agent',
            confidence: 0.98,
            latency_ms: 22
          },
          skuData: chat.title.includes('SKU') ? {
            sku: 'SKU-4521',
            location: 'Aisle 12, Shelf B3, Bay 04',
            stock: '350 units available'
          } : null,
          orderData: chat.title.includes('Order') ? {
            id: '#4521',
            status: 'In Transit — On Schedule',
            carrier: 'FreightExpress • Priority 1'
          } : null,
          timestamp: new Date()
        }
      ])
    }
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
        chatHistory={chatHistory}
        activeChatId={activeChatId}
        onSelectChat={handleSelectChat}
        onNewChat={handleNewChat}
        onClearHistory={() => setChatHistory([])}
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
        <main className="claude-center-canvas spline-active-canvas">
          {/* Ambient Lighting & Micro-Grid Atmosphere */}
          <div className="ambient-canvas-glow" />

          {/* Spline 3D Scene */}
          <SplineScene isChatActive={messages.length > 0} />

          {messages.length === 0 ? (
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
                      setSelectedArtifactMessage(msg)
                      setArtifactTab('bay_visualizer')
                      setArtifactOpen(true)
                    }}
                    onInspectOrder={() => {
                      setSelectedArtifactMessage(msg)
                      setArtifactTab('order_timeline')
                      setArtifactOpen(true)
                    }}
                    onSendQuery={(queryText) => {
                      handleSendMessage({
                        text: queryText,
                        attachments: [],
                        mode: 'auto',
                        targetAgent: 'auto'
                      })
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

      {/* Global Toast Notifications */}
      <ToastContainer toasts={toasts} remove={removeToast} />
    </div>
  )
}
