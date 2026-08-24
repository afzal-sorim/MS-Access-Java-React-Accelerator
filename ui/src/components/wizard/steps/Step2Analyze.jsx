import React, { useEffect, useCallback } from 'react';
import { useWizard } from '../../../context/WizardContext';
import { createJob, connectProgressWebSocket, getVersions } from '../../../services/api';
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
    const { selectedFile, analysisJobId, analysisProgress, analysisComplete, analysisResult, config } = state;
    const [isAnalyzing, setIsAnalyzing] = React.useState(false);
    const [ws, setWs] = React.useState(null);
    // Guards against duplicate job creation. In dev, React.StrictMode
    // mounts -> cleans up -> re-mounts every component once, which fires
    // this effect twice in quick succession. Without this guard that sent
    // two near-simultaneous POST /api/jobs for the same file, and the
    // second write could hit SQLite's "database is locked" error and fail
    // outright - leaving the wizard stuck at 0% with no visible job.
    const startedRef = React.useRef(false);

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
        if (!selectedFile) return;

        setIsAnalyzing(true);
        actions.setError(null);

        try {
            // Create job with current config
            const job = await createJob(selectedFile, config);
            const jobId = job.id;
            actions.setAnalysisJob(jobId);

            // Connect WebSocket for real-time progress
            const websocket = connectProgressWebSocket(jobId, (message) => {
                handleWebSocketMessage(message);
            });
            setWs(websocket);

        } catch (err) {
            actions.setError(err.message);
            setIsAnalyzing(false);
            startedRef.current = false; // allow retry after a genuine failure
        }
    }, [selectedFile, config, actions]);

    // Handle WebSocket messages
    const handleWebSocketMessage = useCallback((message) => {
        const { state: jobState, step, progress, result, error } = message;

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

        // Update counts from progress
        if (progress && typeof progress === 'object') {
            actions.updateAnalysisProgress({
                tables: { ...analysisProgress.tables, count: progress.tables || 0, status: 'completed' },
                queries: { ...analysisProgress.queries, count: progress.queries || 0, status: 'completed' },
                forms: { ...analysisProgress.forms, count: progress.forms || 0, status: 'completed' },
                reports: { ...analysisProgress.reports, count: progress.reports || 0, status: 'completed' },
                macros: { ...analysisProgress.macros, count: progress.macros || 0, status: 'completed' },
                vba: { ...analysisProgress.vba, count: progress.vba_modules || 0, status: 'completed' },
                dependencies: { ...analysisProgress.dependencies, count: progress.dependencies || 0, status: 'completed' },
            });
        }

        // Handle completion
        if (jobState === JOB_STATES.SUPPORTABILITY_ANALYZED || jobState === JOB_STATES.COMPLETED) {
            actions.setAnalysisComplete(true);
            actions.setAnalysisResult(result || { jobId: analysisJobId });
            setIsAnalyzing(false);
            if (ws) ws.close();
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
        if (selectedFile && !analysisJobId && !isAnalyzing && !startedRef.current) {
            startedRef.current = true;
            startAnalysis();
        }
    }, [selectedFile, analysisJobId, isAnalyzing, startAnalysis]);

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
        </div>
    );
}