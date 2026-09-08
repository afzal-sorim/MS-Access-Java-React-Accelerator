import React, { useEffect, useState, useMemo } from 'react';
import ReactDOM from 'react-dom';
import { useWizard } from '../../../context/WizardContext';
import { getReport } from '../../../services/api';
import { formatNumber, formatPercentage } from '../../../utils/helpers';
import { FolderTree, Network } from 'lucide-react';

/**
 * Step 4: Map & Review
 * Redesigned for maximum effectiveness and executive view.
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

const CONVERSION_OPTIONS = {
    tables: ['ENTITY', 'ENUM_LOOKUP', 'AUDIT_TABLE', 'VIEW', 'SKIP'],
    queries: ['REPOSITORY_METHOD', 'NATIVE_QUERY', 'SERVICE_METHOD', 'VIEW', 'MANUAL'],
    forms: ['PAGE_FORM', 'PAGE_DATAGRID', 'PAGE_DASHBOARD', 'MODAL', 'SUB_COMPONENT', 'MANUAL'],
    reports: ['REPORT_SERVICE', 'PDF_SERVICE', 'EXCEL_SERVICE', 'DATA_VIEW', 'MANUAL'],
    modules: ['SERVICE_METHOD', 'SCHEDULED_TASK', 'EVENT_LISTENER', 'UTILITY', 'MANUAL'],
    macros: ['NAVIGATION', 'STARTUP_WORKFLOW', 'SCHEDULED_TASK', 'EVENT_HANDLER', 'MANUAL'],
    externalDependencies: ['MANUAL', 'INTEGRATION_SERVICE', 'ENTITY', 'REST_CLIENT', 'SKIP'],
};

const FORM_TARGET_BY_CONVERSION = {
    PAGE_FORM: 'React Page + Form',
    PAGE_DATAGRID: 'React Page + DataGrid',
    PAGE_DASHBOARD: 'React Dashboard Page',
    MODAL: 'React Modal / Dialog',
    SUB_COMPONENT: 'React Sub-Component',
    MANUAL: 'Manual Migration',
};

const FORM_CONVERSION_BY_TARGET = Object.fromEntries(
    Object.entries(FORM_TARGET_BY_CONVERSION).map(([conversion, target]) => [target, conversion])
);

function normalizeFormMapping(conversion, target) {
    const normalizedConversion = String(conversion || '').toUpperCase().replace(/\s+/g, '_');
    const inferredTarget = FORM_TARGET_BY_CONVERSION[normalizedConversion];

    return {
        conversion: FORM_TARGET_BY_CONVERSION[normalizedConversion] ? normalizedConversion : (target ? FORM_CONVERSION_BY_TARGET[target] || 'PAGE_FORM' : 'PAGE_FORM'),
        target: inferredTarget || FORM_TARGET_BY_CONVERSION[FORM_CONVERSION_BY_TARGET[target] || 'PAGE_FORM'],
    };
}



/** Slide-Over Mapping Drawer Component */
function MappingDrawer({ object, tab, onSave, onClose }) {
    const initialMapping = tab === 'forms'
        ? normalizeFormMapping(object.conversion, object.target)
        : { target: object.target || '', conversion: object.conversion || '' };
    const [target, setTarget] = useState(initialMapping.target);
    const [conversion, setConversion] = useState(initialMapping.conversion);

    const [notes, setNotes] = useState(object.notes || '');

    const targetOptions = TARGET_OPTIONS[tab] || [];
    const conversionOptions = CONVERSION_OPTIONS[tab] || [];

    const handleSave = () => {
        onSave({ target, conversion, status, risk, notes });
    };

    return (
        <div className="slide-over-backdrop" onClick={onClose}>
            <div className="slide-over-panel" onClick={(e) => e.stopPropagation()}>
                <div className="slide-over-header">
                    <div>
                        <h3 style={{ margin: 0, fontSize: '1.25rem', fontWeight: 700, color: 'var(--color-text)' }}>
                            Mapping Configuration
                        </h3>
                        <p style={{ margin: '0.25rem 0 0', fontSize: '0.875rem', color: 'var(--color-text-muted)' }}>
                            {object.name}
                        </p>
                    </div>
                    <button
                        onClick={onClose}
                        style={{
                            background: 'none', border: 'none', cursor: 'pointer',
                            fontSize: '1.5rem', color: 'var(--color-text-light)', padding: '0.25rem',
                        }}
                    >×</button>
                </div>

                <div className="slide-over-body">
                    {object.reason && (
                        <div style={{
                            padding: '1rem', borderRadius: '8px',
                            background: '#eff6ff', border: '1px solid #bfdbfe',
                            color: '#1e3a8a', fontSize: '0.875rem', lineHeight: 1.5,
                        }}>
                            <div style={{ fontWeight: 700, marginBottom: '0.25rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                🤖 AI Analysis Rationale
                            </div>
                            {object.reason}
                        </div>
                    )}

                    <div>
                        <label className="form-label" style={{ display: 'block', fontWeight: 500, marginBottom: '0.375rem', fontSize: '0.8125rem' }}>Target Architecture</label>
                        <select className="form-control" style={{ width: '100%' }} value={target} onChange={(e) => {
                            const newTarget = e.target.value;
                            setTarget(newTarget);
                            if (tab === 'forms' && FORM_CONVERSION_BY_TARGET[newTarget]) {
                                setConversion(FORM_CONVERSION_BY_TARGET[newTarget]);
                            }
                        }}>
                            {!targetOptions.includes(target) && target && <option value={target}>{target} (current)</option>}
                            {targetOptions.map(opt => <option key={opt} value={opt}>{opt}</option>)}
                        </select>
                    </div>

                    <div>
                        <label className="form-label" style={{ display: 'block', fontWeight: 500, marginBottom: '0.375rem', fontSize: '0.8125rem' }}>Conversion Strategy</label>
                        <select className="form-control" style={{ width: '100%' }} value={conversion} onChange={(e) => setConversion(e.target.value)}>
                            {!conversionOptions.includes(conversion) && conversion && <option value={conversion}>{conversion.replace(/_/g, ' ')} (current)</option>}
                            {conversionOptions.map(opt => <option key={opt} value={opt}>{opt.replace(/_/g, ' ')}</option>)}
                        </select>
                    </div>

                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                        <div>
                            <label className="form-label" style={{ display: 'block', fontWeight: 500, marginBottom: '0.375rem', fontSize: '0.8125rem' }}>Status Override</label>
                            <select className="form-control" style={{ width: '100%' }} value={status} onChange={(e) => setStatus(e.target.value)}>
                                {STATUS_OPTIONS.map(opt => <option key={opt} value={opt}>{opt.replace(/_/g, ' ')}</option>)}
                            </select>
                        </div>
                        <div>
                            <label className="form-label" style={{ display: 'block', fontWeight: 500, marginBottom: '0.375rem', fontSize: '0.8125rem' }}>Risk Level</label>
                            <select className="form-control" style={{ width: '100%' }} value={risk} onChange={(e) => setRisk(e.target.value)}>
                                {RISK_OPTIONS.map(opt => <option key={opt} value={opt}>{opt}</option>)}
                            </select>
                        </div>
                    </div>

                    <div>
                        <label className="form-label" style={{ display: 'block', fontWeight: 500, marginBottom: '0.375rem', fontSize: '0.8125rem' }}>Custom Notes</label>
                        <textarea
                            className="form-control" rows={4} style={{ width: '100%' }} value={notes}
                            onChange={(e) => setNotes(e.target.value)}
                            placeholder="Add implementation notes, caveats, or instructions for manual migration..."
                        />
                    </div>
                </div>

                <div className="slide-over-footer">
                    <button className="btn btn-secondary" onClick={onClose}>Cancel</button>
                    <button className="btn btn-primary" onClick={handleSave}>Save Changes</button>
                </div>
            </div>
        </div>
    );
}

function DescriptionPopover({ object, summary, category }) {
    const [showModal, setShowModal] = useState(false);
    const categoryLabels = {
        tables: 'database table',
        forms: 'data-entry form',
        queries: 'data query',
        reports: 'report definition',
        modules: 'VBA module',
        macros: 'automation macro',
        externalDependencies: 'external dependency',
    };
    const typeLabel = categoryLabels[category] || 'Access object';
    const recordDetail = object.recordCount && object.recordCount !== '—'
        ? `The source contains approximately ${object.recordCount} records for this object.`
        : 'The source record count was not available during analysis, so the generated mapping should be verified against the source database.';
    const migrationDetail = object.target
        ? `The recommended migration target is ${object.target}${object.conversion ? ` using the ${object.conversion.replace(/_/g, ' ').toLowerCase()} strategy` : ''}.`
        : 'The migration target still needs to be confirmed during implementation.';

    // Use aiReason if available, fallback to reason
    const detail = object.aiReason || object.reason || `The analyzer classified ${object.name} as a ${typeLabel} based on its Access structure and dependencies.`;

    return (
        <>
            <div
                style={{ cursor: 'pointer', borderBottom: '1px dotted #64748b', display: 'inline-block', width: '100%' }}
                onClick={() => setShowModal(true)}
            >
                {summary}
            </div>
            {showModal && ReactDOM.createPortal(
                <div
                    onClick={() => setShowModal(false)}
                    style={{
                        position: 'fixed', top: 0, left: 0, width: '100vw', height: '100vh',
                        backgroundColor: 'rgba(15, 23, 42, 0.4)', zIndex: 9999,
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        backdropFilter: 'blur(4px)',
                        padding: '2rem', boxSizing: 'border-box'
                    }}
                >
                    <div
                        onClick={e => e.stopPropagation()}
                        style={{
                            width: 'min(650px, 95vw)', background: '#fff', borderRadius: '16px',
                            padding: '2.5rem', boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.25)',
                            position: 'relative', textAlign: 'left',
                            maxHeight: 'calc(100vh - 4rem)', overflowY: 'auto'
                        }}
                    >
                        <button
                            onClick={() => setShowModal(false)}
                            style={{ position: 'absolute', top: '1.25rem', right: '1.25rem', background: 'none', border: 'none', fontSize: '1.5rem', cursor: 'pointer', color: '#64748b' }}
                        >×</button>

                        <div style={{ marginBottom: '1.5rem', color: '#3730a3', fontWeight: 800, fontSize: '1.25rem', display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                            <span style={{ fontSize: '1.75rem' }}>🤖</span>
                            AI Analysis for {object.name}
                        </div>

                        <div style={{ display: 'grid', gap: '1.5rem', color: '#334155', fontSize: '0.95rem', lineHeight: 1.6 }}>
                            <div>
                                <strong style={{ color: '#1e293b', display: 'block', marginBottom: '0.5rem', fontSize: '1rem' }}>Reasoning:</strong>
                                <div style={{ background: '#f8fafc', padding: '1.25rem', borderRadius: '12px', border: '1px solid #e2e8f0', whiteSpace: 'pre-line', maxHeight: '250px', overflowY: 'auto', fontSize: '0.9rem', color: '#334155' }}>
                                    {detail}
                                </div>
                            </div>

                            {object.humanAction && (
                                <div>
                                    <strong style={{ color: '#b45309', display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem', fontSize: '1rem' }}>
                                        ⚠️ Required Human Action:
                                    </strong>
                                    <div style={{ background: '#fffbeb', padding: '1rem', borderRadius: '10px', border: '1px solid #fde68a', color: '#92400e', fontSize: '0.875rem', fontWeight: 500 }}>
                                        {object.humanAction}
                                    </div>
                                </div>
                            )}

                            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem', padding: '1.25rem', background: '#f1f5f9', borderRadius: '12px' }}>
                                <div><strong style={{ color: '#475569', fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Object Profile</strong><div style={{ color: '#1e293b', fontWeight: 600, marginTop: '0.25rem' }}>{typeLabel}</div></div>
                                <div><strong style={{ color: '#475569', fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Data Context</strong><div style={{ color: '#1e293b', fontWeight: 600, marginTop: '0.25rem' }}>{object.recordCount !== '—' ? object.recordCount : 'Not available'}</div></div>
                            </div>

                            <div>
                                <strong style={{ color: '#1e293b', display: 'block', marginBottom: '0.5rem', fontSize: '1rem' }}>Migration Plan:</strong>
                                <div style={{ color: '#4f46e5', fontWeight: 700, padding: '0.75rem 1rem', background: '#eef2ff', borderRadius: '8px', borderLeft: '4px solid #4f46e5' }}>
                                    {migrationDetail}
                                </div>
                            </div>
                        </div>

                        <div style={{ marginTop: '2.5rem', display: 'flex', justifyContent: 'flex-end' }}>
                            <button
                                className="btn btn-primary"
                                onClick={() => setShowModal(false)}
                                style={{ padding: '0.75rem 2.5rem', fontSize: '1rem', fontWeight: 700, borderRadius: '10px' }}
                            >Close</button>
                        </div>
                    </div>
                </div>,
                document.body
            )}
        </>
    );
}

export default function Step4Review({ onOpenExplorer, onOpenErDiagram }) {
    const { state, actions } = useWizard();
    const { reviewData, reviewTab, selectedObjects, analysisJobId } = state;
    
    const [loading, setLoading] = useState(false);
    const [filterStatus, setFilterStatus] = useState('all');
    const [searchQuery, setSearchQuery] = useState('');
    const [batchActionTab, setBatchActionTab] = useState(false);

    // Initial load logic...
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
            actions.setReviewData(transformReportData(report));
        } catch (err) {
            console.error('Failed to load review data:', err);
            actions.setReviewData(getMockReviewData());
        } finally {
            setLoading(false);
        }
    };

    // Transformation logic (simplified for brevity)
    const transformReportData = (report) => {
        const supportability = report.supportability || [];
        const funcSummaries = report.functionality_summaries || [];
        const summaryMap = new Map(funcSummaries.map(s => [s.object_name, s]));

        const enhanceReason = (item) => {
            const summary = summaryMap.get(item.object);
            const status = item.status;
            const originalReason = summary?.what_it_does || summary?.description || item.reason || item.details;
            const isManual = item.conversion === 'MANUAL' || (item.target && item.target.toLowerCase().includes('manual'));

            if (status === 'UNSUPPORTED' || status === 'FAILED_EXTRACTION' || isManual) {
                let strongReasoning = summary?.reason || `Architectural Limitation: This object has been flagged for Manual Migration. `;

                if (!summary?.reason) {
                    if (item.category === 'QUERY' && (originalReason?.includes('CROSSTAB') || originalReason?.includes('PIVOT'))) {
                        strongReasoning += `Automated AI migration is prohibited for CROSSTAB/Pivot structures because they rely on the JET/ACE dynamic column engine. Generating a 1:1 JPA equivalent would lead to unstable schema types and "N+1" performance issues. A human architect must redesign this as a Spring Boot aggregate service and a React DataGrid view.`;
                    } else if (item.category?.includes('VBA') || item.category === 'MODULE') {
                        strongReasoning += `The logic contains deep dependencies on Windows COM/OLE APIs or local file-system hooks (e.g., Outlook/Excel automation). AI cannot safely modernize these to a web-based Spring Boot architecture without risking a complete break in business workflows. Human intervention is required to implement modern API-based alternatives (like Microsoft Graph).`;
                    } else if (item.category === 'FORM' && originalReason?.includes('unbound')) {
                        strongReasoning += `This form uses complex event-driven logic that does not follow standard CRUD patterns. Attempting an automated AI conversion would result in "hallucinated" React states that do not match your original business rules. Manual reconstruction ensures that specific user-interaction sequences are preserved correctly.`;
                    } else {
                        strongReasoning += `${originalReason || 'Proprietary desktop-centric patterns detected.'}\n\nWhy Manual and not AI?\n1. Architectural Integrity: AI-driven "best-guess" conversion of monolithic desktop logic into distributed web code frequently results in brittle, unmaintainable "spaghetti" code.\n2. Security Risk: Legacy Access objects often use insecure data handling patterns. Manual review ensures we implement modern JWT/OAuth2 standards rather than migrating vulnerabilities.\n3. Business Logic Fidelity: Automated tools lack the domain context to distinguish between "legacy dead code" and "critical edge-case logic."`;
                    }
                }

                return strongReasoning;
            }
            return originalReason;
        };

        return {
            tables: supportability.filter(s => s.category === 'TABLE').map((s, i) => {
                const summary = summaryMap.get(s.object);
                return {
                    id: `table-${i}`, name: s.object, category: 'tables', recordCount: summary?.detail_counts || '—', target: 'PostgreSQL Table', status: s.status, risk: s.risk, confidence: s.confidence, reason: enhanceReason(s), conversion: s.conversion, selected: true,
                    aiReason: summary?.description, humanAction: summary?.human_action
                };
            }),
            queries: supportability.filter(s => s.category === 'QUERY').map((s, i) => {
                const summary = summaryMap.get(s.object);
                return {
                    id: `query-${i}`, name: s.object, category: 'queries', recordCount: summary?.detail_counts || '—', target: 'JPA Repository / Custom Query', status: s.status, risk: s.risk, confidence: s.confidence, reason: enhanceReason(s), conversion: s.conversion, selected: true,
                    aiReason: summary?.description, humanAction: summary?.human_action
                };
            }),
            forms: supportability.filter(s => s.category === 'FORM').map((s, i) => {
                const summary = summaryMap.get(s.object);
                const mapping = normalizeFormMapping(s.conversion, s.target);
                const itemWithMapping = { ...s, ...mapping };
                return {
                    id: `form-${i}`, name: s.object, category: 'forms', recordCount: summary?.detail_counts || '—', target: mapping.target, status: s.status, risk: s.risk, confidence: s.confidence, reason: enhanceReason(itemWithMapping), conversion: mapping.conversion, selected: true,
                    aiReason: summary?.description, humanAction: summary?.human_action
                };
            }),
            reports: supportability.filter(s => s.category === 'REPORT').map((s, i) => {
                const summary = summaryMap.get(s.object);
                return {
                    id: `report-${i}`, name: s.object, category: 'reports', recordCount: summary?.detail_counts || '—', target: 'Report Service + PDF/Excel', status: s.status, risk: s.risk, confidence: s.confidence, reason: enhanceReason(s), conversion: s.conversion, selected: true,
                    aiReason: summary?.description, humanAction: summary?.human_action
                };
            }),
            modules: supportability.filter(s => s.category === 'VBA' || s.category === 'VBA_MODULE' || s.category === 'VBA_FUNCTION' || s.category === 'VBA_SUB').map((s, i) => {
                const summary = summaryMap.get(s.object);
                return {
                    id: `module-${i}`, name: s.object, category: 'modules', recordCount: summary?.detail_counts || '—', target: 'Spring Service / Utility', status: s.status, risk: s.risk, confidence: s.confidence, reason: enhanceReason(s), conversion: s.conversion, selected: true,
                    aiReason: summary?.description, humanAction: summary?.human_action
                };
            }),
            macros: supportability.filter(s => s.category === 'MACRO').map((s, i) => {
                const summary = summaryMap.get(s.object);
                return {
                    id: `macro-${i}`, name: s.object, category: 'macros', recordCount: summary?.detail_counts || '—', target: 'React Navigation / API Call', status: s.status, risk: s.risk, confidence: s.confidence, reason: enhanceReason(s), conversion: s.conversion, selected: true,
                    aiReason: summary?.description, humanAction: summary?.human_action
                };
            }),
            externalDependencies: (report.externalDependencies || []).map((dep, i) => {
                const name = dep.name || dep.type;
                const summary = summaryMap.get(name);
                return {
                    id: `ext-${i}`, name: name, category: 'externalDependencies', recordCount: summary?.detail_counts || '—', target: dep.migrationStrategy || 'Manual Review', status: 'UNSUPPORTED', risk: dep.riskLevel || 'HIGH', confidence: 0, reason: enhanceReason({ ...dep, object: name, status: 'UNSUPPORTED', conversion: 'MANUAL' }), conversion: 'MANUAL', selected: false,
                    aiReason: summary?.description, humanAction: summary?.human_action
                };
            }),
        };
    };

    const getMockReviewData = () => ({
        tables: [
            { id: 't1', name: 'Employees', category: 'tables', recordCount: '1,250', target: 'PostgreSQL Table', status: 'SUPPORTED', risk: 'LOW', confidence: 0.99, reason: 'Standard table with PK and indexes.\nAll data types are directly compatible with PostgreSQL.\nNo complex constraints detected.', conversion: 'ENTITY', selected: true },
            { id: 't2', name: 'Departments', category: 'tables', recordCount: '25', target: 'PostgreSQL Table', status: 'SUPPORTED', risk: 'LOW', confidence: 0.99, reason: 'Simple lookup table.\nContains standard text and numeric fields.\nPerfect candidate for automated migration.', conversion: 'ENTITY', selected: true },
            { id: 't4', name: 'SysUsers', category: 'tables', recordCount: '50', target: 'PostgreSQL Table (User)', status: 'SUPPORTED_WITH_REVIEW', risk: 'MEDIUM', confidence: 0.85, reason: 'Contains plaintext password fields.\nSecurity review required for password hashing.\nAudit trails should be implemented during migration.', conversion: 'ENTITY', selected: true },
        ],
        queries: [
            { id: 'q1', name: 'qryActiveEmployees', category: 'queries', recordCount: '—', target: 'JPA Repository Method', status: 'SUPPORTED', risk: 'LOW', confidence: 0.95, reason: 'Simple SELECT with WHERE clause.\nStandard JOIN between Employees and Departments.\nFully convertible to Spring Data JPA method.', conversion: 'REPOSITORY_METHOD', selected: true },
            { id: 'q2', name: 'qryLeaveBalance', category: 'queries', recordCount: '—', target: 'JPA Repository / Custom Query', status: 'SUPPORTED_WITH_REVIEW', risk: 'MEDIUM', confidence: 0.82, reason: 'Uses DLookup domain function.\nRequires conversion to a service-level calculation.\nComplex VBA-based criteria found in SQL.', conversion: 'SERVICE_METHOD', selected: true },
            { id: 'q3', name: 'qryYearlySalesCrosstab', category: 'queries', recordCount: '—', target: 'Manual Migration', status: 'UNSUPPORTED', risk: 'HIGH', confidence: 0, reason: 'CROSSTAB queries not supported in V1.\n\nWhy is this unsupported?\nCROSSTAB is a proprietary Access feature for dynamic pivot tables. Standard SQL does not natively support dynamic pivots without complex PIVOT clauses.\n\nAction Required:\nYou must manually recreate this logic using a Spring Boot aggregate query and a React DataGrid with grouping/pivoting capabilities.', conversion: 'MANUAL', selected: false },
        ],
        forms: [
            { id: 'f1', name: 'frmEmployee', category: 'forms', recordCount: '—', target: 'React Page + Form', status: 'SUPPORTED', risk: 'LOW', confidence: 0.94, reason: 'Standard CRUD form with bound fields.\nClean layout with common UI controls.\nDirect mapping to React Hook Form components.', conversion: 'PAGE_FORM', selected: true },
        ],
        reports: [],
        modules: [],
        macros: [],
        externalDependencies: [
            { id: 'ext1', name: 'Outlook COM', category: 'externalDependencies', recordCount: '—', target: 'Manual Review', status: 'UNSUPPORTED', risk: 'HIGH', confidence: 0, reason: 'External Outlook automation is not cloud-compatible.\n\nWhy is this unsupported?\nThis object relies on proprietary MS Access COM object integration that has no direct equivalent in a modern Java/React stack.\n\nAction Required:\nYou must resolve this manually by redesigning the underlying workflow or implementing a custom API integration (e.g., Microsoft Graph API).', conversion: 'MANUAL', selected: false },
        ],
    });

    const isUnsupported = (obj) =>
        obj.status === 'UNSUPPORTED' ||
        obj.status === 'FAILED_EXTRACTION' ||
        obj.conversion === 'MANUAL' ||
        (obj.target && obj.target.toLowerCase().includes('manual'));

    const isSupported = (obj) =>
        obj.status === 'SUPPORTED' &&
        obj.conversion !== 'MANUAL' &&
        !(obj.target && obj.target.toLowerCase().includes('manual'));

    const isReview = (obj) => !isSupported(obj) && !isUnsupported(obj);

    // Filter logic helper for counts
    const matchesStatusFilter = (obj, status) => {
        if (status === 'all') return true;
        if (status === 'SUPPORTED') return isSupported(obj);
        if (status === 'SUPPORTED_WITH_REVIEW') return isReview(obj);
        if (status === 'UNSUPPORTED') return isUnsupported(obj);
        if (status === 'selected') return selectedObjects.has(obj.id);
        return true;
    };

    const currentObjects = useMemo(() => {
        const objects = reviewTab === 'all'
            ? Object.values(reviewData).flat()
            : (reviewData[reviewTab] || []);

        return objects.filter(obj => {
            const matchesSearch = !searchQuery ||
                obj.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
                obj.target.toLowerCase().includes(searchQuery.toLowerCase());

            const matchesStatus = matchesStatusFilter(obj, filterStatus);

            return matchesSearch && matchesStatus;
        });
    }, [reviewData, reviewTab, filterStatus, searchQuery, selectedObjects]);

    // Summary Card Counts: filtered by current Object Type (reviewTab)
    const objectsForSummary = useMemo(() => {
        return reviewTab === 'all'
            ? Object.values(reviewData).flat()
            : (reviewData[reviewTab] || []);
    }, [reviewData, reviewTab]);

    const totalObjectsCount = objectsForSummary.length;
    const unsupportedCount = objectsForSummary.filter(isUnsupported).length;
    const supportedCount = objectsForSummary.filter(isSupported).length;
    const reviewCount = objectsForSummary.filter(isReview).length;

    // Tab Counts: filtered by current Status (filterStatus)
    const getTabCount = (tabKey) => {
        const objects = reviewData[tabKey] || [];
        return objects.filter(obj => matchesStatusFilter(obj, filterStatus)).length;
    };

    // Calculate true counts for each category (Tier 2 tabs) - independent of selection
    const categoryCounts = useMemo(() => {
        const counts = {};
        REVIEW_TABS.forEach(tab => {
            const objects = reviewData[tab.key] || [];
            counts[tab.key] = {
                category: tab.key,
                total: objects.length,
                fullySupported: objects.filter(isSupported).length,
                needsReview: objects.filter(isReview).length,
                manualSkipped: objects.filter(isUnsupported).length,
            };
        });
        return counts;
    }, [reviewData]);

    // Calculate aggregate totals for all categories
    const globalCounts = useMemo(() => {
        const allObjects = Object.values(reviewData).flat();
        return {
            total: allObjects.length,
            fullySupported: allObjects.filter(isSupported).length,
            needsReview: allObjects.filter(isReview).length,
            manualSkipped: allObjects.filter(isUnsupported).length,
        };
    }, [reviewData]);

    // Tier 1 Summary Data: reflects current category if one is selected, else global
    const summaryData = useMemo(() => {
        if (reviewTab === 'all') {
            return globalCounts;
        }
        return categoryCounts[reviewTab] || { total: 0, fullySupported: 0, needsReview: 0, manualSkipped: 0 };
    }, [reviewTab, globalCounts, categoryCounts]);

    const handleFilterChange = (status) => {
        // Toggle: if clicking the already active filter, go back to 'all'
        const newStatus = filterStatus === status ? 'all' : status;
        setFilterStatus(newStatus);
    };

    const currentSelectedCount = useMemo(() => {
        return currentObjects.filter(o => o.status !== 'UNSUPPORTED' && o.status !== 'FAILED_EXTRACTION' && selectedObjects.has(o.id)).length;
    }, [currentObjects, selectedObjects]);

    const handleSelectAll = () => {
        const selectable = currentObjects.filter(o => o.status !== 'UNSUPPORTED' && o.status !== 'FAILED_EXTRACTION');
        actions.selectAllObjects(selectable);
    };

    const handleGlobalSelectAll = () => {
        const allObjectsFlat = Object.values(reviewData).flat();
        const allSelectable = allObjectsFlat.filter(o => o.status !== 'UNSUPPORTED' && o.status !== 'FAILED_EXTRACTION');
        actions.selectAllObjects(allSelectable);
    };

    const handleDeselectAll = () => {
        actions.deselectAllObjects(currentObjects.map(o => o.id));
    };

    const handleTargetChange = (objectId, newTarget) => {
        // Need to find which tab this object belongs to
        const obj = currentObjects.find(o => o.id === objectId);
        const targetTab = obj?.category || reviewTab;

        const mapping = targetTab === 'forms' && FORM_CONVERSION_BY_TARGET[newTarget]
            ? { target: newTarget, conversion: FORM_CONVERSION_BY_TARGET[newTarget] }
            : { target: newTarget };
        actions.updateObjectMapping(targetTab, objectId, mapping);
    };

    const handleBatchTargetChange = (newTarget) => {
        currentObjects.forEach(obj => {
            if (selectedObjects.has(obj.id)) {
                actions.updateObjectMapping(obj.category || reviewTab, obj.id, { target: newTarget });
            }
        });
        setBatchActionTab(false);
    };

    const getObjectDescription = (object) => {
        const recordSummary = object.recordCount && object.recordCount !== '—'
            ? `Contains ${object.recordCount} records.`
            : 'Record count is available after source inspection.';

        const category = object.category || reviewTab;

        if (category === 'tables') {
            return `${object.name} is a database table. ${recordSummary}`;
        }
        if (category === 'forms') {
            return `${object.name} is an Access form for entering and viewing records. ${recordSummary}`;
        }
        if (category === 'queries') {
            return `${object.name} is an Access query used to retrieve or transform records.`;
        }
        if (category === 'reports') {
            return `${object.name} is an Access report generated from application records.`;
        }
        if (category === 'modules') {
            return `${object.name} is a VBA module containing application logic.`;
        }
        if (category === 'macros') {
            return `${object.name} is an Access macro that automates application actions.`;
        }
        return `${object.name} is an external dependency requiring migration review.`;
    };

    return (
        <div>
            <div className="card-header" style={{ marginBottom: '1.5rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <h2 className="card-title">Map & Review Objects</h2>
                <div style={{ display: 'flex', gap: '0.5rem' }}>
                    <button
                        type="button"
                        title="Open Solution Explorer"
                        aria-label="Open Solution Explorer"
                        onClick={onOpenExplorer}
                        style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', width: '38px', height: '38px', border: '1px solid #c7d2fe', borderRadius: '10px', background: '#eef2ff', color: '#4338ca', cursor: 'pointer' }}
                    >
                        <FolderTree size={19} />
                    </button>
                    {/* <button
                        type="button"
                        title="Open ER Diagram"
                        aria-label="Open ER Diagram"
                        onClick={onOpenErDiagram}
                        style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', width: '38px', height: '38px', border: '1px solid #bae6fd', borderRadius: '10px', background: '#f0f9ff', color: '#0369a1', cursor: 'pointer' }}
                    >
                        <Network size={19} />
                    </button> */}
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
                    {/* Tier 1 - Summary Cards (Read-only aggregate dashboard) */}
                    <div className="kpi-container" style={{ gridTemplateColumns: 'repeat(4, 1fr)', gap: '1.25rem', marginBottom: '2rem' }}>
                        <div
                            className={`kpi-card kpi-total ${filterStatus === 'all' ? 'active' : ''}`}
                            onClick={() => handleFilterChange('all')}
                            style={{
                                cursor: 'pointer',
                                borderLeft: '4px solid #4338ca',
                                background: filterStatus === 'all' ? '#f5f7ff' : '#fff'
                            }}
                        >
                            <div className="kpi-header" style={{ color: '#4338ca' }}>📊 Total Objects</div>
                            <div className="kpi-value" style={{ fontSize: '2.25rem' }}>{summaryData.total}</div>
                        </div>
                        <div
                            className={`kpi-card kpi-supported ${filterStatus === 'SUPPORTED' ? 'active' : ''}`}
                            onClick={() => handleFilterChange('SUPPORTED')}
                            style={{
                                cursor: 'pointer',
                                borderLeft: '4px solid #10b981',
                                background: filterStatus === 'SUPPORTED' ? '#f0fdf4' : '#fff'
                            }}
                        >
                            <div className="kpi-header" style={{ color: '#10b981' }}>✅ Fully Supported</div>
                            <div className="kpi-value" style={{ fontSize: '2.25rem' }}>{summaryData.fullySupported}</div>
                        </div>
                        <div
                            className={`kpi-card kpi-review ${filterStatus === 'SUPPORTED_WITH_REVIEW' ? 'active' : ''}`}
                            onClick={() => handleFilterChange('SUPPORTED_WITH_REVIEW')}
                            style={{
                                cursor: 'pointer',
                                borderLeft: '4px solid #f59e0b',
                                background: filterStatus === 'SUPPORTED_WITH_REVIEW' ? '#fffbeb' : '#fff'
                            }}
                        >
                            <div className="kpi-header" style={{ color: '#f59e0b' }}>⚠️ Needs Review</div>
                            <div className="kpi-value" style={{ fontSize: '2.25rem' }}>{summaryData.needsReview}</div>
                            <div style={{ marginTop: '0.5rem', fontSize: '0.75rem', color: '#64748b', fontWeight: 500 }}>Check mappings</div>
                        </div>
                        <div
                            className={`kpi-card kpi-unsupported ${filterStatus === 'UNSUPPORTED' ? 'active' : ''}`}
                            onClick={() => handleFilterChange('UNSUPPORTED')}
                            style={{
                                cursor: 'pointer',
                                borderLeft: '4px solid #ef4444',
                                background: filterStatus === 'UNSUPPORTED' ? '#fef2f2' : '#fff'
                            }}
                        >
                            <div className="kpi-header" style={{ color: '#ef4444' }}>❌ Manual / Skipped</div>
                            <div className="kpi-value" style={{ fontSize: '2.25rem' }}>{summaryData.manualSkipped}</div>
                            <div style={{ marginTop: '0.5rem', fontSize: '0.75rem', color: '#64748b', fontWeight: 500 }}>Requires attention</div>
                        </div>
                    </div>

                    {/* Tier 2 - Segmented Category Tabs */}
                    <div className="review-tabs" style={{
                        display: 'flex',
                        gap: '0.75rem',
                        padding: '0.75rem 1rem',
                        background: '#f8fafc',
                        borderRadius: '999px',
                        border: '1px solid #e2e8f0',
                        marginBottom: '1.5rem',
                        overflowX: 'auto',
                        whiteSpace: 'nowrap'
                    }}>
                        {REVIEW_TABS.map((tab) => {
                            const stats = categoryCounts[tab.key];
                            const isActive = reviewTab === tab.key;
                            const currentTabCount = getTabCount(tab.key);
                            return (
                                <button
                                    key={tab.key}
                                    className={`review-tab ${isActive ? 'active' : ''}`}
                                    onClick={() => {
                                        const newTab = reviewTab === tab.key ? 'all' : tab.key;
                                        actions.setReviewTab(newTab);
                                    }}
                                    style={{
                                        display: 'flex',
                                        alignItems: 'center',
                                        gap: '0.6rem',
                                        padding: '0.5rem 1rem',
                                        borderRadius: '999px',
                                        border: isActive ? '1.5px solid #4338ca' : '1.5px solid transparent',
                                        background: isActive ? '#fff' : 'transparent',
                                        color: isActive ? '#4338ca' : '#64748b',
                                        boxShadow: isActive ? '0 2px 4px rgba(67, 56, 202, 0.1)' : 'none',
                                        fontWeight: 600,
                                        fontSize: '0.875rem',
                                        opacity: currentTabCount === 0 && filterStatus !== 'all' ? 0.6 : 1
                                    }}
                                >
                                    <span style={{ fontSize: '1.1rem' }}>{tab.icon}</span>
                                    <span>{tab.label}</span>
                                    <span className="review-tab-count" style={{
                                        background: isActive ? '#eef2ff' : '#e2e8f0',
                                        color: isActive ? '#4338ca' : '#64748b',
                                        padding: '1px 8px',
                                        borderRadius: '10px',
                                        fontSize: '0.75rem',
                                        fontWeight: 700
                                    }}>
                                        {currentTabCount}
                                    </span>
                                    {stats.total > 0 && (
                                        <span style={{
                                            width: '6px', height: '6px', borderRadius: '50%',
                                            background: stats.manualSkipped > 0 ? '#ef4444' : '#10b981'
                                        }} />
                                    )}
                                </button>
                            );
                        })}
                    </div>

                    {/* Smart Toolbar */}
                    <div className="review-toolbar">
                        <div className="quick-filters" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
                            <span className={`filter-chip ${filterStatus === 'all' ? 'active' : ''}`} onClick={() => handleFilterChange('all')}>All Statuses</span>
                            <span className={`filter-chip ${filterStatus === 'SUPPORTED' ? 'active' : ''}`} onClick={() => handleFilterChange('SUPPORTED')}>Supported</span>
                            <span className={`filter-chip ${filterStatus === 'SUPPORTED_WITH_REVIEW' ? 'active' : ''}`} onClick={() => handleFilterChange('SUPPORTED_WITH_REVIEW')}>Needs Review</span>
                            <span className={`filter-chip ${filterStatus === 'UNSUPPORTED' ? 'active' : ''}`} onClick={() => handleFilterChange('UNSUPPORTED')}>Manual/Skipped</span>
                            <span className={`filter-chip ${filterStatus === 'selected' ? 'active' : ''}`} onClick={() => handleFilterChange('selected')}>Selected ({selectedObjects.size})</span>
                            <button className="btn btn-primary" onClick={handleGlobalSelectAll} style={{ marginLeft: '1rem', borderRadius: '999px', fontSize: '0.75rem', padding: '0.375rem 0.75rem' }}>Select All Globally</button>
                        </div>
                        <div className="search-box">
                            <input
                                type="text"
                                placeholder="Search by object name, target..."
                                value={searchQuery}
                                onChange={(e) => setSearchQuery(e.target.value)}
                            />
                            {searchQuery && (
                                <button className="clear-btn" onClick={() => setSearchQuery('')}>✕</button>
                            )}
                        </div>
                    </div>


                    {/* Data Grid */}
                    <div style={{ background: '#fff', borderRadius: '12px', border: '1px solid #e2e8f0', overflowX: 'auto' }}>
                        <table className="data-table" style={{ width: '100%', borderCollapse: 'collapse' }}>
                            <thead>
                                <tr style={{ background: '#f8fafc', borderBottom: '1px solid #e2e8f0' }}>
                                    <th style={{ width: '48px', padding: '1rem' }}>
                                        <input
                                            type="checkbox"
                                            checked={currentSelectedCount === currentObjects.filter(o => o.status !== 'UNSUPPORTED' && o.status !== 'FAILED_EXTRACTION').length && currentObjects.length > 0}
                                            onChange={() => currentSelectedCount > 0 ? handleDeselectAll() : handleSelectAll()}
                                        />
                                    </th>
                                    <th style={{ padding: '1rem', textAlign: 'left', fontSize: '0.75rem', fontWeight: 700, color: '#64748b', textTransform: 'uppercase' }}>Object Details</th>
                                    <th style={{ padding: '1rem', textAlign: 'left', fontSize: '0.75rem', fontWeight: 700, color: '#64748b', textTransform: 'uppercase' }}>Target Architecture</th>
                                    <th style={{ padding: '1rem', textAlign: 'left', fontSize: '0.75rem', fontWeight: 700, color: '#64748b', textTransform: 'uppercase' }}>Description</th>
                                </tr>
                            </thead>
                            <tbody>
                                {currentObjects.map((obj) => {
                                    const isInactive = obj.status === 'UNSUPPORTED' || obj.status === 'FAILED_EXTRACTION';
                                    const isSelected = selectedObjects.has(obj.id);

                                    return (
                                            <tr key={obj.id} style={{ background: isSelected ? '#f1f5f9' : 'transparent', borderBottom: '1px solid #e2e8f0' }}>
                                                <td style={{ padding: '0.75rem 1rem' }}>
                                                    {!isInactive && (
                                                        <input type="checkbox" checked={isSelected} onChange={() => actions.toggleObjectSelection(obj.id)} />
                                                    )}
                                                </td>
                                                <td style={{ padding: '0.75rem 1rem' }}>
                                                    <div style={{ fontWeight: 600, color: '#1e293b' }}>{obj.name}</div>
                                                    <div style={{ fontSize: '0.75rem', color: '#64748b', marginTop: '0.125rem' }}>
                                                        {obj.recordCount !== '—' ? `${obj.recordCount} records` : obj.conversion?.replace(/_/g, ' ')}
                                                    </div>
                                                </td>
                                                <td style={{ padding: '0.75rem 1rem' }}>
                                                    <select
                                                        className="inline-select"
                                                        value={obj.target}
                                                        onChange={(e) => handleTargetChange(obj.id, e.target.value)}
                                                        disabled={isInactive}
                                                    >
                                                        {(TARGET_OPTIONS[obj.category || reviewTab] || []).map(opt => <option key={opt} value={opt}>{opt}</option>)}
                                                    </select>
                                                </td>
                                                <td style={{ padding: '0.75rem 1rem', minWidth: '280px' }}>
                                                    <DescriptionPopover object={obj} category={obj.category || reviewTab} summary={getObjectDescription(obj)} />
                                                </td>
                                            </tr>
                                    );
                                })}
                            </tbody>
                        </table>
                        {currentObjects.length === 0 && (
                            <div style={{ textAlign: 'center', padding: '3rem', color: '#64748b' }}>
                                No objects found matching your criteria.
                            </div>
                        )}
                    </div>
                </>
            )}

        </div>
    );
}