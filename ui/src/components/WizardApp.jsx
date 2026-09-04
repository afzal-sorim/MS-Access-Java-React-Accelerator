import React, { useState } from 'react';
import { WizardProvider } from '../context/WizardContext';
import { useAuth } from '../context/AuthContext';
import WizardContainer from './wizard/WizardContainer';
import Access2JavaLogo from './Access2JavaLogo';

/**
 * Main wizard application component.
 */
export default function WizardApp() {
    const { user, logout } = useAuth();
    const [showUserMenu, setShowUserMenu] = useState(false);

    return (
        <WizardProvider>
            <div className="app-container">
                {/* ── Top Header with Access2Java Logo on Left ── */}
                <header className="app-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid #e2e8f0', background: '#ffffff', minHeight: '64px', padding: '0.65rem 2rem' }}>
                    {/* Left: Logo */}
                    <div className="app-logo">
                        <Access2JavaLogo size="sm" header />
                    </div>

                    {/* Right: User profile card */}
                    <div className="app-user-card" onClick={() => setShowUserMenu(!showUserMenu)}>
                        <div className="app-user-avatar">
                            {user?.profile_image ? (
                                <img src={user.profile_image} alt={user.name} />
                            ) : (
                                (user?.name || 'U').charAt(0).toUpperCase()
                            )}
                        </div>
                        <div className="app-user-info">
                            <span className="app-user-name">{user?.name || 'User'}</span>
                            <span className="app-user-email">{user?.email || ''}</span>
                        </div>
                        <div className="app-user-chevron">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                                <polyline points="6 9 12 15 18 9"/>
                            </svg>
                        </div>

                        {showUserMenu && (
                            <div className="app-user-dropdown">
                                <button className="app-user-dropdown-item" onClick={logout}>
                                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                        <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>
                                        <polyline points="16 17 21 12 16 7"/>
                                        <line x1="21" y1="12" x2="9" y2="12"/>
                                    </svg>
                                    Logout
                                </button>
                            </div>
                        )}
                    </div>
                </header>

                <main className="app-content">
                    <WizardContainer />
                </main>
            </div>
        </WizardProvider>
    );
}