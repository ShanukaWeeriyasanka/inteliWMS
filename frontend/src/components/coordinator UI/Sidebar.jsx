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
  onOpenMap,
  onOpenFulfillment,
  onSwitchRoleQuick,
  onSwitchPlanQuick,
  onOpenCommercializationModal,
  onOpenPricingModal
}) {
  const [userDropdownOpen, setUserDropdownOpen] = useState(false)
  const [isSearching, setIsSearching] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')

  const plan = currentUser?.plan || 'starter'

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

      {/* 2. SCROLLABLE ACTIONS & MODULES */}
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

        {/* Warehouse Digital Twin Map: Available for Professional and Enterprise */}
        {plan !== 'starter' && onOpenMap && (
          <button
            onClick={onOpenMap}
            className={`gemini-nav-item ${isOpen ? 'item-expanded' : 'item-collapsed'}`}
            title={!isOpen ? 'Warehouse Map' : undefined}
          >
            <Warehouse size={18} className="gemini-item-icon" />
            {isOpen && <span className="gemini-item-label">Warehouse Map</span>}
          </button>
        )}

        {/* Order Fulfillment Dashboard: Available for Professional and Enterprise */}
        {plan !== 'starter' && onOpenFulfillment && (
          <button
            onClick={onOpenFulfillment}
            className={`gemini-nav-item ${isOpen ? 'item-expanded' : 'item-collapsed'}`}
            title={!isOpen ? 'Order Fulfillment' : undefined}
          >
            <Truck size={18} className="gemini-item-icon" />
            {isOpen && <span className="gemini-item-label">Order Fulfillment</span>}
          </button>
        )}

        {/* 4. RECENT SECTION */}
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
                  <span className="upgrade-title">
                    {plan === 'enterprise' ? 'Enterprise Plan' : plan === 'professional' ? 'Professional' : 'Upgrade Plan'}
                  </span>
                  <span className={`upgrade-pill-badge ${plan === 'enterprise' ? 'badge-ent' : 'badge-pro'}`}>
                    {plan.toUpperCase()}
                  </span>
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
                  {currentUser?.role ? currentUser.role.charAt(0).toUpperCase() + currentUser.role.slice(1) : 'Staff'} • {plan.toUpperCase()}
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

        {/* User Role & Plan Switch / Sign Out Dropdown Menu */}
        {userDropdownOpen && (
          <div className="gemini-user-dropdown-menu">
            <div className="gemini-dropdown-header">
              <span>Subscription Plan (Dev/Demo)</span>
            </div>
            <div className="gemini-role-list">
              <button
                className={`gemini-dropdown-item ${plan === 'starter' ? 'active' : ''}`}
                onClick={() => {
                  onSwitchPlanQuick && onSwitchPlanQuick('starter')
                  setUserDropdownOpen(false)
                }}
              >
                <span>Starter (Inventory Only)</span>
              </button>
              <button
                className={`gemini-dropdown-item ${plan === 'professional' ? 'active' : ''}`}
                onClick={() => {
                  onSwitchPlanQuick && onSwitchPlanQuick('professional')
                  setUserDropdownOpen(false)
                }}
              >
                <span>Professional (3 Specialists)</span>
              </button>
              <button
                className={`gemini-dropdown-item ${plan === 'enterprise' ? 'active' : ''}`}
                onClick={() => {
                  onSwitchPlanQuick && onSwitchPlanQuick('enterprise')
                  setUserDropdownOpen(false)
                }}
              >
                <span>Enterprise (All Agents + Auto)</span>
              </button>
            </div>

            <div className="gemini-dropdown-divider" />

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
