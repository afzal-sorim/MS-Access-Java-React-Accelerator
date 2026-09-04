import React, { useEffect, useCallback, useRef, useState } from 'react';
import { useWizard } from '../../../context/WizardContext';
import { createJob, connectProgressWebSocket, downloadResult, getJob, listJobFiles, getFileContent, getJobDbSchema } from '../../../services/api';
import { JOB_STATES } from '../../../utils/constants';
import { formatNumber } from '../../../utils/helpers';
import { getGeneratedCounts } from '../../../utils/generatedCounts';
import Step4Review from './Step4Review';

/**
 * Step 4: Modernization (combined Map & Review + Solution Explorer)
 */

const GENERATION_STEPS = [
    { key: 'frontend', label: 'Generating Frontend', icon: '⚛️', description: 'Creating React pages, components, API clients, routing' },
    { key: 'backend', label: 'Generating Backend', icon: '☕', description: 'Creating Spring Boot entities, repositories, services, controllers' },
    { key: 'database', label: 'Generating Database', icon: '🗄️', description: 'Creating PostgreSQL schema, migrations, and seed data' },
    { key: 'dependencies', label: 'Resolving Dependencies', icon: '📦', description: 'Resolving Maven and npm dependency versions, checking convergence' },
    { key: 'build_backend', label: 'Building Backend', icon: '🔨', description: 'Running mvn clean package, dependency convergence check' },
    { key: 'build_frontend', label: 'Building Frontend', icon: '📦', description: 'Running npm ci, npm run build' },
    { key: 'tests', label: 'Running Tests', icon: '🧪', description: 'Executing unit tests, API tests, integration tests' },
    { key: 'repair', label: 'Repairing Errors', icon: '🔧', description: 'Applying deterministic and LLM-based fixes for build failures' },
    { key: 'behavioral', label: 'Behavioral Tests', icon: '✅', description: 'Running behavioral regression tests against source Access app' },
];

const STEP_ORDER = GENERATION_STEPS.map(s => s.key);

const BACKEND_STEP_MAP = {
    'generating_database': 'database',
    'generating_backend': 'backend',
    'generating_frontend': 'frontend',
    'generating_reports': 'frontend',
    'resolving_dependencies': 'dependencies',
    'validating_build': 'build_backend',
    'self_healing_repair': 'repair',
    'completed': 'behavioral',
    'GENERATING_DATABASE': 'database',
    'GENERATING_BACKEND': 'backend',
    'GENERATING_FRONTEND': 'frontend',
    'RESOLVING_DEPENDENCIES': 'dependencies',
    'BUILDING': 'build_backend',
    'REPAIRING': 'repair',
    'TESTING': 'tests',
    'VALIDATING': 'behavioral',
    'COMPLETED': 'behavioral',
};

const BACKEND_STATE_ORDER = [
    'GENERATING_DATABASE',
    'GENERATING_BACKEND',
    'GENERATING_FRONTEND',
    'BUILDING',
    'REPAIRING',
    'TESTING',
    'VALIDATING',
    'COMPLETED',
];

function getCompletedFrontendSteps(backendState) {
    const stateIndex = BACKEND_STATE_ORDER.indexOf(backendState);
    if (stateIndex <= 0) return [];
    const completed = [];
    for (let i = 0; i < stateIndex; i++) {
        const frontendKey = BACKEND_STEP_MAP[BACKEND_STATE_ORDER[i]];
        if (frontendKey && !completed.includes(frontendKey)) {
            completed.push(frontendKey);
        }
    }
    return completed;
}

/**
 * ER Diagram Component
 */
function ERDiagram({ schema }) {
    if (!schema || !schema.tables) return null;

    const normalizeName = (name) => String(name || '').replace(/[\[\]`"]+/g, '').trim().toLowerCase();
    const columnCount = Math.max(...schema.tables.map(table => table.columns?.length || 0), 1);
    const rowHeight = Math.max(185, 86 + columnCount * 36);
    const columnsPerRow = 3;
    const diagramRows = Math.ceil(schema.tables.length / columnsPerRow);
    const tablePositions = new Map(schema.tables.map((table, index) => [normalizeName(table.name), {
        index,
        column: index % columnsPerRow,
        row: Math.floor(index / columnsPerRow),
        height: 42 + (table.columns?.length || 0) * 36,
    }]));

    return (
        <div style={{ background: '#f8fafc', minHeight: '100%', position: 'relative' }}>
            {/* Header */}
            <div style={{ padding: '1.25rem 2rem', borderBottom: '1px solid #e2e8f0', display: 'flex', alignItems: 'center', justifyContent: 'space-between', background: '#fff' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                    <div style={{ width: '32px', height: '32px', borderRadius: '8px', background: 'linear-gradient(135deg, #0ea5e9, #6366f1)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '1rem', color: '#fff' }}>🗄️</div>
                    <div>
                        <div style={{ fontSize: '0.9rem', fontWeight: 700, color: '#1e293b' }}>Database Entity-Relationship Diagram</div>
                        <div style={{ fontSize: '0.7rem', color: '#64748b' }}>{schema.tables.length} tables · {schema.relationships?.length || 0} relationships</div>
                    </div>
                </div>
                <div style={{ display: 'flex', gap: '0.5rem' }}>
                    <span style={{ background: '#fff', color: '#64748b', fontSize: '0.65rem', padding: '3px 8px', borderRadius: '20px', border: '1px solid #e2e8f0' }}>🔑 PK = Primary Key</span>
                    <span style={{ background: '#fff', color: '#64748b', fontSize: '0.65rem', padding: '3px 8px', borderRadius: '20px', border: '1px solid #e2e8f0' }}>🔗 FK = Foreign Key</span>
                </div>
            </div>

            {/* Animation Style */}
            <style>
                {`
                @keyframes flowAnimation {
                    from { stroke-dashoffset: 6; }
                    to { stroke-dashoffset: 0; }
                }
                `}
            </style>

            {/* Diagram Canvas */}
            <div style={{ padding: '1.5rem 2rem', position: 'relative', minHeight: `${diagramRows * rowHeight}px`, overflow: 'auto' }}>
                <svg
                    aria-label="Table relationships"
                    viewBox={`0 0 100 ${diagramRows * rowHeight}`}
                    preserveAspectRatio="none"
                    style={{ position: 'absolute', inset: 0, width: '100%', height: `${diagramRows * rowHeight}px`, pointerEvents: 'none', overflow: 'visible' }}
                >
                    <defs>
                        <marker id="erd-arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                            <path d="M 0 0 L 10 5 L 0 10 z" fill="#38bdf8" />
                        </marker>
                    </defs>
                    {(schema.relationships || []).map((rel, index) => {
                        const child = tablePositions.get(normalizeName(rel.child_table));
                        const parent = tablePositions.get(normalizeName(rel.parent_table));
                        if (!child || !parent) return null;
                        const childColumn = rel.child_columns?.join(', ') || 'FK';
                        const parentColumn = rel.parent_columns?.join(', ') || 'PK';
                        const childX = child.column * 33.33;
                        const parentX = parent.column * 33.33;
                        const childY = child.row * rowHeight;
                        const parentY = parent.row * rowHeight;
                        const isHorizontal = child.row === parent.row;
                        const childOnRight = child.column > parent.column;
                        const startX = isHorizontal ? childX + (childOnRight ? 0 : 31) : childX + 15.5;
                        const endX = isHorizontal ? parentX + (childOnRight ? 31 : 0) : parentX + 15.5;
                        const startY = isHorizontal
                            ? childY + Math.min(child.height, parent.height) / 2
                            : childY + (child.row < parent.row ? child.height : 0);
                        const endY = isHorizontal
                            ? parentY + Math.min(child.height, parent.height) / 2
                            : parentY + (child.row < parent.row ? 0 : parent.height);
                        const middleX = (startX + endX) / 2;
                        const middleY = (startY + endY) / 2;
                        
                        const lineProps = {
                            stroke: "#0ea5e9",
                            strokeWidth: "0.4",
                            strokeDasharray: "2 1",
                            markerEnd: "url(#erd-arrow)",
                            style: { animation: 'flowAnimation 1s linear infinite' }
                        };
                        
                        return (
                            <g key={`${rel.child_table}-${rel.parent_table}-${index}`}>
                                {isHorizontal ? (
                                    <line x1={startX} y1={startY} x2={endX} y2={endY} {...lineProps} />
                                ) : (
                                    <path d={`M ${startX} ${startY} C ${startX} ${middleY}, ${endX} ${middleY}, ${endX} ${endY}`} fill="none" {...lineProps} />
                                )}
                                <text x={isHorizontal ? middleX : middleX + 2} y={middleY - 2} textAnchor="middle" fill="#0284c7" fontSize="2" fontWeight="600">
                                    {childColumn} → {parentColumn}
                                </text>
                            </g>
                        );
                    })}
                </svg>
                {schema.tables.map(table => (
                    <div key={table.name} style={{
                        position: 'absolute',
                        left: `${(schema.tables.indexOf(table) % columnsPerRow) * 33.33}%`,
                        top: `${Math.floor(schema.tables.indexOf(table) / columnsPerRow) * rowHeight}px`,
                        width: '31%',
                        background: '#fff',
                        border: '1px solid #e2e8f0',
                        borderRadius: '10px',
                        overflow: 'hidden',
                        boxShadow: '0 4px 6px -1px rgba(0,0,0,0.05), 0 2px 4px -1px rgba(0,0,0,0.03)'
                    }}>
                        {/* Table header */}
                        <div style={{
                            background: 'linear-gradient(90deg, #f0f9ff, #e0f2fe)',
                            color: '#0f172a',
                            padding: '0.65rem 0.85rem',
                            fontWeight: 700,
                            fontSize: '0.8rem',
                            display: 'flex',
                            justifyContent: 'space-between',
                            alignItems: 'center',
                            borderBottom: '1px solid #bae6fd'
                        }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                                <span style={{ fontSize: '0.75rem' }}>▦</span>
                                <span>{table.name}</span>
                            </div>
                            <span style={{ opacity: 0.8, fontSize: '0.65rem', background: '#bae6fd', color: '#0369a1', padding: '2px 6px', borderRadius: '10px' }}>TABLE</span>
                        </div>
                        {/* Columns */}
                        <div style={{ padding: '0.3rem 0' }}>
                            {table.columns.map((col, ci) => (
                                <div key={col.name} style={{
                                    display: 'flex',
                                    justifyContent: 'space-between',
                                    alignItems: 'center',
                                    padding: '0.35rem 0.85rem',
                                    fontSize: '0.72rem',
                                    borderBottom: ci < table.columns.length - 1 ? '1px solid #f1f5f9' : 'none',
                                    background: col.pk ? '#fffbeb' : 'transparent'
                                }}>
                                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                                        {col.pk && <span style={{ background: '#f59e0b', color: '#fff', fontSize: '0.55rem', fontWeight: 900, padding: '1px 4px', borderRadius: '3px' }}>PK</span>}
                                        {col.fk && !col.pk && <span style={{ background: '#6366f1', color: '#fff', fontSize: '0.55rem', fontWeight: 900, padding: '1px 4px', borderRadius: '3px' }}>FK</span>}
                                        <span style={{ fontWeight: col.pk ? 700 : 500, color: col.pk ? '#b45309' : '#334155' }}>{col.name}</span>
                                    </div>
                                    <span style={{ color: '#64748b', fontSize: '0.65rem', fontFamily: 'monospace' }}>{col.type}</span>
                                </div>
                            ))}
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
}

/**
 * Solution Summary Dashboard - Shown when no file is selected
 */
function SolutionSummary({ files, result, analysisProgress, onViewSchema }) {
    const { state } = useWizard();
    const { reviewData } = state;

    const countFiles = (nodes) => {
        if (!Array.isArray(nodes)) return 0;
        let count = 0;
        nodes.forEach(node => {
            if (node.type === 'file') {
                count++;
            } else if (node.children) {
                count += countFiles(node.children);
            }
        });
        return count;
    };

    const treeCounts = {
        java: countFiles(files.backend),
        react: countFiles(files.frontend),
        sql: countFiles(files.database),
    };
    const generated = result?.generated || {};
    const estimated = getGeneratedCounts(analysisProgress);
    const counts = {
        java: estimated.backend || treeCounts.java || (generated.backend_files ?? generated.backendFiles ?? 0),
        react: estimated.frontend || treeCounts.react || (generated.frontend_files ?? generated.frontendFiles ?? 0),
        sql: treeCounts.sql || (generated.database_file || generated.databaseFile ? 1 : 0),
    };
    counts.total = counts.java + counts.react + counts.sql;

    // Compute coverage from reviewData if result doesn't supply it
    const allReviewObjects = Object.values(reviewData || {}).flat();
    const reviewTotal = allReviewObjects.length;
    const reviewSupported = allReviewObjects.filter(
        o => o.status === 'SUPPORTED' || o.status === 'SUPPORTED_WITH_REVIEW' || o.status === 'SUPPORTED_WITH_TRANSFORMATION'
    ).length;
    const computedCoverage = reviewTotal > 0 ? Math.round((reviewSupported / reviewTotal) * 100) : 0;
    const coverage = result?.coverage?.overall
        || result?.coverage_percentage
        || result?.coveragePercentage
        || (reviewTotal > 0 ? computedCoverage : (counts.total > 0 ? 100 : 0));
    const statistics = result?.statistics || result?.migration?.statistics || {
        tables: analysisProgress?.tables?.count || 0,
        queries: analysisProgress?.queries?.count || 0,
        forms: analysisProgress?.forms?.count || 0,
        reports: analysisProgress?.reports?.count || 0,
        macros: analysisProgress?.macros?.count || 0,
        vba_modules: analysisProgress?.vba?.count || 0,
    };
    const migratedObjects = Object.entries({
        Tables: statistics.tables,
        Queries: statistics.queries,
        Forms: statistics.forms,
        Reports: statistics.reports,
        Macros: statistics.macros,
        'Vba Modules': statistics.vba_modules,
    }).filter(([, value]) => typeof value === 'number');
    const totalObjects = migratedObjects.reduce((total, [, value]) => total + value, 0);
    const generatedFiles = estimated.total || result?.files_generated || result?.filesGenerated || generated.total_files || counts.total;
    const unitTests = result?.unit_tests_count ?? result?.unitTestsCount ?? 0;
    const dependencies = result?.dependency_count ?? result?.dependencyCount ?? statistics.dependencies ?? 0;
    const repairErrors = result?.repair_errors ?? result?.repairErrors ?? 0;
    const chartItems = migratedObjects.filter(([, value]) => value > 0);
    const chartMaximum = Math.max(...chartItems.map(([, value]) => value), 1);

    const circumference = 2 * Math.PI * 15.9155;
    const strokeDash = (coverage / 100) * circumference;

    return (
        <div style={{ padding: '2rem', background: '#fff', height: '100%', overflowY: 'auto' }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.25rem', height: '100%' }}>

                {/* ── LEFT: Solution Components ── */}
                <div style={{ background: '#f8fafc', borderRadius: '16px', border: '1px solid #e2e8f0', padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                    {/* {onViewSchema && (
                        <button
                            onClick={onViewSchema}
                            style={{
                                width: '100%', display: 'flex', alignItems: 'center', gap: '0.75rem',
                                padding: '0.75rem 1rem',
                                background: '#fff',
                                color: '#4338ca',
                                border: '1.5px solid #c7d2fe',
                                borderRadius: '10px', cursor: 'pointer', fontWeight: 700, fontSize: '0.82rem',
                                boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
                                transition: 'all 0.2s ease'
                            }}
                        >
                            <span style={{ fontSize: '1.1rem' }}>📊</span>
                            <span>ER Diagram</span>
                            <span style={{
                                marginLeft: 'auto', fontSize: '0.65rem', fontWeight: 700,
                                background: '#eef2ff',
                                color: '#4338ca',
                                padding: '2px 8px', borderRadius: '20px'
                            }}>DB Schema</span>
                        </button>
                    )} */}
                    <div style={{ fontSize: '0.7rem', fontWeight: 800, color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                        Solution Components
                    </div>

                    {/* Component rows */}
                    {[
                        { icon: '☕', label: 'Java (Spring Boot)', value: `${counts.java} files`, color: '#f59e0b', bg: '#fef3c7' },
                        { icon: '⚛️', label: 'React (Frontend)', value: `${counts.react} files`, color: '#3b82f6', bg: '#dbeafe' },
                        { icon: '🗄️', label: 'Database (SQL)', value: `${counts.sql} objects`, color: '#8b5cf6', bg: '#ede9fe' },
                    ].map(item => (
                        <div key={item.label} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0.75rem 1rem', background: '#fff', borderRadius: '10px', border: '1px solid #e2e8f0' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                                <div style={{ width: '34px', height: '34px', borderRadius: '8px', background: item.bg, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '1.1rem' }}>
                                    {item.icon}
                                </div>
                                <span style={{ fontWeight: 600, fontSize: '0.875rem', color: '#334155' }}>{item.label}</span>
                            </div>
                            <span style={{ fontSize: '0.8rem', fontWeight: 700, color: item.color, background: item.bg, padding: '2px 10px', borderRadius: '20px' }}>{item.value}</span>
                        </div>
                    ))}

                    {/* Divider row */}
                    <div style={{ borderTop: '1px solid #e2e8f0', paddingTop: '1rem', display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <span style={{ fontWeight: 700, fontSize: '0.875rem', color: '#1e293b' }}>Migrated Access objects</span>
                            <span style={{ background: '#dcfce7', color: '#15803d', padding: '2px 12px', borderRadius: '20px', fontSize: '0.8rem', fontWeight: 700 }}>{totalObjects || counts.total}</span>
                        </div>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <span style={{ fontSize: '0.8rem', color: '#64748b' }}>Generated project files</span>
                            <span style={{ fontSize: '0.85rem', fontWeight: 700, color: '#334155' }}>{generatedFiles}</span>
                        </div>
                    </div>

                    {/* Stats mini-grid */}
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '0.6rem' }}>
                        {[
                            { label: 'Unit tests', value: unitTests, color: '#4338ca', bg: '#eef2ff' },
                            { label: 'Dependencies', value: dependencies, color: '#0f766e', bg: '#ccfbf1' },
                            { label: 'Repair errors', value: repairErrors, color: '#be123c', bg: '#ffe4e6' },
                        ].map(({ label, value, color, bg }) => (
                            <div key={label} style={{ padding: '0.75rem 0.5rem', background: bg, borderRadius: '8px', textAlign: 'center' }}>
                                <div style={{ fontSize: '1.25rem', fontWeight: 800, color }}>{value}</div>
                                <div style={{ fontSize: '0.6rem', color: '#64748b', marginTop: '2px', fontWeight: 600 }}>{label}</div>
                            </div>
                        ))}
                    </div>
                </div>

                {/* ── RIGHT: Conversion Gauge ── */}
                <div style={{
                    background: 'linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 60%, #f8fafc 100%)',
                    borderRadius: '16px', padding: '2rem', color: '#1e293b',
                    display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center',
                    border: '1px solid #e2e8f0'
                }}>
                    {/* Radial gauge */}
                    <div style={{ position: 'relative', width: '120px', height: '120px', marginBottom: '1.25rem' }}>
                        <svg viewBox="0 0 36 36" style={{ width: '100%', height: '100%', transform: 'rotate(-90deg)' }}>
                            <circle cx="18" cy="18" r="15.9155" fill="none" stroke="#e2e8f0" strokeWidth="3.5" />
                            <circle cx="18" cy="18" r="15.9155" fill="none" stroke="#0ea5e9" strokeWidth="3.5"
                                strokeDasharray={`${strokeDash} ${circumference}`}
                                strokeLinecap="round"
                                style={{ transition: 'stroke-dasharray 1s ease' }}
                            />
                        </svg>
                        <div style={{ position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%, -50%)', textAlign: 'center' }}>
                            <div style={{ fontSize: '1.5rem', fontWeight: 900, lineHeight: 1, color: '#0f172a' }}>{Math.round(coverage)}%</div>
                        </div>
                    </div>

                    <h4 style={{ fontSize: '1rem', fontWeight: 700, margin: 0, color: '#0f172a' }}>Automated Conversion</h4>
                    <p style={{ fontSize: '0.75rem', color: '#64748b', marginTop: '0.3rem', marginBottom: 0 }}>Successfully translated Access objects</p>

                    {/* Migration breakdown bars */}
                    {chartItems.length > 0 && (
                        <div style={{ width: '100%', marginTop: '1.5rem', textAlign: 'left', background: '#fff', borderRadius: '10px', padding: '1rem', border: '1px solid #e2e8f0' }}>
                            <div style={{ fontSize: '0.65rem', fontWeight: 800, color: '#64748b', marginBottom: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                                Migration breakdown
                            </div>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.55rem' }}>
                                {chartItems.map(([category, value]) => (
                                    <div key={category} style={{ display: 'grid', gridTemplateColumns: '80px 1fr 28px', alignItems: 'center', gap: '0.6rem', fontSize: '0.7rem' }}>
                                        <span style={{ fontWeight: 500, color: '#334155' }}>{category}</span>
                                        <div style={{ height: '5px', background: '#e2e8f0', borderRadius: '3px', overflow: 'hidden' }}>
                                            <div style={{
                                                width: `${(value / chartMaximum) * 100}%`, height: '100%',
                                                background: '#0ea5e9', borderRadius: '3px',
                                                transition: 'width 0.8s ease'
                                            }} />
                                        </div>
                                        <span style={{ textAlign: 'right', fontWeight: 700, color: '#0f172a' }}>{value}</span>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}

/**
 * File Explorer Component for generated project
 */
function FileExplorer({ jobId, generationComplete }) {
    const { state } = useWizard();
    const { generationResult, analysisProgress } = state;
    const [files, setFiles] = useState({});
        const [expanded, setExpanded] = useState({ frontend: true, backend: true, database: false });
    const [selectedFile, setSelectedFile] = useState(null);
    const [fileContent, setFileContent] = useState(null);
    const [schemaData, setSchemaData] = useState(null);
    const [loadingFiles, setLoadingFiles] = useState(false);
    const [loadingContent, setLoadingContent] = useState(false);
    const [loadingSchema, setLoadingSchema] = useState(false);
    const [viewMode, setViewMode] = useState('welcome'); // welcome, code, schema

    useEffect(() => {
        if (!jobId) return undefined;

        let cancelled = false;
        let retryTimer;

        const loadUntilAvailable = async () => {
            setLoadingFiles(true);
            try {
                const data = await listJobFiles(jobId);
                if (cancelled) return;
                setFiles(data);
                if (!generationComplete) {
                    retryTimer = window.setTimeout(loadUntilAvailable, 1000);
                }
            } catch (err) {
                if (!cancelled) {
                    console.error('Failed to load files:', err);
                    if (!generationComplete) {
                        retryTimer = window.setTimeout(loadUntilAvailable, 1000);
                    }
                }
            } finally {
                if (!cancelled) setLoadingFiles(false);
            }
        };

        loadUntilAvailable();
        return () => {
            cancelled = true;
            window.clearTimeout(retryTimer);
        };
    }, [jobId, generationComplete]);

    const loadFiles = async () => {
        setLoadingFiles(true);
        try {
            const data = await listJobFiles(jobId);
            setFiles(data);
        } catch (err) {
            console.error('Failed to load files:', err);
        } finally {
            setLoadingFiles(false);
        }
    };

    const loadSchema = async () => {
        if (schemaData) return;
        setLoadingSchema(true);
        try {
            const data = await getJobDbSchema(jobId);
            setSchemaData(data);
        } catch (err) {
            console.error('Failed to load DB schema:', err);
        } finally {
            setLoadingSchema(false);
        }
    };

    const handleFileClick = async (file) => {
        setSelectedFile(file);
        setViewMode('code');
        setLoadingContent(true);
        try {
            const data = await getFileContent(jobId, file.path);
            setFileContent(data.content);
        } catch (err) {
            console.error('Failed to load file content:', err);
            setFileContent('// Error loading file content.');
        } finally {
            setLoadingContent(false);
        }
    };

    const toggleExpand = (cat) => {
        setExpanded(prev => ({ ...prev, [cat]: !prev[cat] }));
    };

    const renderTree = (nodes, level = 0) => {
        return nodes.map(node => (
            <div key={node.path} style={{ marginLeft: `${level * 16 + 12}px` }}>
                {node.type === 'directory' ? (
                    <div>
                        <div style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: '0.4rem',
                            padding: '0.3rem 0',
                            fontSize: '0.85rem',
                            color: '#475569'
                        }}>
                            <span style={{ fontSize: '0.9rem' }}>📁</span>
                            <span style={{ fontWeight: 600, whiteSpace: 'nowrap' }}>{node.name}</span>
                        </div>
                        {renderTree(node.children, level + 1)}
                    </div>
                ) : (
                    <div
                        onClick={() => handleFileClick(node)}
                        style={{
                            cursor: 'pointer',
                            padding: '0.35rem 0.75rem',
                            fontSize: '0.8125rem',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '0.5rem',
                            background: selectedFile?.path === node.path ? '#eef2ff' : 'transparent',
                            color: selectedFile?.path === node.path ? '#4338ca' : '#64748b',
                            borderRadius: '6px',
                            borderLeft: selectedFile?.path === node.path ? '3px solid #4338ca' : '3px solid transparent',
                            marginBottom: '2px',
                            transition: 'all 0.15s ease',
                            whiteSpace: 'nowrap'
                        }}
                    >
                        <span style={{ opacity: 0.8, fontSize: '0.9rem' }}>📄</span>
                        {node.name}
                    </div>
                )}
            </div>
        ));
    };

    return (
        <div style={{
            display: 'grid',
                    gridTemplateColumns: 'minmax(280px, 320px) minmax(0, 1fr)',
            gap: '0',
            marginTop: '1.5rem',
            height: '650px',
            border: '1px solid var(--color-border)',
            borderRadius: '16px',
            overflow: 'hidden',
            background: '#fff',
            boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.05)',
        }}>
            {/* Sidebar */}
            <div style={{
                borderRight: '1px solid var(--color-border)',
                overflowY: 'auto',
                overflowX: 'auto',
                padding: '1.5rem',
                background: '#f8fafc',
                height: '100%'
            }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.85rem' }}>
                    <h3 style={{ fontSize: '0.85rem', fontWeight: 800, margin: 0, color: '#1e293b', letterSpacing: '0.05em', textTransform: 'uppercase' }}>
                        Solution Explorer
                    </h3>
                    <button
                        onClick={loadFiles}
                        style={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: '6px', cursor: 'pointer', padding: '4px 8px', boxShadow: '0 1px 2px rgba(0,0,0,0.05)' }}
                        title="Refresh"
                    >🔄</button>
                </div>

                {/* Sidebar ER Diagram Button */}
                <button
                    type="button"
                    onClick={() => {
                        if (viewMode === 'schema') {
                            setViewMode('welcome');
                        } else {
                            setViewMode('schema');
                            loadSchema();
                            setSelectedFile(null);
                        }
                    }}
                    style={{
                        width: '100%',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '0.75rem',
                        padding: '0.75rem 1rem',
                        marginBottom: '1rem',
                        background: viewMode === 'schema'
                            ? 'linear-gradient(135deg, #4f46e5, #6366f1)'
                            : '#fff',
                        color: viewMode === 'schema' ? '#fff' : '#4338ca',
                        border: viewMode === 'schema' ? '1.5px solid #4338ca' : '1.5px solid #c7d2fe',
                        borderRadius: '10px',
                        cursor: 'pointer',
                        fontWeight: 700,
                        fontSize: '0.82rem',
                        boxShadow: viewMode === 'schema'
                            ? '0 4px 12px rgba(79, 70, 229, 0.25)'
                            : '0 1px 3px rgba(0,0,0,0.06)',
                        transition: 'all 0.2s ease',
                    }}
                    onMouseEnter={(e) => {
                        if (viewMode !== 'schema') {
                            e.currentTarget.style.borderColor = '#818cf8';
                            e.currentTarget.style.background = '#f5f3ff';
                        }
                    }}
                    onMouseLeave={(e) => {
                        if (viewMode !== 'schema') {
                            e.currentTarget.style.borderColor = '#c7d2fe';
                            e.currentTarget.style.background = '#fff';
                        }
                    }}
                >
                    <span style={{ fontSize: '1.1rem' }}>📊</span>
                    <span style={{ flex: 1, textAlign: 'left' }}>ER Diagram</span>
                    <span style={{
                        marginLeft: 'auto',
                        fontSize: '0.65rem',
                        fontWeight: 700,
                        background: viewMode === 'schema' ? 'rgba(255,255,255,0.25)' : '#eef2ff',
                        color: viewMode === 'schema' ? '#fff' : '#4338ca',
                        padding: '2px 8px',
                        borderRadius: '20px'
                    }}>
                        {viewMode === 'schema' ? 'Active' : 'DB Schema'}
                    </span>
                </button>



                {loadingFiles ? (
                    <div style={{ textAlign: 'center', padding: '3rem 0', color: '#64748b' }}>
                        <div className="spinner" style={{ width: '20px', height: '20px', margin: '0 auto 1rem' }} />
                        <span style={{ fontSize: '0.8rem', fontWeight: 500 }}>Indexing solution...</span>
                    </div>
                ) : (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                        {['frontend', 'backend', 'database'].map(cat => (
                            <div key={cat} style={{ marginBottom: '0.25rem' }}>
                                <div
                                    onClick={() => toggleExpand(cat)}
                                    style={{
                                        cursor: 'pointer',
                                        fontWeight: 700,
                                        display: 'flex',
                                        alignItems: 'center',
                                        gap: '0.75rem',
                                        background: expanded[cat] ? '#fff' : '#f1f5f9',
                                        padding: '0.75rem 1rem',
                                        borderRadius: '10px',
                                        fontSize: '0.9rem',
                                        border: expanded[cat] ? '1px solid #4338ca' : '1px solid transparent',
                                        color: expanded[cat] ? '#4338ca' : '#475569',
                                        textTransform: 'capitalize',
                                        transition: 'all 0.2s ease',
                                        boxShadow: expanded[cat] ? '0 4px 6px -1px rgba(67, 56, 202, 0.1)' : 'none',
                                        position: 'relative'
                                    }}
                                >
                                    <span style={{
                                        fontSize: '0.6rem',
                                        width: '14px',
                                        transition: 'transform 0.2s',
                                        transform: expanded[cat] ? 'rotate(90deg)' : 'rotate(0)',
                                        color: expanded[cat] ? '#4338ca' : '#94a3b8'
                                    }}>▶</span>
                                    <span style={{ fontSize: '1.2rem' }}>{cat === 'frontend' ? '⚛️' : cat === 'backend' ? '☕' : '🗄️'}</span>
                                    <span style={{ flex: 1 }}>{cat}</span>

                                </div>
                                {expanded[cat] && (
                                    <div style={{ marginTop: '0.75rem', animation: 'slideDown 0.3s ease-out' }}>
                                        {files[cat] ? renderTree(files[cat]) : (
                                            <div style={{ fontSize: '0.75rem', padding: '0.5rem 2rem', color: '#94a3b8', fontStyle: 'italic' }}>Empty directory.</div>
                                        )}
                                    </div>
                                )}
                            </div>
                        ))}
                    </div>
                )}
            </div>

            {/* Content Area */}
            <div style={{ overflowY: 'auto', background: viewMode === 'code' ? '#1e293b' : '#fff', position: 'relative', height: '100%' }}>
                {viewMode === 'welcome' && (
                    <SolutionSummary files={files} result={generationResult} analysisProgress={analysisProgress} onViewSchema={() => { setViewMode('schema'); loadSchema(); setSelectedFile(null); }} />
                )}

                {viewMode === 'code' && selectedFile && (
                    <>
                        <div style={{
                            background: '#0f172a',
                            padding: '1rem 2rem',
                            borderBottom: '1px solid #334155',
                            display: 'flex',
                            justifyContent: 'space-between',
                            alignItems: 'center',
                            position: 'sticky',
                            top: 0,
                            zIndex: 10
                        }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                                <span style={{ color: '#94a3b8', fontSize: '0.7rem', textTransform: 'uppercase', fontWeight: 800, letterSpacing: '0.05em' }}>Path:</span>
                                <code style={{ color: '#38bdf8', fontSize: '0.875rem', fontWeight: 600 }}>{selectedFile.path}</code>
                            </div>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                                <span style={{ fontSize: '0.75rem', color: '#64748b', background: '#1e293b', padding: '4px 10px', borderRadius: '6px', border: '1px solid #334155' }}>
                                    {(selectedFile.size / 1024).toFixed(1)} KB
                                </span>
                                <button
                                    onClick={() => setViewMode('welcome')}
                                    style={{ background: 'none', border: 'none', color: '#94a3b8', cursor: 'pointer', fontSize: '1rem' }}
                                >✕</button>
                            </div>
                        </div>

                        {loadingContent ? (
                            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '80%', color: '#94a3b8' }}>
                                <div className="spinner" style={{ marginBottom: '1rem' }} />
                                <span>Reading file content...</span>
                            </div>
                        ) : (
                            <div style={{ padding: '2rem' }}>
                                <pre style={{
                                    margin: 0,
                                    fontSize: '0.875rem',
                                    lineHeight: 1.7,
                                    color: '#f8fafc',
                                    whiteSpace: 'pre-wrap',
                                    fontFamily: '"Fira Code", "JetBrains Mono", monospace',
                                    tabSize: 4
                                }}>
                                    {fileContent}
                                </pre>
                            </div>
                        )}
                    </>
                )}

                {viewMode === 'schema' && (
                    <div style={{ height: '100%', position: 'relative' }}>
                        <button
                            onClick={() => setViewMode('welcome')}
                            style={{ position: 'absolute', top: '1.5rem', right: '1.5rem', zIndex: 100, background: '#fff', border: '1px solid #e2e8f0', borderRadius: '50%', width: '32px', height: '32px', display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer', boxShadow: '0 2px 4px rgba(0,0,0,0.05)' }}
                        >✕</button>
                        {loadingSchema ? (
                            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', color: '#64748b' }}>
                                <div className="spinner" style={{ marginBottom: '1rem' }} />
                                <span>Building Schema Model...</span>
                            </div>
                        ) : (
                            <ERDiagram schema={schemaData} />
                        )}
                    </div>
                )}
            </div>


            <style>{`
                @keyframes slideDown {
                    from { opacity: 0; transform: translateY(-10px); }
                    to { opacity: 1; transform: translateY(0); }
                }
            `}</style>
        </div>
    );
}

export default function Step5Generate() {
    const { state, actions } = useWizard();
    const { selectedFile, localSource, config, analysisJobId, generationJobId, generationProgress, generationComplete, generationResult } = state;
    const [isGenerating, setIsGenerating] = useState(false);
    const [activeTab, setActiveTab] = useState('review');
    const wsRef = useRef(null);
    const startedRef = useRef(false);

    // Generation Complete Toast state
    const [showToast, setShowToast] = useState(false);
    const [isToastClosing, setIsToastClosing] = useState(false);
    const toastTimerRef = useRef(null);
    const closeTimerRef = useRef(null);
    const prevCompleteRef = useRef(false);

    const dismissToast = useCallback(() => {
        if (toastTimerRef.current) {
            clearTimeout(toastTimerRef.current);
            toastTimerRef.current = null;
        }
        setIsToastClosing(true);
        if (closeTimerRef.current) {
            clearTimeout(closeTimerRef.current);
        }
        closeTimerRef.current = setTimeout(() => {
            setShowToast(false);
            setIsToastClosing(false);
        }, 400);
    }, []);

    useEffect(() => {
        if (generationComplete && generationResult) {
            if (!prevCompleteRef.current) {
                prevCompleteRef.current = true;
                setShowToast(true);
                setIsToastClosing(false);

                if (toastTimerRef.current) clearTimeout(toastTimerRef.current);
                toastTimerRef.current = setTimeout(() => {
                    dismissToast();
                }, 5000);
            }
        } else {
            prevCompleteRef.current = false;
            setShowToast(false);
            setIsToastClosing(false);
            if (toastTimerRef.current) clearTimeout(toastTimerRef.current);
            if (closeTimerRef.current) clearTimeout(closeTimerRef.current);
        }

        return () => {
            if (toastTimerRef.current) clearTimeout(toastTimerRef.current);
            if (closeTimerRef.current) clearTimeout(closeTimerRef.current);
        };
    }, [generationComplete, Boolean(generationResult), dismissToast]);

    // Start generation when entering step
    const startGeneration = useCallback(async () => {
        if ((!selectedFile && !localSource) || !analysisJobId) return;

        setIsGenerating(true);
        actions.setError(null);

        try {
            // The analysis step already created a job and ran the full pipeline
            // (extract → IR → graph → supportability → generate).
            // The generation happens as part of the same pipeline.
            // We just need to connect to the existing job's WebSocket to
            // track its progress through the generation phases.
            //
            // However, if the pipeline already completed during analysis,
            // we should check the job state first.
            let jobId = analysisJobId;

            try {
                const existingJob = await getJob(analysisJobId);
                if (existingJob && existingJob.state === JOB_STATES.COMPLETED) {
                    // Job already completed during analysis - show results directly
                    actions.setGenerationJob(analysisJobId);
                    actions.updateGenerationProgress({
                        currentStep: 'completed',
                        completedSteps: [...STEP_ORDER],
                        percentage: 100,
                    });
                    actions.setGenerationComplete(true);
                    actions.setGenerationResult(existingJob.result || existingJob);
                    setIsGenerating(false);
                    return;
                }
                if (existingJob && existingJob.state === JOB_STATES.FAILED) {
                    actions.setError(existingJob.error?.message || 'Previous job failed');
                    setIsGenerating(false);
                    return;
                }
            } catch (err) {
                // If we can't fetch the existing job, fall through to create a new one
                console.warn('Could not fetch existing job, creating new one:', err);
            }

            // If the analysis job is still running or in a pre-generation state,
            // connect to its WebSocket. If we need a fresh generation, create a new job.
            const needsNewJob = !jobId;
            if (needsNewJob) {
                const job = await createJob(selectedFile, config);
                jobId = job.id;
            }

            actions.setGenerationJob(jobId);

            // Connect WebSocket for real-time progress
            const websocket = connectProgressWebSocket(jobId, (message) => {
                handleWebSocketMessage(message);
            });
            wsRef.current = websocket;

        } catch (err) {
            actions.setError(err.message);
            setIsGenerating(false);
            startedRef.current = false;
        }
    }, [selectedFile, localSource, config, analysisJobId, actions]);

    // Handle WebSocket messages
    // Using a ref-based approach to avoid stale closure issues
    const handleWebSocketMessage = useCallback((message) => {
        const { state: jobState, step, progress, result, error, statistics } = message;

        // Determine the current frontend step key from the backend message.
        // The backend sends step names via broadcast (e.g., "generating_database")
        // and job states via polling (e.g., "GENERATING_DATABASE").
        // The progress object may also contain current_step.
        const backendStep = step
            || (typeof progress === 'object' && progress?.current_step)
            || null;
        const backendState = jobState || null;

        // Map to frontend step key
        let frontendStepKey = null;
        if (backendStep && BACKEND_STEP_MAP[backendStep]) {
            frontendStepKey = BACKEND_STEP_MAP[backendStep];
        } else if (backendState && BACKEND_STEP_MAP[backendState]) {
            frontendStepKey = BACKEND_STEP_MAP[backendState];
        }

        // Determine completed steps based on the current backend state
        const completedSteps = backendState
            ? getCompletedFrontendSteps(backendState)
            : [];

        // Use backend percentage if available, otherwise calculate from steps
        const backendPercentage = (typeof progress === 'object' && progress?.percentage)
            || (typeof message.percentage === 'number' ? message.percentage : null);

        // Map backend overall percentage (0-100) to generation phase (60-100 range)
        // The generation steps start at ~60% in the backend pipeline
        let displayPercentage = 0;
        if (backendPercentage !== null) {
            if (backendPercentage >= 60) {
                // Map 60-100 backend range to 0-100 for generation display
                displayPercentage = Math.min(((backendPercentage - 60) / 40) * 100, 100);
            }
        } else if (completedSteps.length > 0) {
            displayPercentage = (completedSteps.length / STEP_ORDER.length) * 100;
        }

        // Build the progress update
        const progressUpdate = {};

        if (frontendStepKey) {
            progressUpdate.currentStep = frontendStepKey;
        }

        if (completedSteps.length > 0) {
            progressUpdate.completedSteps = completedSteps;
        }

        progressUpdate.percentage = displayPercentage;

        // Apply progress update
        if (Object.keys(progressUpdate).length > 0) {
            actions.updateGenerationProgress(progressUpdate);
        }

        // Add detail message if provided
        const detailMessage = message.message
            || (typeof progress === 'object' && progress?.message)
            || null;

        if (detailMessage && frontendStepKey) {
            actions.addGenerationDetail({
                step: frontendStepKey,
                timestamp: new Date().toISOString(),
                message: detailMessage,
            });
        }

        // Handle completion
        if (backendState === JOB_STATES.COMPLETED) {
            actions.updateGenerationProgress({
                currentStep: 'completed',
                completedSteps: [...STEP_ORDER],
                percentage: 100,
            });
            actions.setGenerationComplete(true);
            actions.setGenerationResult(result || { jobId: generationJobId || analysisJobId });
            setIsGenerating(false);
            if (wsRef.current) {
                wsRef.current.close();
                wsRef.current = null;
            }
        }

        // Handle failure
        if (backendState === JOB_STATES.FAILED) {
            actions.setError(error || 'Generation failed');
            actions.setGenerationComplete(false);
            if (frontendStepKey) {
                actions.updateGenerationProgress({
                    failedSteps: [frontendStepKey],
                });
            }
            setIsGenerating(false);
            if (wsRef.current) {
                wsRef.current.close();
                wsRef.current = null;
            }
        }
    }, [actions, generationJobId, analysisJobId]);

    // Cleanup WebSocket on unmount
    useEffect(() => {
        return () => {
            if (wsRef.current) {
                wsRef.current.close();
                wsRef.current = null;
            }
        };
    }, []);

    // Auto-start generation (with guard against StrictMode double-mount)
    useEffect(() => {
        if ((selectedFile || localSource) && analysisJobId && !generationJobId && !isGenerating && !startedRef.current) {
            startedRef.current = true;
            startGeneration();
        }
    }, [selectedFile, localSource, analysisJobId, generationJobId, isGenerating, startGeneration]);

    const completedCount = generationProgress.completedSteps?.length || 0;
    const totalSteps = GENERATION_STEPS.length;
    const overallProgress = generationProgress.percentage || (completedCount / totalSteps) * 100;

    return (
        <div>
            <div className="card-header" style={{ marginBottom: '0' }}>
                <p className="card-subtitle">
                    {activeTab === 'review' 
                        ? 'Review your Access database objects and how they map to the new architecture.' 
                        : 'Track generation progress and explore your modernized solution files.'}
                </p>
            </div>

            {/* ── Toggle Tab Bar ── */}
            <div style={{
                display: 'flex',
                gap: '0',
                marginBottom: '1.5rem',
                background: '#f1f5f9',
                borderRadius: '12px',
                padding: '4px',
                border: '1px solid #e2e8f0',
            }}>
                {[
                    { key: 'review', label: 'Map & Review Objects', icon: '📋' },
                    { key: 'explorer', label: 'Solution Explorer', icon: '🏗️' },
                ].map(tab => (
                    <button
                        key={tab.key}
                        onClick={() => setActiveTab(tab.key)}
                        style={{
                            flex: 1,
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            gap: '0.5rem',
                            padding: '0.7rem 1.25rem',
                            border: 'none',
                            borderRadius: '10px',
                            cursor: 'pointer',
                            fontWeight: 700,
                            fontSize: '0.875rem',
                            transition: 'all 0.2s ease',
                            background: activeTab === tab.key
                                ? 'linear-gradient(135deg, #4f46e5, #6366f1)'
                                : 'transparent',
                            color: activeTab === tab.key ? '#fff' : '#64748b',
                            boxShadow: activeTab === tab.key
                                ? '0 4px 12px rgba(79, 70, 229, 0.3)'
                                : 'none',
                        }}
                    >
                        <span style={{ fontSize: '1rem' }}>{tab.icon}</span>
                        <span>{tab.label}</span>
                        {tab.key === 'explorer' && !generationComplete && (
                            <span style={{
                                width: '8px', height: '8px', borderRadius: '50%',
                                background: '#f59e0b',
                                animation: 'pulse 1.5s ease-in-out infinite',
                                marginLeft: '0.25rem',
                            }} />
                        )}
                        {tab.key === 'explorer' && generationComplete && (
                            <span style={{
                                width: '8px', height: '8px', borderRadius: '50%',
                                background: '#10b981',
                                marginLeft: '0.25rem',
                            }} />
                        )}
                    </button>
                ))}
            </div>

            <style>{`
                @keyframes pulse {
                    0%, 100% { opacity: 1; }
                    50% { opacity: 0.4; }
                }
            `}</style>

            {/* ── Tab Content ── */}
            {activeTab === 'review' && (
                <Step4Review />
            )}

            {activeTab === 'explorer' && (
                <div>
                   

                    {/* Solution Explorer */}
                    {(generationJobId || analysisJobId) && (
                        <FileExplorer jobId={generationJobId || analysisJobId} generationComplete={generationComplete} />
                    )}

                    {!generationComplete && (
                        <div className="alert alert-info" style={{ marginTop: '1.5rem' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                                <div className="spinner" style={{ width: '20px', height: '20px', borderWidth: '2px' }} />
                                <span>
                                    {isGenerating ? 'Generating project...' : 'Starting generation...'}
                                </span>
                            </div>
                        </div>
                    )}

                    {generationComplete && generationResult && (
                        <div style={{ marginTop: '1.5rem', display: 'flex', gap: '0.75rem' }}>
                            <button
                                className="btn btn-primary"
                                onClick={() => downloadResult(generationJobId, config.project_name)}
                            >
                                Download Project ZIP
                            </button>
                            <button
                                className="btn btn-secondary"
                                onClick={() => {
                                    actions.setStep(5);
                                }}
                            >
                                View Summary →
                            </button>
                        </div>
                    )}
                </div>
            )}

            {/* Generation Complete Toast Notification */}
            {showToast && generationResult && (
                <>
                    <style>
                        {`
                        @keyframes toastSlideIn {
                            0% { transform: translateY(-16px) scale(0.96); opacity: 0; }
                            100% { transform: translateY(0) scale(1); opacity: 1; }
                        }
                        @keyframes toastSlideOut {
                            0% { transform: translateY(0) scale(1); opacity: 1; }
                            100% { transform: translateY(-16px) scale(0.96); opacity: 0; }
                        }
                        @keyframes toastProgress {
                            0% { width: 100%; }
                            100% { width: 0%; }
                        }
                        `}
                    </style>
                    <div style={{
                        position: 'fixed',
                        top: '2rem',
                        right: '2rem',
                        zIndex: 9999,
                        width: '450px',
                        padding: '1.25rem 1.5rem',
                        background: '#fff',
                        borderRadius: '12px',
                        boxShadow: '0 20px 25px -5px rgba(34, 197, 94, 0.25), 0 10px 10px -5px rgba(34, 197, 94, 0.1)',
                        border: '1px solid #bbf7d0',
                        borderLeft: '4px solid #22c55e',
                        display: 'flex',
                        alignItems: 'flex-start',
                        gap: '1.25rem',
                        animation: isToastClosing
                            ? 'toastSlideOut 0.4s cubic-bezier(0.16, 1, 0.3, 1) forwards'
                            : 'toastSlideIn 0.5s cubic-bezier(0.16, 1, 0.3, 1)',
                        overflow: 'hidden'
                    }}>
                        {/* Close button (cross mark) */}
                        <button
                            type="button"
                            onClick={dismissToast}
                            aria-label="Close notification"
                            title="Close"
                            style={{
                                position: 'absolute',
                                top: '0.75rem',
                                right: '0.75rem',
                                background: 'transparent',
                                border: 'none',
                                borderRadius: '6px',
                                width: '26px',
                                height: '26px',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                cursor: 'pointer',
                                color: '#6b7280',
                                fontSize: '0.95rem',
                                lineHeight: 1,
                                padding: 0,
                                transition: 'all 0.15s ease',
                                zIndex: 2,
                            }}
                            onMouseEnter={(e) => {
                                e.currentTarget.style.color = '#1f2937';
                                e.currentTarget.style.backgroundColor = 'rgba(0, 0, 0, 0.06)';
                            }}
                            onMouseLeave={(e) => {
                                e.currentTarget.style.color = '#6b7280';
                                e.currentTarget.style.backgroundColor = 'transparent';
                            }}
                        >
                            ✕
                        </button>
                        <div style={{ position: 'absolute', top: 0, right: 0, width: '150px', height: '100%', background: 'linear-gradient(90deg, transparent, rgba(220, 252, 231, 0.5))', pointerEvents: 'none' }} />
                        <div style={{ 
                            background: '#dcfce7', color: '#16a34a', width: '38px', height: '38px', 
                            borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', 
                            fontSize: '1.1rem', flexShrink: 0, boxShadow: '0 0 0 4px rgba(220, 252, 231, 0.5)'
                        }}>
                            ✔️
                        </div>
                        <div style={{ flex: 1, paddingRight: '1rem' }}>
                            <h4 style={{ margin: '0 0 0.35rem 0', color: '#166534', fontSize: '1.05rem', fontWeight: 800 }}>Generation Complete!</h4>
                            <div style={{ color: '#15803d', fontSize: '0.85rem', marginBottom: '0.35rem', lineHeight: 1.5 }}>
                                The project was successfully generated and saved to: <br/>
                                <span style={{ background: '#f0fdf4', border: '1px solid #bbf7d0', padding: '2px 8px', borderRadius: '4px', fontFamily: 'monospace', fontWeight: 600, color: '#16a34a', display: 'inline-block', marginTop: '0.35rem', wordBreak: 'break-all' }}>
                                    {generationResult.outputPath || generationResult.output_path || 'outputs/job-id'}
                                </span>
                            </div>
                            {generationResult.filesGenerated && (
                                <div style={{ fontSize: '0.8rem', color: '#16a34a', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '0.35rem', marginTop: '0.5rem' }}>
                                    <span>📄</span> {formatNumber(generationResult.filesGenerated)} files generated and ready
                                </div>
                            )}
                        </div>
                        {/* Auto-dismiss countdown bar */}
                        <div style={{
                            position: 'absolute',
                            bottom: 0,
                            left: 0,
                            height: '3px',
                            background: '#22c55e',
                            animation: 'toastProgress 5s linear forwards',
                        }} />
                    </div>
                </>
            )}
        </div>
    );
}