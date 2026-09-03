import React, { useState } from 'react';
import { useSearchParams, useNavigate, Link } from 'react-router-dom';
import * as api from '../services/api';
import './LoginPage.css';
import Access2JavaLogo from './Access2JavaLogo';

export default function ResetPasswordPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const token = searchParams.get('token');

  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [isSuccess, setIsSuccess] = useState(false);
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    if (!token) {
      setError('Invalid reset token.');
      return;
    }

    if (password !== confirmPassword) {
      setError('Passwords do not match.');
      return;
    }

    setIsLoading(true);
    try {
      await api.resetPassword(token, password);
      setIsSuccess(true);
      setTimeout(() => navigate('/login'), 3000);
    } catch (err) {
      setError(err.message || 'Failed to reset password.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="lp-root">
      <div className="lp-bg-decor lp-bg-blob-1"></div>
      <div className="lp-bg-decor lp-bg-blob-2"></div>
      <div className="lp-right" style={{ width: '100%', maxWidth: '450px', margin: '0 auto' }}>
        <div className="lp-card">
          <div className="lp-avatar">
            <svg viewBox="0 0 24 24" width="34" height="34" fill="#4338CA">
              <path d="M12.65 10C11.83 7.67 9.61 6 7 6c-3.31 0-6 2.69-6 6s2.69 6 6 6c2.61 0 4.83-1.67 5.65-4H17v4h4v-4h2v-4H12.65zM7 14c-1.1 0-2-.9-2-2s.9-2 2-2 2 .9 2 2-.9 2-2 2z"/>
            </svg>
          </div>

          <h2 className="lp-card-title">Reset Password</h2>
          <p className="lp-card-sub">
            {isSuccess
              ? "Your password has been reset successfully. Redirecting to login..."
              : "Enter your new password below."}
          </p>

          {!isSuccess ? (
            <form className="lp-form" onSubmit={handleSubmit}>
              {error && <div className="lp-error-msg">{error}</div>}
              <div className="lp-field">
                <label className="lp-label">New Password</label>
                <div className="lp-input-wrap">
                  <span className="lp-input-icon">
                    <svg viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" fill="none" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
                      <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
                    </svg>
                  </span>
                  <input
                    type="password"
                    placeholder="New password"
                    value={password}
                    onChange={e => setPassword(e.target.value)}
                    required
                    disabled={isLoading}
                  />
                </div>
              </div>
              <div className="lp-field">
                <label className="lp-label">Confirm New Password</label>
                <div className="lp-input-wrap">
                  <span className="lp-input-icon">
                    <svg viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" fill="none" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
                      <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
                    </svg>
                  </span>
                  <input
                    type="password"
                    placeholder="Confirm new password"
                    value={confirmPassword}
                    onChange={e => setConfirmPassword(e.target.value)}
                    required
                    disabled={isLoading}
                  />
                </div>
              </div>
              <button type="submit" className="lp-btn-login" disabled={isLoading}>
                {isLoading ? 'Updating...' : 'Reset Password'}
              </button>
            </form>
          ) : (
            <Link to="/login" className="lp-btn-login" style={{ textAlign: 'center', textDecoration: 'none', display: 'block', lineHeight: '44px' }}>
              Login Now
            </Link>
          )}
        </div>
      </div>
    </div>
  );
}
