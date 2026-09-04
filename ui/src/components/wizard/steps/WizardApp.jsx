import React from 'react';
import { WizardProvider } from '../context/WizardContext';
import WizardContainer from './wizard/WizardContainer';
import Access2JavaLogo from './Access2JavaLogo';

/**
 * Main wizard application component.
 * Entry point for the 6-step conversion wizard per spec section 47.
 * Redesigned header to match AccessMigra brand identity.
 */
export default function WizardApp() {
    return (
        <WizardProvider>
            <div className="app-container">
                {/* ── AccessMigra Top Header ── */}
                <header className="app-header">
                    {/* Left: Logo */}
                    <div className="app-logo">
                        <Access2JavaLogo size="sm" header />
                    </div>


                    {/* Right: User profile card */}
                    <div className="app-user-card">
                        <div className="app-user-avatar">A</div>
                        <div className="app-user-info">
                            <span className="app-user-name">Admin User</span>
                            <span className="app-user-email">admin@accessmigra.com</span>
                        </div>
                        <div className="app-user-chevron">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                                <polyline points="6 9 12 15 18 9"/>
                            </svg>
                        </div>
                    </div>
                </header>

                <main className="app-content">
                    <WizardContainer />
                </main>
            </div>
        </WizardProvider>
    );
}