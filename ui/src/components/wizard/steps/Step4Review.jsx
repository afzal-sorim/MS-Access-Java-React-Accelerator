import React, { useEffect, useState, useMemo } from 'react';
import { useWizard } from '../../../context/WizardContext';
import { getReport } from '../../../services/api';
import { OBJECT_STATUS, SUPPORTABILITY_STATUS, RISK_LEVELS, STATUS_COLORS } from '../../../utils/constants';
import { getStatusColor, getRiskColor, formatNumber, formatPercentage } from '../../../utils/helpers';

/**
 * Step 4: Map & Review
 * Per spec section 47:
 * - Tabs: Tables, Queries, Forms, Reports, Modules, Macros, External Dependencies
 * - Allow automatic mapping and manual mapping
 * - Show: Access object, records, target, status, risk, comments
 */
const REVIEW_TABS = [
    { key: 'tables', label: 'Tables', icon: '🗃️' },
    { key: 'queries', label: 'Queries', icon: '🔍' },
    { key: 'forms', label: 'Forms', icon: '📋' },
    { key: 'reports', label: 'Reports', icon: '📊' },
    { key: 'modules', label: 'Modules', icon: '💻' },
    { key: 'macros', label: 'Macros', icon: '⚡' },
    { key: 'externalDependencies', label: 'External Dependencies', icon: '🔗' },
];

/** Mapping target options per object category (tab) */
const TARGET_OPTIONS = {
    tables: [
        'PostgreSQL Table',
        'PostgreSQL Table (Enum/Lookup)',
        'PostgreSQL Table (Audit)',
        'PostgreSQL View',
        'Skip – Do Not Migrate',
    ],
    queries: [
        'JPA Repository Method',
        'JPA Repository / Custom Query',
        'Native SQL @Query',
        'Spring Service Method',
        'Database View',
        'Manual Migration',
    ],
    forms: [
        'React Page + Form',
        'React Page + DataGrid',
        'React Dashboard Page',
        'React Modal / Dialog',
        'React Sub-Component',
        'Manual Migration',
    ],
    reports: [
        'Report Service + PDF/Excel',
        'PDF Report Service',
        'Excel Export Service',
        'React Data View',
        'Manual Migration',
    ],
    modules: [
        'Spring Service / Utility',
        'Spring Service Method',
        'Spring Scheduled Task',
        'Spring Event Listener',
        'Manual Migration',
    ],
    macros: [
        'React Navigation / API Call',
        'Application Startup',
        'Spring Scheduled Task',
        'React Event Handler',
        'Manual Migration',
    ],
    externalDependencies: [
        'Manual Review',
        'Spring Integration Service',
        'PostgreSQL (Migration)',
        'REST API Client',
        'Skip – Do Not Migrate',
    ],
};

/** Conversion strategy options per category */
const CONVERSION_OPTIONS = {
    tables: ['ENTITY', 'ENUM_LOOKUP', 'AUDIT_TABLE', 'VIEW', 'SKIP'],
    queries: ['REPOSITORY_METHOD', 'NATIVE_QUERY', 'SERVICE_METHOD', 'VIEW', 'MANUAL'],
    forms: ['PAGE_FORM', 'PAGE_DATAGRID', 'PAGE_DASHBOARD', 'MODAL', 'SUB_COMPONENT', 'MANUAL'],
    reports: ['REPORT_SERVICE', 'PDF_SERVICE', 'EXCEL_SERVICE', 'DATA_VIEW', 'MANUAL'],
    modules: ['SERVICE_METHOD', 'SCHEDULED_TASK', 'EVENT_LISTENER', 'UTILITY', 'MANUAL'],
    macros: ['NAVIGATION', 'STARTUP_WORKFLOW', 'SCHEDULED_TASK', 'EVENT_HANDLER', 'MANUAL'],
    externalDependencies: ['MANUAL', 'INTEGRATION_SERVICE', 'ENTITY', 'REST_CLIENT', 'SKIP'],
};

const STATUS_OPTIONS = ['SUPPORTED', 'SUPPORTED_WITH_REVIEW', 'SUPPORTED_WITH_TRANSFORMATION', 'UNSUPPORTED'];
const RISK_OPTIONS = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'];

/**
 * Modal component for editing an object's mapping
 */
function MappingEditorModal({ object, tab, onSave, onClose }) {
    const [target, setTarget] = useState(object.target || '');
    const [conversion, setConversion] = useState(object.conversion || '');
    const [status, setStatus] = useState(object.status || 'SUPPORTED');
    const [risk, setRisk] = useState(object.risk || 'LOW');
    const [notes, setNotes] = useState(object.notes || '');

    const targetOptions = TARGET_OPTIONS[tab] || [];
    const conversionOptions = CONVERSION_OPTIONS[tab] || [];

    const handleSave = () => {
        onSave({ target, conversion, status, risk, notes });
    };

    return (
        <div
            style={{
                position: 'fixed', inset: 0, zIndex: 9999,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}
            onClick={onClose}
        >
            {/* Backdrop */}
            <div style={{
                position: 'absolute', inset: 0,
                background: 'rgba(0, 0, 0, 0.6)', backdropFilter: 'blur(4px)',
            }} />

            {/* Modal Card */}
            <div
                onClick={(e) => e.stopPropagation()}
                style={{
                    position: 'relative', zIndex: 1,
                    background: 'var(--color-bg-card, #1e1e2e)',
                    border: '1px solid var(--color-border, #333)',
                    borderRadius: '12px',
                    width: '520px', maxWidth: '92vw', maxHeight: '85vh',
                    overflow: 'auto',
                    boxShadow: '0 24px 64px rgba(0,0,0,0.45)',
                    animation: 'fadeIn 0.2s ease-out',
                }}
            >
                {/* Header */}
                <div style={{
                    padding: '1.25rem 1.5rem',
                    borderBottom: '1px solid var(--color-border, #333)',
                    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                }}>
                    <div>
                        <h3 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 600 }}>Edit Mapping</h3>
                        <p style={{ margin: '0.25rem 0 0', fontSize: '0.8125rem', opacity: 0.6 }}>
                            {object.name}
                        </p>
                    </div>
                    <button
                        onClick={onClose}
                        style={{
                            background: 'none', border: 'none', cursor: 'pointer',
                            fontSize: '1.25rem', color: 'var(--color-text-muted)', padding: '0.25rem',
                        }}
                        aria-label="Close"
                    >✕</button>
                </div>

                {/* Body */}
                <div style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
                    {/* Target */}
                    <div>
                        <label style={{ display: 'block', fontWeight: 500, marginBottom: '0.375rem', fontSize: '0.8125rem' }}>
                            Target Architecture
                        </label>
                        <select
                            className="form-control"
                            value={target}
                            onChange={(e) => setTarget(e.target.value)}
                            style={{ width: '100%' }}
                        >
                            {/* Keep current value if not in the list */}
                            {!targetOptions.includes(target) && target && (
                                <option value={target}>{target} (current)</option>
                            )}
                            {targetOptions.map(opt => (
                                <option key={opt} value={opt}>{opt}</option>
                            ))}
                        </select>
                    </div>

                    {/* Conversion Strategy */}
                    <div>
                        <label style={{ display: 'block', fontWeight: 500, marginBottom: '0.375rem', fontSize: '0.8125rem' }}>
                            Conversion Strategy
                        </label>
                        <select
                            className="form-control"
                            value={conversion}
                            onChange={(e) => setConversion(e.target.value)}
                            style={{ width: '100%' }}
                        >
                            {!conversionOptions.includes(conversion) && conversion && (
                                <option value={conversion}>{conversion.replace(/_/g, ' ')} (current)</option>
                            )}
                            {conversionOptions.map(opt => (
                                <option key={opt} value={opt}>{opt.replace(/_/g, ' ')}</option>
                            ))}
                        </select>
                    </div>

                    {/* Status + Risk side by side */}
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                        <div>
                            <label style={{ display: 'block', fontWeight: 500, marginBottom: '0.375rem', fontSize: '0.8125rem' }}>
                                Status Override
                            </label>
                            <select
                                className="form-control"
                                value={status}
                                onChange={(e) => setStatus(e.target.value)}
                                style={{ width: '100%' }}
                            >
                                {STATUS_OPTIONS.map(opt => (
                                    <option key={opt} value={opt}>{opt.replace(/_/g, ' ')}</option>
                                ))}
                            </select>
                        </div>
                        <div>
                            <label style={{ display: 'block', fontWeight: 500, marginBottom: '0.375rem', fontSize: '0.8125rem' }}>
                                Risk Level
                            </label>
                            <select
                                className="form-control"
                                value={risk}
                                onChange={(e) => setRisk(e.target.value)}
                                style={{ width: '100%' }}
                            >
                                {RISK_OPTIONS.map(opt => (
                                    <option key={opt} value={opt}>{opt}</option>
                                ))}
                            </select>
                        </div>
                    </div>

                    {/* Notes */}
                    <div>
                        <label style={{ display: 'block', fontWeight: 500, marginBottom: '0.375rem', fontSize: '0.8125rem' }}>
                            Notes
                        </label>
                        <textarea
                            className="form-control"
                            rows={3}
                            value={notes}
                            onChange={(e) => setNotes(e.target.value)}
                            placeholder="Optional migration notes or special instructions..."
                            style={{ width: '100%', resize: 'vertical' }}
                        />
                    </div>

                    {/* Reason (read-only) */}
                    {object.reason && (
                        <div style={{
                            padding: '0.75rem 1rem', borderRadius: '8px',
                            background: 'var(--color-bg-alt, #2a2a3e)',
                            fontSize: '0.8125rem', lineHeight: 1.5,
                        }}>
                            <span style={{ fontWeight: 600 }}>Analysis note: </span>
                            {object.reason}
                        </div>
                    )}
                </div>

                {/* Footer */}
                <div style={{
                    padding: '1rem 1.5rem',
                    borderTop: '1px solid var(--color-border, #333)',
                    display: 'flex', justifyContent: 'flex-end', gap: '0.75rem',
                }}>
                    <button className="btn btn-secondary" onClick={onClose}>Cancel</button>
                    <button className="btn btn-primary" onClick={handleSave}>Save Mapping</button>
                </div>
            </div>
        </div>
    );
}

export default function Step4Review() {
    const { state, actions } = useWizard();
    const { reviewData, reviewTab, selectedObjects, analysisJobId } = state;
    const [loading, setLoading] = useState(false);
    const [filterStatus, setFilterStatus] = useState('all');
    const [searchQuery, setSearchQuery] = useState('');
    const [editingObject, setEditingObject] = useState(null);

    // Load review data from backend when step is entered
    useEffect(() => {
        if (analysisJobId && (!reviewData.tables || reviewData.tables.length === 0)) {
            loadReviewData();
        }
    }, [analysisJobId]);

    const loadReviewData = async () => {
        if (!analysisJobId) return;
        setLoading(true);
        try {
            const report = await getReport(analysisJobId);
            // Transform report data into review format
            const transformed = transformReportData(report);
            actions.setReviewData(transformed);
        } catch (err) {
            console.error('Failed to load review data:', err);
            // Use mock data for demonstration
            actions.setReviewData(getMockReviewData());
        } finally {
            setLoading(false);
        }
    };

    // Transform backend report data to review format
    const transformReportData = (report) => {
        const supportability = report.supportability || [];

        return {
            tables: supportability
                .filter(s => s.category === 'TABLE')
                .map((s, i) => ({
                    id: `table-${i}`,
                    name: s.object,
                    recordCount: '—',
                    target: 'PostgreSQL Table',
                    status: s.status,
                    risk: s.risk,
                    confidence: s.confidence,
                    reason: s.reason,
                    conversion: s.conversion,
                    selected: true,
                })),
            queries: supportability
                .filter(s => s.category === 'QUERY')
                .map((s, i) => ({
                    id: `query-${i}`,
                    name: s.object,
                    recordCount: '—',
                    target: 'JPA Repository / Custom Query',
                    status: s.status,
                    risk: s.risk,
                    confidence: s.confidence,
                    reason: s.reason,
                    conversion: s.conversion,
                    selected: true,
                })),
            forms: supportability
                .filter(s => s.category === 'FORM')
                .map((s, i) => ({
                    id: `form-${i}`,
                    name: s.object,
                    recordCount: '—',
                    target: 'React Page + Components',
                    status: s.status,
                    risk: s.risk,
                    confidence: s.confidence,
                    reason: s.reason,
                    conversion: s.conversion,
                    selected: true,
                })),
            reports: supportability
                .filter(s => s.category === 'REPORT')
                .map((s, i) => ({
                    id: `report-${i}`,
                    name: s.object,
                    recordCount: '—',
                    target: 'Report Service + PDF/Excel',
                    status: s.status,
                    risk: s.risk,
                    confidence: s.confidence,
                    reason: s.reason,
                    conversion: s.conversion,
                    selected: true,
                })),
            modules: supportability
                .filter(s => s.category === 'VBA_MODULE' || s.category === 'VBA_FUNCTION' || s.category === 'VBA_SUB')
                .map((s, i) => ({
                    id: `module-${i}`,
                    name: s.object,
                    recordCount: '—',
                    target: 'Spring Service / Utility',
                    status: s.status,
                    risk: s.risk,
                    confidence: s.confidence,
                    reason: s.reason,
                    conversion: s.conversion,
                    selected: true,
                })),
            macros: supportability
                .filter(s => s.category === 'MACRO')
                .map((s, i) => ({
                    id: `macro-${i}`,
                    name: s.object,
                    recordCount: '—',
                    target: 'React Navigation / API Call',
                    status: s.status,
                    risk: s.risk,
                    confidence: s.confidence,
                    reason: s.reason,
                    conversion: s.conversion,
                    selected: true,
                })),
            externalDependencies: (report.externalDependencies || []).map((dep, i) => ({
                id: `ext-${i}`,
                name: dep.name || dep.type,
                recordCount: '—',
                target: dep.migrationStrategy || 'Manual Review',
                status: 'UNSUPPORTED',
                risk: dep.riskLevel || 'HIGH',
                confidence: 0,
                reason: dep.details || 'External dependency requires manual migration',
                conversion: 'MANUAL',
                selected: false,
            })),
        };
    };

    // Mock data for demonstration
    const getMockReviewData = () => ({
        tables: [
            { id: 't1', name: 'Employees', recordCount: '1,250', target: 'PostgreSQL Table', status: 'SUPPORTED', risk: 'LOW', confidence: 0.99, reason: 'Standard table with PK and indexes', conversion: 'ENTITY', selected: true },
            { id: 't2', name: 'Departments', recordCount: '25', target: 'PostgreSQL Table', status: 'SUPPORTED', risk: 'LOW', confidence: 0.99, reason: 'Simple lookup table', conversion: 'ENTITY', selected: true },
            { id: 't3', name: 'LeaveRequests', recordCount: '3,420', target: 'PostgreSQL Table', status: 'SUPPORTED', risk: 'LOW', confidence: 0.98, reason: 'Standard transaction table', conversion: 'ENTITY', selected: true },
            { id: 't4', name: 'SysUsers', recordCount: '50', target: 'PostgreSQL Table (User)', status: 'SUPPORTED_WITH_REVIEW', risk: 'MEDIUM', confidence: 0.85, reason: 'Contains plaintext passwords', conversion: 'ENTITY', selected: true },
        ],
        queries: [
            { id: 'q1', name: 'qryActiveEmployees', recordCount: '—', target: 'JPA Repository', status: 'SUPPORTED', risk: 'LOW', confidence: 0.95, reason: 'Simple SELECT with WHERE', conversion: 'REPOSITORY_METHOD', selected: true },
            { id: 'q2', name: 'qryLeaveBalance', recordCount: '—', target: 'Custom Query', status: 'SUPPORTED_WITH_REVIEW', risk: 'MEDIUM', confidence: 0.82, reason: 'Uses DLookup domain function', conversion: 'SERVICE_METHOD', selected: true },
            { id: 'q3', name: 'qryDeptSummary', recordCount: '—', target: 'JPA Repository', status: 'SUPPORTED', risk: 'LOW', confidence: 0.93, reason: 'GROUP BY with aggregates', conversion: 'REPOSITORY_METHOD', selected: true },
        ],
        forms: [
            { id: 'f1', name: 'frmEmployee', recordCount: '—', target: 'React Page + Form', status: 'SUPPORTED', risk: 'LOW', confidence: 0.94, reason: 'Standard CRUD form', conversion: 'PAGE_FORM', selected: true },
            { id: 'f2', name: 'frmLeaveRequest', recordCount: '—', target: 'React Page + Form', status: 'SUPPORTED_WITH_REVIEW', risk: 'MEDIUM', confidence: 0.78, reason: 'Complex validation with VBA', conversion: 'PAGE_FORM', selected: true },
            { id: 'f3', name: 'frmDashboard', recordCount: '—', target: 'React Dashboard Page', status: 'SUPPORTED', risk: 'LOW', confidence: 0.91, reason: 'Read-only dashboard with charts', conversion: 'PAGE_DASHBOARD', selected: true },
        ],
        reports: [
            { id: 'r1', name: 'rptEmployeeDirectory', recordCount: '—', target: 'PDF Report Service', status: 'SUPPORTED', risk: 'LOW', confidence: 0.89, reason: 'Tabular report with grouping', conversion: 'REPORT_SERVICE', selected: true },
            { id: 'r2', name: 'rptLeaveSummary', recordCount: '—', target: 'PDF Report Service', status: 'SUPPORTED_WITH_REVIEW', risk: 'MEDIUM', confidence: 0.75, reason: 'Complex subreport structure', conversion: 'REPORT_SERVICE', selected: true },
        ],
        modules: [
            { id: 'm1', name: 'modLeave.CalculateDays', recordCount: '—', target: 'Spring Service', status: 'SUPPORTED', risk: 'LOW', confidence: 0.96, reason: 'Pure business logic function', conversion: 'SERVICE_METHOD', selected: true },
            { id: 'm2', name: 'modEmail.SendNotification', recordCount: '—', target: 'Email Service', status: 'SUPPORTED_WITH_REVIEW', risk: 'HIGH', confidence: 0.65, reason: 'Outlook COM automation', conversion: 'SERVICE_METHOD', selected: true },
        ],
        macros: [
            { id: 'mc1', name: 'AutoExec', recordCount: '—', target: 'Application Startup', status: 'SUPPORTED', risk: 'LOW', confidence: 0.92, reason: 'Standard startup macro', conversion: 'STARTUP_WORKFLOW', selected: true },
            { id: 'mc2', name: 'mcrPrintReport', recordCount: '—', target: 'React Navigation', status: 'SUPPORTED', risk: 'LOW', confidence: 0.90, reason: 'OpenReport action', conversion: 'NAVIGATION', selected: true },
        ],
        externalDependencies: [
            { id: 'ext1', name: 'Outlook COM', recordCount: '—', target: 'Email Service (Manual)', status: 'UNSUPPORTED', risk: 'HIGH', confidence: 0, reason: 'External Outlook automation requires manual implementation', conversion: 'MANUAL', selected: false },
            { id: 'ext2', name: 'SQL Server Linked Table', recordCount: '—', target: 'PostgreSQL (Migration)', status: 'SUPPORTED_WITH_REVIEW', risk: 'MEDIUM', confidence: 0.80, reason: 'Linked SQL Server table needs migration', conversion: 'ENTITY', selected: true },
        ],
    });

    // Filter and search objects
    const currentObjects = useMemo(() => {
        const objects = reviewData[reviewTab] || [];
        return objects.filter(obj => {
            const matchesSearch = !searchQuery ||
                obj.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
                obj.target.toLowerCase().includes(searchQuery.toLowerCase());
            const matchesStatus = filterStatus === 'all' || obj.status === filterStatus;
            return matchesSearch && matchesStatus;
        });
    }, [reviewData, reviewTab, filterStatus, searchQuery]);

    // Count by status
    const statusCounts = useMemo(() => {
        const objects = reviewData[reviewTab] || [];
        return objects.reduce((acc, obj) => {
            acc[obj.status] = (acc[obj.status] || 0) + 1;
            return acc;
        }, {});
    }, [reviewData, reviewTab]);

    // Count how many of the current tab's objects are selected
    const currentSelectedCount = useMemo(() => {
        return currentObjects.filter(o => selectedObjects.has(o.id)).length;
    }, [currentObjects, selectedObjects]);

    const handleSelectAll = () => {
        actions.selectAllObjects(currentObjects);
    };

    const handleDeselectAll = () => {
        const currentIds = currentObjects.map(o => o.id);
        actions.deselectAllObjects(currentIds);
    };

    const handleRowClick = (objectId) => {
        actions.toggleObjectSelection(objectId);
    };

    const handleSaveMapping = (mapping) => {
        if (editingObject) {
            actions.updateObjectMapping(reviewTab, editingObject.id, mapping);
            setEditingObject(null);
        }
    };

    const getStatusBadge = (status) => {
        const colors = {
            SUPPORTED: 'badge-success',
            SUPPORTED_WITH_REVIEW: 'badge-warning',
            SUPPORTED_WITH_TRANSFORMATION: 'badge-blue',
            UNSUPPORTED: 'badge-danger',
            FAILED_EXTRACTION: 'badge-danger',
            MANUAL: 'badge-neutral',
        };
        return <span className={`badge ${colors[status] || 'badge-neutral'}`}>{status.replace(/_/g, ' ')}</span>;
    };

    const getRiskBadge = (risk) => {
        const colors = {
            LOW: 'badge-success',
            MEDIUM: 'badge-warning',
            HIGH: 'badge-danger',
            CRITICAL: 'badge-danger',
        };
        return <span className={`badge ${colors[risk] || 'badge-neutral'}`}>{risk}</span>;
    };

    // Get columns for current tab
    const getColumns = () => {
        const baseColumns = [
            { key: 'name', label: 'Access Object', width: '25%' },
            { key: 'target', label: 'Target', width: '20%' },
            { key: 'status', label: 'Status', width: '15%' },
            { key: 'risk', label: 'Risk', width: '10%' },
        ];

        const tabSpecificColumns = {
            tables: [
                ...baseColumns,
                { key: 'recordCount', label: 'Records', width: '10%' },
                { key: 'confidence', label: 'Confidence', width: '10%' },
            ],
            queries: [
                ...baseColumns,
                { key: 'conversion', label: 'Conversion', width: '15%' },
            ],
            forms: [
                ...baseColumns,
                { key: 'conversion', label: 'Type', width: '15%' },
            ],
            reports: [
                ...baseColumns,
                { key: 'conversion', label: 'Type', width: '15%' },
            ],
            modules: [
                ...baseColumns,
                { key: 'conversion', label: 'Target', width: '15%' },
            ],
            macros: [
                ...baseColumns,
                { key: 'conversion', label: 'Action', width: '15%' },
            ],
            externalDependencies: [
                { key: 'name', label: 'Dependency', width: '25%' },
                { key: 'target', label: 'Migration Strategy', width: '25%' },
                { key: 'status', label: 'Status', width: '15%' },
                { key: 'risk', label: 'Risk', width: '10%' },
            ],
        };

        return tabSpecificColumns[reviewTab] || baseColumns;
    };

    return (
        <div>
            <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '1rem' }}>
                <div>
                    <h2 className="card-title">Map & Review Objects</h2>
                    <p className="card-subtitle">
                        Review extracted objects, their conversion status, and adjust mappings as needed.
                    </p>
                </div>
                <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                    <select
                        className="form-control"
                        style={{ width: 'auto', minWidth: '180px' }}
                        value={filterStatus}
                        onChange={(e) => setFilterStatus(e.target.value)}
                    >
                        <option value="all">All Statuses</option>
                        <option value="SUPPORTED">Supported</option>
                        <option value="SUPPORTED_WITH_REVIEW">Needs Review</option>
                        <option value="SUPPORTED_WITH_TRANSFORMATION">With Transformation</option>
                        <option value="UNSUPPORTED">Unsupported</option>
                    </select>
                    <input
                        type="text"
                        className="form-control"
                        style={{ width: 'auto', minWidth: '200px' }}
                        placeholder="Search objects..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                    />
                </div>
            </div>

            {loading && (
                <div className="alert alert-info" style={{ textAlign: 'center', padding: '3rem' }}>
                    <div className="spinner" style={{ margin: '0 auto 1rem' }} />
                    <p>Loading analysis results...</p>
                </div>
            )}

            {!loading && (
                <>
                    {/* Tab Bar */}
                    <div className="tab-bar" role="tablist">
                        {REVIEW_TABS.map((tab) => {
                            const count = reviewData[tab.key]?.length || 0;
                            return (
                                <button
                                    key={tab.key}
                                    role="tab"
                                    aria-selected={reviewTab === tab.key}
                                    className={`tab-button ${reviewTab === tab.key ? 'active' : ''}`}
                                    onClick={() => actions.setReviewTab(tab.key)}
                                >
                                    {tab.icon} {tab.label}
                                    <span style={{ marginLeft: '0.5rem', fontSize: '0.75rem', opacity: 0.7 }}>
                                        {formatNumber(count)}
                                    </span>
                                </button>
                            );
                        })}
                    </div>

                    {/* Status Summary */}
                    <div style={{ display: 'flex', gap: '1rem', marginBottom: '1rem', flexWrap: 'wrap' }}>
                        {Object.entries(statusCounts).map(([status, count]) => (
                            <span
                                key={status}
                                className={`badge ${getStatusBadge(status).props.className.replace('badge ', '')}`}
                                style={{ fontSize: '0.75rem', padding: '0.25rem 0.625rem' }}
                            >
                                {status.replace(/_/g, ' ')}: {count}
                            </span>
                        ))}
                    </div>

                    {/* Selection Actions */}
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                        <div style={{ display: 'flex', gap: '0.5rem' }}>
                            <button
                                className="btn btn-secondary btn-sm"
                                onClick={handleSelectAll}
                                disabled={currentSelectedCount === currentObjects.length}
                            >
                                Select All ({formatNumber(currentObjects.length)})
                            </button>
                            <button
                                className="btn btn-secondary btn-sm"
                                onClick={handleDeselectAll}
                                disabled={currentSelectedCount === 0}
                            >
                                Deselect All
                            </button>
                        </div>
                        <div style={{ fontSize: '0.8125rem', color: 'var(--color-text-muted)' }}>
                            {formatNumber(currentSelectedCount)} of {formatNumber(currentObjects.length)} selected
                        </div>
                    </div>

                    {/* Objects Table */}
                    <div style={{ overflowX: 'auto' }}>
                        <table className="data-table">
                            <thead>
                                <tr>
                                    <th style={{ width: '40px' }}>
                                        <input
                                            type="checkbox"
                                            checked={currentSelectedCount === currentObjects.length && currentObjects.length > 0}
                                            indeterminate={currentSelectedCount > 0 && currentSelectedCount < currentObjects.length ? true : undefined}
                                            onChange={() => currentSelectedCount === currentObjects.length ? handleDeselectAll() : handleSelectAll()}
                                            aria-label="Select all"
                                        />
                                    </th>
                                    {getColumns().map(col => (
                                        <th key={col.key} style={{ width: col.width }}>
                                            {col.label}
                                        </th>
                                    ))}
                                    <th style={{ width: '120px' }}>Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                {currentObjects.map((obj) => (
                                    <tr
                                        key={obj.id}
                                        onClick={() => handleRowClick(obj.id)}
                                        style={{ cursor: 'pointer', background: selectedObjects.has(obj.id) ? 'rgba(59, 130, 246, 0.05)' : 'transparent' }}
                                    >
                                        <td>
                                            <input
                                                type="checkbox"
                                                checked={selectedObjects.has(obj.id)}
                                                onChange={(e) => {
                                                    e.stopPropagation();
                                                    actions.toggleObjectSelection(obj.id);
                                                }}
                                            />
                                        </td>
                                        <td style={{ fontWeight: 500 }}>{obj.name}</td>
                                        <td>{obj.target}</td>
                                        <td>{getStatusBadge(obj.status)}</td>
                                        <td>{getRiskBadge(obj.risk)}</td>
                                        {getColumns().some(c => c.key === 'recordCount') && (
                                            <td>{obj.recordCount}</td>
                                        )}
                                        {getColumns().some(c => c.key === 'confidence') && (
                                            <td>
                                                {obj.confidence !== undefined ? (
                                                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                                        <div style={{ width: '60px', height: '4px', background: 'var(--color-bg-alt)', borderRadius: '2px', overflow: 'hidden' }}>
                                                            <div
                                                                style={{
                                                                    width: `${Math.round(obj.confidence * 100)}%`,
                                                                    height: '100%',
                                                                    background: obj.confidence > 0.8 ? 'var(--color-success)' : obj.confidence > 0.6 ? 'var(--color-warning)' : 'var(--color-danger)',
                                                                }}
                                                            />
                                                        </div>
                                                        <span style={{ fontSize: '0.75rem' }}>{formatPercentage(obj.confidence * 100)}</span>
                                                    </div>
                                                ) : (
                                                    '—'
                                                )}
                                            </td>
                                        )}
                                        {getColumns().some(c => c.key === 'conversion') && (
                                            <td>
                                                <span className="badge badge-info" style={{ textTransform: 'lowercase' }}>
                                                    {obj.conversion?.toLowerCase().replace(/_/g, ' ') || '—'}
                                                </span>
                                            </td>
                                        )}
                                        <td>
                                            <button
                                                className="btn btn-secondary btn-sm"
                                                onClick={(e) => {
                                                    e.stopPropagation();
                                                    setEditingObject(obj);
                                                }}
                                                style={{ padding: '0.25rem 0.5rem', fontSize: '0.6875rem' }}
                                            >
                                                Edit Mapping
                                            </button>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>

                    {currentObjects.length === 0 && (
                        <div className="alert alert-info" style={{ textAlign: 'center', padding: '3rem' }}>
                            <p>No objects found for this category.</p>
                        </div>
                    )}
                </>
            )}

            {/* Mapping Editor Modal */}
            {editingObject && (
                <MappingEditorModal
                    object={editingObject}
                    tab={reviewTab}
                    onSave={handleSaveMapping}
                    onClose={() => setEditingObject(null)}
                />
            )}
        </div>
    );
}