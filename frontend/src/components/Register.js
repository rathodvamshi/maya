import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { Mail, Lock, Eye, EyeOff, UserPlus, Sparkles, Shield, CheckCircle, AlertCircle } from 'lucide-react';
import authService from '../services/auth';
import '../styles/Register.css';

const Register = () => {
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [confirmPassword, setConfirmPassword] = useState('');
    const [message, setMessage] = useState('');
    const [successful, setSuccessful] = useState(false);
    const [isLoading, setIsLoading] = useState(false);
    const [showPassword, setShowPassword] = useState(false);
    const [showConfirmPassword, setShowConfirmPassword] = useState(false);
    const [passwordStrength, setPasswordStrength] = useState({ score: 0, feedback: [] });

    const checkPasswordStrength = (password) => {
        let score = 0;
        const feedback = [];

        if (password.length >= 8) {
            score++;
        } else {
            feedback.push('At least 8 characters');
        }

        if (/[A-Z]/.test(password)) {
            score++;
        } else {
            feedback.push('One uppercase letter');
        }

        if (/[a-z]/.test(password)) {
            score++;
        } else {
            feedback.push('One lowercase letter');
        }

        if (/[0-9]/.test(password)) {
            score++;
        } else {
            feedback.push('One number');
        }

        if (/[^A-Za-z0-9]/.test(password)) {
            score++;
        } else {
            feedback.push('One special character');
        }

        return { score, feedback };
    };

    const handlePasswordChange = (e) => {
        const newPassword = e.target.value;
        setPassword(newPassword);
        setPasswordStrength(checkPasswordStrength(newPassword));
    };

    const handleRegister = async (e) => {
        e.preventDefault();
        setMessage('');
        setSuccessful(false);
        setIsLoading(true);

        if (password !== confirmPassword) {
            setMessage('Passwords do not match');
            setSuccessful(false);
            setIsLoading(false);
            return;
        }

        try {
            await authService.register(email, password);
            setMessage('Registration successful! You can now log in.');
            setSuccessful(true);
        } catch (error) {
            const resMessage =
                (error.response &&
                    error.response.data &&
                    error.response.data.detail) ||
                error.message ||
                error.toString();
            setMessage(resMessage);
            setSuccessful(false);
        } finally {
            setIsLoading(false);
        }
    };

    const togglePasswordVisibility = () => {
        setShowPassword(!showPassword);
    };

    const toggleConfirmPasswordVisibility = () => {
        setShowConfirmPassword(!showConfirmPassword);
    };

    const getStrengthColor = (score) => {
        if (score <= 2) return '#ef4444';
        if (score <= 3) return '#f59e0b';
        if (score <= 4) return '#10b981';
        return '#059669';
    };

    const getStrengthText = (score) => {
        if (score <= 2) return 'Weak';
        if (score <= 3) return 'Fair';
        if (score <= 4) return 'Good';
        return 'Strong';
    };

    return (
        <div className="register-screen">
            <div className="register-background">
                <div className="floating-particles">
                    <div className="particle particle-1"></div>
                    <div className="particle particle-2"></div>
                    <div className="particle particle-3"></div>
                    <div className="particle particle-4"></div>
                    <div className="particle particle-5"></div>
                    <div className="particle particle-6"></div>
                </div>
            </div>
            
            <div className="register-container">
                <div className="register-header">
                    <div className="logo-wrapper">
                        <Shield className="logo-icon" size={32} />
                        <UserPlus className="plus-icon" size={16} />
                        <Sparkles className="sparkle-icon" size={16} />
                    </div>
                    <h1 className="register-title">Create Account</h1>
                    <p className="register-subtitle">Join our community and start your amazing journey</p>
                </div>

                <form onSubmit={handleRegister} className="register-form">
                    <div className="form-group">
                        <label htmlFor="email" className="form-label">
                            Email Address
                        </label>
                        <div className="input-wrapper">
                            <Mail className="input-icon" size={20} />
                            <input
                                id="email"
                                name="email"
                                type="email"
                                autoComplete="email"
                                required
                                className="form-input"
                                value={email}
                                onChange={(e) => setEmail(e.target.value)}
                                placeholder="Enter your email address"
                                disabled={isLoading}
                            />
                        </div>
                    </div>

                    <div className="form-group">
                        <label htmlFor="password" className="form-label">
                            Password
                        </label>
                        <div className="input-wrapper">
                            <Lock className="input-icon" size={20} />
                            <input
                                id="password"
                                name="password"
                                type={showPassword ? 'text' : 'password'}
                                autoComplete="new-password"
                                required
                                className="form-input"
                                value={password}
                                onChange={handlePasswordChange}
                                placeholder="Create a strong password"
                                disabled={isLoading}
                            />
                            <button
                                type="button"
                                className="password-toggle"
                                onClick={togglePasswordVisibility}
                                disabled={isLoading}
                            >
                                {showPassword ? <EyeOff size={20} /> : <Eye size={20} />}
                            </button>
                        </div>
                        
                        {password && (
                            <div className="password-strength">
                                <div className="strength-bar">
                                    <div 
                                        className="strength-fill"
                                        style={{ 
                                            width: `${(passwordStrength.score / 5) * 100}%`,
                                            backgroundColor: getStrengthColor(passwordStrength.score)
                                        }}
                                    ></div>
                                </div>
                                <div className="strength-info">
                                    <span 
                                        className="strength-text"
                                        style={{ color: getStrengthColor(passwordStrength.score) }}
                                    >
                                        {getStrengthText(passwordStrength.score)}
                                    </span>
                                    {passwordStrength.feedback.length > 0 && (
                                        <div className="strength-feedback">
                                            <span className="feedback-label">Missing:</span>
                                            <ul className="feedback-list">
                                                {passwordStrength.feedback.map((item, index) => (
                                                    <li key={index}>{item}</li>
                                                ))}
                                            </ul>
                                        </div>
                                    )}
                                </div>
                            </div>
                        )}
                    </div>

                    <div className="form-group">
                        <label htmlFor="confirmPassword" className="form-label">
                            Confirm Password
                        </label>
                        <div className="input-wrapper">
                            <Lock className="input-icon" size={20} />
                            <input
                                id="confirmPassword"
                                name="confirmPassword"
                                type={showConfirmPassword ? 'text' : 'password'}
                                autoComplete="new-password"
                                required
                                className={`form-input ${
                                    confirmPassword && password !== confirmPassword ? 'error' : 
                                    confirmPassword && password === confirmPassword ? 'success' : ''
                                }`}
                                value={confirmPassword}
                                onChange={(e) => setConfirmPassword(e.target.value)}
                                placeholder="Confirm your password"
                                disabled={isLoading}
                            />
                            <button
                                type="button"
                                className="password-toggle"
                                onClick={toggleConfirmPasswordVisibility}
                                disabled={isLoading}
                            >
                                {showConfirmPassword ? <EyeOff size={20} /> : <Eye size={20} />}
                            </button>
                            {confirmPassword && (
                                <div className="validation-icon">
                                    {password === confirmPassword ? (
                                        <CheckCircle size={16} className="success-icon" />
                                    ) : (
                                        <AlertCircle size={16} className="error-icon" />
                                    )}
                                </div>
                            )}
                        </div>
                    </div>

                    <div className="terms-agreement">
                        <input
                            id="terms"
                            type="checkbox"
                            required
                            className="checkbox"
                            disabled={isLoading}
                        />
                        <label htmlFor="terms" className="checkbox-label">
                            I agree to the <Link to="/terms" className="terms-link">Terms of Service</Link> and{' '}
                            <Link to="/privacy" className="terms-link">Privacy Policy</Link>
                        </label>
                    </div>

                    {message && (
                        <div className={`message ${successful ? 'success-message' : 'error-message'}`}>
                            <div className="message-content">
                                {successful ? (
                                    <CheckCircle size={20} className="message-icon" />
                                ) : (
                                    <AlertCircle size={20} className="message-icon" />
                                )}
                                {message}
                            </div>
                        </div>
                    )}

                    <button 
                        type="submit" 
                        className={`register-button ${isLoading ? 'loading' : ''}`}
                        disabled={isLoading}
                    >
                        <span className="button-text">
                            {isLoading ? 'Creating Account...' : 'Create Account'}
                        </span>
                        <UserPlus className="button-icon" size={20} />
                        <div className="button-loader">
                            <div className="loader-spinner"></div>
                        </div>
                    </button>
                </form>

                <div className="register-footer">
                    <p className="login-prompt">
                        Already have an account? 
                        <Link to="/login" className="login-link">
                            Sign in here
                        </Link>
                    </p>
                </div>

                <div className="social-register">
                    <div className="divider">
                        <span className="divider-text">Or register with</span>
                    </div>
                    <div className="social-buttons">
                        <button className="social-button google">
                            <svg width="20" height="20" viewBox="0 0 24 24">
                                <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                                <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                                <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
                                <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
                            </svg>
                            Google
                        </button>
                        <button className="social-button github">
                            <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
                                <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0 0 24 12c0-6.63-5.37-12-12-12z"/>
                            </svg>
                            GitHub
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default Register;