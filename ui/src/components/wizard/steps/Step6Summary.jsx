import React, { useEffect, useCallback, useState, useMemo } from 'react';
import { useWizard } from '../../../context/WizardContext';
import { getReport, downloadResult } from '../../../services/api';
import { formatNumber, formatPercentage } from '../../../utils/helpers';
import { getGeneratedCounts } from '../../../utils/generatedCounts';

/* ─── tiny SVG icons (inline to avoid extra deps) ─── */
const CheckIcon = () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12" /></svg>
);
const DownloadIcon = () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
);
const FileTextIcon = () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>
);
const FolderIcon = () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>
);
const BookIcon = () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>
);
const DatabaseIcon = () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/></svg>
);
const SearchIcon = () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
);
const LayoutIcon = () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><line x1="3" y1="9" x2="21" y2="9"/><line x1="9" y1="21" x2="9" y2="9"/></svg>
);
const BarChartIcon = () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="12" y1="20" x2="12" y2="10"/><line x1="18" y1="20" x2="18" y2="4"/><line x1="6" y1="20" x2="6" y2="16"/></svg>
);
const ZapIcon = () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>
);
const CodeIcon = () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>
);
const ClockIcon = () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
);
const SettingsIcon = () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>
);
const AppIcon = () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="2" y="3" width="20" height="14" rx="2" ry="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>
);
const AlertTriangleIcon = () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
);
const XCircleIcon = () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>
);
const ChevronDownIcon = () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="6 9 12 15 18 9"/></svg>
);
const ArrowRightIcon = () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg>
);
const LayersIcon = () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polygon points="12 2 2 7 12 12 22 7 12 2"/><polyline points="2 17 12 22 22 17"/><polyline points="2 12 12 17 22 12"/></svg>
);
const ToolIcon = () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/></svg>
);


/* ─── category icon map ─── */
const categoryIcons = {
    TABLE: DatabaseIcon,
    QUERY: SearchIcon,
    FORM: LayoutIcon,
    REPORT: BarChartIcon,
    MACRO: ZapIcon,
    VBA: CodeIcon,
    EXTERNAL: LayersIcon,
};

/* ─── donut chart ─── */
function DonutChart({ segments, total }) {
    const radius = 48;
    const circumference = 2 * Math.PI * radius;
    let offset = 0;
    return (
        <div className="s6-donut-wrap">
            <svg className="s6-donut-svg" viewBox="0 0 130 130">
                {segments.map((seg, i) => {
                    const pct = total > 0 ? seg.value / total : 0;
                    const dash = circumference * pct;
                    const gap = circumference - dash;
                    const currentOffset = offset;
                    offset += dash;
                    return (
                        <circle
                            key={i}
                            cx="65" cy="65" r={radius}
                            fill="none"
                            stroke={seg.color}
                            strokeWidth="14"
                            strokeDasharray={`${dash} ${gap}`}
                            strokeDashoffset={-currentOffset}
                            strokeLinecap="round"
                        />
                    );
                })}
            </svg>
            <div className="s6-donut-center">
                <div className="s6-donut-total-label">Total</div>
                <div className="s6-donut-total-value">{formatNumber(total)}</div>
                <div style={{ fontSize: '0.55rem', color: '#94A3B8' }}>Components</div>
            </div>
        </div>
    );
}


/* ─── Functionality Card ─── */
function FunctionalityCard({ func, index }) {
    const [expanded, setExpanded] = useState(false);
    const CatIcon = categoryIcons[func.category] || LayersIcon;

    const statusConfig = {
        fully_automated: { color: '#059669', bg: '#ECFDF5', border: '#10B981', label: 'Fully Automated', dot: '✓' },
        needs_review: { color: '#D97706', bg: '#FFFBEB', border: '#F59E0B', label: 'Needs Review', dot: '⚠' },
        manual_required: { color: '#DC2626', bg: '#FEF2F2', border: '#EF4444', label: 'Manual Required', dot: '✕' },
    };
    const sc = statusConfig[func.status] || statusConfig.needs_review;

    return (
        <div
            className={`s6-func-card s6-func-card--${func.status}`}
            style={{ animationDelay: `${index * 0.04}s` }}
            onClick={() => setExpanded(!expanded)}
        >
            {/* Card Header */}
            <div className="s6-func-header">
                <div className="s6-func-cat-icon" style={{ background: sc.bg, color: sc.color }}>
                    <CatIcon />
                </div>
                <div className="s6-func-header-text">
                    <div className="s6-func-business-name">{func.business_name}</div>
                    <div className="s6-func-obj-name">{func.object_name}</div>
                </div>
                <span className="s6-func-status-pill" style={{ background: sc.bg, color: sc.color, borderColor: sc.border }}>
                    {sc.dot} {sc.label}
                </span>
                <span className={`s6-func-chevron ${expanded ? 'expanded' : ''}`}><ChevronDownIcon /></span>
            </div>

            {/* Description */}
            <p className="s6-func-desc">{func.description}</p>

            {/* Source → Target mapping */}
            <div className="s6-func-mapping">
                <div className="s6-func-map-source">
                    <span className="s6-func-map-label">Source</span>
                    <span className="s6-func-map-value">{func.source_label || func.category}</span>
                    {func.detail_counts && <span className="s6-func-map-detail">{func.detail_counts}</span>}
                </div>
                <span className="s6-func-map-arrow"><ArrowRightIcon /></span>
                <div className="s6-func-map-target">
                    <span className="s6-func-map-label">Target</span>
                    <span className="s6-func-map-value">{func.conversion_target}</span>
                </div>
            </div>

            {/* Expanded details */}
            {expanded && (
                <div className="s6-func-expanded">
                    {func.what_it_does && (
                        <div className="s6-func-detail-row">
                            <strong>What it does:</strong> {func.what_it_does}
                        </div>
                    )}
                    <div className="s6-func-meta-row">
                        <span>Confidence: <strong>{Math.round((func.confidence || 0) * 100)}%</strong></span>
                        <span>Risk: <strong className={`risk-${(func.risk || 'LOW').toLowerCase()}`}>{func.risk}</strong></span>
                        <span>Complexity: <strong>{func.complexity}</strong></span>
                    </div>
                </div>
            )}

            {/* Human action callout */}
            {func.human_action && (
                <div className="s6-func-action-callout">
                    <ToolIcon />
                    <span>{func.human_action}</span>
                </div>
            )}
        </div>
    );
}


/* ─── Intervention Item Card (expandable, detailed) ─── */
function InterventionItemCard({ item }) {
    const [expanded, setExpanded] = useState(false);

    const severityConfig = {
        high: { emoji: '🔴', color: '#DC2626', bg: '#FEF2F2', border: '#FCA5A5', label: 'HIGH PRIORITY' },
        medium: { emoji: '🟡', color: '#D97706', bg: '#FFFBEB', border: '#FCD34D', label: 'MEDIUM PRIORITY' },
        low: { emoji: '🟢', color: '#059669', bg: '#ECFDF5', border: '#6EE7B7', label: 'LOW PRIORITY' },
    };
    const sc = severityConfig[item.severity] || severityConfig.medium;

    const effortColors = { Low: '#059669', Medium: '#D97706', High: '#DC2626' };

    return (
        <div className={`s6-intervention-item s6-intervention-item--${item.severity}`}>
            {/* Header row — always visible */}
            <div className="s6-intervention-item-header" onClick={() => setExpanded(!expanded)} style={{ cursor: 'pointer' }}>
                <div className="s6-intervention-item-top">
                    <span className="s6-intervention-item-emoji">{item.icon || sc.emoji}</span>
                    <div className="s6-intervention-item-title-wrap">
                        <span className={`s6-intervention-severity s6-severity--${item.severity}`}>
                            {sc.label} — {item.category}
                        </span>
                        <div className="s6-intervention-item-name">{item.name}</div>
                    </div>
                    <div className="s6-intervention-item-badges">
                        {item.effort && (
                            <span className="s6-intervention-badge" style={{ color: effortColors[item.effort] || '#6B7280', borderColor: effortColors[item.effort] || '#6B7280' }}>
                                ⏱ {item.effort} Effort
                            </span>
                        )}
                        <span className={`s6-func-chevron ${expanded ? 'expanded' : ''}`}><ChevronDownIcon /></span>
                    </div>
                </div>
            </div>

            {/* Impact summary — always visible */}
            {item.impact && (
                <div className="s6-intervention-impact">{item.impact}</div>
            )}

            {/* Expanded details */}
            {expanded && (
                <div className="s6-intervention-details">
                    {/* Affected objects */}
                    {item.affectedObjects && item.affectedObjects.length > 0 && (
                        <div className="s6-intervention-section">
                            <div className="s6-intervention-section-title">📦 Affected Objects</div>
                            <div className="s6-intervention-objects">
                                {item.affectedObjects.map((obj, i) => (
                                    <span key={i} className="s6-intervention-obj-tag">{obj}</span>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* Step-by-step instructions */}
                    {item.steps && item.steps.length > 0 && (
                        <div className="s6-intervention-section">
                            <div className="s6-intervention-section-title">📝 Step-by-Step Resolution Guide</div>
                            <ol className="s6-intervention-steps">
                                {item.steps.map((step, i) => (
                                    <li key={i}>{step}</li>
                                ))}
                            </ol>
                        </div>
                    )}

                    {/* Relevant file paths */}
                    {item.filePaths && item.filePaths.length > 0 && (
                        <div className="s6-intervention-section">
                            <div className="s6-intervention-section-title">📁 Relevant Files & Directories</div>
                            <div className="s6-intervention-files">
                                {item.filePaths.map((fp, i) => (
                                    <div key={i} className="s6-intervention-file-row">
                                        <span className="s6-intervention-file-label">{fp.label}</span>
                                        <code className="s6-intervention-file-path">{fp.path}</code>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* Pro tip */}
                    {item.tip && (
                        <div className="s6-intervention-tip">
                            <span className="s6-intervention-tip-icon">💡</span>
                            <span><strong>Pro Tip:</strong> {item.tip}</span>
                        </div>
                    )}
                </div>
            )}

            {/* Expand prompt */}
            {!expanded && (
                <div className="s6-intervention-expand-hint" onClick={() => setExpanded(true)}>
                    Click to expand step-by-step resolution guide →
                </div>
            )}
        </div>
    );
}


/**
 * Step 6: Summary
 * Premium dashboard-style conversion summary page with business-logic functionality descriptions
 */
export default function Step6Summary() {
    const { state, actions } = useWizard();
    const { generationResult, config, analysisJobId, analysisProgress, generationJobId } = state;
    const [report, setReport] = useState(null);
    const [loading, setLoading] = useState(false);
    const [showAllWarnings, setShowAllWarnings] = useState(false);

    // Filters
    const [categoryFilter, setCategoryFilter] = useState('ALL');
    const [statusFilter, setStatusFilter] = useState('ALL');
    const [searchQuery, setSearchQuery] = useState('');
    const [showAllFuncs, setShowAllFuncs] = useState(false);

    // Load full report when step is entered
    useEffect(() => {
        const loadReport = async () => {
            if (!analysisJobId) return;
            setLoading(true);
            try {
                const data = await getReport(analysisJobId);
                setReport(data);
            } catch (err) {
                console.warn('Could not load full report:', err);
            } finally {
                setLoading(false);
            }
        };
        loadReport();
    }, [analysisJobId]);

    // Calculate summary statistics
    const stats = report ? {
        tables: report.statistics?.tables || 0,
        queries: report.statistics?.queries || 0,
        forms: report.statistics?.forms || 0,
        reports: report.statistics?.reports || 0,
        macros: report.statistics?.macros || 0,
        vbaModules: report.statistics?.vba_modules || 0,
    } : {
        tables: analysisProgress.tables?.count || 0,
        queries: analysisProgress.queries?.count || 0,
        forms: analysisProgress.forms?.count || 0,
        reports: analysisProgress.reports?.count || 0,
        macros: analysisProgress.macros?.count || 0,
        vbaModules: analysisProgress.vba?.count || 0,
    };

    const totalObjects = Object.values(stats).reduce((a, b) => a + b, 0);

    // Coverage from report
    const coverage = report?.coverage || {
        overall: 0,
        fully_supported_pct: 0,
        supported_with_review_pct: 0,
        unsupported_pct: 0,
        table_coverage: 0,
        query_coverage: 0,
        form_coverage: 0,
        report_coverage: 0,
        macro_coverage: 0,
        vba_coverage: 0,
    };

    // Functionality summaries from report
    const allFuncs = report?.functionality_summaries || [];

    // Count by status
    const automatedCount = allFuncs.filter(f => f.status === 'fully_automated').length;
    const reviewCount = allFuncs.filter(f => f.status === 'needs_review').length;
    const manualCount = allFuncs.filter(f => f.status === 'manual_required').length;

    // Generated file counts
    const generated = report?.generated || {};
    const estimated = getGeneratedCounts(analysisProgress);
    const backendFiles = estimated.backend || generated.backend_files || 0;
    const frontendFiles = estimated.frontend || generated.frontend_files || 0;
    const totalFilesGenerated = estimated.total || (backendFiles + frontendFiles + (estimated.database || 0));

    // Filter functionalities
    const filteredFuncs = useMemo(() => {
        let result = allFuncs;
        if (categoryFilter !== 'ALL') {
            result = result.filter(f => f.category === categoryFilter);
        }
        if (statusFilter !== 'ALL') {
            result = result.filter(f => f.status === statusFilter);
        }
        if (searchQuery.trim()) {
            const q = searchQuery.toLowerCase();
            result = result.filter(f =>
                (f.business_name || '').toLowerCase().includes(q) ||
                (f.object_name || '').toLowerCase().includes(q) ||
                (f.description || '').toLowerCase().includes(q)
            );
        }
        return result;
    }, [allFuncs, categoryFilter, statusFilter, searchQuery]);

    const visibleFuncs = showAllFuncs ? filteredFuncs : filteredFuncs.slice(0, 8);

    // Human intervention items — rich actionable guidance
    const interventionItems = useMemo(() => {
        const items = [];
        const projectName = config.project_name || 'project';
        const basePackagePath = (config.base_package || 'com.app').replace(/\./g, '/');

        // Unsupported objects — each gets its own detailed card
        const unsupported = allFuncs.filter(f => f.status === 'manual_required');
        if (unsupported.length > 0) {
            const affectedNames = unsupported.map(f => f.object_name);
            items.push({
                severity: 'high',
                category: 'Unsupported Components',
                icon: '🚫',
                name: `${unsupported.length} component(s) could not be automatically converted`,
                impact: 'These components have no generated output. The application will not include their functionality until manually implemented.',
                affectedObjects: affectedNames,
                effort: unsupported.length <= 2 ? 'Medium' : 'High',
                steps: [
                    'Review each component listed below to understand its original purpose in the Access application',
                    `Create equivalent Spring Boot service classes under src/main/java/${basePackagePath}/service/`,
                    'If the component involves UI, create corresponding React components under src/components/',
                    'Add REST controller endpoints to expose the new service methods to the frontend',
                    'Write unit tests for the new service methods to validate business logic',
                ],
                filePaths: [
                    { label: 'Backend services directory', path: `backend/src/main/java/${basePackagePath}/service/` },
                    { label: 'Frontend components', path: `frontend/src/components/` },
                ],
                tip: 'Start with the components that are referenced by other parts of the application. Check the Functionality Cards above to see which converted components depend on these.',
            });
        }

        // Forms with VBA events — detailed migration guide
        const formsBreakdown = report?.forms_breakdown || {};
        if (formsBreakdown.forms_with_unconverted_vba_events > 0) {
            const vbaFormNames = allFuncs
                .filter(f => f.category === 'FORM' && f.status !== 'fully_automated')
                .map(f => f.object_name);
            items.push({
                severity: 'medium',
                category: 'VBA Event Handlers Not Migrated',
                icon: '⚡',
                name: `${formsBreakdown.forms_with_unconverted_vba_events} form(s) contain VBA event handlers that were not converted`,
                impact: 'The form layouts and data bindings were converted to React, but VBA code in event handlers (OnClick, BeforeUpdate, AfterUpdate, OnOpen, etc.) was not migrated. Buttons may not trigger actions, and validation/business logic may be missing.',
                affectedObjects: vbaFormNames.length > 0 ? vbaFormNames : undefined,
                effort: 'Medium',
                steps: [
                    'Open the generated React form component (e.g., FrmCustomerEditPage.jsx)',
                    'Look for TODO comments in the generated code — these mark where VBA event logic should be placed',
                    'For OnClick handlers: implement the equivalent action in a React onClick handler or call a backend API',
                    'For BeforeUpdate/AfterUpdate: use React form validation (e.g., onBlur or onSubmit) to replicate the validation logic',
                    'For data manipulation (DoCmd.RunSQL, CurrentDb.Execute): move the logic to a Spring Boot @Service method and call it via the REST API',
                    'For navigation logic (DoCmd.OpenForm): replace with React Router navigation (e.g., navigate("/customers/edit"))',
                ],
                filePaths: [
                    { label: 'Generated form components', path: `frontend/src/components/forms/` },
                    { label: 'Backend services for form logic', path: `backend/src/main/java/${basePackagePath}/service/` },
                ],
                tip: 'The original VBA source code for each form is available in the migration report. Search for the form name in migration-report.json under the "supportability" section to see the VBA event details.',
            });
        }

        // Unbound forms — specific guidance per form
        const unboundForms = formsBreakdown.unbound_form_names || [];
        if (unboundForms.length > 0) {
            items.push({
                severity: 'low',
                category: 'Unbound Forms (No Data Source)',
                icon: '📋',
                name: `${unboundForms.length} form(s) have no record source and were converted as static layouts`,
                impact: 'These forms were used in Access without being bound to a table or query. They may serve as dashboards, navigation menus, search dialogs, or settings screens. The generated React components have the visual layout but no data fetching logic.',
                affectedObjects: unboundForms,
                effort: 'Low',
                steps: [
                    'Identify the purpose of each unbound form — common types are: dashboards, search/filter screens, navigation menus, dialog boxes, or settings panels',
                    'For dashboard forms: connect them to relevant API endpoints to fetch summary data (e.g., counts, recent records)',
                    'For search/filter forms: wire the form inputs to a GET endpoint with query parameters and display results',
                    'For navigation menus: link buttons/links to the appropriate React Router routes of other converted forms',
                    'For dialog/popup forms: ensure they open as modals and pass data back to the calling component',
                ],
                filePaths: unboundForms.slice(0, 4).map(name => {
                    const componentName = name.replace(/^frm/i, '').replace(/([a-z])([A-Z])/g, '$1$2');
                    return { label: `${name}`, path: `frontend/src/components/forms/${componentName}Page.jsx` };
                }),
                tip: 'Dashboard and menu forms are often the most important screens in the application. Prioritize connecting frmDashboard and frmMainMenu to actual data and navigation first.',
            });
        }

        // Dropped queries with custom VBA functions
        const droppedQueries = report?.dropped_queries?.filter(q =>
            q.custom_vba_functions && q.custom_vba_functions.length > 0
        ) || [];
        if (droppedQueries.length > 0) {
            const vbaFunctions = [...new Set(droppedQueries.flatMap(q => q.custom_vba_functions || []))];
            items.push({
                severity: 'medium',
                category: 'Queries Using Custom VBA Functions',
                icon: '🔧',
                name: `${droppedQueries.length} query(s) reference ${vbaFunctions.length} custom VBA function(s) not available in PostgreSQL`,
                impact: `These queries call custom VBA functions (${vbaFunctions.slice(0, 3).join(', ')}${vbaFunctions.length > 3 ? '...' : ''}) that only exist in the Access VBA environment. The queries were emitted as TODO stubs in the backend. Any forms or reports that depended on these queries may return empty results.`,
                affectedObjects: droppedQueries.map(q => q.name),
                effort: vbaFunctions.length <= 3 ? 'Medium' : 'High',
                steps: [
                    `Locate the VBA function definitions in the original Access database — look for: ${vbaFunctions.slice(0, 5).join(', ')}`,
                    'Implement equivalent logic as Java methods in a Spring Boot @Service or @Component class',
                    `Create the service at: src/main/java/${basePackagePath}/service/CustomFunctionService.java`,
                    'For each affected query, update the corresponding Repository or @Query method to use the new Java implementation',
                    'If the function was a simple calculation, consider implementing it as a PostgreSQL function instead (add to schema.sql)',
                    'Test each affected endpoint to verify the query results match the original Access behavior',
                ],
                filePaths: [
                    { label: 'Database schema', path: `database/schema.sql` },
                    { label: 'Repository layer', path: `backend/src/main/java/${basePackagePath}/repository/` },
                    { label: 'Custom function service (create)', path: `backend/src/main/java/${basePackagePath}/service/CustomFunctionService.java` },
                ],
                tip: `Common VBA functions like DLookup, DCount, and DSum are domain aggregate functions. In Spring Boot, replace them with JPA repository methods like findBy...(), count(), or custom @Query annotations.`,
            });
        }

        // Extraction failures — critical path items
        const failures = report?.extraction_failures || [];
        if (failures.length > 0) {
            items.push({
                severity: 'high',
                category: 'Extraction Failures',
                icon: '❌',
                name: `${failures.length} object(s) could not be extracted from the Access database`,
                impact: 'These objects exist in the original Access database but the converter was unable to read or parse their definition. They have no generated output at all. This may happen with corrupted objects, objects with very complex VBA, or unsupported Access features.',
                affectedObjects: failures.map(f => `${f.object} (${f.category})`),
                effort: 'High',
                steps: [
                    'Open the original Access database (.accdb) in Microsoft Access',
                    'Navigate to each failed object and examine its design view',
                    'Manually recreate the equivalent functionality in the target stack:',
                    '  — For Tables: create a JPA @Entity class and add a CREATE TABLE to schema.sql',
                    '  — For Queries: write a Spring Data JPA repository method or native @Query',
                    '  — For Forms: create a new React page component with the form layout',
                    '  — For VBA Modules: implement the logic as Spring Boot @Service methods',
                    'Add the new components to the application routing and navigation',
                ],
                filePaths: [
                    { label: 'Migration report (details)', path: `migration-report/migration-report.json` },
                ],
                tip: 'Check the Warnings section below — extraction warnings may provide additional details about why these objects failed.',
            });
        }

        // Needs review items — general guidance
        const reviewItems = allFuncs.filter(f => f.status === 'needs_review');
        if (reviewItems.length > 0 && items.every(i => i.category !== 'Review Required')) {
            const reviewByCategory = {};
            reviewItems.forEach(r => {
                if (!reviewByCategory[r.category]) reviewByCategory[r.category] = [];
                reviewByCategory[r.category].push(r.object_name);
            });
            const categoryBreakdown = Object.entries(reviewByCategory)
                .map(([cat, names]) => `${names.length} ${cat.toLowerCase()}(s)`).join(', ');

            items.push({
                severity: 'medium',
                category: 'Components Converted with Review Notes',
                icon: '👁️',
                name: `${reviewItems.length} component(s) were converted but flagged for developer review: ${categoryBreakdown}`,
                impact: 'These components were successfully converted but may contain edge cases, complex transformations, or Access-specific patterns that need verification. The generated code is functional but may not perfectly replicate the original behavior.',
                affectedObjects: reviewItems.slice(0, 10).map(r => r.object_name),
                effort: 'Low',
                steps: [
                    'Review the generated code for each flagged component — look for // REVIEW or // TODO comments',
                    'Compare the generated output against the original Access behavior for critical business logic',
                    'Test data entry forms with edge cases (empty fields, max length, special characters)',
                    'Verify that calculated fields, default values, and validation rules produce the same results',
                    'Run the application and navigate through each flagged screen to check for UI issues',
                ],
                filePaths: [
                    { label: 'All generated backend code', path: `backend/src/main/java/${basePackagePath}/` },
                    { label: 'All generated frontend code', path: `frontend/src/components/` },
                ],
                tip: 'Focus your review on components with the lowest confidence scores. Click on each functionality card above and expand it to see the confidence percentage — items below 85% confidence should be reviewed first.',
            });
        }

        return items;
    }, [allFuncs, report, config]);

    // Donut chart data
    const donutSegments = [
        { label: 'Fully Automated', value: automatedCount, color: '#10B981', pct: totalObjects > 0 ? (automatedCount / allFuncs.length * 100) : 0 },
        { label: 'Needs Review', value: reviewCount, color: '#F59E0B', pct: totalObjects > 0 ? (reviewCount / allFuncs.length * 100) : 0 },
        { label: 'Manual Required', value: manualCount, color: '#EF4444', pct: totalObjects > 0 ? (manualCount / allFuncs.length * 100) : 0 },
    ];

    // Coverage rows with source→target labels
    const categoryRows = [
        { key: 'table_coverage', label: 'Tables', Icon: DatabaseIcon, count: stats.tables, sourceLabel: 'Access Tables', targetLabel: 'PostgreSQL + JPA Entities', barColor: 'green' },
        { key: 'query_coverage', label: 'Queries', Icon: SearchIcon, count: stats.queries, sourceLabel: 'Access Queries', targetLabel: 'REST API Endpoints', barColor: 'purple' },
        { key: 'form_coverage', label: 'Forms', Icon: LayoutIcon, count: stats.forms, sourceLabel: 'Access Forms', targetLabel: 'React Page Components', barColor: 'blue' },
        { key: 'report_coverage', label: 'Reports', Icon: BarChartIcon, count: stats.reports, sourceLabel: 'Access Reports', targetLabel: 'PDF Report Services', barColor: 'orange' },
        { key: 'macro_coverage', label: 'Macros', Icon: ZapIcon, count: stats.macros, sourceLabel: 'Access Macros', targetLabel: 'Spring Service Methods', barColor: 'red' },
        { key: 'vba_coverage', label: 'VBA Modules', Icon: CodeIcon, count: stats.vbaModules, sourceLabel: 'VBA Modules', targetLabel: 'Spring Boot Services', barColor: 'purple' },
    ];

    // Warnings
    const warnings = report?.warnings || [];

    const handleDownload = useCallback(() => {
        if (generationJobId) {
            downloadResult(generationJobId, config.project_name);
        }
    }, [generationJobId, config.project_name]);

    const handleOpenReport = useCallback(() => {
        if (generationResult?.outputPath) {
            window.open(`${generationResult.outputPath}/migration-report/migration-report.html`, '_blank');
        }
    }, [generationResult]);

    const handleOpenProject = useCallback(() => {
        if (generationResult?.outputPath) {
            window.open(`file://${generationResult.outputPath}`, '_blank');
        }
    }, [generationResult]);

    const convertedDate = new Date().toLocaleDateString('en-US', {
        day: '2-digit', month: 'short', year: 'numeric',
    }) + ', ' + new Date().toLocaleTimeString('en-US', {
        hour: '2-digit', minute: '2-digit', hour12: true,
    });

    const dbFileName = state.selectedFile?.name
        || state.localSource?.name
        || state.fileMetadata?.name
        || 'database.accdb';

    // Category filter options
    const categoryOptions = [
        { key: 'ALL', label: 'All' },
        { key: 'TABLE', label: 'Tables' },
        { key: 'QUERY', label: 'Queries' },
        { key: 'FORM', label: 'Forms' },
        { key: 'REPORT', label: 'Reports' },
        { key: 'MACRO', label: 'Macros' },
        { key: 'VBA', label: 'VBA' },
    ];
    const statusOptions = [
        { key: 'ALL', label: 'All Statuses' },
        { key: 'fully_automated', label: '✅ Automated' },
        { key: 'needs_review', label: '⚠️ Needs Review' },
        { key: 'manual_required', label: '❌ Manual' },
    ];

    return (
        <div style={{ width: '100%' }}>

            {/* ── HERO ── */}
            <div className="s6-hero">
                <div className="s6-hero-inner">
                    <div className="s6-hero-left">
                        <div className="s6-hero-check"><CheckIcon /></div>
                        <div className="s6-hero-text">
                            <h2>Conversion Complete!</h2>
                            <p>
                                <strong>{automatedCount}</strong> of <strong>{allFuncs.length}</strong> functionalities fully automated.
                                {reviewCount > 0 && <> <strong>{reviewCount}</strong> need your review.</>}
                                {manualCount > 0 && <> <strong>{manualCount}</strong> need manual work.</>}
                            </p>
                            <div className="s6-hero-tech">
                                <span>Spring Boot</span>
                                <span className="separator">•</span>
                                <span>React</span>
                                <span className="separator">•</span>
                                <span>PostgreSQL</span>
                            </div>
                        </div>
                    </div>
                    <div className="s6-hero-meta">
                        <span className="s6-hero-meta-label" style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                            <span style={{ width: 14, height: 14, display: 'inline-flex' }}><AppIcon /></span> Application
                        </span>
                        <span className="s6-hero-meta-value">{config.project_name}</span>

                        <span className="s6-hero-meta-label" style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                            <span style={{ width: 14, height: 14, display: 'inline-flex' }}><DatabaseIcon /></span> Database
                        </span>
                        <span className="s6-hero-meta-value">{dbFileName}</span>

                        <span className="s6-hero-meta-label" style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                            <span style={{ width: 14, height: 14, display: 'inline-flex' }}><ClockIcon /></span> Converted On
                        </span>
                        <span className="s6-hero-meta-value">{convertedDate}</span>

                        {/* <span className="s6-hero-meta-label" style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                            <span style={{ width: 14, height: 14, display: 'inline-flex' }}><SettingsIcon /></span> Conversion Mode
                        </span>
                        <span className="s6-hero-meta-value">Standard</span> */}
                    </div>
                </div>
            </div>

            {/* ── STAT CARDS ── */}
            <div className="s6-stats-row">
                <div className="s6-stat-card s6-stat-card--overall">
                    <div className="s6-stat-card-header"><div className="s6-stat-card-icon"><CheckIcon /></div></div>
                    <div className="s6-stat-card-value">{automatedCount}</div>
                    <div className="s6-stat-card-label">FULLY AUTOMATED</div>
                    <div className="s6-stat-card-desc">Ready to use, no changes needed</div>
                    <div className="s6-stat-card-bar"><div className="s6-stat-card-bar-fill green" style={{ width: `${allFuncs.length ? (automatedCount / allFuncs.length * 100) : 0}%` }} /></div>
                </div>
                <div className="s6-stat-card s6-stat-card--supported">
                    <div className="s6-stat-card-header"><div className="s6-stat-card-icon"><AlertTriangleIcon /></div></div>
                    <div className="s6-stat-card-value">{reviewCount}</div>
                    <div className="s6-stat-card-label">NEEDS YOUR REVIEW</div>
                    <div className="s6-stat-card-desc">Converted with items requiring attention</div>
                    <div className="s6-stat-card-bar"><div className="s6-stat-card-bar-fill amber" style={{ width: `${allFuncs.length ? (reviewCount / allFuncs.length * 100) : 0}%` }} /></div>
                </div>
                <div className="s6-stat-card s6-stat-card--review">
                    <div className="s6-stat-card-header"><div className="s6-stat-card-icon"><XCircleIcon /></div></div>
                    <div className="s6-stat-card-value">{manualCount}</div>
                    <div className="s6-stat-card-label">MANUAL WORK</div>
                    <div className="s6-stat-card-desc">Requires developer implementation</div>
                    <div className="s6-stat-card-bar"><div className="s6-stat-card-bar-fill red" style={{ width: `${allFuncs.length ? (manualCount / allFuncs.length * 100) : 0}%` }} /></div>
                </div>
                <div className="s6-stat-card s6-stat-card--unsupported">
                    <div className="s6-stat-card-header"><div className="s6-stat-card-icon"><LayersIcon /></div></div>
                    <div className="s6-stat-card-value">{formatNumber(totalFilesGenerated)}</div>
                    <div className="s6-stat-card-label">FILES GENERATED</div>
                    <div className="s6-stat-card-desc">{backendFiles} backend + {frontendFiles} frontend</div>
                    <div className="s6-stat-card-bar"><div className="s6-stat-card-bar-fill blue" style={{ width: '100%' }} /></div>
                </div>
            </div>

            {/* ── YOUR APPLICATION'S FUNCTIONALITIES ── */}
            <div className="s6-section-card s6-func-section">
                <div className="s6-section-header">
                    <div>
                        <div className="s6-section-title">Your Application's Components and their Mappings</div>
                        <div className="s6-section-subtitle">
                            Each component from your Access application, described in business terms
                            {allFuncs.length > 0 && <span style={{ marginLeft: '0.5rem', fontWeight: 600 }}>({allFuncs.length} total)</span>}
                        </div>
                    </div>
                </div>

                {/* Filter bar */}
                <div className="s6-filter-bar">
                    <div className="s6-filter-tabs">
                        {categoryOptions.map(opt => (
                            <button
                                key={opt.key}
                                className={`s6-filter-tab ${categoryFilter === opt.key ? 'active' : ''}`}
                                onClick={() => setCategoryFilter(opt.key)}
                            >
                                {opt.label}
                                {opt.key !== 'ALL' && (
                                    <span className="s6-filter-count">
                                        {allFuncs.filter(f => f.category === opt.key).length}
                                    </span>
                                )}
                            </button>
                        ))}
                    </div>
                    <div className="s6-filter-right">
                        <div className="s6-filter-status-pills">
                            {statusOptions.map(opt => (
                                <button
                                    key={opt.key}
                                    className={`s6-filter-pill ${statusFilter === opt.key ? 'active' : ''}`}
                                    onClick={() => setStatusFilter(opt.key)}
                                >
                                    {opt.label}
                                </button>
                            ))}
                        </div>
                        <div className="s6-filter-search">
                            <SearchIcon />
                            <input
                                type="text"
                                placeholder="Search functionalities..."
                                value={searchQuery}
                                onChange={e => setSearchQuery(e.target.value)}
                            />
                        </div>
                    </div>
                </div>

                {/* Functionality cards */}
                <div className="s6-func-grid">
                    {visibleFuncs.length > 0 ? (
                        visibleFuncs.map((func, i) => (
                            <FunctionalityCard key={func.object_name || i} func={func} index={i} />
                        ))
                    ) : (
                        <div style={{ padding: '2rem', color: 'var(--color-text-muted)', fontSize: '0.85rem', textAlign: 'center', gridColumn: '1 / -1' }}>
                            {allFuncs.length === 0
                                ? (loading ? 'Loading functionality data...' : 'No functionality data available')
                                : 'No functionalities match the current filters'}
                        </div>
                    )}
                </div>

                {filteredFuncs.length > 8 && (
                    <button className="s6-show-all-btn" onClick={() => setShowAllFuncs(!showAllFuncs)}>
                        {showAllFuncs ? 'Show Less' : `Show All ${filteredFuncs.length} Functionalities`}
                    </button>
                )}
            </div>

            {/* ── HUMAN INTERVENTION REQUIRED ── */}
            {interventionItems.length > 0 && (
                <div className="s6-intervention-card">
                    <div className="s6-intervention-header">
                        <div className="s6-intervention-icon"><ToolIcon /></div>
                        <div>
                            <div className="s6-intervention-title">Human Intervention Required</div>
                            <div className="s6-intervention-subtitle">
                                {interventionItems.length} area(s) need developer attention to complete the modernization.
                                Expand each item below for step-by-step guidance.
                            </div>
                        </div>
                    </div>
                    <div className="s6-intervention-list">
                        {interventionItems.map((item, i) => (
                            <InterventionItemCard key={i} item={item} projectName={config.project_name} />
                        ))}
                    </div>
                </div>
            )}

            {/* ── SOURCE APPLICATION COVERAGE ── */}
            <div className="s6-cols">
                {/* Coverage Donut + Legend */}
                <div className="s6-section-card">
                    <div className="s6-section-header">
                        <div>
                            <div className="s6-section-title">Conversion Insights</div>
                            <div className="s6-section-subtitle">How your source application was covered</div>
                        </div>
                    </div>
                    <div className="s6-insights-wrap">
                        <DonutChart segments={donutSegments} total={allFuncs.length || totalObjects} />
                        <div className="s6-legend">
                            {donutSegments.map((seg, i) => (
                                <div key={i} className="s6-legend-item">
                                    <span className="s6-legend-dot" style={{ background: seg.color }} />
                                    <span className="s6-legend-label">{seg.label}</span>
                                    <span className="s6-legend-value">
                                        {formatPercentage(seg.pct)} ({seg.value})
                                    </span>
                                </div>
                            ))}
                        </div>
                    </div>

                    {/* Generated output summary */}
                    <div className="s6-generated-bar">
                        <span className="s6-generated-label">Generated Output</span>
                        <span className="s6-generated-value">{backendFiles} Java files</span>
                        <span className="s6-generated-sep">•</span>
                        <span className="s6-generated-value">{frontendFiles} React files</span>
                        <span className="s6-generated-sep">•</span>
                        <span className="s6-generated-value">1 SQL schema</span>
                    </div>
                </div>

                {/* Coverage by Category */}
                <div className="s6-section-card">
                    <div className="s6-section-header">
                        <div>
                            <div className="s6-section-title">Coverage by Category</div>
                            <div className="s6-section-subtitle">Source → Target mapping per category</div>
                        </div>
                    </div>
                    <div className="s6-coverage-list">
                        {categoryRows.map(row => {
                            const pct = coverage[row.key] || 0;
                            const coveredCount = Math.round((pct / 100) * row.count) || 0;
                            return (
                                <div key={row.key} className="s6-coverage-row">
                                    <div className="s6-coverage-icon"><row.Icon /></div>
                                    <div className="s6-coverage-info">
                                        <div className="s6-coverage-label">{row.label}</div>
                                        <div className="s6-coverage-target-label">{row.count} {row.sourceLabel} → {row.targetLabel}</div>
                                    </div>
                                    <div className="s6-coverage-bar-wrap">
                                        <div className="s6-coverage-bar">
                                            <div className={`s6-coverage-bar-fill ${row.barColor}`} style={{ width: `${pct}%` }} />
                                        </div>
                                        <span className="s6-coverage-pct">{formatPercentage(pct)}</span>
                                    </div>
                                    <span className="s6-coverage-count">{coveredCount} / {row.count}</span>
                                </div>
                            );
                        })}
                    </div>
                    {/* <a className="s6-detail-link" onClick={handleOpenReport}>
                        View detailed analysis →
                    </a> */}
                </div>
            </div>

            {/* ── WARNINGS ── */}
            {warnings.length > 0 && (
                <div className="s6-collapsible s6-collapsible--warning" style={{ position: 'relative' }}>
                    <div className="s6-collapsible-header" style={{ color: '#D97706' }}>
                        <AlertTriangleIcon />
                        Warnings
                        <span className="s6-collapsible-count">({warnings.length})</span>
                    </div>
                    <div className="s6-collapsible-body">
                        <ul className="s6-warning-list">
                            {(showAllWarnings ? warnings : warnings.slice(0, 5)).map((w, i) => (
                                <li key={i}>{w}</li>
                            ))}
                        </ul>
                        {warnings.length > 5 && !showAllWarnings && (
                            <a className="s6-expand-link" onClick={() => setShowAllWarnings(true)}>
                                + {warnings.length - 5} more warnings
                            </a>
                        )}
                        {showAllWarnings && warnings.length > 5 && (
                            <a className="s6-expand-link" onClick={() => setShowAllWarnings(false)}>
                                Show less
                            </a>
                        )}
                    </div>
                </div>
            )}

            {/* ── ACTION BUTTONS ── */}
            <div className="s6-actions">
                <button className="s6-action-btn s6-action-btn--outline" onClick={handleOpenReport}>
                    <FileTextIcon /> Open Report
                </button>
                {generationJobId && (
                    <button className="s6-action-btn s6-action-btn--download" onClick={handleDownload}>
                        <DownloadIcon /> Download Project ZIP
                    </button>
                )}
                <button className="s6-action-btn s6-action-btn--outline" onClick={handleOpenProject}>
                    <FolderIcon /> Open Project Folder
                </button>
            </div>

            {/* ── FOOTER ── */}
            <div className="s6-footer">
                <p>Need help with the generated project?</p>
                <a href="#" target="_blank" rel="noopener noreferrer" className="s6-footer-link">
                    <BookIcon /> View Documentation
                </a>
            </div>
        </div>
    );
}