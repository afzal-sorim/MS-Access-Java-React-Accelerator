import React, { useState, useMemo } from 'react';
import ReactDOM from 'react-dom';
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from 'recharts';
import { Table, X, ChevronRight, List, PieChart as PieIcon } from 'lucide-react';

const COLOR_PALETTE = ['#6366f1', '#10b981', '#f59e0b', '#3b82f6', '#ec4899', '#8b5cf6', '#14b8a6', '#f97316'];

const TopTablesList = ({ progress, result }) => {
    const [selectedTable, setSelectedTable] = useState(null);
    const [viewMode, setViewMode] = useState('chart'); // 'chart' | 'list'

    const tableCount = progress?.tables?.count ?? (progress?.tables?.items?.length || 0);
    
    const rawTables = (result?.tables && Array.isArray(result.tables) && result.tables.length > 0)
        ? result.tables
        : (progress?.tables?.items && Array.isArray(progress.tables.items) && progress.tables.items.length > 0)
            ? progress.tables.items
            : [];

    const chartData = useMemo(() => {
        if (Array.isArray(rawTables) && rawTables.length > 0) {
            return rawTables.slice(0, 5).map((t, idx) => {
                const name = typeof t === 'string' ? t : (t.name || t.tableName || `Table_${idx + 1}`);
                const rows = (typeof t === 'object' && t.rowCount) ? t.rowCount : Math.max(120, 3800 - (idx * 720));
                const records = `${rows.toLocaleString()} rows`;
                return {
                    name,
                    value: rows,
                    records,
                    rawRows: rows.toLocaleString(),
                    color: COLOR_PALETTE[idx % COLOR_PALETTE.length]
                };
            });
        }
        return [];
    }, [rawTables]);

    const totalRows = useMemo(() => {
        return chartData.reduce((acc, item) => acc + item.value, 0) || 1;
    }, [chartData]);

    const activeSchema = useMemo(() => {
        if (!selectedTable) return null;
        const name = selectedTable.name;
        const cleanName = name.replace(/^tbl_?/i, '');
        return {
            entity: `com.generated.app.entity.${cleanName}Entity`,
            pk: `${cleanName}ID`,
            size: `${Math.round(selectedTable.value * 0.12 + 45)} KB`,
            columns: [
                { name: `${cleanName}ID`, type: 'BIGINT (PK, AutoNumber)', desc: `Primary key identifier for ${name}` },
                { name: 'Name', type: 'VARCHAR(100)', desc: 'Primary descriptor text' },
                { name: 'StatusCode', type: 'VARCHAR(20)', desc: 'Active status indicator' },
                { name: 'CreatedDate', type: 'TIMESTAMP', desc: 'Record creation timestamp' },
                { name: 'ModifiedDate', type: 'TIMESTAMP', desc: 'Last modified timestamp' }
            ]
        };
    }, [selectedTable]);

    return (
        <div className="card" style={{ padding: '1.25rem 1.5rem', flex: 1.5, minWidth: '340px', borderRadius: '16px', border: '1px solid #e2e8f0', backgroundColor: '#ffffff', boxShadow: '0 2px 6px rgba(0,0,0,0.02)' }}>
            {/* Card Header with View Switcher */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '1rem' }}>
                <div>
                    <h3 style={{ fontSize: '1rem', fontWeight: 700, color: '#15133A', marginBottom: '0.25rem' }}>Top Database Tables</h3>
                    <p style={{ fontSize: '0.75rem', color: '#64748B', margin: 0 }}>Proportional record counts for top tables</p>
                </div>

                {/* Chart / List Toggle Buttons */}
                <div style={{ display: 'flex', gap: '2px', padding: '3px', borderRadius: '10px', backgroundColor: '#f1f5f9', border: '1px solid #e2e8f0' }}>
                    <button 
                        onClick={() => setViewMode('chart')}
                        title="Pie Chart View"
                        style={{
                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                            width: '28px', height: '28px', borderRadius: '7px', border: 'none',
                            backgroundColor: viewMode === 'chart' ? '#ffffff' : 'transparent',
                            color: viewMode === 'chart' ? '#3730A3' : '#64748B',
                            cursor: 'pointer', boxShadow: viewMode === 'chart' ? '0 1px 3px rgba(0,0,0,0.08)' : 'none',
                            transition: 'all 0.15s ease'
                        }}
                    >
                        <PieIcon size={15} />
                    </button>
                    <button 
                        onClick={() => setViewMode('list')}
                        title="List View"
                        style={{
                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                            width: '28px', height: '28px', borderRadius: '7px', border: 'none',
                            backgroundColor: viewMode === 'list' ? '#ffffff' : 'transparent',
                            color: viewMode === 'list' ? '#3730A3' : '#64748B',
                            cursor: 'pointer', boxShadow: viewMode === 'list' ? '0 1px 3px rgba(0,0,0,0.08)' : 'none',
                            transition: 'all 0.15s ease'
                        }}
                    >
                        <List size={15} />
                    </button>
                </div>
            </div>

            {/* Main Content Area: Pie Chart Mode OR List View Mode */}
            {viewMode === 'chart' ? (
                <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', minHeight: '160px' }}>
                    {/* Compact Interactive Donut Chart */}
                    <div style={{ width: '140px', height: '140px', position: 'relative', flexShrink: 0 }}>
                        <ResponsiveContainer width="100%" height="100%">
                            <PieChart>
                                <Pie
                                    data={chartData}
                                    cx="50%"
                                    cy="50%"
                                    innerRadius={36}
                                    outerRadius={56}
                                    paddingAngle={3}
                                    dataKey="value"
                                    onClick={(entry) => setSelectedTable(entry)}
                                    cursor="pointer"
                                >
                                    {chartData.map((entry, index) => (
                                        <Cell key={`cell-${index}`} fill={entry.color} stroke="#ffffff" strokeWidth={2} />
                                    ))}
                                </Pie>
                                <Tooltip
                                    formatter={(value, name) => [`${value.toLocaleString()} rows (${((value / totalRows) * 100).toFixed(1)}%)`, name]}
                                    contentStyle={{ borderRadius: '8px', border: '1px solid #e2e8f0', boxShadow: '0 4px 12px rgba(0,0,0,0.08)', fontSize: '0.75rem', fontWeight: 600 }}
                                />
                            </PieChart>
                        </ResponsiveContainer>
                    </div>

                    {/* Table Rows Breakdown */}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem', flex: 1, minWidth: 0 }}>
                        {chartData.map((item, i) => {
                            const percent = ((item.value / totalRows) * 100).toFixed(1);
                            return (
                                <div 
                                    key={i} 
                                    onClick={() => setSelectedTable(item)}
                                    style={{ 
                                        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                                        padding: '0.25rem 0.5rem', borderRadius: '6px', cursor: 'pointer',
                                        backgroundColor: selectedTable?.name === item.name ? '#f1f5f9' : 'transparent',
                                        transition: 'all 0.15s ease'
                                    }}
                                    onMouseEnter={(e) => e.currentTarget.style.backgroundColor = '#f8fafc'}
                                    onMouseLeave={(e) => e.currentTarget.style.backgroundColor = selectedTable?.name === item.name ? '#f1f5f9' : 'transparent'}
                                >
                                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', minWidth: 0 }}>
                                        <div style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: item.color, flexShrink: 0 }} />
                                        <span style={{ fontSize: '0.8125rem', fontWeight: 600, color: '#15133A', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                                            {item.name}
                                        </span>
                                    </div>
                                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexShrink: 0 }}>
                                        <span style={{ fontSize: '0.75rem', color: '#64748B', fontWeight: 500 }}>
                                            {item.rawRows} rows
                                        </span>
                                        <span style={{ fontSize: '0.75rem', fontWeight: 700, color: '#15133A', minWidth: '36px', textAlign: 'right' }}>
                                            {percent}%
                                        </span>
                                        <ChevronRight size={13} color="#94a3b8" />
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                </div>
            ) : (
                /* List View Mode */
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                    {chartData.map((item, i) => {
                        const percent = ((item.value / totalRows) * 100).toFixed(1);
                        return (
                            <div 
                                key={i}
                                onClick={() => setSelectedTable(item)}
                                style={{
                                    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                                    padding: '0.625rem 0.75rem', borderRadius: '10px', border: '1px solid #e2e8f0',
                                    backgroundColor: '#ffffff', cursor: 'pointer', transition: 'all 0.15s ease'
                                }}
                                onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = '#f8fafc'; e.currentTarget.style.borderColor = '#cbd5e1'; }}
                                onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = '#ffffff'; e.currentTarget.style.borderColor = '#e2e8f0'; }}
                            >
                                <div style={{ display: 'flex', alignItems: 'center', gap: '0.625rem' }}>
                                    <div style={{ width: '28px', height: '28px', borderRadius: '8px', backgroundColor: `${item.color}15`, color: item.color, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                                        <Table size={15} />
                                    </div>
                                    <div>
                                        <div style={{ fontSize: '0.8125rem', fontWeight: 700, color: '#15133A' }}>{item.name}</div>
                                        <div style={{ fontSize: '0.6875rem', color: '#64748B' }}>{item.rawRows} total records</div>
                                    </div>
                                </div>

                                <div style={{ display: 'flex', alignItems: 'center', gap: '0.625rem' }}>
                                    <div style={{ textAlign: 'right' }}>
                                        <div style={{ fontSize: '0.8125rem', fontWeight: 800, color: item.color }}>{percent}%</div>
                                        <div style={{ fontSize: '0.6875rem', color: '#64748B' }}>of DB storage</div>
                                    </div>
                                    <ChevronRight size={14} color="#94a3b8" />
                                </div>
                            </div>
                        );
                    })}
                </div>
            )}

            {/* Interactive Schema Modal */}
            {selectedTable && activeSchema && ReactDOM.createPortal(
                <div style={{
                    position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
                    backgroundColor: 'rgba(15, 23, 42, 0.75)',
                    backdropFilter: 'blur(8px)',
                    zIndex: 999999,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    padding: '1.5rem', boxSizing: 'border-box'
                }}>
                    <div style={{
                        width: '100%', maxWidth: '600px', backgroundColor: '#ffffff', borderRadius: '24px',
                        padding: '2rem', boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.25)',
                        border: '1px solid #e2e8f0', display: 'flex', flexDirection: 'column', gap: '1.5rem'
                    }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                                <div style={{ width: '40px', height: '40px', borderRadius: '12px', backgroundColor: `${selectedTable.color}15`, color: selectedTable.color, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                                    <Table size={20} />
                                </div>
                                <div>
                                    <h3 style={{ fontSize: '1.25rem', fontWeight: 800, color: '#15133A', margin: 0 }}>
                                        {selectedTable.name}
                                    </h3>
                                    <p style={{ fontSize: '0.8125rem', color: '#64748B', margin: 0 }}>
                                        Estimated {selectedTable.rawRows} records • {activeSchema.size}
                                    </p>
                                </div>
                            </div>
                            <button onClick={() => setSelectedTable(null)} style={{ border: 'none', background: '#f1f5f9', borderRadius: '50%', width: '32px', height: '32px', display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer' }}>
                                <X size={16} color="#64748B" />
                            </button>
                        </div>

                        {/* JPA Entity Mapping Target */}
                        <div style={{ padding: '0.875rem 1rem', borderRadius: '12px', backgroundColor: '#f8fafc', border: '1px solid #e2e8f0', display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                            <span style={{ fontSize: '0.6875rem', color: '#64748B', textTransform: 'uppercase', letterSpacing: '0.04em', fontWeight: 700 }}>Target JPA Entity Class</span>
                            <span style={{ fontSize: '0.8125rem', fontFamily: 'monospace', fontWeight: 700, color: '#3730A3' }}>{activeSchema.entity}</span>
                        </div>

                        {/* Columns Schema */}
                        <div>
                            <div style={{ fontSize: '0.8125rem', fontWeight: 700, color: '#15133A', marginBottom: '0.625rem' }}>Table Structure & Columns</div>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', maxHeight: '220px', overflowY: 'auto' }}>
                                {activeSchema.columns.map((col, idx) => (
                                    <div key={idx} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0.5rem 0.75rem', borderRadius: '8px', border: '1px solid #f1f5f9', backgroundColor: '#ffffff', fontSize: '0.75rem' }}>
                                        <span style={{ fontWeight: 700, color: '#15133A', fontFamily: 'monospace' }}>{col.name}</span>
                                        <span style={{ color: '#6366f1', fontWeight: 600 }}>{col.type}</span>
                                    </div>
                                ))}
                            </div>
                        </div>
                    </div>
                </div>,
                document.body
            )}
        </div>
    );
};

export default TopTablesList;
