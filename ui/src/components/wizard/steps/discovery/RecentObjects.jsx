import React from 'react';
import { Database, Layout, FileText, Code, PlaySquare } from 'lucide-react';

const RecentObjects = () => {
    // Mock data for recently modified objects
    const recentObjects = [
        { name: 'qryOrderSummary', type: 'Query', icon: Database, color: '#10b981', bg: '#ecfdf5', time: 'May 19, 2025 09:15 AM' },
        { name: 'frmCustomerDetails', type: 'Form', icon: Layout, color: '#f59e0b', bg: '#fffbeb', time: 'May 18, 2025 08:45 AM' },
        { name: 'rptSalesReport', type: 'Report', icon: FileText, color: '#3b82f6', bg: '#eff6ff', time: 'May 18, 2025 04:30 PM' },
        { name: 'OrderUtils', type: 'Module', icon: Code, color: '#8b5cf6', bg: '#f5f3ff', time: 'May 18, 2025 02:20 PM' },
        { name: 'macAutoExec', type: 'Macro', icon: PlaySquare, color: '#f97316', bg: '#fff7ed', time: 'May 17, 2025 11:10 AM' },
    ];

    return (
        <div className="card" style={{ padding: '1.5rem', flex: 1, minWidth: '300px' }}>
            <h3 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '0.25rem' }}>Recent Objects</h3>
            <p style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', marginBottom: '1.5rem' }}>Recently modified database objects</p>
            
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                {recentObjects.map((obj, i) => (
                    <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                        <div style={{ 
                            width: '32px', height: '32px', borderRadius: '8px', 
                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                            backgroundColor: obj.bg, color: obj.color
                        }}>
                            <obj.icon size={16} />
                        </div>
                        <div style={{ flex: 1, fontSize: '0.875rem', fontWeight: 500, color: 'var(--color-navy)' }}>
                            {obj.name}
                        </div>
                        <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>
                            {obj.type}
                        </div>
                        <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', textAlign: 'right', minWidth: '120px' }}>
                            {obj.time}
                        </div>
                    </div>
                ))}
            </div>
            
            <div style={{ marginTop: '1.5rem' }}>
                <a href="#" style={{ fontSize: '0.75rem', color: 'var(--color-purple-bright)', fontWeight: 500 }}>
                    View All Objects →
                </a>
            </div>
        </div>
    );
};

export default RecentObjects;
