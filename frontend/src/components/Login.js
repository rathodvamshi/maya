import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import authService from '../services/auth';
import '../styles/Form.css';

const Login = () => {
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [message, setMessage] = useState('');

    const handleLogin = async (e) => {
        e.preventDefault();
        setMessage('');
        try {
            const response = await authService.login(email, password);
            if (response.data.access_token) {
                authService.storeTokens({ ...response.data, email });
                window.location.href = "/dashboard";
            }
        } catch (error) {
            const resMessage =
                (error.response &&
                    error.response.data &&
                    error.response.data.detail) ||
                error.message ||
                error.toString();
            setMessage(resMessage);
        }
    };

    return (
        <div className="form-screen">
            <div className="form-container">
                <h2>Welcome Back</h2>
                <form onSubmit={handleLogin}>
                    <div className="form-group">
                        <label htmlFor="email">Email address</label>
                        <input
                            id="email"
                            name="email"
                            type="email"
                            autoComplete="email"
                            required
                            className="form-input"
                            value={email}
                            onChange={(e) => setEmail(e.target.value)}
                            placeholder="Enter your email"
                        />
                    </div>
                    <div className="form-group">
                        <label htmlFor="password">Password</label>
                        <input
                            id="password"
                            name="password"
                            type="password"
                            autoComplete="current-password"
                            required
                            className="form-input"
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                            placeholder="Enter your password"
                        />
                    </div>
                    {message && (
                        <div className="message error-message">
                            {message}
                        </div>
                    )}
                    <div>
                        <button type="submit" className="form-button">
                            Sign in
                        </button>
                    </div>
                </form>
                <p className="form-switch-link">
                    Don't have an account? <Link to="/register">Sign Up</Link>
                </p>
            </div>
        </div>
    );
};

export default Login;