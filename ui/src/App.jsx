import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import WizardApp from './components/WizardApp';
import './styles/index.css';

export default function App() {
    return (
        <Router>
            <Routes>
                <Route path="/*" element={<WizardApp />} />
            </Routes>
        </Router>
    );
}