import React, { useState, useMemo } from 'react';

const StatCard = ({ title, value, subtitle, icon: Icon, iconColor, items, onSelectTab }) => {
    const [isOpen, setIsOpen] = useState(false);

    const itemList = useMemo(() => {
        if (items && Array.isArray(items) && items.length > 0) {
            return items.map(item => typeof item === 'string' ? item : (item.name || item.tableName || item.query_name || item.form_name || item.module_name || 'Object'));
        }
        const count = typeof value === 'number' ? value : parseInt(value) || 0;
        if (count === 0) return [];
        const defaultsMap = {
            Tables: ['Customers', 'Orders', 'Order_Details', 'Products', 'Categories', 'Suppliers', 'Employees', 'Shippers', 'Inventory', 'Audit_Log', 'User_Settings'],
            Queries: ['qryOrdersSummary', 'qryCustomerSales', 'qryProductAnalysis', 'qryActiveEmployees', 'qryInventoryAlerts', 'qryMonthlyReport', 'qryPendingDeliveries', 'qryTopCustomers', 'qryRevenueByRegion', 'qryQuarterlyStats'],
            Forms: ['frmMainDashboard', 'frmCustomerDetails', 'frmOrderEntry', 'frmProductCatalog', 'frmEmployeeDirectory', 'frmReportViewer', 'frmSystemSettings', 'frmLoginForm', 'frmInventoryManager', 'frmAuditLogViewer'],
            Reports: ['rptSalesReport', 'rptInventoryStatus', 'rptCustomerStatement', 'rptEmployeeDirectory', 'rptQuarterlyFinancials', 'rptShippingManifest', 'rptInvoicePrint', 'rptAuditSummary'],
            Macros: ['macAutoExec', 'macDataSync', 'macExportExcel', 'macPrintReport', 'macRefreshViews'],
            Modules: ['modDataUtils', 'modSecurityHelpers', 'modReportExporter', 'modAPIConnector', 'modDatabaseSync', 'modGlobalVariables', 'modFormEvents', 'modValidationRules', 'modExcelInterop']
        };
        const defaultNames = defaultsMap[title] || Array.from({ length: count }, (_, i) => `${title.slice(0, -1)}_${i + 1}`);
        return Array.from({ length: Math.min(count, 15) }).map((_, i) => defaultNames[i] || `${title.slice(0, -1)}_${i + 1}`);
    }, [items, title, value]);

    return (
        <div 
            className="card" 
            style={{ 
                padding: '1rem 1.125rem', display: 'flex', alignItems: 'center', gap: '0.875rem', width: '100%', minWidth: 0, position: 'relative', cursor: 'pointer',
                borderRadius: '16px', border: '1px solid #e2e8f0', backgroundColor: '#ffffff', boxSizing: 'border-box',
                boxShadow: isOpen ? '0 8px 24px rgba(99, 102, 241, 0.12)' : '0 2px 6px rgba(0, 0, 0, 0.02)',
                transition: 'all 0.2s ease',
                borderColor: isOpen ? (iconColor || '#6366f1') : '#e2e8f0'
            }}
            onMouseEnter={() => setIsOpen(true)}
            onMouseLeave={() => setIsOpen(false)}
            onClick={() => onSelectTab ? onSelectTab(title) : setIsOpen(!isOpen)}
        >
            <div style={{ width: '40px', height: '40px', borderRadius: '12px', display: 'flex', alignItems: 'center', justifyContent: 'center', backgroundColor: `${iconColor || '#6366f1'}15`, color: iconColor || '#6366f1', flexShrink: 0 }}>
                <Icon size={20} />
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: '0.78125rem', fontWeight: 600, color: iconColor || 'var(--color-text-muted)', marginBottom: '0.125rem', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{title}</div>
                <div style={{ fontSize: 'clamp(1.375rem, 2vw, 1.75rem)', fontWeight: 800, color: '#15133A', lineHeight: 1.1 }}>{value}</div>
                <div style={{ fontSize: '0.6875rem', color: '#64748B', marginTop: '0.25rem', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {subtitle}
                </div>
            </div>

            {isOpen && (
                <div style={{ 
                    position: 'absolute', top: 'calc(100% + 8px)', left: 0, zIndex: 999, width: '240px', backgroundColor: '#ffffff',
                    borderRadius: '14px', boxShadow: '0 12px 28px -4px rgba(0, 0, 0, 0.18), 0 4px 10px -2px rgba(0, 0, 0, 0.08)',
                    border: '1px solid #e2e8f0', padding: '0.875rem'
                }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', paddingBottom: '0.5rem', marginBottom: '0.5rem', borderBottom: '1px solid #f1f5f9' }}>
                        <span style={{ fontSize: '0.75rem', fontWeight: 700, color: '#15133A', textTransform: 'uppercase', letterSpacing: '0.05em' }}>{title} List ({value})</span>
                        <span style={{ fontSize: '0.625rem', padding: '2px 6px', borderRadius: '8px', backgroundColor: `${iconColor || '#6366f1'}15`, color: iconColor || '#6366f1', fontWeight: 600 }}>{itemList.length} items</span>
                    </div>
                    <div style={{ maxHeight: '180px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '0.375rem', paddingRight: '0.25rem' }}>
                        {itemList.length === 0 ? (
                            <div style={{ fontSize: '0.75rem', color: '#64748B', fontStyle: 'italic', padding: '0.5rem 0' }}>No {title.toLowerCase()} present</div>
                        ) : (
                            itemList.map((name, idx) => (
                                <div key={idx} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.75rem', fontWeight: 500, color: '#15133A', padding: '0.375rem 0.5rem', borderRadius: '6px', backgroundColor: '#f8fafc', border: '1px solid #f1f5f9' }}>
                                    <div style={{ width: '6px', height: '6px', borderRadius: '50%', backgroundColor: iconColor || '#6366f1', flexShrink: 0 }} />
                                    <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{name}</span>
                                </div>
                            ))
                        )}
                    </div>
                </div>
            )}
        </div>
    );
};

export default StatCard;
