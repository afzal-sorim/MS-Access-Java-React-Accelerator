import React, { useEffect } from 'react';
import { WizardProvider } from '../context/WizardContext';
import WizardContainer from './wizard/WizardContainer';

/**
 * Main wizard application component.
 * Entry point for the 6-step conversion wizard per spec section 47.
 */
export default function WizardApp() {
    return (
        <WizardProvider>
            <div className="app-container">
                <header className="app-header">
                    <h1>MS Access → Spring Boot + React + PostgreSQL Converter</h1>
                </header>
                <main className="app-content">
                    <WizardContainer />
                </main>
                <footer className="app-footer">
                    MS Access Converter Wizard • Sorim AI
                </footer>
            </div>
        </WizardProvider>
    );
}