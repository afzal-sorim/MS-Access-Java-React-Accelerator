import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import './LoginPage.css';
import Access2JavaLogo from './Access2JavaLogo';

export default function LoginPage() {
  const navigate = useNavigate();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [rememberMe, setRememberMe] = useState(false);

  const handleLogin = (e) => {
    e.preventDefault();
    navigate('/wizard');
  };

  const features = [
    {
      icon: (
        <svg viewBox="0 0 24 24" width="22" height="22" stroke="currentColor" fill="none" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
          <polyline points="14 2 14 8 20 8"/>
          <line x1="9" y1="13" x2="15" y2="13"/>
          <line x1="9" y1="17" x2="13" y2="17"/>
        </svg>
      ),
      title: 'Smart Discovery',
      desc: 'Automatically analyze Access forms, queries, tables, reports, VBA and relationships.',
    },
    {
      icon: (
        <svg viewBox="0 0 24 24" width="22" height="22" stroke="currentColor" fill="none" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
          <rect x="2" y="3" width="20" height="14" rx="2"/>
          <line x1="8" y1="21" x2="16" y2="21"/>
          <line x1="12" y1="17" x2="12" y2="21"/>
        </svg>
      ),
      title: 'Modern UI in React',
      desc: 'Access forms transformed into responsive, modern React components.',
    },
    {
      icon: (
        <svg viewBox="0 0 24 24" width="22" height="22" stroke="currentColor" fill="none" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
          <polyline points="16 18 22 12 16 6"/>
          <polyline points="8 6 2 12 8 18"/>
        </svg>
      ),
      title: 'Intelligent Conversion',
      desc: 'AI + rule based engine converts Access objects to Java, React and PostgreSQL efficiently.',
    },
    {
      icon: (
        <svg viewBox="0 0 24 24" width="22" height="22" stroke="currentColor" fill="none" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
          <ellipse cx="12" cy="5" rx="9" ry="3"/>
          <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/>
          <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/>
        </svg>
      ),
      title: 'PostgreSQL Ready',
      desc: 'Access tables and relationships converted to optimized PostgreSQL schema.',
    },
    {
      icon: (
        <svg viewBox="0 0 24 24" width="22" height="22" stroke="currentColor" fill="none" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
          <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
          <polyline points="9 12 11 14 15 10"/>
        </svg>
      ),
      title: 'Business Logic Preservation',
      desc: 'VBA and business rules are understood and converted to robust Java services.',
    },
    {
      icon: (
        <svg viewBox="0 0 24 24" width="22" height="22" stroke="currentColor" fill="none" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
          <path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/>
          <rect x="8" y="2" width="8" height="4" rx="1" ry="1"/>
          <polyline points="9 14 11 16 15 12"/>
        </svg>
      ),
      title: 'Validation & Assurance',
      desc: 'Built-in validation, comparison and reports to ensure zero data loss and business continuity.',
    },
  ];

  const steps = [
    { num: '01', label: 'Connect',      sub: 'Connect your Access\ndatabase repository.' },
    { num: '02', label: 'Discover',     sub: 'Discover and analyze\nall Access objects.' },
    { num: '03', label: 'Map & Review', sub: 'Review mappings and\nbusiness rules.' },
    { num: '04', label: 'Convert',      sub: 'Convert to Java, React\nand PostgreSQL.' },
    { num: '05', label: 'Validate',     sub: 'Validate results and\ngenerate reports.' },
    { num: '06', label: 'Deploy',       sub: 'Deploy modern\napplication with ease.' },
  ];

  return (
    <div className="lp-root">
      {/* Background Decorative Elements */}
      <div className="lp-bg-decor lp-bg-blob-1"></div>
      <div className="lp-bg-decor lp-bg-blob-2"></div>
      <div className="lp-bg-decor lp-bg-blob-3"></div>

      {/* ═══════════════════════════════════════════
          LEFT PANEL
      ═══════════════════════════════════════════ */}
      <div className="lp-left">

        {/* ── Logo ── */}
        <div className="lp-logo">
          <Access2JavaLogo size="lg" />
        </div>

        {/* ── Hero ── */}
        <div className="lp-hero">
          <h1 className="lp-headline">
            Migrate MS Access Applications<br/>
            to Modern. Smart. Future-Ready.
          </h1>
          <p className="lp-hero-desc">
            Access2Java helps you automatically analyze, convert and migrate your MS Access applications to Java, React and PostgreSQL with accuracy and confidence.
          </p>
        </div>

        {/* ── Powerful Features ── */}
        <div className="lp-section">
          <h2 className="lp-section-title">
            {/* Rocket icon */}
            <svg viewBox="0 0 24 24" width="20" height="20" fill="#4338CA" stroke="none">
              <path d="M13.13 22.19L11.5 18.36C13.07 17.78 14.54 17 15.9 16.09L13.13 22.19M5.64 12.5L1.81 10.87L7.91 8.1C7 9.46 6.22 10.93 5.64 12.5M21.61 2.39C21.61 2.39 16.66.269 11 5.93C8.81 8.12 7.5 10.53 6.65 12.64C6.37 13.39 6.56 14.21 7.11 14.77L9.24 16.89C9.79 17.45 10.61 17.63 11.36 17.35C13.5 16.53 15.88 15.19 18.07 13C23.73 7.34 21.61 2.39 21.61 2.39M14.54 9.46C13.76 8.68 13.76 7.41 14.54 6.63C15.32 5.85 16.59 5.85 17.37 6.63C18.14 7.41 18.15 8.68 17.37 9.46C16.59 10.24 15.32 10.24 14.54 9.46M8.88 16.53L7.47 15.12L8.88 16.53M6.24 22L9.88 18.36C9.54 18.27 9.21 18.12 8.91 17.91L4.83 22H6.24M2 22H3.41L8.18 17.24L6.76 15.83L2 20.59V22M2 19.17L6.09 15.09C5.88 14.79 5.73 14.46 5.64 14.12L2 17.76V19.17Z"/>
            </svg>
            Powerful Features
          </h2>
          <div className="lp-features-grid">
            {features.map((f, i) => (
              <div className="lp-feat-card" key={i}>
                <div className="lp-feat-icon">{f.icon}</div>
                <div>
                  <div className="lp-feat-title">{f.title}</div>
                  <div className="lp-feat-desc">{f.desc}</div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* ── Migration Steps ── */}
        <div className="lp-section">
          <h2 className="lp-section-title">
            {/* List icon */}
            <svg viewBox="0 0 24 24" width="20" height="20" stroke="#4338CA" fill="none" strokeWidth="2.2" strokeLinecap="round">
              <line x1="8" y1="6" x2="21" y2="6"/>
              <line x1="8" y1="12" x2="21" y2="12"/>
              <line x1="8" y1="18" x2="21" y2="18"/>
              <circle cx="3" cy="6" r="1.2" fill="#4338CA" stroke="none"/>
              <circle cx="3" cy="12" r="1.2" fill="#4338CA" stroke="none"/>
              <circle cx="3" cy="18" r="1.2" fill="#4338CA" stroke="none"/>
            </svg>
            Migration Steps
          </h2>

          <div className="lp-steps-row">
            {steps.map((s, i) => (
              <React.Fragment key={i}>
                <div className="lp-step">
                  <div className="lp-step-circle">{s.num}</div>
                  <div className="lp-step-label">{s.label}</div>
                  <div className="lp-step-sub">
                    {s.sub.split('\n').map((line, li) => (
                      <React.Fragment key={li}>{line}{li < s.sub.split('\n').length - 1 && <br/>}</React.Fragment>
                    ))}
                  </div>
                </div>
                {i < steps.length - 1 && (
                  <div className="lp-step-connector">
                    <span/><span/><span/>
                  </div>
                )}
              </React.Fragment>
            ))}
          </div>
        </div>

        {/* ── Footer Stats Bar (pinned to bottom of left panel) ── */}
        <div className="lp-footer-bar">
          <div className="lp-stat">
            <svg viewBox="0 0 24 24" width="24" height="24" stroke="white" fill="none" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
              <polyline points="9 12 11 14 15 10"/>
            </svg>
            <div className="lp-stat-text">
              <span className="lp-stat-title">Secure</span>
              <span className="lp-stat-sub">Enterprise Grade Security</span>
            </div>
          </div>

          <div className="lp-divider"/>

          <div className="lp-stat">
            <svg viewBox="0 0 24 24" width="24" height="24" stroke="white" fill="none" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
              <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>
            </svg>
            <div className="lp-stat-text">
              <span className="lp-stat-title">Fast</span>
              <span className="lp-stat-sub">Accelerated Migration</span>
            </div>
          </div>

          <div className="lp-divider"/>

          <div className="lp-stat">
            <svg viewBox="0 0 24 24" width="24" height="24" stroke="white" fill="none" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
              <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
              <polyline points="22 4 12 14.01 9 11.01"/>
            </svg>
            <div className="lp-stat-text">
              <span className="lp-stat-title">Accurate</span>
              <span className="lp-stat-sub">High Accuracy & Reliability</span>
            </div>
          </div>

          <div className="lp-divider"/>

          <div className="lp-stat">
            <svg viewBox="0 0 24 24" width="24" height="24" stroke="white" fill="none" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/>
              <polyline points="17 6 23 6 23 12"/>
            </svg>
            <div className="lp-stat-text">
              <span className="lp-stat-title">Scalable</span>
              <span className="lp-stat-sub">For Projects of Any Size</span>
            </div>
          </div>
        </div>
      </div>

      {/* ═══════════════════════════════════════════
          RIGHT PANEL — Login Card
      ═══════════════════════════════════════════ */}
      <div className="lp-right">
        <div className="lp-card">
          {/* Avatar */}
          <div className="lp-avatar">
            <svg viewBox="0 0 24 24" width="34" height="34" fill="#4338CA">
              <path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z"/>
            </svg>
          </div>

          <h2 className="lp-card-title">Welcome Back!</h2>
          <p className="lp-card-sub">Login to access your migration projects</p>

          <form className="lp-form" onSubmit={handleLogin}>
            {/* Username */}
            <div className="lp-field">
              <label className="lp-label">Username</label>
              <div className="lp-input-wrap">
                <span className="lp-input-icon">
                  <svg viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" fill="none" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
                    <circle cx="12" cy="7" r="4"/>
                  </svg>
                </span>
                <input
                  type="text"
                  placeholder="Enter your username"
                  value={username}
                  onChange={e => setUsername(e.target.value)}
                  required
                />
              </div>
            </div>

            {/* Password */}
            <div className="lp-field">
              <label className="lp-label">Password</label>
              <div className="lp-input-wrap">
                <span className="lp-input-icon">
                  <svg viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" fill="none" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
                    <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
                  </svg>
                </span>
                <input
                  type={showPassword ? 'text' : 'password'}
                  placeholder="Enter your password"
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  required
                />
                <button type="button" className="lp-eye-btn" onClick={() => setShowPassword(!showPassword)}>
                  {showPassword ? (
                    <svg viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" fill="none" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94"/>
                      <path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19"/>
                      <line x1="1" y1="1" x2="23" y2="23"/>
                    </svg>
                  ) : (
                    <svg viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" fill="none" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
                      <circle cx="12" cy="12" r="3"/>
                    </svg>
                  )}
                </button>
              </div>
            </div>

            {/* Remember + Forgot */}
            <div className="lp-row-remember">
              <label className="lp-remember">
                <input type="checkbox" checked={rememberMe} onChange={e => setRememberMe(e.target.checked)}/>
                Remember me
              </label>
              <a href="#" className="lp-forgot">Forgot Password?</a>
            </div>

            <button type="submit" className="lp-btn-login">Login</button>
          </form>

          {/* OR */}
          <div className="lp-or-divider"><span>or</span></div>

          {/* Microsoft */}
          <button type="button" className="lp-btn-microsoft">
            <svg viewBox="0 0 21 21" width="18" height="18">
              <rect x="0"  y="0"  width="9" height="9" fill="#F25022"/>
              <rect x="11" y="0"  width="9" height="9" fill="#7FBA00"/>
              <rect x="0"  y="11" width="9" height="9" fill="#00A4EF"/>
              <rect x="11" y="11" width="9" height="9" fill="#FFB900"/>
            </svg>
            Login with Microsoft
          </button>

          {/* Contact admin */}
          <div className="lp-no-account">
            Don't have an account?&nbsp;
            <a href="#" className="lp-contact-admin">Contact Administrator</a>
          </div>
        </div>

        {/* Copyright outside card, pinned to bottom */}
        <div className="lp-card-footer">
          © 2024 Access2Java. All rights reserved.
        </div>
      </div>

    </div>
  );
}
