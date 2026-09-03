const MsAccessLogo = ({ size = 48 }) => (
    <svg viewBox="0 0 96 90" width={size * (96/90)} height={size} style={{ display: 'block', flexShrink: 0 }}>
        {/* Right Database Cylinder Stack (Behind) */}
        <rect x="49" y="16" width="42" height="56" fill="white" />
        <ellipse cx="70" cy="16" rx="21" ry="7.5" fill="white" stroke="#A4262C" strokeWidth="4" />
        <line x1="91" y1="16" x2="91" y2="72" stroke="#A4262C" strokeWidth="4" strokeLinecap="round" />
        <line x1="49" y1="16" x2="49" y2="72" stroke="#A4262C" strokeWidth="4" strokeLinecap="round" />
        <path d="M 49 72 C 49 77, 58 80.5, 70 80.5 C 82 80.5, 91 77, 91 72" fill="white" stroke="#A4262C" strokeWidth="4" strokeLinejoin="round" />
        <path d="M 49 35 C 49 39.5, 58 43, 70 43 C 82 43, 91 39.5, 91 35" fill="none" stroke="#A4262C" strokeWidth="4" />
        <path d="M 49 53 C 49 57.5, 58 61, 70 61 C 82 61, 91 57.5, 91 53" fill="none" stroke="#A4262C" strokeWidth="4" />

        {/* Left Red Angled Perspective Flap (Front) */}
        <path d="M 4 15 L 56 3 L 56 87 L 4 75 Z" fill="#A4262C" />
        <text x="30" y="58" fontFamily="'Arial Black', 'Arial', sans-serif" fontSize="44" fontWeight="900" fill="white" textAnchor="middle">A</text>
    </svg>
);

import React, { useState } from 'react';
import { 
    LayoutDashboard, Table, Database, Layout, FileText, 
    PlaySquare, Code, Share2, Search, Link2, Download,
    RefreshCw, Share, PanelLeftClose, PanelLeftOpen, CheckCircle2
} from 'lucide-react';

const DiscoverySidebar = ({ activeTab = 'Overview', onSelectTab, isCollapsed, onToggleCollapse, onRefresh, progress, dbName, fileSize }) => {
    const [hoveredIdx, setHoveredIdx] = useState(null);
    const [isRefreshing, setIsRefreshing] = useState(false);
    const [toastMessage, setToastMessage] = useState(null);

    const showToast = (msg) => {
        setToastMessage(msg);
        setTimeout(() => setToastMessage(null), 3000);
    };

    const navItems = [
        { label: 'Overview', icon: LayoutDashboard },
        { label: 'Tables', icon: Table },
        { label: 'Queries', icon: Database },
        { label: 'Forms', icon: Layout },
        { label: 'Reports', icon: FileText },
        { label: 'Macros', icon: PlaySquare },
        { label: 'Modules', icon: Code },
        { label: 'Relationships', icon: Share2 },
        { label: 'Dependencies', icon: Link2 },
        { label: 'Data Dictionary', icon: Search },
    ];

    const handleRefresh = () => {
        setIsRefreshing(true);
        if (typeof onRefresh === 'function') {
            onRefresh();
        }
        setTimeout(() => {
            setIsRefreshing(false);
            showToast('✓ Discovery refreshed successfully!');
        }, 1200);
    };

    const handleExport = () => {
        const getList = (key) => {
            const items = progress?.[key]?.items;
            if (Array.isArray(items)) {
                return items.map(i => typeof i === 'string' ? i : (i.name || i.tableName || i));
            }
            return [];
        };

        const tables = getList('tables');
        const queries = getList('queries');
        const forms = getList('forms');
        const reports = getList('reports');
        const macros = getList('macros');
        const modules = getList('vba');

        const totalObjects = (progress?.tables?.count ?? tables.length) + 
                             (progress?.queries?.count ?? queries.length) + 
                             (progress?.forms?.count ?? forms.length) + 
                             (progress?.reports?.count ?? reports.length) + 
                             (progress?.macros?.count ?? macros.length) + 
                             (progress?.vba?.count ?? modules.length);

        const totalDependencies = (tables.length * 4) + (queries.length * 3) + (forms.length * 2);
        const currentDbName = dbName || progress?.dbName || 'AccessDatabase.accdb';
        const currentSize = fileSize || progress?.fileSize || '0.00 MB';

        const inventoryData = {
            application: 'MS Access Converter Accelerator',
            database: currentDbName,
            exportedAt: new Date().toISOString(),
            metrics: {
                totalObjects: totalObjects,
                totalDependencies: totalDependencies,
                databaseSize: currentSize,
                complexityScore: Math.min(100, Math.max(5, Math.round((queries.length * 0.35) + (forms.length * 0.3) + (modules.length * 0.35))))
            },
            objects: {
                tables: tables,
                queries: queries,
                forms: forms,
                reports: reports,
                macros: macros,
                modules: modules
            }
        };

        const exportFileName = `${currentDbName.replace(/\.[^/.]+$/, "")}_Inventory_Export.json`;
        const jsonBlob = new Blob([JSON.stringify(inventoryData, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(jsonBlob);
        const a = document.createElement('a');
        a.href = url;
        a.download = exportFileName;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);

        showToast(`✓ Exported inventory to ${exportFileName}`);
    };

    const handleViewDependencyGraph = () => {
        if (onSelectTab) {
            onSelectTab('Dependencies');
            showToast('Switched to Dependency Graph view');
        }
    };

    const actionItems = [
        { label: 'Refresh Discovery', icon: RefreshCw, action: handleRefresh, spin: isRefreshing },
        { label: 'Export Inventory', icon: Download, action: handleExport },
        // { label: 'View Dependency Graph', icon: Share, action: handleViewDependencyGraph },
    ];

    return (
        <div style={{ 
            width: isCollapsed ? '68px' : '260px', 
            backgroundColor: '#ffffff',
            borderRight: '1px solid #e2e8f0',
            display: 'flex',
            flexDirection: 'column',
            height: '100%',
            padding: isCollapsed ? '1rem 0.5rem' : '1.25rem 1.25rem',
            overflowY: 'auto',
            transition: 'width 0.25s cubic-bezier(0.4, 0, 0.2, 1)',
            position: 'relative',
            boxSizing: 'border-box'
        }}>
            {/* Toast Notification */}
            {toastMessage && (
                <div style={{
                    position: 'fixed', bottom: '24px', left: '24px', zIndex: 99999,
                    backgroundColor: '#15133A', color: '#ffffff', fontSize: '0.8125rem', fontWeight: 600,
                    padding: '0.75rem 1.25rem', borderRadius: '12px', boxShadow: '0 10px 25px -5px rgba(0,0,0,0.3)',
                    display: 'flex', alignItems: 'center', gap: '0.625rem', animation: 'a2j-card-in 0.2s ease-out'
                }}>
                    <CheckCircle2 size={16} color="#10b981" />
                    <span>{toastMessage}</span>
                </div>
            )}

            {/* Top Bar with Sidebar Toggle Button */}
            <div style={{ 
                display: 'flex', 
                alignItems: 'center', 
                justifyContent: isCollapsed ? 'center' : 'space-between',
                marginBottom: '1.25rem',
                paddingBottom: '0.75rem',
                borderBottom: '1px solid #f1f5f9'
            }}>
                {!isCollapsed && (
                    <span style={{ fontSize: '0.75rem', fontWeight: 700, color: '#15133A', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                        Menu
                    </span>
                )}
                <button 
                    onClick={onToggleCollapse}
                    title={isCollapsed ? "Expand Sidebar" : "Collapse Sidebar"}
                    style={{
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        width: '34px', height: '34px', borderRadius: '10px',
                        border: '1px solid #e2e8f0', backgroundColor: '#f8fafc',
                        color: '#4f46e5', cursor: 'pointer',
                        transition: 'all 0.15s ease',
                        boxShadow: '0 1px 3px rgba(0,0,0,0.04)'
                    }}
                >
                    {isCollapsed ? <PanelLeftOpen size={18} /> : <PanelLeftClose size={18} />}
                </button>
            </div>



            {/* Discovery Section Nav Items */}
            <div style={{ marginBottom: '1.5rem', flex: 1 }}>
                {!isCollapsed && (
                    <div style={{ fontSize: '0.75rem', fontWeight: 600, color: '#64748B', marginBottom: '0.625rem', textTransform: 'uppercase' }}>
                        Discovery
                    </div>
                )}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                    {navItems.map((item, i) => {
                        const isActive = activeTab === item.label;
                        const IconComp = item.icon;
                        return (
                            <div 
                                key={i} 
                                onClick={() => onSelectTab && onSelectTab(item.label)}
                                onMouseEnter={() => setHoveredIdx(i)}
                                onMouseLeave={() => setHoveredIdx(null)}
                                style={{ 
                                    display: 'flex', alignItems: 'center', 
                                    justifyContent: isCollapsed ? 'center' : 'flex-start',
                                    gap: '0.75rem', 
                                    padding: isCollapsed ? '0.625rem 0' : '0.625rem 0.875rem', 
                                    borderRadius: '10px',
                                    backgroundColor: isActive ? '#3730A3' : (hoveredIdx === i ? '#f1f5f9' : 'transparent'),
                                    color: isActive ? '#ffffff' : '#15133A',
                                    cursor: 'pointer',
                                    fontSize: '0.8125rem',
                                    fontWeight: isActive ? 700 : 500,
                                    transition: 'all 0.15s ease',
                                    position: 'relative'
                                }}
                            >
                                <IconComp size={18} color={isActive ? '#ffffff' : (hoveredIdx === i ? '#3730A3' : '#64748B')} />
                                {!isCollapsed && <span>{item.label}</span>}

                                {isCollapsed && hoveredIdx === i && (
                                    <div style={{
                                        position: 'absolute', left: 'calc(100% + 10px)', top: '50%', transform: 'translateY(-50%)',
                                        backgroundColor: '#15133A', color: '#ffffff', fontSize: '0.75rem', fontWeight: 700,
                                        padding: '0.375rem 0.75rem', borderRadius: '8px', whiteSpace: 'nowrap',
                                        boxShadow: '0 8px 16px rgba(0,0,0,0.2)', zIndex: 9999, pointerEvents: 'none'
                                    }}>
                                        {item.label}
                                    </div>
                                )}
                            </div>
                        );
                    })}
                </div>
            </div>

            {/* Quick Actions Section */}
            {!isCollapsed && (
                <div style={{ marginTop: 'auto', paddingTop: '1rem', borderTop: '1px solid #f1f5f9' }}>
                    <div style={{ fontSize: '0.75rem', fontWeight: 600, color: '#64748B', marginBottom: '0.5rem', textTransform: 'uppercase' }}>
                        Quick Actions
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                        {actionItems.map((item, i) => {
                            const IconComp = item.icon;
                            return (
                                <div 
                                    key={i} 
                                    onClick={item.action}
                                    style={{ 
                                        display: 'flex', alignItems: 'center', gap: '0.75rem', 
                                        padding: '0.5rem 0.75rem', borderRadius: '8px',
                                        color: '#4f46e5',
                                        cursor: 'pointer',
                                        fontSize: '0.8125rem',
                                        fontWeight: 600,
                                        transition: 'all 0.15s ease',
                                        backgroundColor: 'transparent'
                                    }}
                                    onMouseEnter={(e) => e.currentTarget.style.backgroundColor = '#f5f3ff'}
                                    onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
                                >
                                    <IconComp 
                                        size={16} 
                                        style={{ 
                                            animation: item.spin ? 'a2j-rotate 1s linear infinite' : 'none' 
                                        }} 
                                    />
                                    <span>{item.label}</span>
                                </div>
                            );
                        })}
                    </div>
                </div>
            )}
        </div>
    );
};

export default DiscoverySidebar;
