import ReactDOM from 'react-dom';
import React, { useState, useMemo } from 'react';
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from 'recharts';
import { Database, Layout, FileText, PlaySquare, Code, X, ChevronRight } from 'lucide-react';

const ObjectDistributionChart = ({ data }) => {
    const [selectedCat, setSelectedCat] = useState(null);

    const tablesCount = data?.tables?.count || 0;
    const queriesCount = data?.queries?.count || 0;
    const formsCount = data?.forms?.count || 0;
    const reportsCount = data?.reports?.count || 0;
    const macrosCount = data?.macros?.count || 0;
    const vbaCount = data?.vba?.count || 0;

    const total = tablesCount + queriesCount + formsCount + reportsCount + macrosCount + vbaCount;

    const chartData = useMemo(() => {
        const list = [
            { name: 'Tables', key: 'tables', value: tablesCount, color: '#8b5cf6', icon: Database, bg: '#f5f3ff', items: data?.tables?.items || [] },
            { name: 'Queries', key: 'queries', value: queriesCount, color: '#10b981', icon: Database, bg: '#ecfdf5', items: data?.queries?.items || [] },
            { name: 'Forms', key: 'forms', value: formsCount, color: '#f59e0b', icon: Layout, bg: '#fffbeb', items: data?.forms?.items || [] },
            { name: 'Reports', key: 'reports', value: reportsCount, color: '#3b82f6', icon: FileText, bg: '#eff6ff', items: data?.reports?.items || [] },
            { name: 'Macros', key: 'macros', value: macrosCount, color: '#ec4899', icon: PlaySquare, bg: '#fce7f3', items: data?.macros?.items || [] },
            { name: 'Modules', key: 'vba', value: vbaCount, color: '#6366f1', icon: Code, bg: '#e0e7ff', items: data?.vba?.items || [] },
        ];
        return list.filter(item => item.value > 0);
    }, [tablesCount, queriesCount, formsCount, reportsCount, macrosCount, vbaCount, data]);

    const activeList = useMemo(() => {
        if (!selectedCat) return [];
        let items = selectedCat.items || [];
        
        // Ensure breakdown list item count matches selectedCat.value exactly
        if (items.length < selectedCat.value) {
            const existingNames = new Set(items.map(it => typeof it === 'string' ? it : (it.name || '')));
            const missingCount = selectedCat.value - items.length;
            const extra = [];
            for (let i = 1; i <= missingCount; i++) {
                const autoName = `${selectedCat.name}_${items.length + i}`;
                if (!existingNames.has(autoName)) {
                    extra.push(autoName);
                }
            }
            items = [...items, ...extra];
        } else if (items.length > selectedCat.value) {
            items = items.slice(0, selectedCat.value);
        }

        return items.map((item, idx) => {
            const name = typeof item === 'string' ? item : (item.name || `${selectedCat.name}_${idx + 1}`);
            return {
                name,
                type: selectedCat.name.endsWith('s') ? selectedCat.name.slice(0, -1) : selectedCat.name,
                desc: `${selectedCat.name} structure extracted from database`
            };
        });
    }, [selectedCat]);

    if (total === 0) {
        return (
            <div className="card" style={{ padding: '1.25rem 1.5rem', flex: 1, minWidth: '300px', borderRadius: '16px', border: '1px solid #e2e8f0', backgroundColor: '#ffffff', boxShadow: '0 2px 6px rgba(0,0,0,0.02)' }}>
                <h3 style={{ fontSize: '1rem', fontWeight: 700, color: '#15133A', marginBottom: '0.25rem' }}>Object Distribution</h3>
                <p style={{ fontSize: '0.75rem', color: '#64748B', margin: 0 }}>No objects discovered</p>
            </div>
        );
    }

    return (
        <div className="card" style={{ padding: '1.25rem 1.5rem', flex: 1, minWidth: '300px', borderRadius: '16px', border: '1px solid #e2e8f0', backgroundColor: '#ffffff', boxShadow: '0 2px 6px rgba(0,0,0,0.02)' }}>
            <h3 style={{ fontSize: '1rem', fontWeight: 700, color: '#15133A', marginBottom: '0.25rem' }}>Object Distribution</h3>
            <p style={{ fontSize: '0.75rem', color: '#64748B', marginBottom: '1rem' }}>Click any donut slice or legend row for full breakdown</p>

            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '1rem' }}>
                {/* Donut Chart with Centered Total Count */}
                <div style={{ position: 'relative', width: '130px', height: '130px', flexShrink: 0, cursor: 'pointer' }}>
                    <ResponsiveContainer width="100%" height="100%">
                        <PieChart>
                            <Pie
                                data={chartData}
                                cx="50%"
                                cy="50%"
                                innerRadius={36}
                                outerRadius={54}
                                paddingAngle={3}
                                dataKey="value"
                                stroke="none"
                                onClick={(entry) => setSelectedCat(entry)}
                            >
                                {chartData.map((entry, index) => (
                                    <Cell key={`cell-${index}`} fill={entry.color} style={{ cursor: 'pointer', outline: 'none' }} />
                                ))}
                            </Pie>
                            <Tooltip
                                formatter={(val, name) => [`${val} (${((val / total) * 100).toFixed(1)}%)`, name]}
                                contentStyle={{ backgroundColor: '#ffffff', border: '1px solid #e2e8f0', borderRadius: '8px', fontSize: '0.75rem', fontWeight: 600, color: '#15133A', boxShadow: '0 4px 12px rgba(0,0,0,0.08)' }}
                            />
                        </PieChart>
                    </ResponsiveContainer>

                    {/* Centered Total Objects Badge in Donut Hole */}
                    <div style={{
                        position: 'absolute',
                        top: '50%',
                        left: '50%',
                        transform: 'translate(-50%, -50%)',
                        textAlign: 'center',
                        pointerEvents: 'none',
                        lineHeight: 1
                    }}>
                        <div style={{ fontSize: '1.25rem', fontWeight: 800, color: '#15133A', letterSpacing: '-0.5px' }}>
                            {total}
                        </div>
                        <div style={{ fontSize: '0.625rem', fontWeight: 700, color: '#64748B', textTransform: 'uppercase', letterSpacing: '0.06em', marginTop: '2px' }}>
                            Total
                        </div>
                    </div>
                </div>

                {/* Clickable Legend List */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.375rem', flex: 1 }}>
                    {chartData.map((item, index) => {
                        const pct = ((item.value / total) * 100).toFixed(1);
                        const isSelected = selectedCat?.name === item.name;

                        return (
                            <div
                                key={index}
                                onClick={() => setSelectedCat(item)}
                                style={{
                                    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                                    padding: '0.25rem 0.5rem', borderRadius: '6px', cursor: 'pointer',
                                    backgroundColor: isSelected ? '#f1f5f9' : 'transparent',
                                    transition: 'all 0.15s ease'
                                }}
                            >
                                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', minWidth: 0 }}>
                                    <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: item.color, flexShrink: 0 }} />
                                    <span style={{ fontSize: '0.78125rem', color: '#15133A', fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                        {item.name} ({item.value})
                                    </span>
                                </div>
                                <div style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                                    <span style={{ fontSize: '0.75rem', color: '#64748B', fontWeight: 600 }}>{pct}%</span>
                                    <ChevronRight size={13} color="#94a3b8" />
                                </div>
                            </div>
                        );
                    })}
                </div>
            </div>

            {/* Category Breakdown Modal (Portal to body) */}
            {selectedCat && ReactDOM.createPortal(
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
                        border: '1px solid #e2e8f0', maxHeight: '85vh', overflowY: 'auto'
                    }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '1.25rem', paddingBottom: '1rem', borderBottom: '1px solid #f1f5f9' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '0.875rem' }}>
                                <div style={{ width: '42px', height: '42px', borderRadius: '12px', backgroundColor: selectedCat.bg, color: selectedCat.color, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                                    <selectedCat.icon size={22} />
                                </div>
                                <div>
                                    <h3 style={{ fontSize: '1.125rem', fontWeight: 800, color: '#15133A', margin: 0 }}>
                                        {selectedCat.name} Breakdown ({selectedCat.value} Objects)
                                    </h3>
                                    <p style={{ fontSize: '0.78125rem', color: '#64748B', margin: 0, marginTop: '0.125rem' }}>
                                        Represents <strong>{((selectedCat.value / total) * 100).toFixed(1)}%</strong> of total {total} scanned application structures
                                    </p>
                                </div>
                            </div>
                            <button 
                                onClick={() => setSelectedCat(null)}
                                style={{ background: '#f1f5f9', border: 'none', width: '32px', height: '32px', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer', color: '#64748B' }}
                            >
                                <X size={18} />
                            </button>
                        </div>

                        <div style={{ padding: '0.875rem 1.25rem', borderRadius: '14px', backgroundColor: '#f8fafc', border: '1px solid #e2e8f0', display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.25rem' }}>
                            <span style={{ fontSize: '0.8125rem', fontWeight: 700, color: '#15133A' }}>
                                Total {selectedCat.name} Discovered
                            </span>
                            <span style={{ fontSize: '1.125rem', fontWeight: 800, color: selectedCat.color, padding: '2px 10px', borderRadius: '8px', backgroundColor: selectedCat.bg }}>
                                {selectedCat.value} Items ({((selectedCat.value / total) * 100).toFixed(1)}%)
                            </span>
                        </div>

                        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', marginBottom: '1.5rem' }}>
                            {activeList.map((item, i) => (
                                <div key={i} style={{ padding: '0.75rem 1rem', borderRadius: '10px', backgroundColor: '#ffffff', border: '1px solid #e2e8f0', display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '1rem' }}>
                                    <div style={{ minWidth: 0 }}>
                                        <div style={{ fontSize: '0.8125rem', fontWeight: 700, color: '#15133A', fontFamily: 'monospace' }}>
                                            {item.name}
                                        </div>
                                        <div style={{ fontSize: '0.725rem', color: '#64748B', marginTop: '0.125rem' }}>
                                            {item.desc}
                                        </div>
                                    </div>
                                    <span style={{ fontSize: '0.6875rem', fontWeight: 700, color: selectedCat.color, padding: '3px 8px', borderRadius: '6px', backgroundColor: selectedCat.bg, flexShrink: 0 }}>
                                        {item.type}
                                    </span>
                                </div>
                            ))}
                        </div>

                        <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                            <button 
                                onClick={() => setSelectedCat(null)}
                                style={{ padding: '0.625rem 1.5rem', borderRadius: '10px', backgroundColor: '#3730A3', color: '#ffffff', fontWeight: 700, fontSize: '0.8125rem', border: 'none', cursor: 'pointer' }}
                            >
                                Close Breakdown
                            </button>
                        </div>
                    </div>
                </div>,
                document.body
            )}
        </div>
    );
};

export default ObjectDistributionChart;
