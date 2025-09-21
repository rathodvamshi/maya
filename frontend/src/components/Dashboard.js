// frontend/src/components/Dashboard.js

import React, { useEffect, useReducer, useCallback, useMemo } from 'react';
// ... (all other imports remain the same)
import chatService from '../services/chatService';
import sessionService from '../services/sessionService';
import authService from '../services/auth';
import '../styles/Dashboard.css';

import ChatWindowNew from './ChatWindowNew';
import RightSidebarNew from './RightSidebarNew';
import LeftSidebarNew from './LeftSidebarNew';
import LoadingSpinner from './LoadingSpinner';
import ErrorDisplay from './ErrorDisplay';
import ChatSkeletonLoader from './ChatSkeletonLoader';


// --- The Reducer and Custom Hook sections remain completely the same ---
// No changes are needed in this logic.

const initialState = {
  messages: [],
  sessions: [],
  activeSessionId: null,
  input: '',
  status: 'idle', 
  error: null,
  currentUserEmail: '',
  pendingTasks: [],
  currentPage: 1,
  hasMoreMessages: true,
};

function chatReducer(state, action) {
  // ... (no changes in the reducer logic)
  switch (action.type) {
    case 'INITIAL_LOAD_START':
      return { ...state, status: 'pageLoading' };
    case 'INITIAL_LOAD_SUCCESS':
      return { ...state, status: 'idle', sessions: action.payload.sessions, messages: [action.payload.initialMessage] };
    case 'INITIAL_LOAD_ERROR':
      return { ...state, status: 'error', error: action.payload };
    
    case 'SELECT_SESSION_START':
      return { ...state, status: 'sessionLoading', activeSessionId: action.payload, messages: [], currentPage: 1, hasMoreMessages: true };
    case 'SELECT_SESSION_SUCCESS':
      return { ...state, status: 'idle', messages: action.payload.messages || [], hasMoreMessages: action.payload.hasMore };
    case 'SELECT_SESSION_ERROR':
      return { ...state, status: 'error', error: action.payload };

    case 'SEND_MESSAGE_START':
      return { ...state, status: 'loading', input: '', messages: [...state.messages, action.payload.userMessage] };
    case 'SEND_MESSAGE_SUCCESS':
      return { ...state, status: 'idle', messages: [...state.messages, action.payload.assistantMessage] };
    case 'SEND_MESSAGE_ERROR':
      return { ...state, status: 'error', error: action.payload, messages: [...state.messages, { sender: 'assistant', text: 'Sorry, an error occurred.' }] };
    
    case 'NEW_SESSION_CREATED':
      return { ...state, activeSessionId: action.payload.sessionId, sessions: action.payload.updatedSessions };

    case 'NEW_CHAT':
      return { ...state, activeSessionId: null, messages: action.payload, status: 'idle' };

    case 'UPDATE_SESSIONS':
      return { ...state, sessions: action.payload };
    
    case 'SET_INPUT':
      return { ...state, input: action.payload };

    case 'SET_USER_EMAIL':
      return { ...state, currentUserEmail: action.payload };
      
    default:
      throw new Error(`Unhandled action type: ${action.type}`);
  }
}

const useChatManager = ({ state, dispatch }) => {
    // ... (no changes in the custom hook logic)
    const initialMessage = useMemo(
        () => ({ sender: 'assistant', text: 'Hello! How can I assist you today?' }),
        []
      );
    
      const loadSessions = useCallback(async () => {
        try {
          const response = await sessionService.getSessions();
          dispatch({ type: 'UPDATE_SESSIONS', payload: response.data });
          return response.data;
        } catch (err) {
          console.error("Failed to load sessions:", err);
          throw new Error("Could not load sessions.");
        }
      }, [dispatch]);
    
      const loadInitialData = useCallback(async () => {
        dispatch({ type: 'INITIAL_LOAD_START' });
        try {
          const sessions = await loadSessions();
          dispatch({ type: 'INITIAL_LOAD_SUCCESS', payload: { sessions, initialMessage } });
        } catch (err) {
          dispatch({ type: 'INITIAL_LOAD_ERROR', payload: err.message });
        }
      }, [dispatch, loadSessions, initialMessage]);
    
      const handleSelectSession = useCallback(async (sessionId) => {
        if (!sessionId || sessionId === state.activeSessionId) return;
        dispatch({ type: 'SELECT_SESSION_START', payload: sessionId });
        try {
          const response = await sessionService.getSessionMessages(sessionId, 1);
          const hasMore = (response.data.messages?.length || 0) < response.data.totalMessages;
          dispatch({ type: 'SELECT_SESSION_SUCCESS', payload: { messages: response.data.messages, hasMore } });
        } catch (err) {
          console.error("Failed to load session:", err);
          dispatch({ type: 'SELECT_SESSION_ERROR', payload: 'Could not load chat history.' });
        }
      }, [state.activeSessionId, dispatch]);
    
      const handleNewChat = useCallback(() => {
        dispatch({ type: 'NEW_CHAT', payload: [initialMessage] });
      }, [dispatch, initialMessage]);
    
      const handleDeleteSession = useCallback(async (sessionId) => {
        try {
          await sessionService.deleteSession(sessionId);
          if (state.activeSessionId === sessionId) {
            handleNewChat();
          }
          await loadSessions();
        } catch (err) {
          dispatch({ type: 'INITIAL_LOAD_ERROR', payload: 'Could not delete the session.' });
        }
      }, [state.activeSessionId, dispatch, loadSessions, handleNewChat]);
    
      const handleSendMessage = useCallback(async (e) => {
        e.preventDefault();
        if (!state.input.trim() || state.status === 'loading') return;
    
        const userMessage = { sender: 'user', text: state.input };
        dispatch({ type: 'SEND_MESSAGE_START', payload: { userMessage } });
        
        try {
          if (!state.activeSessionId) {
            const newChatResponse = await chatService.startNewChat(userMessage.text);
            const assistantMessage = { sender: 'assistant', text: newChatResponse.data.response_text };
            const updatedSessions = await loadSessions();
            dispatch({ type: 'NEW_SESSION_CREATED', payload: { sessionId: newChatResponse.data.session_id, updatedSessions } });
            dispatch({ type: 'SEND_MESSAGE_SUCCESS', payload: { assistantMessage } });
          } else {
            const continueChatResponse = await chatService.sendMessage(state.activeSessionId, userMessage.text);
            const assistantMessage = { sender: 'assistant', text: continueChatResponse.data.response_text };
            dispatch({ type: 'SEND_MESSAGE_SUCCESS', payload: { assistantMessage } });
          }
        } catch (error) {
          console.error("Error sending message:", error);
          dispatch({ type: 'SEND_MESSAGE_ERROR', payload: error.message });
        }
      }, [state.activeSessionId, state.input, state.status, dispatch, loadSessions]);
      
      return useMemo(() => ({
        loadInitialData,
        handleSelectSession,
        handleNewChat,
        handleDeleteSession,
        handleSendMessage,
      }), [loadInitialData, handleSelectSession, handleNewChat, handleDeleteSession, handleSendMessage]);
};


// ==================================================
// 🔹 Main Dashboard Component
// ==================================================

const Dashboard = () => {
  const [state, dispatch] = useReducer(chatReducer, initialState);
  const handlers = useChatManager({ state, dispatch });
  
  const { 
    status, error, sessions, activeSessionId, 
    messages, input, currentUserEmail, pendingTasks 
  } = state;

  useEffect(() => {
    const user = authService.getCurrentUser();
    if (user?.access_token) {
      try {
        const tokenData = JSON.parse(atob(user.access_token.split('.')[1]));
        dispatch({ type: 'SET_USER_EMAIL', payload: tokenData.sub });
      } catch (e) { console.error("Failed to decode token:", e); }
    }
    handlers.loadInitialData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (status === 'pageLoading') return <LoadingSpinner />;
  if (status === 'error') return <ErrorDisplay message={error} onRetry={handlers.loadInitialData} />;

  return (
    <div className="dashboard-container">
      <LeftSidebarNew
        sessions={sessions}
        activeSessionId={activeSessionId}
        onNewChat={handlers.handleNewChat}
        onSelectSession={handlers.handleSelectSession}
        onDeleteSession={handlers.handleDeleteSession}
      />
      <main className="dashboard-main">
        {status === 'sessionLoading'
          ? <ChatSkeletonLoader />
          : <ChatWindowNew
              messages={messages}
              isLoading={status === 'loading'}
              activeSessionId={activeSessionId} // <-- ADDED: Pass session ID for feedback submissions
            />
        }
        <form className="chat-input-area" onSubmit={handlers.handleSendMessage}>
          <input
            type="text"
            className="chat-input"
            placeholder="Type your message here..."
            value={input}
            onChange={(e) => dispatch({ type: 'SET_INPUT', payload: e.target.value })}
            disabled={status === 'loading'}
          />
          <button type="submit" className="send-button" disabled={status === 'loading'}>
            {status === 'loading' ? 'Sending...' : 'Send'}
          </button>
        </form>
      </main>
      <RightSidebarNew 
        currentUserEmail={currentUserEmail} 
        pendingTasks={pendingTasks} 
      />
    </div>
  );
};

export default Dashboard;