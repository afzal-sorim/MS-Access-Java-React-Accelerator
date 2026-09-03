import React from 'react';
import { PieChart, Pie, Cell, ResponsiveContainer } from 'recharts';

const FileGenerationChart = ({ progress }) => {
    const tablesCount = progress?.tables?.count || 11;
    const queriesCount = progress?.queries?.count || 10;
    const formsCount = progress?.forms?.count || 10;
    const reportsCount = progress?.reports?.count || 8;
    const vbaCount = progress?.vba?.count || 9;
    const macrosCount = progress?.macros?.count || 5;

    const frontendFiles = Math.max(1, formsCount + Math.ceil(reportsCount * 0.375)) +
                          Math.max(5, (formsCount * 3) + Math.ceil(reportsCount * 0.25)) +
                          Math.max(2, Math.ceil(formsCount * 0.4) + Math.ceil(reportsCount * 0.25)) +
                          Math.max(2, formsCount + Math.ceil(queriesCount * 0.8)) +
                          Math.max(2, Math.ceil((formsCount + tablesCount) * 0.33)) +
                          Math.max(4, tablesCount + queriesCount + Math.ceil(formsCount * 0.3));

    const backendFiles = Math.max(1, formsCount + Math.ceil(queriesCount * 0.6)) +
                         Math.max(1, vbaCount + queriesCount + macrosCount) +
                         tablesCount +
                         (tablesCount + Math.ceil(queriesCount * 0.7)) +
                         (formsCount + Math.ceil(queriesCount * 0.5)) +
                         Math.max(3, Math.ceil(vbaCount * 0.4) + 2);

    const total = frontendFiles + backendFiles;

    const data = [
        { name: 'Frontend Files (UI)', value: frontendFiles, color: '#6366f1', pct: `${(frontendFiles / total * 100).toFixed(1)}%` },
        { name: 'Backend Files (Java)', value: backendFiles, color: '#10b981', pct: `${(backendFiles / total * 100).toFixed(1)}%` }
    ];

    return (
        <div className="card" style={{ padding: '1.25rem 1.5rem', flex: 1, minWidth: '280px', borderRadius: '16px', border: '1px solid #e2e8f0', backgroundColor: '#ffffff', boxShadow: '0 2px 6px rgba(0,0,0,0.02)' }}>
            <h3 style={{ fontSize: '1rem', fontWeight: 700, color: '#15133A', marginBottom: '0.25rem' }}>File Generation Summary</h3>
            <p style={{ fontSize: '0.75rem', color: '#64748B', marginBottom: '1rem' }}>Total estimated modernized output</p>
            
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div style={{ position: 'relative', width: '140px', height: '140px', flexShrink: 0 }}>
                    <ResponsiveContainer width="100%" height="100%">
                        <PieChart>
                            <Pie data={data} cx="50%" cy="50%" innerRadius={46} outerRadius={62} paddingAngle={4} dataKey="value" stroke="none">
                                {data.map((entry, index) => (
                                    <Cell key={`cell-${index}`} fill={entry.color} />
                                ))}
                            </Pie>
                        </PieChart>
                    </ResponsiveContainer>
                    <div style={{ position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%, -50%)', textAlign: 'center' }}>
                        <div style={{ fontSize: '1.625rem', fontWeight: 800, color: '#15133A', lineHeight: 1 }}>{total}</div>
                        <div style={{ fontSize: '0.6875rem', color: '#64748B', marginTop: '0.125rem' }}>Total Files</div>
                    </div>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', flex: 1, paddingLeft: '1rem' }}>
                    {data.map((entry, index) => (
                        <div key={index}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '0.375rem', marginBottom: '0.125rem' }}>
                                <div style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: entry.color }}></div>
                                <span style={{ fontSize: '0.725rem', color: '#64748B', fontWeight: 500 }}>{entry.name}</span>
                            </div>
                            <div style={{ fontSize: '0.875rem', fontWeight: 700, color: '#15133A', paddingLeft: '1.125rem' }}>
                                {entry.value} <span style={{ fontSize: '0.75rem', color: '#64748B', fontWeight: 500 }}>({entry.pct})</span>
                            </div>
                        </div>
                    ))}
                </div>
            </div>

            <div style={{ textAlign: 'center', marginTop: '0.875rem' }}>
                <span style={{ fontSize: '0.6875rem', color: '#94A3B8' }}>Estimated output after modernization</span>
            </div>
        </div>
    );
};

export default FileGenerationChart;
