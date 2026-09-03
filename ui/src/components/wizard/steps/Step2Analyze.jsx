import React, { useEffect, useCallback } from 'react';
import { useWizard } from '../../../context/WizardContext';
import { createJob, createLocalJob, connectProgressWebSocket, getVersions, getJob, generateBrdReport, getBrdPreviewUrl, getBrdDownloadUrl } from '../../../services/api';
import { JOB_STATES } from '../../../utils/constants';
import { formatNumber } from '../../../utils/helpers';

/**
 * Analysis items per spec section 47 Step 2:
 * - table scan, query scan, form scan, report scan, VBA scan, macro scan, dependency scan
 */
const ANALYSIS_ITEMS = [
    { key: 'tables', label: 'Table Scan', icon: '🗃️', description: 'Extracting tables, columns, indexes, relationships' },
    { key: 'queries', label: 'Query Scan', icon: '🔍', description: 'Analyzing SELECT, INSERT, UPDATE, DELETE, parameter, crosstab queries' },
    { key: 'forms', label: 'Form Scan', icon: '📋', description: 'Extracting forms, controls, events, subforms, validation rules' },
    { key: 'reports', label: 'Report Scan', icon: '📊', description: 'Analyzing reports, sections, grouping, sorting, subreports' },
    { key: 'vba', label: 'VBA Scan', icon: '💻', description: 'Parsing modules, functions, subs, event procedures, business rules' },
    { key: 'macros', label: 'Macro Scan', icon: '⚡', description: 'Extracting macro actions, conditions, nested structures' },
    { key: 'dependencies', label: 'Dependency Scan', icon: '🔗', description: 'Discovering linked tables, external databases, COM references' },
];

const STATUS_ICONS = {
    pending: '⏳',
    in_progress: '🔄',
    completed: '✅',
    error: '❌',
};

export default function Step2Analyze() {
    const { state, actions } = useWizard();
    const { selectedFile, localSource, analysisJobId, analysisProgress, analysisComplete, analysisResult, config } = state;
    const [isAnalyzing, setIsAnalyzing] = React.useState(false);
    const [ws, setWs] = React.useState(null);
    // Guards against duplicate job creation. In dev, React.StrictMode
    // mounts -> cleans up -> re-mounts every component once, which fires
    // this effect twice in quick succession. Without this guard that sent
    // two near-simultaneous POST /api/jobs for the same file, and the
    // second write could hit SQLite's "database is locked" error and fail
    // outright - leaving the wizard stuck at 0% with no visible job.
    const startedRef = React.useRef(false);

    // BRD Report state
    const [brdLoading, setBrdLoading] = React.useState(false);
    const [brdGenerated, setBrdGenerated] = React.useState(false);
    const [brdError, setBrdError] = React.useState(null);

    const handleGenerateBrd = async () => {
        if (!analysisJobId) {
            setBrdError('Please upload or select a project before generating the BRD.');
            return;
        }

        setBrdLoading(true);
        setBrdError(null);

        try {
            await generateBrdReport(analysisJobId);
            setBrdGenerated(true);
        } catch (err) {
            console.error('BRD generation error:', err);
            setBrdError(err.message || 'Unable to generate the BRD. Please try again.');
        } finally {
            setBrdLoading(false);
        }
    };

    const handleViewBrd = () => {
        if (!analysisJobId) return;
        const previewUrl = getBrdPreviewUrl(analysisJobId);
        window.open(previewUrl, '_blank');
    };

    const handleDownloadBrd = () => {
        if (!analysisJobId) return;
        const downloadUrl = getBrdDownloadUrl(analysisJobId);
        const link = document.createElement('a');
        link.href = downloadUrl;
        link.setAttribute('download', 'BRD.html');
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    };

    // Fetch available versions on mount
    useEffect(() => {
        const fetchVersions = async () => {
            try {
                const versions = await getVersions();
                actions.setVersions(versions);
            } catch (err) {
                console.warn('Could not fetch versions:', err);
            }
        };
        fetchVersions();
    }, [actions]);

    // Start analysis when entering step
    const startAnalysis = useCallback(async () => {
        if (!selectedFile && !localSource) return;

        setIsAnalyzing(true);
        actions.setError(null);

        try {
            // Both input modes produce the same JobResponse; everything after
            // this point (WebSocket, progress, completion) is identical.
            const job = localSource
                ? await createLocalJob(localSource.path, config)
                : await createJob(selectedFile, config);
            const jobId = job.id;
            actions.setAnalysisJob(jobId);

            // Connect WebSocket for real-time progress
            const websocket = connectProgressWebSocket(jobId, (message) => {
                handleWebSocketMessage(message, jobId);
            });
            setWs(websocket);

        } catch (err) {
            actions.setError(err.message);
            setIsAnalyzing(false);
            startedRef.current = false; // allow retry after a genuine failure
        }
    }, [selectedFile, localSource, config, actions]);

    // Handle WebSocket messages
    const handleWebSocketMessage = useCallback((message, activeJobId) => {
        const { state: jobState, step, progress, result, error, statistics } = message;

        // Update analysis progress based on step
        if (step) {
            const progressMap = {
                extracting: 'tables',
                building_ir: 'queries',
                building_graph: 'dependencies',
                analyzing_supportability: 'vba',
            };

            const key = progressMap[step];
            if (key && analysisProgress[key]) {
                actions.updateAnalysisProgress({
                    [key]: { ...analysisProgress[key], status: 'in_progress' },
                });
            }
        }

        // Update counts from statistics or progress
        const stats = statistics || (typeof progress === 'object' ? progress : null);
        if (stats) {
            actions.updateAnalysisProgress({
                tables: { count: stats.tables ?? 0, status: stats.tables !== undefined ? 'completed' : 'in_progress' },
                queries: { count: stats.queries ?? 0, status: stats.queries !== undefined ? 'completed' : 'in_progress' },
                forms: { count: stats.forms ?? 0, status: stats.forms !== undefined ? 'completed' : 'in_progress' },
                reports: { count: stats.reports ?? 0, status: stats.reports !== undefined ? 'completed' : 'in_progress' },
                macros: { count: stats.macros ?? 0, status: stats.macros !== undefined ? 'completed' : 'in_progress' },
                vba: { count: stats.vba_modules ?? 0, status: stats.vba_modules !== undefined ? 'completed' : 'in_progress' },
                dependencies: { count: stats.dependencies ?? 0, status: stats.dependencies !== undefined ? 'completed' : 'in_progress' },
            });
        }

        // Handle completion
        const targetId = activeJobId || analysisJobId;
        if (jobState === JOB_STATES.SUPPORTABILITY_ANALYZED || jobState === JOB_STATES.COMPLETED) {
            actions.setAnalysisComplete(true);
            actions.setAnalysisResult(result || { jobId: targetId });
            setIsAnalyzing(false);
            if (ws) ws.close();

            if (targetId) {
                getJob(targetId).then(jobData => {
                    if (jobData?.statistics) {
                        actions.updateAnalysisProgress({
                            tables: { count: jobData.statistics.tables ?? 0, status: 'completed' },
                            queries: { count: jobData.statistics.queries ?? 0, status: 'completed' },
                            forms: { count: jobData.statistics.forms ?? 0, status: 'completed' },
                            reports: { count: jobData.statistics.reports ?? 0, status: 'completed' },
                            macros: { count: jobData.statistics.macros ?? 0, status: 'completed' },
                            vba: { count: jobData.statistics.vba_modules ?? 0, status: 'completed' },
                            dependencies: { count: jobData.statistics.dependencies ?? 0, status: 'completed' },
                        });
                    }
                }).catch(e => console.error('Error fetching final job stats:', e));
            }
        }

        // Handle failure
        if (jobState === JOB_STATES.FAILED) {
            actions.setError(error || 'Analysis failed');
            actions.setAnalysisComplete(false);
            setIsAnalyzing(false);
            if (ws) ws.close();
        }
    }, [analysisProgress, analysisJobId, actions, ws]);

    // Cleanup WebSocket on unmount
    useEffect(() => {
        return () => {
            if (ws) ws.close();
        };
    }, [ws]);

    // Auto-start analysis
    useEffect(() => {
        if ((selectedFile || localSource) && !analysisJobId && !isAnalyzing && !startedRef.current) {
            startedRef.current = true;
            startAnalysis();
        }
    }, [selectedFile, localSource, analysisJobId, isAnalyzing, startAnalysis]);

    // Determine overall progress
    const completedCount = Object.values(analysisProgress).filter(p => p.status === 'completed').length;
    const totalCount = ANALYSIS_ITEMS.length;
    const overallProgress = (completedCount / totalCount) * 100;

    return (
        <div>
            <div className="card-header">
                <h2 className="card-title">Analyze Application</h2>
                <p className="card-subtitle">
                    Scanning the Access database to extract all objects and build the dependency graph.
                </p>
            </div>

            {/* Overall Progress */}
            <div style={{ marginBottom: '1.5rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                    <span style={{ fontWeight: 500 }}>Overall Progress</span>
                    <span>{Math.round(overallProgress)}%</span>
                </div>
                <div className="progress-bar">
                    <div
                        className="progress-bar-fill"
                        style={{ width: `${overallProgress}%` }}
                    />
                </div>
            </div>

            {/* Analysis Items */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                {ANALYSIS_ITEMS.map((item) => {
                    const progress = analysisProgress[item.key];
                    const status = progress?.status || 'pending';
                    const count = progress?.count || 0;

                    return (
                        <div
                            key={item.key}
                            className="card"
                            style={{
                                padding: '1rem',
                                borderLeft: `4px solid ${
                                    status === 'completed' ? 'var(--color-success)' :
                                    status === 'in_progress' ? 'var(--color-primary)' :
                                    status === 'error' ? 'var(--color-danger)' : 'var(--color-border)'
                                }`,
                                background: status === 'in_progress' ? 'rgba(59, 130, 246, 0.05)' : 'transparent',
                                transition: 'all 0.3s ease',
                            }}
                        >
                            <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', flexWrap: 'wrap' }}>
                                <span style={{ fontSize: '1.5rem' }}>{STATUS_ICONS[status]}</span>
                                <span style={{ fontSize: '1.5rem' }}>{item.icon}</span>
                                <div style={{ flex: 1, minWidth: 200 }}>
                                    <div style={{ fontWeight: 600, fontSize: '0.9375rem' }}>{item.label}</div>
                                    <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>{item.description}</div>
                                </div>
                                <div style={{ textAlign: 'right' }}>
                                    <div style={{ fontWeight: 600, fontSize: '1rem', color: 'var(--color-primary)' }}>
                                        {formatNumber(count)}
                                    </div>
                                    <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', textTransform: 'capitalize' }}>
                                        {status.replace('_', ' ')}
                                    </div>
                                </div>
                            </div>
                        </div>
                    );
                })}
            </div>

            {/* Status message */}
            {!analysisComplete && (
                <div className="alert alert-info" style={{ marginTop: '1.5rem' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                        <div className="spinner" style={{ width: '20px', height: '20px', borderWidth: '2px' }} />
                        <span>
                            {isAnalyzing ? 'Analyzing Access application...' : 'Starting analysis...'}
                        </span>
                    </div>
                </div>
            )}

            {analysisComplete && analysisResult && (
                <div className="alert alert-success" style={{ marginTop: '1.5rem' }}>
                    <strong>Analysis Complete!</strong>
                    <div style={{ marginTop: '0.5rem', fontSize: '0.875rem' }}>
                        Found {formatNumber(analysisProgress.tables.count)} tables, {formatNumber(analysisProgress.queries.count)} queries,
                        {formatNumber(analysisProgress.forms.count)} forms, {formatNumber(analysisProgress.reports.count)} reports,
                        {formatNumber(analysisProgress.macros.count)} macros, {formatNumber(analysisProgress.vba.count)} VBA modules.
                    </div>
                </div>
            )}

            {/* ── BRD Report Action Bar ── */}
            <div style={{
                marginTop: '1.5rem',
                padding: '1.1rem 1.4rem',
                borderRadius: 14,
                background: '#F8FAFC',
                border: '1.5px solid #C7D2FE',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                flexWrap: 'wrap',
                gap: '1rem'
            }}>
                <div>
                    <div style={{ fontWeight: 700, fontSize: '0.95rem', color: '#1E1B4B', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                        <span style={{ fontSize: '1.1rem' }}>📄</span>
                        Business Requirements Document (BRD)
                    </div>
                    <div style={{ fontSize: '0.8rem', color: '#6B7280', marginTop: '0.2rem' }}>
                        Generate a comprehensive HTML technical report from the analyzed source database.
                    </div>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
                    {!brdGenerated ? (
                        <button
                            type="button"
                            onClick={handleGenerateBrd}
                            disabled={brdLoading}
                            style={{
                                display: 'inline-flex',
                                alignItems: 'center',
                                gap: '0.5rem',
                                padding: '0.65rem 1.4rem',
                                borderRadius: 10,
                                background: brdLoading
                                    ? '#E0E7FF'
                                    : 'linear-gradient(135deg, #3730A3 0%, #4F46E5 100%)',
                                color: brdLoading ? '#3730A3' : '#fff',
                                fontWeight: 700,
                                fontSize: '0.875rem',
                                border: 'none',
                                boxShadow: brdLoading ? 'none' : '0 4px 14px rgba(55,48,163,0.25)',
                                cursor: brdLoading ? 'not-allowed' : 'pointer',
                                transition: 'all 0.2s ease',
                            }}
                        >
                            {brdLoading ? (
                                <>
                                    <div className="spinner" style={{ width: '16px', height: '16px', borderWidth: '2px' }} />
                                    Generating BRD...
                                </>
                            ) : (
                                <>
                                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                                        <polyline points="14 2 14 8 20 8"/>
                                        <line x1="16" y1="13" x2="8" y2="13"/>
                                        <line x1="16" y1="17" x2="8" y2="17"/>
                                        <polyline points="10 9 9 9 8 9"/>
                                    </svg>
                                    BRD Report
                                </>
                            )}
                        </button>
                    ) : (
                        <>
                            <span style={{
                                display: 'inline-flex',
                                alignItems: 'center',
                                gap: '0.35rem',
                                color: '#059669',
                                fontWeight: 700,
                                fontSize: '0.875rem',
                                marginRight: '0.5rem'
                            }}>
                                BRD Generated ✓
                            </span>

                            <button
                                type="button"
                                onClick={handleViewBrd}
                                style={{
                                    display: 'inline-flex',
                                    alignItems: 'center',
                                    gap: '0.45rem',
                                    padding: '0.6rem 1.25rem',
                                    borderRadius: 10,
                                    background: '#EEF2FF',
                                    color: '#3730A3',
                                    fontWeight: 600,
                                    fontSize: '0.875rem',
                                    border: '1.5px solid #C7D2FE',
                                    cursor: 'pointer',
                                    transition: 'all 0.15s ease',
                                }}
                            >
                                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                    <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
                                    <circle cx="12" cy="12" r="3"/>
                                </svg>
                                View BRD
                            </button>

                            <button
                                type="button"
                                onClick={handleDownloadBrd}
                                style={{
                                    display: 'inline-flex',
                                    alignItems: 'center',
                                    gap: '0.45rem',
                                    padding: '0.6rem 1.25rem',
                                    borderRadius: 10,
                                    background: 'linear-gradient(135deg, #3730A3 0%, #4F46E5 100%)',
                                    color: '#fff',
                                    fontWeight: 600,
                                    fontSize: '0.875rem',
                                    border: 'none',
                                    boxShadow: '0 4px 14px rgba(55,48,163,0.25)',
                                    cursor: 'pointer',
                                    transition: 'all 0.15s ease',
                                }}
                            >
                                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                                    <polyline points="7 10 12 15 17 10"/>
                                    <line x1="12" y1="15" x2="12" y2="3"/>
                                </svg>
                                Download BRD
                            </button>
                        </>
                    )}
                </div>
            </div>

            {/* Error display if BRD generation failed */}
            {brdError && (
                <div className="alert alert-danger" style={{ marginTop: '0.75rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span>{brdError}</span>
                    <button
                        type="button"
                        onClick={() => setBrdError(null)}
                        style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: '1.2rem', lineHeight: 1 }}
                    >
                        ×
                    </button>
                </div>
            )}
        </div>
    );
}