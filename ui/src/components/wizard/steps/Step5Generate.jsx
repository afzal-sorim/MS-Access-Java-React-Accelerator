import React, { useEffect, useCallback, useRef, useState } from 'react';
import { useWizard } from '../../../context/WizardContext';
import { createJob, connectProgressWebSocket, downloadResult } from '../../../services/api';
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

export default function Step5Generate() {
    const { state, actions } = useWizard();
    const { selectedFile, config, analysisJobId, generationJobId, generationProgress, generationComplete, generationResult } = state;
    const [isGenerating, setIsGenerating] = useState(false);
    const [ws, setWs] = useState(null);
    const [stepDetails, setStepDetails] = useState({});

    // Start generation when entering step
    const startGeneration = useCallback(async () => {
        if (!selectedFile || !analysisJobId) return;

        setIsGenerating(true);
        actions.setError(null);

        try {
            // Create a new generation job or continue from analysis job
            // For now, we'll use the same job ID pattern
            const job = await createJob(selectedFile, config);
            const jobId = job.id;
            actions.setGenerationJob(jobId);

            // Connect WebSocket for real-time progress
            const websocket = connectProgressWebSocket(jobId, (message) => {
                handleWebSocketMessage(message);
            });
            setWs(websocket);

        } catch (err) {
            actions.setError(err.message);
            setIsGenerating(false);
        }
    }, [selectedFile, config, analysisJobId, actions]);

    // Handle WebSocket messages
    const handleWebSocketMessage = useCallback((message) => {
        const { state: jobState, step, progress, result, error, details } = message;

        // Update generation progress based on step
        if (step) {
            // Mark previous steps as completed
            const currentIndex = STEP_ORDER.indexOf(step);
            if (currentIndex > 0) {
                const completedSteps = STEP_ORDER.slice(0, currentIndex);
                actions.updateGenerationProgress({
                    completedSteps: [...new Set([...generationProgress.completedSteps, ...completedSteps])],
                });
            }

            // Mark current step as in progress
            actions.updateGenerationProgress({
                currentStep: step,
            });

            // Add detail if provided
            if (details) {
                actions.addGenerationDetail({
                    step,
                    timestamp: new Date().toISOString(),
                    message: details,
                });
            }
        }

        // Update percentage based on completed steps
        const completedCount = generationProgress.completedSteps?.length || 0;
        const totalSteps = STEP_ORDER.length;
        const percentage = Math.min((completedCount / totalSteps) * 100, 100);
        actions.updateGenerationProgress({ percentage });

        // Handle completion
        if (jobState === JOB_STATES.COMPLETED) {
            actions.setGenerationComplete(true);
            actions.setGenerationResult(result || { jobId: generationJobId });
            setIsGenerating(false);
            if (ws) ws.close();
        }

        // Handle failure
        if (jobState === JOB_STATES.FAILED) {
            actions.setError(error || 'Generation failed');
            actions.setGenerationComplete(false);
            actions.updateGenerationProgress({
                failedSteps: [...new Set([...(generationProgress.failedSteps || []), generationProgress.currentStep])],
            });
            setIsGenerating(false);
            if (ws) ws.close();
        }

        // Handle repair attempts
        if (jobState === JOB_STATES.REPAIRING) {
            actions.updateGenerationProgress({
                currentStep: 'repair',
            });
            if (details) {
                actions.addGenerationDetail({
                    step: 'repair',
                    timestamp: new Date().toISOString(),
                    message: `Repair attempt: ${details}`,
                });
            }
        }

        // Handle testing
        if (jobState === JOB_STATES.TESTING) {
            actions.updateGenerationProgress({
                currentStep: 'behavioral',
            });
        }
    }, [generationProgress, generationJobId, actions, ws]);

    // Cleanup WebSocket on unmount
    useEffect(() => {
        return () => {
            if (ws) ws.close();
        };
    }, [ws]);

    // Auto-start generation
    useEffect(() => {
        if (selectedFile && analysisJobId && !generationJobId && !isGenerating) {
            startGeneration();
        }
    }, [selectedFile, analysisJobId, generationJobId, isGenerating, startGeneration]);

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
                {generationProgress.currentStep && (
                    <p className="form-hint" style={{ marginTop: '0.5rem', textAlign: 'right' }}>
                        Current: <strong>{GENERATION_STEPS.find(s => s.key === generationProgress.currentStep)?.label || generationProgress.currentStep}</strong>
                    </p>
                )}
            </div>

            {/* Generation Steps */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                {GENERATION_STEPS.map((step) => {
                    const status = getStepStatus(step.key);
                    const detail = stepDetails[step.key];

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

                            {detail && (
                                <div style={{ marginTop: '0.75rem', paddingLeft: '3.5rem', fontSize: '0.75rem', color: 'var(--color-text-muted)', fontFamily: 'monospace' }}>
                                    {detail.message}
                                </div>
                            )}
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