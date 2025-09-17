import React, { useState } from 'react';
import '../styles/LeftSidebar.css';

const chatSessions = [
  { id: 1, name: 'General', active: true },
  { id: 2, name: 'Project', active: false },
  { id: 3, name: 'Support', active: false }
];

const LeftSidebar = ({ onNewChat, onClearChat, onDeleteSession, onProfileClick, taskCount = 0 }) => {
  const [expanded, setExpanded] = useState(false);
  const [showProfile, setShowProfile] = useState(false);

  return (
    <aside
      className={`left-sidebar${expanded ? ' expanded' : ''}`}
      onMouseEnter={() => setExpanded(true)}
      onMouseLeave={() => { setExpanded(false); setShowProfile(false); }}
    >
      <div className="sidebar-icons">
        <div className="sidebar-icon profile-icon" title="Profile" onClick={() => setShowProfile(!showProfile)}>
          <svg width="24" height="24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="7" r="4"/><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/></svg>
        </div>
        <div className="sidebar-icon" title="New Chat" onClick={onNewChat}>
          <svg width="22" height="22" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="16"/><line x1="8" y1="12" x2="16" y2="12"/></svg>
        </div>
        <div className="sidebar-icon" title="Clear Chat" onClick={onClearChat}>
          <svg width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><line x1="10" y1="11" x2="10" y2="17"/><line x1="14" y1="11" x2="14" y2="17"/></svg>
        </div>
        <div className="sidebar-icon task-icon" title="Tasks">
          <svg width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>
          {taskCount > 0 && <span className="task-count-badge">{taskCount}</span>}
        </div>
      </div>
      {expanded && (
        <div className="sidebar-content">
          <h3 className="sidebar-title">Chats</h3>
          <ul className="chat-session-list">
            {chatSessions.map(session => (
              <li key={session.id} className={`chat-session-item${session.active ? ' active' : ''}`}>
                <span className="chat-session-icon">
                  <svg width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
                </span>
                <span className="chat-session-name">{session.name}</span>
                <button className="delete-session-btn" title="Delete" onClick={() => onDeleteSession(session.id)}>
                  <svg width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
      {showProfile && expanded && (
        <div className="profile-popup">
          <div className="profile-popup-content">
            <div className="profile-logo">👤</div>
            <button onClick={onProfileClick}>Profile</button>
            <button>Settings</button>
            <button>Logout</button>
          </div>
        </div>
      )}
    </aside>
  );
};

export default LeftSidebar;
