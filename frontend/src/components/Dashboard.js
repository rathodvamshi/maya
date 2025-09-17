    import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
    import chatService from '../services/chatService';
    import authService from '../services/auth';
    import '../styles/Dashboard.css';
    import ChatWindow from './ChatWindow';
    import RightSidebar from './RightSidebar';
    import LeftSidebar from './LeftSidebar';

    // --- Reusable Components ---
    const TaskModal = ({ task, onSave, onClose }) => {
        const [content, setContent] = useState(task ? task.content : "");
        const [dueDate, setDueDate] = useState(task ? task.due_date : "");

        const handleSubmit = (e) => {
            e.preventDefault();
            onSave({ ...task, content, due_date: dueDate });
        };

        return (
            <div className="task-modal-overlay" onClick={onClose}>
                <div className="task-modal-content" onClick={(e) => e.stopPropagation()}>
                    <h3>
                        {task ? "Edit Task" : (
                            <span className="modal-title-with-icon">
                                Create New Task
                                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="calendar-icon">
                                    <rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect>
                                    <line x1="16" y1="2" x2="16" y2="6"></line>
                                    <line x1="8" y1="2" x2="8" y2="6"></line>
                                    <line x1="3" y1="10" x2="21" y2="10"></line>
                                </svg>
                            </span>
                        )}
                    </h3>
                    <form onSubmit={handleSubmit}>
                        <div className="form-group">
                            <label>Task</label>
                            <input 
                                type="text" 
                                value={content} 
                                onChange={(e) => setContent(e.target.value)} 
                                placeholder="What needs to be done?" 
                                required 
                            />
                        </div>
                        <div className="form-group">
                            <label>Due Date</label>
                            <input 
                                type="text" 
                                value={dueDate} 
                                onChange={(e) => setDueDate(e.target.value)} 
                                placeholder="e.g., Tomorrow at 5pm" 
                                required 
                            />
                        </div>
                        <div className="modal-actions">
                            <button type="button" onClick={onClose} className="cancel-btn">Cancel</button>
                            <button type="submit" className="save-btn">Save Task</button>
                        </div>
                    </form>
                </div>
            </div>
        );
    };

    const LoadingSpinner = () => (
        <div className="loading-container">
            <div className="spinner"></div>
            <p>Loading Your Dashboard...</p>
        </div>
    );

    const ErrorDisplay = ({ message, onRetry }) => (
        <div className="loading-container">
            <p className="error-message">Sorry, something went wrong.</p>
            <p className="error-detail">{message}</p>
            <button onClick={onRetry} className="retry-btn">Try Again</button>
        </div>
    );

    // --- Main Dashboard Component ---
    const Dashboard = () => {
        const initialMessage = useMemo(
            () => ({ sender: 'assistant', text: 'Hello! How can I assist you today?' }),
            []
        );

        const [messages, setMessages] = useState([]);
        const [input, setInput] = useState('');
        const [isLoading, setIsLoading] = useState(false);
        const [isPageLoading, setIsPageLoading] = useState(true);
        const [error, setError] = useState(null);
        const [currentUserEmail, setCurrentUserEmail] = useState('');
        const [pendingTasks, setPendingTasks] = useState([]);
        const [completedTasks, setCompletedTasks] = useState([]);
        const [isModalOpen, setIsModalOpen] = useState(false);
        const [taskToEdit, setTaskToEdit] = useState(null);

        // chatWindowRef moved to ChatWindow component

        const loadInitialData = useCallback(async () => {
            setIsPageLoading(true);
            setError(null);
            try {
                const [historyResponse, pendingResponse, completedResponse] = await Promise.all([
                    chatService.getHistory(),
                    chatService.getTasks(),
                    chatService.getTaskHistory()
                ]);
                setMessages(historyResponse.data && historyResponse.data.length > 0 ? historyResponse.data : [initialMessage]);
                setPendingTasks(pendingResponse.data);
                setCompletedTasks(completedResponse.data);
            } catch (err) {
                console.error("Failed to load initial data:", err);
                setError("Could not connect to the server. Please check your connection and try again.");
            } finally {
                setIsPageLoading(false);
            }
        }, [initialMessage]);

        useEffect(() => {
            const user = authService.getCurrentUser();
            if (user && user.access_token) {
                try {
                    const tokenData = JSON.parse(atob(user.access_token.split('.')[1]));
                    setCurrentUserEmail(tokenData.sub);
                } catch (e) { console.error("Failed to decode token:", e); }
            }
            loadInitialData();
        }, [loadInitialData]);

        useEffect(() => {
            // Scrolling handled in ChatWindow component
        }, [messages]);

        const fetchAllTasks = async () => {
            try {
                const [pendingResponse, completedResponse] = await Promise.all([
                    chatService.getTasks(),
                    chatService.getTaskHistory()
                ]);
                setPendingTasks(pendingResponse.data);
                setCompletedTasks(completedResponse.data);
            } catch (error) {
                console.error("Failed to fetch tasks:", error);
            }
        };

        const handleSendMessage = async (e) => {
            e.preventDefault();
            if (!input.trim() || isLoading) return;
            const userMessage = { sender: 'user', text: input };
            setMessages(prev => [...prev, userMessage]);
            const currentInput = input;
            setInput('');
            setIsLoading(true);
            try {
                const response = await chatService.sendMessage(currentInput);
                const assistantMessage = { sender: 'assistant', text: response.data.response };
                setMessages(prev => [...prev, assistantMessage]);
                await fetchAllTasks();
            } catch (error) {
                console.error("Error sending message:", error);
                const errorMessage = { sender: 'assistant', text: 'Sorry, I encountered an error. Please try again.' };
                setMessages(prev => [...prev, errorMessage]);
            } finally {
                setIsLoading(false);
            }
        };

        const handleOpenModal = (task = null) => {
            setTaskToEdit(task);
            setIsModalOpen(true);
        };

        const handleCloseModal = () => {
            setIsModalOpen(false);
            setTaskToEdit(null);
        };

        const handleSaveTask = async (taskData) => {
            try {
                if (taskToEdit) {
                    await chatService.updateTask(taskToEdit.id, { content: taskData.content, due_date: taskData.due_date });
                } else {
                    await chatService.createTask(taskData.content, taskData.due_date);
                }
                await fetchAllTasks();
                handleCloseModal();
            } catch (error) {
                console.error("Failed to save task:", error);
            }
        };

        const handleMarkAsDone = async (taskId) => {
            try {
                await chatService.markTaskAsDone(taskId);
                await fetchAllTasks();
            } catch (error) {
                console.error("Failed to mark task as done:", error);
            }
        };
        
        const handleClearChat = async () => {
            if (window.confirm("Are you sure you want to delete your entire chat history?")) {
                try {
                    await chatService.clearHistory();
                    setMessages([initialMessage]);
                } catch (error) {
                    console.error("Failed to clear chat history:", error);
                }
            }
        };

        if (isPageLoading) {
            return <LoadingSpinner />;
        }

        if (error) {
            return <ErrorDisplay message={error} onRetry={loadInitialData} />;
        }

        return (
            <>
                {isModalOpen && <TaskModal task={taskToEdit} onSave={handleSaveTask} onClose={handleCloseModal} />}
                <div className="dashboard-container" style={{ display: 'flex', flexDirection: 'row' }}>
                    <LeftSidebar
                        onNewChat={() => {}}
                        onClearChat={handleClearChat}
                        onDeleteSession={() => {}}
                        onProfileClick={() => {}}
                        taskCount={pendingTasks.length}
                    />
                    <main className="dashboard-main" style={{ flex: 1 }}>
                        <ChatWindow messages={messages} isLoading={isLoading} />
                        <div className="chat-input-area">
                            <input 
                                type="text" 
                                className="chat-input" 
                                placeholder="Type your message here..." 
                                value={input} 
                                onChange={(e) => setInput(e.target.value)} 
                                disabled={isLoading} 
                                onKeyPress={(e) => e.key === 'Enter' && handleSendMessage(e)}
                            />
                            <button 
                                type="button" 
                                className="send-button" 
                                disabled={isLoading}
                                onClick={handleSendMessage}
                            >
                                {isLoading ? 'Sending...' : 'Send'}
                            </button>
                        </div>
                    </main>
                    <RightSidebar
                        currentUserEmail={currentUserEmail}
                        pendingTasks={pendingTasks}
                        completedTasks={completedTasks}
                        handleOpenModal={handleOpenModal}
                        handleMarkAsDone={handleMarkAsDone}
                        handleClearChat={handleClearChat}
                    />
                </div>
            </>
        );
    };

    export default Dashboard;
