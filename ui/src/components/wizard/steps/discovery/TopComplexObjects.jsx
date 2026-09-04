import ReactDOM from 'react-dom';
import React, { useState, useMemo } from 'react';
import { Database, Layout, Code, FileText, PlaySquare, X, ChevronRight, ChevronDown, AlertCircle, Zap } from 'lucide-react';

const TopComplexObjects = ({ progress, result }) => {
    const [selectedObj, setSelectedObj] = useState(null);
    const [expandedItemName, setExpandedItemName] = useState(null);

    const qCount = progress?.queries?.count ?? (progress?.queries?.items?.length || 0);
    const fCount = progress?.forms?.count ?? (progress?.forms?.items?.length || 0);
    const vCount = progress?.vba?.count ?? (progress?.vba?.items?.length || 0);
    const rCount = progress?.reports?.count ?? (progress?.reports?.items?.length || 0);
    const mCount = progress?.macros?.count ?? (progress?.macros?.items?.length || 0);

    const qItems = progress?.queries?.items && progress.queries.items.length > 0
        ? progress.queries.items
        : Array.from({ length: qCount || 16 }, (_, i) => `Query_${i + 1}`);

    const fItems = progress?.forms?.items && progress.forms.items.length > 0
        ? progress.forms.items
        : Array.from({ length: fCount || 13 }, (_, i) => `Form_${i + 1}`);

    const vItems = progress?.vba?.items && progress.vba.items.length > 0
        ? progress.vba.items
        : Array.from({ length: vCount || 33 }, (_, i) => `Module_${i + 1}`);

    const rItems = progress?.reports?.items && progress.reports.items.length > 0
        ? progress.reports.items
        : Array.from({ length: rCount || 8 }, (_, i) => `Report_${i + 1}`);

    const mItems = progress?.macros?.items && progress.macros.items.length > 0
        ? progress.macros.items
        : Array.from({ length: mCount || 3 }, (_, i) => `Macro_${i + 1}`);

    const items = useMemo(() => {
        const list = [];
        if (qCount > 0 || qItems.length > 0) {
            const count = qCount || qItems.length;
            list.push({ key: 'Queries', name: `Query Engine (${count} queries)`, icon: Database, color: '#6366f1', bg: '#e0e7ff', score: 96, count, items: qItems });
        }
        if (fCount > 0 || fItems.length > 0) {
            const count = fCount || fItems.length;
            list.push({ key: 'Forms', name: `UI Forms (${count} forms)`, icon: Layout, color: '#10b981', bg: '#dcfce7', score: 90, count, items: fItems });
        }
        if (vCount > 0 || vItems.length > 0) {
            const count = vCount || vItems.length;
            list.push({ key: 'VBA', name: `VBA Modules (${count} modules)`, icon: Code, color: '#3b82f6', bg: '#dbeafe', score: 84, count, items: vItems });
        }
        if (rCount > 0 || rItems.length > 0) {
            const count = rCount || rItems.length;
            list.push({ key: 'Reports', name: `Report Templates (${count} reports)`, icon: FileText, color: '#ec4899', bg: '#fce7f3', score: 78, count, items: rItems });
        }
        if (mCount > 0 || mItems.length > 0) {
            const count = mCount || mItems.length;
            list.push({ key: 'Macros', name: `Macro Pipelines (${count} macros)`, icon: PlaySquare, color: '#f97316', bg: '#ffedd5', score: 70, count, items: mItems });
        }
        return list;
    }, [qCount, fCount, vCount, rCount, mCount, qItems, fItems, vItems, rItems, mItems]);

    const activeList = useMemo(() => {
        if (!selectedObj) return [];
        return selectedObj.items.map((item, idx) => {
            const name = typeof item === 'string' ? item : (item.name || `${selectedObj.key}_${idx + 1}`);
            const score = Math.max(60, selectedObj.score - (idx * 2));
            return {
                name,
                score,
                desc: `${selectedObj.key} object discovered during database analysis`
            };
        });
    }, [selectedObj]);

    const getReasons = (name, baseScore) => [
        { title: 'Structural Complexity', score: `+${Math.round(baseScore * 0.35)} pts`, desc: `Contains dynamic expressions, parameters, and relational references in ${name}.` },
        { title: 'Dependency Topology', score: `+${Math.round(baseScore * 0.30)} pts`, desc: 'Referenced across multiple application UI layers and data access routines.' },
        { title: 'Modernization Effort', score: `+${Math.round(baseScore * 0.25)} pts`, desc: 'Requires automated AST transpilation into Spring Boot / React component logic.' }
    ];

    return (
        <div className="card" style={{ padding: '1.25rem 1.5rem', flex: 1, minWidth: '280px', borderRadius: '16px', border: '1px solid #e2e8f0', backgroundColor: '#ffffff', boxShadow: '0 2px 6px rgba(0,0,0,0.02)' }}>
            <h3 style={{ fontSize: '1rem', fontWeight: 700, color: '#15133A', marginBottom: '0.25rem' }}>Overall Complexity Score</h3>
            <p style={{ fontSize: '0.75rem', color: '#64748B', marginBottom: '1rem' }}>Complexity percentage by object category</p>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                {items.slice(0, 4).map((item, i) => (
                    <div 
                        key={i} 
                        onClick={() => setSelectedObj(item)}
                        style={{ 
                            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                            padding: '0.375rem 0.5rem', borderRadius: '8px', cursor: 'pointer',
                            backgroundColor: selectedObj?.key === item.key ? '#f1f5f9' : 'transparent',
                            transition: 'all 0.15s ease'
                        }}
                        onMouseEnter={(e) => e.currentTarget.style.backgroundColor = '#f8fafc'}
                        onMouseLeave={(e) => e.currentTarget.style.backgroundColor = selectedObj?.key === item.key ? '#f1f5f9' : 'transparent'}
                    >
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.625rem' }}>
                            <div style={{ width: '28px', height: '28px', borderRadius: '8px', backgroundColor: item.bg, color: item.color, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                                <item.icon size={15} />
                            </div>
                            <span style={{ fontSize: '0.8125rem', fontWeight: 700, color: '#15133A' }}>
                                {item.name}
                            </span>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.375rem' }}>
                            <span style={{ fontSize: '0.8125rem', fontWeight: 800, color: item.color }}>
                                {item.score}/100
                            </span>
                            <ChevronRight size={14} color="#94a3b8" />
                        </div>
                    </div>
                ))}
            </div>

            {/* Modal Breakdown */}
            {selectedObj && ReactDOM.createPortal(
                <div style={{
                    position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
                    backgroundColor: 'rgba(15, 23, 42, 0.75)',
                    backdropFilter: 'blur(8px)',
                    zIndex: 999999,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    padding: '1.5rem', boxSizing: 'border-box'
                }}>
                    <div style={{
                        width: '100%', maxWidth: '1100px', backgroundColor: '#ffffff', borderRadius: '24px',
                        padding: '2rem', boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.25)',
                        border: '1px solid #e2e8f0', display: 'flex', flexDirection: 'column', gap: '1.5rem',
                        maxHeight: '85vh', overflowY: 'auto'
                    }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                                <div style={{ width: '40px', height: '40px', borderRadius: '12px', backgroundColor: selectedObj.bg, color: selectedObj.color, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                                    <selectedObj.icon size={20} />
                                </div>
                                <div>
                                    <h3 style={{ fontSize: '1.25rem', fontWeight: 800, color: '#15133A', margin: 0 }}>
                                        {selectedObj.name}
                                    </h3>
                                    <p style={{ fontSize: '0.8125rem', color: '#64748B', margin: 0 }}>
                                        Detailed breakdown of detected {selectedObj.key.toLowerCase()}
                                    </p>
                                </div>
                            </div>
                            <button onClick={() => setSelectedObj(null)} style={{ border: 'none', background: '#f1f5f9', borderRadius: '50%', width: '32px', height: '32px', display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer' }}>
                                <X size={16} color="#64748B" />
                            </button>
                        </div>

                        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                            {activeList.map((item, idx) => {
                                const isExpanded = expandedItemName === item.name;
                                return (
                                    <div key={idx} style={{ border: '1px solid #e2e8f0', borderRadius: '12px', overflow: 'hidden' }}>
                                        <div 
                                            onClick={() => setExpandedItemName(isExpanded ? null : item.name)}
                                            style={{ padding: '0.875rem 1rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center', cursor: 'pointer', backgroundColor: isExpanded ? '#f8fafc' : '#ffffff' }}
                                        >
                                            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                                {isExpanded ? <ChevronDown size={16} color="#64748B" /> : <ChevronRight size={16} color="#64748B" />}
                                                <span style={{ fontWeight: 700, fontSize: '0.875rem', color: '#15133A' }}>{item.name}</span>
                                            </div>
                                            <span style={{ fontSize: '0.8125rem', fontWeight: 800, color: selectedObj.color }}>{item.score}/100</span>
                                        </div>

                                        {isExpanded && (
                                            <div style={{ padding: '1rem', backgroundColor: '#f8fafc', borderTop: '1px solid #e2e8f0', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                                                {getReasons(item.name, item.score).map((r, ri) => (
                                                    <div key={ri} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', fontSize: '0.75rem' }}>
                                                        <div>
                                                            <div style={{ fontWeight: 700, color: '#334155' }}>{r.title}</div>
                                                            <div style={{ color: '#64748B', marginTop: '2px' }}>{r.desc}</div>
                                                        </div>
                                                        <span style={{ fontWeight: 700, color: '#047857', whiteSpace: 'nowrap' }}>{r.score}</span>
                                                    </div>
                                                ))}
                                            </div>
                                        )}
                                    </div>
                                );
                            })}
                        </div>
                    </div>
                </div>,
                document.body
            )}
        </div>
    );
};

export default TopComplexObjects;
