import React, { useEffect, useCallback, useRef, useState } from 'react';
import { useWizard } from '../../../context/WizardContext';
import { createJob, connectProgressWebSocket, downloadResult, getJob } from '../../../services/api';
import { JOB_STATES } from '../../../utils/constants';
import { formatNumber } from '../../../utils/helpers';

/**
 * Step 5: Generate Project
 * Per spec section 47:
 * - Show real-time progress of:
 *   Generating backend, Generating frontend, Generating DB
 *   Resolving dependencies, Building backend, Building frontend
 *   Running tests, Repairing errors, Running behavioral tests
 */

const GENERATION_STEPS = [
    { key: 'database', label: 'Generating Database', icon: '🗄️', description: 'Creating PostgreSQL schema, migrations, and seed data' },
    { key: 'backend', label: 'Generating Backend', icon: '☕', description: 'Creating Spring Boot entities, repositories, services, controllers' },
    { key: 'frontend', label: 'Generating Frontend', icon: '⚛️', description: 'Creating React pages, components, API clients, routing' },
    { key: 'dependencies', label: 'Resolving Dependencies', icon: '📦', description: 'Resolving Maven and npm dependency versions, checking convergence' },
    { key: 'build_backend', label: 'Building Backend', icon: '🔨', description: 'Running mvn clean package, dependency convergence check' },
    { key: 'build_frontend', label: 'Building Frontend', icon: '📦', description: 'Running npm ci, npm run build' },
    { key: 'tests', label: 'Running Tests', icon: '🧪', description: 'Executing unit tests, API tests, integration tests' },
    { key: 'repair', label: 'Repairing Errors', icon: '🔧', description: 'Applying deterministic and LLM-based fixes for build failures' },
    { key: 'behavioral', label: 'Behavioral Tests', icon: '✅', description: 'Running behavioral regression tests against source Access app' },
];

const STEP_ORDER = GENERATION_STEPS.map(s => s.key);

const STATUS_ICONS = {
    pending: '⏳',
    in_progress: '🔄',
    completed: '✅',
    error: '❌',
    skipped: '⏭️',
};

/**
 * Map backend step names and job states to frontend step keys.
 * The backend pipeline sends step names like "generating_database",
 * "generating_backend", etc. and job states like "GENERATING_DATABASE".
 * We need to map these to our STEP_ORDER keys.
 */
const BACKEND_STEP_MAP = {
    // Pipeline broadcast step names
    'generating_database': 'database',
    'generating_backend': 'backend',
    'generating_frontend': 'frontend',
    'generating_reports': 'frontend',  // report generation is part of the frontend phase
    'resolving_dependencies': 'dependencies',
    'validating_build': 'build_backend',
    'self_healing_repair': 'repair',
    'completed': 'behavioral',

    // Job state values (sent by WebSocket polling)
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

/**
 * Ordered list of backend states that correspond to generation.
 * Used to figure out which frontend steps are "completed" based on
 * the current backend state.
 */
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

export default function Step5Generate() {
    const { state, actions } = useWizard();
    const { selectedFile, localSource, config, analysisJobId, generationJobId, generationProgress, generationComplete, generationResult } = state;
    const [isGenerating, setIsGenerating] = useState(false);
    const wsRef = useRef(null);
    const startedRef = useRef(false);

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

    // Build step status map
    const getStepStatus = (stepKey) => {
        if (generationProgress.completedSteps?.includes(stepKey)) return 'completed';
        if (generationProgress.failedSteps?.includes(stepKey)) return 'error';
        if (generationProgress.currentStep === stepKey) return 'in_progress';
        return 'pending';
    };

    const completedCount = generationProgress.completedSteps?.length || 0;
    const totalSteps = GENERATION_STEPS.length;
    const overallProgress = generationProgress.percentage || (completedCount / totalSteps) * 100;

    return (
        <div>
            <div className="card-header">
                <h2 className="card-title">Generate Project</h2>
                <p className="card-subtitle">
                    Building the complete Spring Boot + React + PostgreSQL application with validation.
                </p>
            </div>

            {/* Overall Progress */}
            <div style={{ marginBottom: '1.5rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                    <span style={{ fontWeight: 500 }}>Overall Progress</span>
                    <span>{Math.round(overallProgress)}%</span>
                </div>
                <div className="progress-bar">
                    <div
                        className="progress-bar-fill"
                        style={{ width: `${overallProgress}%` }}
                    />
                </div>
                {generationProgress.currentStep && generationProgress.currentStep !== 'initializing' && generationProgress.currentStep !== 'completed' && (
                    <p className="form-hint" style={{ marginTop: '0.5rem', textAlign: 'right' }}>
                        Current: <strong>{GENERATION_STEPS.find(s => s.key === generationProgress.currentStep)?.label || generationProgress.currentStep}</strong>
                    </p>
                )}
                {generationProgress.currentStep === 'initializing' && (
                    <p className="form-hint" style={{ marginTop: '0.5rem', textAlign: 'right' }}>
                        Current: <strong>initializing</strong>
                    </p>
                )}
            </div>

            {/* Generation Steps */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                {GENERATION_STEPS.map((step) => {
                    const status = getStepStatus(step.key);

                    return (
                        <div
                            key={step.key}
                            className="card"
                            style={{
                                padding: '1rem',
                                borderLeft: `4px solid ${
                                    status === 'completed' ? 'var(--color-success)' :
                                    status === 'in_progress' ? 'var(--color-primary)' :
                                    status === 'error' ? 'var(--color-danger)' :
                                    'var(--color-border)'
                                }`,
                                background: status === 'in_progress' ? 'rgba(59, 130, 246, 0.05)' : 'transparent',
                                transition: 'all 0.3s ease',
                            }}
                        >
                            <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', flexWrap: 'wrap' }}>
                                <span style={{ fontSize: '1.5rem' }}>{STATUS_ICONS[status]}</span>
                                <span style={{ fontSize: '1.5rem' }}>{step.icon}</span>
                                <div style={{ flex: 1, minWidth: 200 }}>
                                    <div style={{ fontWeight: 600, fontSize: '0.9375rem' }}>{step.label}</div>
                                    <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>{step.description}</div>
                                </div>
                                <div style={{ textAlign: 'right' }}>
                                    <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', textTransform: 'capitalize' }}>
                                        {status.replace('_', ' ')}
                                    </div>
                                </div>
                            </div>
                        </div>
                    );
                })}
            </div>

            {/* Live Log */}
            {generationProgress.details && generationProgress.details.length > 0 && (
                <div style={{ marginTop: '1.5rem' }}>
                    <h3 style={{ fontSize: '0.875rem', fontWeight: 600, marginBottom: '0.75rem', color: 'var(--color-text-muted)' }}>
                        Build Log
                    </h3>
                    <div style={{
                        background: '#1e1e1e',
                        color: '#d4d4d4',
                        borderRadius: 'var(--radius-md)',
                        padding: '1rem',
                        maxHeight: '300px',
                        overflowY: 'auto',
                        fontFamily: 'monospace',
                        fontSize: '0.75rem',
                        lineHeight: 1.5,
                    }}>
                        {generationProgress.details.slice(-50).map((detail, i) => (
                            <div key={i} style={{ borderBottom: '1px solid #333', padding: '0.25rem 0' }}>
                                <span style={{ color: '#888' }}>{new Date(detail.timestamp).toLocaleTimeString()}</span>
                                <span style={{ color: '#9cdcfe', margin: '0 0.5rem' }}>[ {detail.step} ]</span>
                                <span>{detail.message}</span>
                            </div>
                        ))}
                    </div>
                </div>
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
                <div className="alert alert-success" style={{ marginTop: '1.5rem' }}>
                    <strong>Generation Complete!</strong>
                    <div style={{ marginTop: '0.5rem', fontSize: '0.875rem' }}>
                        Project generated at: <code>{generationResult.outputPath || generationResult.output_path || 'outputs/job-id'}</code>
                    </div>
                    {generationResult.filesGenerated && (
                        <div style={{ marginTop: '0.25rem', fontSize: '0.8125rem', color: 'var(--color-text-muted)' }}>
                            Generated {formatNumber(generationResult.filesGenerated)} files
                        </div>
                    )}
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
                            // Navigate to summary step
                            actions.setStep(6);
                        }}
                    >
                        View Summary →
                    </button>
                </div>
            )}
        </div>
    );
}