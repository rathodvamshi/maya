import React, { useRef, useEffect, useState } from 'react';
import { Copy, ThumbsUp, Volume2, VolumeX, Edit3, Bot, User } from 'lucide-react';
import '../styles/ChatWindow.css';

const ChatWindow = ({ messages, isLoading }) => {
  const chatWindowRef = useRef(null);
  const [copiedIndex, setCopiedIndex] = useState(null);
  const [likedMessages, setLikedMessages] = useState(new Set());
  const [speakingIndex, setSpeakingIndex] = useState(null);

  useEffect(() => {
    if (chatWindowRef.current) {
      chatWindowRef.current.scrollTop = chatWindowRef.current.scrollHeight;
    }
  }, [messages]);

  const copyToClipboard = async (text, index) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedIndex(index);
      setTimeout(() => setCopiedIndex(null), 2000);
    } catch (err) {
      console.error('Failed to copy text: ', err);
    }
  };

  const toggleLike = (index) => {
    const newLikedMessages = new Set(likedMessages);
    if (newLikedMessages.has(index)) {
      newLikedMessages.delete(index);
    } else {
      newLikedMessages.add(index);
    }
    setLikedMessages(newLikedMessages);
  };

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

  const editMessage = (index) => {
    console.log('Edit message:', index);
  };

  return (
    <div className="chat-container">
      <div className="chat-window" ref={chatWindowRef}>
        {messages.map((msg, index) => (
          <div key={index} className={`message-wrapper ${msg.sender}`}>
            <div className="avatar">
              {msg.sender === 'user' ? (
                <User size={20} className="avatar-icon user-icon" />
              ) : (
                <Bot size={20} className="avatar-icon ai-icon" />
              )}
            </div>

            <div className="message-content">
              <div className={`chat-message ${msg.sender}`}>
                <p>{msg.text}</p>
              </div>

              <div className="message-actions">
                <button
                  className={`action-btn copy-btn ${copiedIndex === index ? 'copied' : ''}`}
                  onClick={() => copyToClipboard(msg.text, index)}
                  title="Copy message"
                >
                  <Copy size={14} />
                  <span className="tooltip">{copiedIndex === index ? 'Copied!' : 'Copy'}</span>
                </button>

                <button
                  className={`action-btn like-btn ${likedMessages.has(index) ? 'liked' : ''}`}
                  onClick={() => toggleLike(index)}
                  title="Like message"
                >
                  <ThumbsUp size={14} />
                  <span className="tooltip">{likedMessages.has(index) ? 'Liked' : 'Like'}</span>
                </button>

                <button
                  className={`action-btn speak-btn ${speakingIndex === index ? 'speaking' : ''}`}
                  onClick={() => toggleSpeak(msg.text, index)}
                  title={speakingIndex === index ? 'Stop speaking' : 'Read aloud'}
                >
                  {speakingIndex === index ? <VolumeX size={14} /> : <Volume2 size={14} />}
                  <span className="tooltip">{speakingIndex === index ? 'Stop' : 'Speak'}</span>
                </button>

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
