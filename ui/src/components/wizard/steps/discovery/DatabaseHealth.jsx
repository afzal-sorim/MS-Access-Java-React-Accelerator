import React from 'react';
import { CheckCircle2, AlertTriangle } from 'lucide-react';

const DatabaseHealth = () => {
    const checks = [
        { name: 'Database Integrity', status: 'Healthy', isGood: true },
        { name: 'Relationships', status: 'Healthy', isGood: true },
        { name: 'Orphaned Objects', status: 'Healthy', isGood: true },
        { name: 'Performance', status: 'Good', isGood: true },
        { name: 'Security Issues', status: '1 Warning', isGood: false },
    ];

    return (
        <div className="card" style={{ padding: '1.5rem', flex: 1, minWidth: '300px' }}>
            <h3 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '0.25rem' }}>Database Health</h3>
            <p style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', marginBottom: '1rem' }}>Health check of your database</p>
            
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', marginTop: '1.5rem' }}>
                {checks.map((check, i) => (
                    <div key={i} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                            {check.isGood ? (
                                <CheckCircle2 size={16} color="#10b981" />
                            ) : (
                                <AlertTriangle size={16} color="#f59e0b" />
                            )}
                            <span style={{ fontSize: '0.875rem', fontWeight: 500 }}>{check.name}</span>
                        </div>
                        <span style={{ fontSize: '0.75rem', fontWeight: 600, color: check.isGood ? '#10b981' : '#f59e0b' }}>
                            {check.status}
                        </span>
                    </div>
                ))}
            </div>
        </div>
    );
};

export default DatabaseHealth;
