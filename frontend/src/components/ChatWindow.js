// frontend/src/components/ChatWindow.js

import React, { useRef, useEffect, useState, useCallback } from 'react';
import { Copy, ThumbsUp, Volume2, VolumeX, Edit3, Bot, User } from 'lucide-react';
import '../styles/ChatWindow.css';

const ChatWindow = ({
  messages,
  isLoading,
  onFetchMore,       // Callback for loading older messages
  hasMoreMessages    // Boolean: are there more messages to fetch
}) => {
  const chatWindowRef = useRef(null);
  const topObserver = useRef(null);

  const [copiedIndex, setCopiedIndex] = useState(null);
  const [likedMessages, setLikedMessages] = useState(new Set());
  const [speakingIndex, setSpeakingIndex] = useState(null);

  // Scroll to bottom whenever new messages are added
  useEffect(() => {
    if (chatWindowRef.current) {
      chatWindowRef.current.scrollTop = chatWindowRef.current.scrollHeight;
    }
  }, [messages]);

  // Infinite scroll: observe top of chat
  const topElementRef = useCallback(node => {
    if (isLoading || !hasMoreMessages) return;
    if (topObserver.current) topObserver.current.disconnect();

    topObserver.current = new IntersectionObserver(entries => {
      if (entries[0].isIntersecting && hasMoreMessages) {
        onFetchMore();
      }
    });

    if (node) topObserver.current.observe(node);
  }, [isLoading, hasMoreMessages, onFetchMore]);

  // Copy message to clipboard
  const copyToClipboard = async (text, index) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedIndex(index);
      setTimeout(() => setCopiedIndex(null), 2000);
    } catch (err) {
      console.error('Failed to copy text: ', err);
    }
  };

  // Toggle like for message
  const toggleLike = (index) => {
    const newLikedMessages = new Set(likedMessages);
    likedMessages.has(index) ? newLikedMessages.delete(index) : newLikedMessages.add(index);
    setLikedMessages(newLikedMessages);
  };

  // Read aloud message
  const toggleSpeak = (text, index) => {
    if (speakingIndex === index) {
      window.speechSynthesis.cancel();
      setSpeakingIndex(null);
    } else {
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.onend = () => setSpeakingIndex(null);
      window.speechSynthesis.speak(utterance);
      setSpeakingIndex(index);
    }
  };

  // Edit message handler (user-only messages)
  const editMessage = (index) => {
    console.log('Edit message:', index);
    // Implement your edit modal or inline editing here
  };

  return (
    <div className="chat-container">
      <div className="chat-window" ref={chatWindowRef}>

        {/* Top element to trigger loading older messages */}
        {hasMoreMessages && <div ref={topElementRef} style={{height: '1px'}}></div>}

        {/* Messages */}
        {messages.map((msg, index) => (
          <div key={index} className={`message-wrapper ${msg.sender}`}>
            <div className="avatar">
              {msg.sender === 'user' ? <User size={20} className="avatar-icon user-icon" />
                                      : <Bot size={20} className="avatar-icon ai-icon" />}
            </div>

            <div className="message-content">
              <div className={`chat-message ${msg.sender}`}>
                <p>{msg.text}</p>
              </div>

              <div className="message-actions">
                {/* Copy */}
                <button
                  className={`action-btn copy-btn ${copiedIndex === index ? 'copied' : ''}`}
                  onClick={() => copyToClipboard(msg.text, index)}
                  title="Copy message"
                >
                  <Copy size={14} />
                  <span className="tooltip">{copiedIndex === index ? 'Copied!' : 'Copy'}</span>
                </button>

                {/* Like */}
                <button
                  className={`action-btn like-btn ${likedMessages.has(index) ? 'liked' : ''}`}
                  onClick={() => toggleLike(index)}
                  title="Like message"
                >
                  <ThumbsUp size={14} />
                  <span className="tooltip">{likedMessages.has(index) ? 'Liked' : 'Like'}</span>
                </button>

                {/* Text-to-speech */}
                <button
                  className={`action-btn speak-btn ${speakingIndex === index ? 'speaking' : ''}`}
                  onClick={() => toggleSpeak(msg.text, index)}
                  title={speakingIndex === index ? 'Stop speaking' : 'Read aloud'}
                >
                  {speakingIndex === index ? <VolumeX size={14} /> : <Volume2 size={14} />}
                  <span className="tooltip">{speakingIndex === index ? 'Stop' : 'Speak'}</span>
                </button>

                {/* Edit (user only) */}
                {msg.sender === 'user' && (
                  <button
                    className="action-btn edit-btn"
                    onClick={() => editMessage(index)}
                    title="Edit message"
                  >
                    <Edit3 size={14} />
                    <span className="tooltip">Edit</span>
                  </button>
                )}
              </div>
            </div>
          </div>
        ))}

        {/* Typing indicator */}
        {isLoading && (
          <div className="message-wrapper assistant">
            <div className="avatar">
              <Bot size={20} className="avatar-icon ai-icon" />
            </div>
            <div className="message-content">
              <div className="chat-message assistant typing">
                <div className="typing-indicator">
                  <span></span>
                  <span></span>
                  <span></span>
                </div>
                <p className="typing-text">AI is thinking...</p>
              </div>
            </div>
          </div>
        )}

      </div>
    </div>
  );
};

export default ChatWindow;
