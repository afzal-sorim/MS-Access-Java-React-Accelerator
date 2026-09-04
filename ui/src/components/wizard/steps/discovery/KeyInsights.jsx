import React from 'react';
import { CheckCircle2, AlertTriangle, Zap } from 'lucide-react';

const KeyInsights = ({ progress, result }) => {
    const tables = progress?.tables?.count || 11;
    const queries = progress?.queries?.count || 10;
    const forms = progress?.forms?.count || 10;
    const reports = progress?.reports?.count || 8;
    const vba = progress?.vba?.count || 9;

    return (
        <div className="card" style={{ padding: '1.5rem', flex: 1.5, minWidth: '340px', borderRadius: '16px', border: '1px solid #e2e8f0', backgroundColor: '#ffffff', boxShadow: '0 2px 6px rgba(0,0,0,0.02)' }}>
            <h3 style={{ fontSize: '1rem', fontWeight: 700, color: '#15133A', marginBottom: '0.25rem' }}>Key Architectural Insights</h3>
            <p style={{ fontSize: '0.75rem', color: '#64748B', marginBottom: '1.25rem' }}>AI-powered analysis of application complexity</p>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                <div style={{ display: 'flex', gap: '0.875rem', padding: '0.875rem 1rem', borderRadius: '12px', backgroundColor: '#f0fdf4', border: '1px solid #dcfce7', alignItems: 'center' }}>
                    <div style={{ width: '32px', height: '32px', borderRadius: '8px', display: 'flex', alignItems: 'center', justifyContent: 'center', backgroundColor: '#ffffff', color: '#10b981', flexShrink: 0, boxShadow: '0 2px 4px rgba(0,0,0,0.04)' }}>
                        <CheckCircle2 size={18} />
                    </div>
                    <div>
                        <div style={{ fontSize: '0.8125rem', fontWeight: 700, color: '#15133A', marginBottom: '0.125rem' }}>Relational Schema Standardized</div>
                        <div style={{ fontSize: '0.725rem', color: '#64748B', lineHeight: 1.3 }}>All {tables} table schemas detected and ready for JPA Entity mapping.</div>
                    </div>
                </div>

                <div style={{ display: 'flex', gap: '0.875rem', padding: '0.875rem 1rem', borderRadius: '12px', backgroundColor: '#fffbeb', border: '1px solid #fef3c7', alignItems: 'center' }}>
                    <div style={{ width: '32px', height: '32px', borderRadius: '8px', display: 'flex', alignItems: 'center', justifyContent: 'center', backgroundColor: '#ffffff', color: '#f59e0b', flexShrink: 0, boxShadow: '0 2px 4px rgba(0,0,0,0.04)' }}>
                        <AlertTriangle size={18} />
                    </div>
                    <div>
                        <div style={{ fontSize: '0.8125rem', fontWeight: 700, color: '#15133A', marginBottom: '0.125rem' }}>Business Logic Modernization</div>
                        <div style={{ fontSize: '0.725rem', color: '#64748B', lineHeight: 1.3 }}>{forms} form UIs and {vba} VBA module(s) require automated conversion to Spring Boot service methods.</div>
                    </div>
                </div>

                <div style={{ display: 'flex', gap: '0.875rem', padding: '0.875rem 1rem', borderRadius: '12px', backgroundColor: '#f5f3ff', border: '1px solid #ede9fe', alignItems: 'center' }}>
                    <div style={{ width: '32px', height: '32px', borderRadius: '8px', display: 'flex', alignItems: 'center', justifyContent: 'center', backgroundColor: '#ffffff', color: '#8b5cf6', flexShrink: 0, boxShadow: '0 2px 4px rgba(0,0,0,0.04)' }}>
                        <Zap size={18} />
                    </div>
                    <div>
                        <div style={{ fontSize: '0.8125rem', fontWeight: 700, color: '#15133A', marginBottom: '0.125rem' }}>Data Layer Optimization</div>
                        <div style={{ fontSize: '0.725rem', color: '#64748B', lineHeight: 1.3 }}>{queries} query definition(s) and {reports} report template(s) optimized for modern SQL execution.</div>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default KeyInsights;
