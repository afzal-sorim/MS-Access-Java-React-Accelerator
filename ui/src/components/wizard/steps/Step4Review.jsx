import React, { useEffect, useState, useMemo } from 'react';
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
    const [showPopover, setShowPopover] = useState(false);
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
    const detail = object.reason || `The analyzer classified ${object.name} as a ${typeLabel} based on its Access structure and dependencies.`;

    return (
        <div
            style={{ position: 'relative', display: 'inline-block', width: '100%' }}
            onMouseEnter={() => setShowPopover(true)}
            onMouseLeave={() => setShowPopover(false)}
        >
            <span style={{ cursor: 'help', borderBottom: '1px dotted #64748b' }}>{summary}</span>
            {showPopover && (
                <div style={{
                    position: 'absolute', bottom: 'calc(100% + 10px)', left: 0, zIndex: 9999,
                    width: 'min(470px, 72vw)', maxHeight: '340px', overflowY: 'auto', padding: '1.1rem 1.2rem',
                    background: 'linear-gradient(145deg, #ffffff 0%, #f8faff 100%)', color: '#334155',
                    border: '1px solid #a5b4fc', borderLeft: '4px solid #4f46e5', borderRadius: '12px',
                    boxShadow: '0 18px 40px rgba(30, 41, 59, 0.24)', fontSize: '0.8125rem', lineHeight: 1.55,
                    textAlign: 'left', pointerEvents: 'none'
                }}>
                    <div style={{ marginBottom: '0.8rem', color: '#3730a3', fontWeight: 800, fontSize: '0.875rem' }}>
                        AI analysis for {object.name}
                    </div>
                    <div style={{ display: 'grid', gap: '0.65rem' }}>
                        <div><strong style={{ color: '#1e293b' }}>Reasoning:</strong> <span style={{ whiteSpace: 'pre-line' }}>{detail}</span></div>
                        <div><strong style={{ color: '#1e293b' }}>Object profile:</strong> {summary} This is classified as a {typeLabel}.</div>
                        <div><strong style={{ color: '#1e293b' }}>Data context:</strong> {recordDetail}</div>
                        <div><strong style={{ color: '#1e293b' }}>Migration plan:</strong> {migrationDetail}</div>
                    </div>
                    <div style={{
                        position: 'absolute', top: '100%', left: '2rem', width: 0, height: 0,
                        borderLeft: '7px solid transparent', borderRight: '7px solid transparent', borderTop: '7px solid #c7d2fe'
                    }} />
                </div>
            )}
        </div>
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

        const enhanceReason = (status, originalReason) => {
            if (status === 'UNSUPPORTED' || status === 'FAILED_EXTRACTION') {
                return `${originalReason || 'Object could not be parsed automatically.'}\n\nWhy is this unsupported?\nThis object relies on proprietary MS Access features (e.g. CROSSTAB queries, complex VBA automation, or proprietary binary formats) that have no direct 1:1 equivalent in a modern Java/React stack.\n\nAction Required:\nYou must resolve this manually by redesigning the underlying workflow or implementing a custom Java/React solution tailored to this specific requirement.`;
            }
            return originalReason;
        };

        return {
            tables: supportability.filter(s => s.category === 'TABLE').map((s, i) => ({
                id: `table-${i}`, name: s.object, recordCount: '—', target: 'PostgreSQL Table', status: s.status, risk: s.risk, confidence: s.confidence, reason: enhanceReason(s.status, s.reason), conversion: s.conversion, selected: true,
            })),
            queries: supportability.filter(s => s.category === 'QUERY').map((s, i) => ({
                id: `query-${i}`, name: s.object, recordCount: '—', target: 'JPA Repository / Custom Query', status: s.status, risk: s.risk, confidence: s.confidence, reason: enhanceReason(s.status, s.reason), conversion: s.conversion, selected: true,
            })),
            forms: supportability.filter(s => s.category === 'FORM').map((s, i) => {
                const mapping = normalizeFormMapping(s.conversion, s.target);
                return {
                id: `form-${i}`, name: s.object, recordCount: '—', target: mapping.target, status: s.status, risk: s.risk, confidence: s.confidence, reason: enhanceReason(s.status, s.reason), conversion: mapping.conversion, selected: true,
                };
            }),
            reports: supportability.filter(s => s.category === 'REPORT').map((s, i) => ({
                id: `report-${i}`, name: s.object, recordCount: '—', target: 'Report Service + PDF/Excel', status: s.status, risk: s.risk, confidence: s.confidence, reason: enhanceReason(s.status, s.reason), conversion: s.conversion, selected: true,
            })),
            modules: supportability.filter(s => s.category === 'VBA' || s.category === 'VBA_MODULE' || s.category === 'VBA_FUNCTION' || s.category === 'VBA_SUB').map((s, i) => ({
                id: `module-${i}`, name: s.object, recordCount: '—', target: 'Spring Service / Utility', status: s.status, risk: s.risk, confidence: s.confidence, reason: enhanceReason(s.status, s.reason), conversion: s.conversion, selected: true,
            })),
            macros: supportability.filter(s => s.category === 'MACRO').map((s, i) => ({
                id: `macro-${i}`, name: s.object, recordCount: '—', target: 'React Navigation / API Call', status: s.status, risk: s.risk, confidence: s.confidence, reason: enhanceReason(s.status, s.reason), conversion: s.conversion, selected: true,
            })),
            externalDependencies: (report.externalDependencies || []).map((dep, i) => ({
                id: `ext-${i}`, name: dep.name || dep.type, recordCount: '—', target: dep.migrationStrategy || 'Manual Review', status: 'UNSUPPORTED', risk: dep.riskLevel || 'HIGH', confidence: 0, reason: enhanceReason('UNSUPPORTED', dep.details || 'External dependency requires manual migration'), conversion: 'MANUAL', selected: false,
            })),
        };
    };

    const getMockReviewData = () => ({
        tables: [
            { id: 't1', name: 'Employees', recordCount: '1,250', target: 'PostgreSQL Table', status: 'SUPPORTED', risk: 'LOW', confidence: 0.99, reason: 'Standard table with PK and indexes.\nAll data types are directly compatible with PostgreSQL.\nNo complex constraints detected.', conversion: 'ENTITY', selected: true },
            { id: 't2', name: 'Departments', recordCount: '25', target: 'PostgreSQL Table', status: 'SUPPORTED', risk: 'LOW', confidence: 0.99, reason: 'Simple lookup table.\nContains standard text and numeric fields.\nPerfect candidate for automated migration.', conversion: 'ENTITY', selected: true },
            { id: 't4', name: 'SysUsers', recordCount: '50', target: 'PostgreSQL Table (User)', status: 'SUPPORTED_WITH_REVIEW', risk: 'MEDIUM', confidence: 0.85, reason: 'Contains plaintext password fields.\nSecurity review required for password hashing.\nAudit trails should be implemented during migration.', conversion: 'ENTITY', selected: true },
        ],
        queries: [
            { id: 'q1', name: 'qryActiveEmployees', recordCount: '—', target: 'JPA Repository Method', status: 'SUPPORTED', risk: 'LOW', confidence: 0.95, reason: 'Simple SELECT with WHERE clause.\nStandard JOIN between Employees and Departments.\nFully convertible to Spring Data JPA method.', conversion: 'REPOSITORY_METHOD', selected: true },
            { id: 'q2', name: 'qryLeaveBalance', recordCount: '—', target: 'JPA Repository / Custom Query', status: 'SUPPORTED_WITH_REVIEW', risk: 'MEDIUM', confidence: 0.82, reason: 'Uses DLookup domain function.\nRequires conversion to a service-level calculation.\nComplex VBA-based criteria found in SQL.', conversion: 'SERVICE_METHOD', selected: true },
            { id: 'q3', name: 'qryYearlySalesCrosstab', recordCount: '—', target: 'Manual Migration', status: 'UNSUPPORTED', risk: 'HIGH', confidence: 0, reason: 'CROSSTAB queries not supported in V1.\n\nWhy is this unsupported?\nCROSSTAB is a proprietary Access feature for dynamic pivot tables. Standard SQL does not natively support dynamic pivots without complex PIVOT clauses.\n\nAction Required:\nYou must manually recreate this logic using a Spring Boot aggregate query and a React DataGrid with grouping/pivoting capabilities.', conversion: 'MANUAL', selected: false },
        ],
        forms: [
            { id: 'f1', name: 'frmEmployee', recordCount: '—', target: 'React Page + Form', status: 'SUPPORTED', risk: 'LOW', confidence: 0.94, reason: 'Standard CRUD form with bound fields.\nClean layout with common UI controls.\nDirect mapping to React Hook Form components.', conversion: 'PAGE_FORM', selected: true },
        ],
        reports: [],
        modules: [],
        macros: [],
        externalDependencies: [
            { id: 'ext1', name: 'Outlook COM', recordCount: '—', target: 'Manual Review', status: 'UNSUPPORTED', risk: 'HIGH', confidence: 0, reason: 'External Outlook automation is not cloud-compatible.\n\nWhy is this unsupported?\nThis object relies on proprietary MS Access COM object integration that has no direct equivalent in a modern Java/React stack.\n\nAction Required:\nYou must resolve this manually by redesigning the underlying workflow or implementing a custom API integration (e.g., Microsoft Graph API).', conversion: 'MANUAL', selected: false },
        ],
    });

    const currentObjects = useMemo(() => {
        const objects = reviewData[reviewTab] || [];
        return objects.filter(obj => {
            const matchesSearch = !searchQuery ||
                obj.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
                obj.target.toLowerCase().includes(searchQuery.toLowerCase());
            const matchesStatus = filterStatus === 'all' || 
                (filterStatus === 'selected' ? selectedObjects.has(obj.id) : obj.status === filterStatus);
            return matchesSearch && matchesStatus;
        });
    }, [reviewData, reviewTab, filterStatus, searchQuery, selectedObjects]);

    // KPI Metrics calculation
    const allObjectsFlat = useMemo(() => Object.values(reviewData).flat(), [reviewData]);
    const totalObjectsCount = allObjectsFlat.length;
    const supportedCount = allObjectsFlat.filter(o => o.status === 'SUPPORTED').length;
    const reviewCount = allObjectsFlat.filter(o => o.status.includes('REVIEW') || o.status.includes('TRANSFORMATION')).length;
    const unsupportedCount = allObjectsFlat.filter(o => o.status === 'UNSUPPORTED' || o.status === 'FAILED_EXTRACTION').length;
    const readinessScore = totalObjectsCount > 0 ? Math.round(((supportedCount + reviewCount * 0.5) / totalObjectsCount) * 100) : 0;

    const currentSelectedCount = useMemo(() => {
        return currentObjects.filter(o => o.status !== 'UNSUPPORTED' && o.status !== 'FAILED_EXTRACTION' && selectedObjects.has(o.id)).length;
    }, [currentObjects, selectedObjects]);

    const handleSelectAll = () => {
        const selectable = currentObjects.filter(o => o.status !== 'UNSUPPORTED' && o.status !== 'FAILED_EXTRACTION');
        actions.selectAllObjects(selectable);
    };

    const handleGlobalSelectAll = () => {
        const allSelectable = allObjectsFlat.filter(o => o.status !== 'UNSUPPORTED' && o.status !== 'FAILED_EXTRACTION');
        actions.selectAllObjects(allSelectable);
    };

    const handleDeselectAll = () => {
        actions.deselectAllObjects(currentObjects.map(o => o.id));
    };

    const handleTargetChange = (objectId, newTarget) => {
        const mapping = reviewTab === 'forms' && FORM_CONVERSION_BY_TARGET[newTarget]
            ? { target: newTarget, conversion: FORM_CONVERSION_BY_TARGET[newTarget] }
            : { target: newTarget };
        actions.updateObjectMapping(reviewTab, objectId, mapping);
    };

    const handleBatchTargetChange = (newTarget) => {
        currentObjects.forEach(obj => {
            if (selectedObjects.has(obj.id)) {
                actions.updateObjectMapping(reviewTab, obj.id, { target: newTarget });
            }
        });
        setBatchActionTab(false);
    };

    const getObjectDescription = (object) => {
        const recordSummary = object.recordCount && object.recordCount !== '—'
            ? `Contains ${object.recordCount} records.`
            : 'Record count is available after source inspection.';

        if (reviewTab === 'tables') {
            return `${object.name} is a database table. ${recordSummary}`;
        }
        if (reviewTab === 'forms') {
            return `${object.name} is an Access form for entering and viewing records. ${recordSummary}`;
        }
        if (reviewTab === 'queries') {
            return `${object.name} is an Access query used to retrieve or transform records.`;
        }
        if (reviewTab === 'reports') {
            return `${object.name} is an Access report generated from application records.`;
        }
        if (reviewTab === 'modules') {
            return `${object.name} is a VBA module containing application logic.`;
        }
        if (reviewTab === 'macros') {
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
                    {/* KPI Scorecards */}
                    <div className="kpi-container">
                        <div className={`kpi-card kpi-total ${filterStatus === 'all' ? 'active' : ''}`} onClick={() => setFilterStatus('all')}>
                            <div className="kpi-header">📊 Total Objects</div>
                            <div className="kpi-value">{totalObjectsCount}</div>
                            <div style={{ marginTop: '0.5rem', fontSize: '0.75rem', color: '#64748b' }}>
                                <span style={{ color: readinessScore > 80 ? '#10b981' : '#f59e0b', fontWeight: 600 }}>{readinessScore}%</span> Auto-Ready
                            </div>
                        </div>
                        <div className={`kpi-card kpi-supported ${filterStatus === 'SUPPORTED' ? 'active' : ''}`} onClick={() => setFilterStatus('SUPPORTED')}>
                            <div className="kpi-header">✅ Fully Supported</div>
                            <div className="kpi-value">{supportedCount}</div>
                            <div style={{ marginTop: '0.5rem', fontSize: '0.75rem', color: '#64748b' }}>Ready for codegen</div>
                        </div>
                        <div className={`kpi-card kpi-review ${filterStatus === 'SUPPORTED_WITH_REVIEW' ? 'active' : ''}`} onClick={() => setFilterStatus('SUPPORTED_WITH_REVIEW')}>
                            <div className="kpi-header">⚠️ Needs Review</div>
                            <div className="kpi-value">{reviewCount}</div>
                            <div style={{ marginTop: '0.5rem', fontSize: '0.75rem', color: '#64748b' }}>Check mappings</div>
                        </div>
                        <div className={`kpi-card kpi-unsupported ${filterStatus === 'UNSUPPORTED' ? 'active' : ''}`} onClick={() => setFilterStatus('UNSUPPORTED')}>
                            <div className="kpi-header">❌ Manual / Skipped</div>
                            <div className="kpi-value">{unsupportedCount}</div>
                            <div style={{ marginTop: '0.5rem', fontSize: '0.75rem', color: '#64748b' }}>Requires attention</div>
                        </div>
                    </div>

                    {/* Segmented Category Tabs */}
                    <div className="review-tabs">
                        {REVIEW_TABS.map((tab) => {
                            const count = reviewData[tab.key]?.length || 0;
                            const hasIssues = reviewData[tab.key]?.some(o => o.status === 'UNSUPPORTED' || o.status === 'FAILED_EXTRACTION');
                            return (
                                <button
                                    key={tab.key}
                                    className={`review-tab ${reviewTab === tab.key ? 'active' : ''}`}
                                    onClick={() => actions.setReviewTab(tab.key)}
                                >
                                    {tab.icon} {tab.label}
                                    <span className="review-tab-count">{formatNumber(count)}</span>
                                    {count > 0 && (
                                        <span style={{
                                            width: '8px', height: '8px', borderRadius: '50%',
                                            background: hasIssues ? '#ef4444' : '#10b981'
                                        }} />
                                    )}
                                </button>
                            );
                        })}
                    </div>

                    {/* Smart Toolbar */}
                    <div className="review-toolbar">
                        <div className="quick-filters" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
                            <span className={`filter-chip ${filterStatus === 'all' ? 'active' : ''}`} onClick={() => setFilterStatus('all')}>All</span>
                            <span className={`filter-chip ${filterStatus === 'SUPPORTED' ? 'active' : ''}`} onClick={() => setFilterStatus('SUPPORTED')}>Supported</span>
                            <span className={`filter-chip ${filterStatus === 'selected' ? 'active' : ''}`} onClick={() => setFilterStatus('selected')}>Selected ({selectedObjects.size})</span>
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
                                                        {(TARGET_OPTIONS[reviewTab] || []).map(opt => <option key={opt} value={opt}>{opt}</option>)}
                                                    </select>
                                                </td>
                                                <td style={{ padding: '0.75rem 1rem', minWidth: '280px' }}>
                                                    <DescriptionPopover object={obj} category={reviewTab} summary={getObjectDescription(obj)} />
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