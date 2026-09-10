import React, { useState } from 'react'
import {
  Plus,
  Warehouse,
  Truck,
  ShieldCheck,
  Activity,
  MessageSquare,
  LogOut,
  ChevronDown,
  Trash2,
  PanelLeftClose,
  Sparkles,
  Boxes
} from 'lucide-react'

export default function Sidebar({
  isOpen,
  onToggle,
  chatHistory,
  activeChatId,
  onSelectChat,
  onNewChat,
  onClearHistory,
  currentUser,
  onLogout,
  onOpenArtifactTab,
  onSwitchRoleQuick
}) {
  const [userDropdownOpen, setUserDropdownOpen] = useState(false)

  return (
    <aside className={`claude-sidebar ${isOpen ? 'open' : 'closed'}`}>
      {/* Brand Header */}
      <div className="sidebar-brand-row">
        <div className="sidebar-brand">
          <div className="sidebar-emblem-glow">
            <img src="/intelliwms_logo.png" alt="IntelliWMS" className="sidebar-logo-img" />
          </div>
          <div className="sidebar-brand-text">
            <h2>IntelliWMS</h2>
            <span>Supply Chain Intelligence</span>
          </div>
        </div>
        <button
          onClick={onToggle}
          className="sidebar-toggle-btn"
          title={isOpen ? 'Collapse Sidebar' : 'Expand Sidebar'}
        >
          <PanelLeftClose size={16} />
        </button>
      </div>

      {/* New Query / Chat Button */}
      <div className="sidebar-new-query-wrapper">
        <button onClick={onNewChat} className="btn-new-query">
          <Plus size={16} />
          <span>New Warehouse Query</span>
        </button>
      </div>

      {/* Primary Operational Modules */}
      <div className="sidebar-section">
        <div className="sidebar-section-title">
          <span>Operational Modules</span>
          <Warehouse size={12} />
        </div>

        <button
          className="sidebar-nav-item"
          onClick={() => onOpenArtifactTab('bay_visualizer')}
        >
          <div className="nav-item-left">
            <Warehouse size={15} className="text-amber" />
            <span>Floor & Bay Map</span>
          </div>
          <span className="nav-shortcut">Bay</span>
        </button>

        <button
          className="sidebar-nav-item"
          onClick={() => onOpenArtifactTab('order_timeline')}
        >
          <div className="nav-item-left">
            <Truck size={15} className="text-blue" />
            <span>Order Fulfillment</span>
          </div>
          <span className="nav-shortcut">Fleet</span>
        </button>

        <button
          className="sidebar-nav-item"
          onClick={() => onOpenArtifactTab('rbac_claims')}
        >
          <div className="nav-item-left">
            <ShieldCheck size={15} className="text-emerald" />
            <span>JWT & RBAC Shield</span>
          </div>
          <span className="nav-shortcut">Token</span>
        </button>

        <button
          className="sidebar-nav-item"
          onClick={() => onOpenArtifactTab('soc_audit')}
        >
          <div className="nav-item-left">
            <Activity size={15} className="text-coral" />
            <span>Security SOC Stream</span>
          </div>
          <span className="nav-shortcut">Audit</span>
        </button>
      </div>

      {/* Session History & Tasks */}
      <div className="sidebar-section chat-history-section">
        <div className="sidebar-section-title">
          <span>Recent Queries & Tasks</span>
          {chatHistory.length > 0 && (
            <button
              onClick={onClearHistory}
              className="clear-history-icon-btn"
              title="Clear history"
            >
              <Trash2 size={12} />
            </button>
          )}
        </div>

        <div className="sidebar-history-list">
          {chatHistory.length === 0 ? (
            <div className="empty-history-notice">
              <Boxes size={14} className="text-muted" />
              <span>No recent queries yet</span>
            </div>
          ) : (
            chatHistory.map((item) => (
              <button
                key={item.id}
                onClick={() => onSelectChat(item.id)}
                className={`history-item-btn ${activeChatId === item.id ? 'active' : ''}`}
              >
                <MessageSquare size={13} className="history-msg-icon" />
                <span className="history-item-title">{item.title}</span>
                <span className="history-item-time">
                  {new Date(item.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </span>
              </button>
            ))
          )}
        </div>
      </div>

      {/* Bottom User Profile Section */}
      <div className="sidebar-user-footer">
        <div className="user-profile-tile" onClick={() => setUserDropdownOpen(!userDropdownOpen)}>
          <div className="user-avatar-pill">
            {currentUser?.name?.[0]?.toUpperCase() || currentUser?.username?.[0]?.toUpperCase() || 'U'}
          </div>
          <div className="user-info-text">
            <div className="user-name-line">
              <span className="user-display-name">
                {currentUser?.name || currentUser?.username || 'Operator'}
              </span>
              <span className={`role-tag role-tag-${currentUser?.role || 'staff'}`}>
                {currentUser?.role?.toUpperCase() || 'STAFF'}
              </span>
            </div>
            <span className="user-sub-label">Verified Cryptographic Session</span>
          </div>
          <ChevronDown size={14} className={`dropdown-chevron ${userDropdownOpen ? 'rotated' : ''}`} />
        </div>

        {userDropdownOpen && (
          <div className="sidebar-user-menu">
            <div className="menu-header">
              <span>Switch Simulated Role</span>
            </div>
            <div className="role-switch-grid">
              <button
                className={`role-choice-btn ${currentUser?.role === 'staff' ? 'active' : ''}`}
                onClick={() => {
                  onSwitchRoleQuick('staff')
                  setUserDropdownOpen(false)
                }}
              >
                Staff (Floor)
              </button>
              <button
                className={`role-choice-btn ${currentUser?.role === 'manager' ? 'active' : ''}`}
                onClick={() => {
                  onSwitchRoleQuick('manager')
                  setUserDropdownOpen(false)
                }}
              >
                Manager (Supervisor)
              </button>
              <button
                className={`role-choice-btn ${currentUser?.role === 'admin' ? 'active' : ''}`}
                onClick={() => {
                  onSwitchRoleQuick('admin')
                  setUserDropdownOpen(false)
                }}
              >
                Admin (SOC)
              </button>
            </div>

            <div className="menu-divider" />

            <button onClick={onLogout} className="menu-logout-btn">
              <LogOut size={14} />
              <span>Sign Out Session</span>
            </button>
          </div>
        )}
      </div>
    </aside>
  )
}
