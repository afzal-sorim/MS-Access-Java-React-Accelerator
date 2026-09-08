import React, { useMemo } from 'react';

const RelationshipDiagram = ({ data }) => {
    const { tables = {}, relationships = [] } = data;

    const tableItems = useMemo(() => {
        if (Array.isArray(tables.items)) return tables.items;
        if (Array.isArray(tables)) return tables;
        return [];
    }, [tables]);

    if (!tableItems || tableItems.length === 0) {
        return (
            <div className="card" style={{ padding: '2rem', textAlign: 'center', background: '#fff', borderRadius: '16px', border: '1px solid #e2e8f0', gridColumn: 'span 2', minHeight: '300px', display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
                <div style={{ fontSize: '3rem', marginBottom: '1rem' }}>🗄️</div>
                <h3 style={{ margin: '0 0 0.5rem 0', color: '#1e293b' }}>Discovery in Progress</h3>
                <p style={{ color: '#64748b', fontSize: '0.875rem' }}>Waiting for database schema analysis to complete...</p>
            </div>
        );
    }

    const normalizeName = (name) => String(name || '').replace(/[\[\]`"]+/g, '').trim().toLowerCase();

    // Limit to first 12 tables for performance in discovery view
    const displayTables = tableItems.slice(0, 12);
    const displayTableNames = new Set(displayTables.map(t => normalizeName(t.name)));

    const filteredRelationships = relationships.filter(rel =>
        displayTableNames.has(normalizeName(rel.parent_table)) &&
        displayTableNames.has(normalizeName(rel.child_table))
    );

    const columnsPerRow = Math.min(displayTables.length, 3);
    const columnCount = Math.max(...displayTables.map(table => table.columns?.length || 0), 1);
    const rowHeight = Math.max(220, 100 + columnCount * 32);
    const diagramRows = Math.ceil(displayTables.length / columnsPerRow);

    const tablePositions = new Map(displayTables.map((table, index) => [normalizeName(table.name), {
        index,
        column: index % columnsPerRow,
        row: Math.floor(index / columnsPerRow),
        height: 42 + (table.columns?.length || 0) * 32,
    }]));

    return (
        <div className="card" style={{
            background: '#f8fafc',
            borderRadius: '16px',
            border: '1px solid #e2e8f0',
            gridColumn: 'span 2',
            overflow: 'hidden',
            display: 'flex',
            flexDirection: 'column',
            minHeight: '500px'
        }}>
            {/* Header */}
            <div style={{ padding: '1.25rem 1.5rem', borderBottom: '1px solid #e2e8f0', display: 'flex', alignItems: 'center', justifyContent: 'space-between', background: '#fff' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                    <div style={{ width: '32px', height: '32px', borderRadius: '8px', background: 'linear-gradient(135deg, #4f46e5, #06b6d4)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '1rem', color: '#fff' }}>📐</div>
                    <div>
                        <div style={{ fontSize: '0.9rem', fontWeight: 800, color: '#1e293b' }}>Detailed Entity-Relationship Diagram</div>
                        <div style={{ fontSize: '0.7rem', color: '#64748b' }}>{tableItems.length} tables · {relationships.length} relationships</div>
                    </div>
                </div>
                <div style={{ display: 'flex', gap: '0.5rem' }}>
                    <span style={{ background: '#f1f5f9', color: '#475569', fontSize: '0.65rem', padding: '4px 10px', borderRadius: '20px', fontWeight: 600 }}>🔑 PK</span>
                    <span style={{ background: '#f1f5f9', color: '#475569', fontSize: '0.65rem', padding: '4px 10px', borderRadius: '20px', fontWeight: 600 }}>🔗 FK</span>
                </div>
            </div>

            <style>
                {`
                @keyframes flowAnimation {
                    from { stroke-dashoffset: 8; }
                    to { stroke-dashoffset: 0; }
                }
                .erd-canvas::-webkit-scrollbar { width: 6px; height: 6px; }
                .erd-canvas::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 10px; }
                `}
            </style>

            {/* Diagram Canvas */}
            <div className="erd-canvas" style={{ padding: '2rem', position: 'relative', flex: 1, overflow: 'auto', background: '#fff' }}>
                <div style={{ position: 'relative', minWidth: '800px', height: `${diagramRows * rowHeight}px` }}>
                    <svg
                        aria-label="Table relationships"
                        viewBox={`0 0 100 ${diagramRows * rowHeight}`}
                        preserveAspectRatio="none"
                        style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', pointerEvents: 'none', overflow: 'visible' }}
                    >
                        <defs>
                            <marker id="erd-arrow-head" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse">
                                <path d="M 0 0 L 10 5 L 0 10 z" fill="#6366f1" />
                            </marker>
                        </defs>
                        {filteredRelationships.map((rel, index) => {
                            const child = tablePositions.get(normalizeName(rel.child_table));
                            const parent = tablePositions.get(normalizeName(rel.parent_table));
                            if (!child || !parent) return null;

                            const colWidth = 100 / columnsPerRow;
                            const tableW = colWidth * 0.9;

                            const childX = child.column * colWidth;
                            const parentX = parent.column * colWidth;
                            const childY = child.row * rowHeight;
                            const parentY = parent.row * rowHeight;

                            const isHorizontal = child.row === parent.row;
                            const childOnRight = child.column > parent.column;

                            const startX = isHorizontal ? childX + (childOnRight ? 0 : tableW) : childX + tableW/2;
                            const endX = isHorizontal ? parentX + (childOnRight ? tableW : 0) : parentX + tableW/2;

                            const startY = isHorizontal
                                ? childY + 60
                                : childY + (child.row < parent.row ? child.height : 0);
                            const endY = isHorizontal
                                ? parentY + 60
                                : parentY + (child.row < parent.row ? 0 : parent.height);

                            const middleY = (startY + endY) / 2;

                            return (
                                <g key={`rel-${index}`}>
                                    {isHorizontal ? (
                                        <line x1={startX} y1={startY} x2={endX} y2={endY} stroke="#6366f1" strokeWidth="0.3" markerEnd="url(#erd-arrow-head)" strokeDasharray="1.5 1" style={{ animation: 'flowAnimation 2s linear infinite' }} />
                                    ) : (
                                        <path d={`M ${startX} ${startY} C ${startX} ${middleY}, ${endX} ${middleY}, ${endX} ${endY}`} fill="none" stroke="#6366f1" strokeWidth="0.3" markerEnd="url(#erd-arrow-head)" strokeDasharray="1.5 1" style={{ animation: 'flowAnimation 2s linear infinite' }} />
                                    )}
                                </g>
                            );
                        })}
                    </svg>

                    {displayTables.map((table, tIdx) => (
                        <div key={table.name} style={{
                            position: 'absolute',
                            left: `${(tIdx % columnsPerRow) * (100 / columnsPerRow)}%`,
                            top: `${Math.floor(tIdx / columnsPerRow) * rowHeight}px`,
                            width: `${(100 / columnsPerRow) * 0.9}%`,
                            background: '#fff',
                            border: '1px solid #e2e8f0',
                            borderRadius: '12px',
                            overflow: 'hidden',
                            boxShadow: '0 4px 15px -3px rgba(0, 0, 0, 0.07)'
                        }}>
                            {/* Table header */}
                            <div style={{
                                background: 'linear-gradient(90deg, #f8fafc, #f1f5f9)',
                                color: '#0f172a',
                                padding: '0.75rem 1rem',
                                fontWeight: 800,
                                fontSize: '0.8rem',
                                display: 'flex',
                                justifyContent: 'space-between',
                                alignItems: 'center',
                                borderBottom: '1px solid #e2e8f0'
                            }}>
                                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                    <span style={{ color: '#6366f1' }}>▦</span>
                                    <span>{table.name}</span>
                                </div>
                                <span style={{ fontSize: '0.6rem', background: '#e2e8f0', color: '#475569', padding: '2px 8px', borderRadius: '10px' }}>DB TABLE</span>
                            </div>

                            {/* Columns */}
                            <div style={{ padding: '0.25rem 0' }}>
                                {(table.columns || []).slice(0, 10).map((col, ci) => (
                                    <div key={col.name} style={{
                                        display: 'flex',
                                        justifyContent: 'space-between',
                                        alignItems: 'center',
                                        padding: '0.4rem 1rem',
                                        fontSize: '0.7rem',
                                        borderBottom: ci < (table.columns.length > 10 ? 9 : table.columns.length - 1) ? '1px solid #f8fafc' : 'none',
                                        background: col.is_pk ? '#fefce8' : 'transparent'
                                    }}>
                                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                            {col.is_pk && <span style={{ color: '#ca8a04', fontWeight: 900 }}>🔑</span>}
                                            {col.is_fk && !col.is_pk && <span style={{ color: '#6366f1', fontWeight: 900 }}>🔗</span>}
                                            <span style={{ fontWeight: col.is_pk ? 700 : 500, color: col.is_pk ? '#854d0e' : '#334155' }}>{col.name}</span>
                                        </div>
                                        <span style={{ color: '#94a3b8', fontSize: '0.6rem', fontFamily: 'monospace' }}>{col.pg_type || col.access_type || 'TEXT'}</span>
                                    </div>
                                ))}
                                {table.columns?.length > 10 && (
                                    <div style={{ padding: '0.4rem 1rem', fontSize: '0.65rem', color: '#94a3b8', fontStyle: 'italic', textAlign: 'center', background: '#f8fafc' }}>
                                        + {table.columns.length - 10} more columns
                                    </div>
                                )}
                            </div>
                        </div>
                    ))}
                </div>
            </div>

            {/* Legend / Footer */}
            <div style={{ padding: '0.75rem 1.5rem', borderTop: '1px solid #e2e8f0', background: '#f8fafc', display: 'flex', justifyContent: 'center', gap: '2rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.7rem', color: '#64748b' }}>
                    <div style={{ width: '12px', height: '0px', borderTop: '2px dashed #6366f1' }}></div>
                    <span>Data Flow</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.7rem', color: '#64748b' }}>
                    <div style={{ width: '10px', height: '10px', borderRadius: '2px', background: '#fefce8', border: '1px solid #e2e8f0' }}></div>
                    <span>Primary Key</span>
                </div>
                {tableItems.length > 12 && (
                    <div style={{ fontSize: '0.7rem', color: '#6366f1', fontWeight: 600 }}>
                        Showing 12 of {tableItems.length} tables
                    </div>
                )}
            </div>
        </div>
    );
};

export default RelationshipDiagram;
