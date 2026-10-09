import React, { useState } from 'react'
import {
  SquarePen,
  Search,
  Warehouse,
  Truck,
  Settings,
  PanelLeftClose,
  PanelLeft,
  Trash2,
  LogOut,
  Sparkles,
  Crown,
  Compass,
  X
} from 'lucide-react'

export default function Sidebar({
  isOpen,
  onToggle,
  chatHistory = [],
  activeChatId,
  onSelectChat,
  onNewChat,
  onClearHistory,
  currentUser,
  onLogout,
  onOpenArtifactTab,
  onSwitchRoleQuick,
  onOpenCommercializationModal,
  onOpenPricingModal
}) {
  const [userDropdownOpen, setUserDropdownOpen] = useState(false)
  const [activeMode, setActiveMode] = useState('chat') // 'chat' | 'ops'
  const [isSearching, setIsSearching] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')

  const filteredHistory = searchQuery.trim()
    ? chatHistory.filter((item) =>
        item.title?.toLowerCase().includes(searchQuery.toLowerCase())
      )
    : chatHistory

  const displayName = currentUser?.name || currentUser?.username || 'Signed-in user'
  const userInitial =
    currentUser?.name?.[0]?.toUpperCase() ||
    currentUser?.username?.[0]?.toUpperCase() ||
    'U'

  return (
    <aside className={`gemini-sidebar ${isOpen ? 'expanded' : 'collapsed'}`}>
      {/* 1. TOP BRAND & TOGGLE ROW */}
      <div className="gemini-sidebar-header">
        {isOpen ? (
          <>
            <div className="gemini-brand-left" onClick={onNewChat} role="button" title="IntelliWMS Home">
              <div className="gemini-brand-logo-wrap">
                <img
                  src="/intelliwms_logo.png"
                  alt="IntelliWMS"
                  className="gemini-brand-logo-img"
                  onError={(e) => {
                    e.target.style.display = 'none'
                  }}
                />
                <Sparkles size={18} className="gemini-brand-fallback-sparkle" />
              </div>
              <span className="gemini-brand-title">IntelliWMS</span>
            </div>
            <button
              onClick={onToggle}
              className="gemini-icon-btn"
              title="Collapse sidebar"
            >
              <PanelLeftClose size={18} />
            </button>
          </>
        ) : (
          <div className="gemini-collapsed-top">
            <div className="gemini-brand-logo-wrap" title="IntelliWMS" onClick={onToggle}>
              <img
                src="/intelliwms_logo.png"
                alt="IntelliWMS"
                className="gemini-brand-logo-img"
                onError={(e) => {
                  e.target.style.display = 'none'
                }}
              />
              <Sparkles size={18} className="gemini-brand-fallback-sparkle" />
            </div>
            <button
              onClick={onToggle}
              className="gemini-icon-btn"
              title="Expand sidebar"
            >
              <PanelLeft size={18} />
            </button>
          </div>
        )}
      </div>

      {/* 2. MODE SWITCHER PILL (Expanded Only, matching Gemini's Chat | Spark) */}
      {isOpen && (
        <div className="gemini-pill-tabs-wrapper">
          <div className="gemini-pill-tabs">
            <button
              className={`gemini-pill-tab ${activeMode === 'chat' ? 'active' : ''}`}
              onClick={() => setActiveMode('chat')}
            >
              Chat
            </button>
            <button
              className={`gemini-pill-tab ${activeMode === 'ops' ? 'active' : ''}`}
              onClick={() => {
                setActiveMode('ops')
                onOpenArtifactTab('bay_visualizer')
              }}
            >
              Hub <span className="gemini-tab-badge">LIVE</span>
            </button>
          </div>
        </div>
      )}

      {/* 3. SCROLLABLE ACTIONS & MODULES */}
      <div className="gemini-sidebar-body">
        {/* Action: New Query */}
        <button
          onClick={onNewChat}
          className={`gemini-nav-item ${isOpen ? 'item-expanded' : 'item-collapsed'}`}
          title={!isOpen ? 'New query' : undefined}
        >
          <SquarePen size={18} className="gemini-item-icon" />
          {isOpen && <span className="gemini-item-label">New query</span>}
        </button>

        {/* Action: Search Queries */}
        <button
          onClick={() => {
            if (!isOpen) {
              onToggle()
              setIsSearching(true)
            } else {
              setIsSearching(!isSearching)
            }
          }}
          className={`gemini-nav-item ${isOpen ? 'item-expanded' : 'item-collapsed'} ${isSearching ? 'active-nav' : ''}`}
          title={!isOpen ? 'Search queries' : undefined}
        >
          <Search size={18} className="gemini-item-icon" />
          {isOpen && <span className="gemini-item-label">Search queries</span>}
        </button>

        {/* Inline Search Input if searching */}
        {isOpen && isSearching && (
          <div className="gemini-search-input-wrapper">
            <Search size={13} className="gemini-search-inner-icon" />
            <input
              type="text"
              placeholder="Search chats..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              autoFocus
              className="gemini-search-input"
            />
            {searchQuery && (
              <button
                onClick={() => setSearchQuery('')}
                className="gemini-search-clear-btn"
              >
                <X size={12} />
              </button>
            )}
          </div>
        )}

        {/* Operational Modules (Site Plan, Floor Map, Fleet, RBAC, SOC) */}
        <button
          onClick={() => onOpenArtifactTab('site_plan')}
          className={`gemini-nav-item ${isOpen ? 'item-expanded' : 'item-collapsed'}`}
          title={!isOpen ? 'Warehouse Site Plan' : undefined}
        >
          <Compass size={18} className="gemini-item-icon" />
          {isOpen && <span className="gemini-item-label">Warehouse Site Plan</span>}
        </button>

        <button
          onClick={() => onOpenArtifactTab('floor_map')}
          className={`gemini-nav-item ${isOpen ? 'item-expanded' : 'item-collapsed'}`}
          title={!isOpen ? 'Floor & Bay Map' : undefined}
        >
          <Warehouse size={18} className="gemini-item-icon" />
          {isOpen && <span className="gemini-item-label">Floor & Bay Map</span>}
        </button>

        <button
          onClick={() => onOpenArtifactTab('order_timeline')}
          className={`gemini-nav-item ${isOpen ? 'item-expanded' : 'item-collapsed'}`}
          title={!isOpen ? 'Order Fulfillment' : undefined}
        >
          <Truck size={18} className="gemini-item-icon" />
          {isOpen && <span className="gemini-item-label">Order Fulfillment</span>}
        </button>

        {/* 4. RECENT SECTION (Expanded Only, exactly like Gemini Image 2) */}
        {isOpen && (
          <div className="gemini-recent-section">
            <div className="gemini-recent-header">
              <span className="gemini-recent-title">Recent</span>
              {chatHistory.length > 0 && (
                <button
                  onClick={onClearHistory}
                  className="gemini-clear-btn"
                  title="Clear recent queries"
                >
                  <Trash2 size={12} />
                </button>
              )}
            </div>

            <div className="gemini-recent-list">
              {filteredHistory.length === 0 ? (
                <div className="gemini-empty-recent">
                  <span>{searchQuery ? 'No matching queries' : 'No recent queries'}</span>
                </div>
              ) : (
                filteredHistory.map((item) => {
                  const isActive = activeChatId === item.id
                  return (
                    <button
                      key={item.id}
                      onClick={() => onSelectChat(item.id)}
                      className={`gemini-recent-item ${isActive ? 'active' : ''}`}
                      title={item.title}
                    >
                      <span className="gemini-recent-item-text">{item.title}</span>
                    </button>
                  )
                })
              )}
            </div>
          </div>
        )}
      </div>

      {/* 4.5 UPGRADE WMS BUTTON */}
      <div className={`gemini-upgrade-section ${isOpen ? 'expanded' : 'collapsed'}`}>
        {isOpen ? (
          <button
            onClick={onOpenPricingModal || onOpenCommercializationModal}
            className="gemini-upgrade-btn"
            title="Upgrade WMS — SaaS Pricing & Plans"
          >
            <div className="upgrade-btn-content">
              <div className="upgrade-icon-wrap">
                <Crown size={15} className="upgrade-crown-icon" />
              </div>
              <div className="upgrade-text-wrap">
                <div className="upgrade-title-row">
                  <span className="upgrade-title">Upgrade WMS</span>
                  <span className="upgrade-pill-badge">PRO</span>
                </div>
                <span className="upgrade-subtitle">Pricing & Plans</span>
              </div>
            </div>
            <Sparkles size={14} className="upgrade-sparkle-right" />
          </button>
        ) : (
          <button
            onClick={onOpenPricingModal || onOpenCommercializationModal}
            className="gemini-upgrade-btn-collapsed"
            title="Upgrade WMS — SaaS Pricing & Plans"
          >
            <Crown size={16} className="upgrade-crown-icon" />
            <span className="upgrade-dot-pulse" />
          </button>
        )}
      </div>

      {/* 5. BOTTOM USER FOOTER */}
      <div className="gemini-sidebar-footer">
        {isOpen ? (
          <div className="gemini-user-row">
            <div
              className="gemini-user-info-group"
              onClick={() => setUserDropdownOpen(!userDropdownOpen)}
            >
              <div className="gemini-avatar-circle">
                {userInitial}
              </div>
              <div className="gemini-user-details">
                <span className="gemini-user-name">
                  {displayName}
                </span>
                <span className="gemini-user-role">
                  {currentUser?.role ? currentUser.role.charAt(0).toUpperCase() + currentUser.role.slice(1) : 'Staff'}
                </span>
              </div>
            </div>

            <button
              onClick={() => setUserDropdownOpen(!userDropdownOpen)}
              className={`gemini-icon-btn ${userDropdownOpen ? 'active' : ''}`}
              title="Settings & session"
            >
              <Settings size={18} />
            </button>
          </div>
        ) : (
          <div className="gemini-collapsed-footer">
            <button
              onClick={() => setUserDropdownOpen(!userDropdownOpen)}
              className="gemini-icon-btn"
              title="Settings & session"
            >
              <Settings size={18} />
            </button>
            <div
              className="gemini-avatar-circle"
              onClick={() => {
                onToggle()
                setUserDropdownOpen(true)
              }}
              title={displayName}
            >
              {userInitial}
            </div>
          </div>
        )}

        {/* User Role Switch / Sign Out Dropdown Menu */}
        {userDropdownOpen && (
          <div className="gemini-user-dropdown-menu">
            <div className="gemini-dropdown-header">
              <span>Switch Simulated Role</span>
            </div>
            <div className="gemini-role-list">
              <button
                className={`gemini-dropdown-item ${currentUser?.role === 'staff' ? 'active' : ''}`}
                onClick={() => {
                  onSwitchRoleQuick('staff')
                  setUserDropdownOpen(false)
                }}
              >
                <span>Staff (Floor)</span>
              </button>
              <button
                className={`gemini-dropdown-item ${currentUser?.role === 'manager' ? 'active' : ''}`}
                onClick={() => {
                  onSwitchRoleQuick('manager')
                  setUserDropdownOpen(false)
                }}
              >
                <span>Manager (Supervisor)</span>
              </button>
              <button
                className={`gemini-dropdown-item ${currentUser?.role === 'admin' ? 'active' : ''}`}
                onClick={() => {
                  onSwitchRoleQuick('admin')
                  setUserDropdownOpen(false)
                }}
              >
                <span>Admin (SOC)</span>
              </button>
            </div>

            <div className="gemini-dropdown-divider" />

            <button onClick={onLogout} className="gemini-dropdown-logout">
              <LogOut size={15} />
              <span>Sign Out Session</span>
            </button>
          </div>
        )}
      </div>
    </aside>
  )
}
