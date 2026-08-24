import React, { useEffect, useCallback, useState } from 'react';
import { useWizard } from '../../../context/WizardContext';
import { getReport, downloadResult } from '../../../services/api';
import { formatNumber, formatPercentage } from '../../../utils/helpers';

/**
 * Step 6: Summary
 * Per spec section 47:
 * - Show: conversion coverage, supported objects, unsupported objects, warnings
 * - Build status, test status, generated project location
 * - Actions: Open Project, Run Application, Open Report, View Documentation, Close Wizard
 */
export default function Step6Summary() {
    const { state, actions } = useWizard();
    const { generationResult, config, analysisJobId, analysisProgress, generationJobId } = state;
    const [report, setReport] = useState(null);
    const [loading, setLoading] = useState(false);

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

    // Unsupported objects
    const unsupportedObjects = report?.supportability
        ?.filter(s => s.status === 'UNSUPPORTED')
        ?.map(s => ({ name: s.object, reason: s.reason, category: s.category })) || [];

    // Warnings
    const warnings = report?.warnings || [];

    const handleDownload = useCallback(() => {
        if (generationJobId) {
            downloadResult(generationJobId, config.project_name);
        }
    }, [generationJobId, config.project_name]);

    const handleOpenReport = useCallback(() => {
        // In a real app, this would open the migration-report.html
        if (generationResult?.outputPath) {
            window.open(`${generationResult.outputPath}/migration-report/migration-report.html`, '_blank');
        }
    }, [generationResult]);

    const handleOpenProject = useCallback(() => {
        // In a real app, this might open the project in an IDE or file explorer
        if (generationResult?.outputPath) {
            window.open(`file://${generationResult.outputPath}`, '_blank');
        }
    }, [generationResult]);

    const handleRunApplication = useCallback(() => {
        // In a real app, this would start the generated application
        alert('To run the application:\n\n1. Start PostgreSQL database\n2. Run: cd backend && mvn spring-boot:run\n3. Run: cd frontend && npm run dev\n\nThe application will be available at http://localhost:3000');
    }, []);

    return (
        <div style={{ maxWidth: '1000px', margin: '0 auto' }}>
            <div className="card-header" style={{ textAlign: 'center', marginBottom: '2rem' }}>
                <div style={{ fontSize: '4rem', marginBottom: '1rem' }}>✅</div>
                <h2 className="card-title" style={{ fontSize: '2rem' }}>Conversion Complete!</h2>
                <p className="card-subtitle" style={{ fontSize: '1.125rem' }}>
                    Your Access application has been converted to Spring Boot + React + PostgreSQL
                </p>
            </div>

            {/* Coverage Overview */}
            <div className="grid grid-4" style={{ marginBottom: '2rem' }}>
                <div className="stat-card">
                    <div className="stat-card-value" style={{ color: 'var(--color-success)' }}>
                        {formatPercentage(coverage.overall)}
                    </div>
                    <div className="stat-card-label">Overall Coverage</div>
                </div>
                <div className="stat-card">
                    <div className="stat-card-value" style={{ color: 'var(--color-primary)' }}>
                        {formatPercentage(coverage.fully_supported_pct)}
                    </div>
                    <div className="stat-card-label">Fully Supported</div>
                </div>
                <div className="stat-card">
                    <div className="stat-card-value" style={{ color: 'var(--color-warning)' }}>
                        {formatPercentage(coverage.supported_with_review_pct)}
                    </div>
                    <div className="stat-card-label">Needs Review</div>
                </div>
                <div className="stat-card">
                    <div className="stat-card-value" style={{ color: 'var(--color-danger)' }}>
                        {formatPercentage(coverage.unsupported_pct)}
                    </div>
                    <div className="stat-card-label">Unsupported</div>
                </div>
            </div>

            {/* Category Coverage */}
            <div className="card" style={{ marginBottom: '2rem' }}>
                <h3 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '1rem' }}>Coverage by Category</h3>
                <div className="grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '1rem' }}>
                    {[
                        { key: 'table_coverage', label: 'Tables', icon: '🗃️' },
                        { key: 'query_coverage', label: 'Queries', icon: '🔍' },
                        { key: 'form_coverage', label: 'Forms', icon: '📋' },
                        { key: 'report_coverage', label: 'Reports', icon: '📊' },
                        { key: 'macro_coverage', label: 'Macros', icon: '⚡' },
                        { key: 'vba_coverage', label: 'VBA', icon: '💻' },
                    ].map(cat => (
                        <div key={cat.key} style={{ textAlign: 'center', padding: '1rem', background: 'var(--color-bg-alt)', borderRadius: 'var(--radius-md)' }}>
                            <div style={{ fontSize: '1.5rem', marginBottom: '0.25rem' }}>{cat.icon}</div>
                            <div style={{ fontSize: '2rem', fontWeight: 700, color: 'var(--color-primary)' }}>
                                {formatPercentage(coverage[cat.key])}
                            </div>
                            <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', textTransform: 'uppercase' }}>
                                {cat.label}
                            </div>
                        </div>
                    ))}
                </div>
            </div>

            {/* Object Counts */}
            <div className="card" style={{ marginBottom: '2rem' }}>
                <h3 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '1rem' }}>Object Inventory</h3>
                <div className="grid grid-3">
                    {[
                        { label: 'Tables', value: stats.tables, icon: '🗃️' },
                        { label: 'Queries', value: stats.queries, icon: '🔍' },
                        { label: 'Forms', value: stats.forms, icon: '📋' },
                        { label: 'Reports', value: stats.reports, icon: '📊' },
                        { label: 'Macros', value: stats.macros, icon: '⚡' },
                        { label: 'VBA Modules', value: stats.vbaModules, icon: '💻' },
                    ].map(item => (
                        <div key={item.label} className="stat-card">
                            <div style={{ fontSize: '1.5rem', marginBottom: '0.25rem' }}>{item.icon}</div>
                            <div className="stat-card-value">{formatNumber(item.value)}</div>
                            <div className="stat-card-label">{item.label}</div>
                        </div>
                    ))}
                </div>
                <div style={{ textAlign: 'right', marginTop: '1rem', fontWeight: 500 }}>
                    Total Objects: {formatNumber(totalObjects)}
                </div>
            </div>

            {/* Build & Test Status */}
            <div className="grid grid-2" style={{ marginBottom: '2rem' }}>
                <div className="card" style={{ textAlign: 'center', padding: '2rem' }}>
                    <div style={{ fontSize: '3rem', marginBottom: '0.5rem' }}>
                        {generationResult?.buildSuccess ? '✅' : '⏳'}
                    </div>
                    <div style={{ fontSize: '1.5rem', fontWeight: 700, color: generationResult?.buildSuccess ? 'var(--color-success)' : 'var(--color-primary)' }}>
                        {generationResult?.buildSuccess ? 'PASS' : 'PENDING'}
                    </div>
                    <div style={{ color: 'var(--color-text-muted)' }}>Backend Build</div>
                </div>
                <div className="card" style={{ textAlign: 'center', padding: '2rem' }}>
                    <div style={{ fontSize: '3rem', marginBottom: '0.5rem' }}>
                        {generationResult?.testSuccess ? '✅' : '⏳'}
                    </div>
                    <div style={{ fontSize: '1.5rem', fontWeight: 700, color: generationResult?.testSuccess ? 'var(--color-success)' : 'var(--color-primary)' }}>
                        {generationResult?.testSuccess ? 'PASS' : 'PENDING'}
                    </div>
                    <div style={{ color: 'var(--color-text-muted)' }}>Tests</div>
                </div>
            </div>

            {/* Unsupported Objects */}
            {unsupportedObjects.length > 0 && (
                <div className="card" style={{ marginBottom: '2rem', border: '1px solid var(--color-danger)' }}>
                    <h3 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '1rem', color: 'var(--color-danger)' }}>
                        ⚠️ Unsupported Objects ({unsupportedObjects.length})
                    </h3>
                    <div style={{ maxHeight: '200px', overflowY: 'auto' }}>
                        <table className="data-table" style={{ fontSize: '0.8125rem' }}>
                            <thead>
                                <tr>
                                    <th>Object</th>
                                    <th>Category</th>
                                    <th>Reason</th>
                                </tr>
                            </thead>
                            <tbody>
                                {unsupportedObjects.slice(0, 10).map((obj, i) => (
                                    <tr key={i}>
                                        <td style={{ fontFamily: 'monospace' }}>{obj.name}</td>
                                        <td><span className="badge badge-neutral">{obj.category}</span></td>
                                        <td style={{ color: 'var(--color-text-muted)' }}>{obj.reason}</td>
                                    </tr>
                                ))}
                                {unsupportedObjects.length > 10 && (
                                    <tr>
                                        <td colSpan={3} style={{ textAlign: 'center', color: 'var(--color-text-muted)', fontStyle: 'italic' }}>
                                            ... and {unsupportedObjects.length - 10} more
                                        </td>
                                    </tr>
                                )}
                            </tbody>
                        </table>
                    </div>
                </div>
            )}

            {/* Warnings */}
            {warnings.length > 0 && (
                <div className="card" style={{ marginBottom: '2rem', border: '1px solid var(--color-warning)' }}>
                    <h3 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '1rem', color: 'var(--color-warning)' }}>
                        ⚠️ Warnings ({warnings.length})
                    </h3>
                    <ul style={{ fontSize: '0.8125rem', color: 'var(--color-text-muted)', paddingLeft: '1.25rem', display: 'grid', gap: '0.25rem' }}>
                        {warnings.slice(0, 5).map((w, i) => (
                            <li key={i} style={{ maxWidth: '100%', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{w}</li>
                        ))}
                        {warnings.length > 5 && (
                            <li style={{ color: 'var(--color-text-muted)', fontStyle: 'italic' }}>
                                ... and {warnings.length - 5} more warnings
                            </li>
                        )}
                    </ul>
                </div>
            )}

            {/* Generated Project Location */}
            {generationResult?.outputPath && (
                <div className="card" style={{ marginBottom: '2rem', background: 'rgba(59, 130, 246, 0.05)', border: '1px solid var(--color-primary)' }}>
                    <h3 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '0.75rem', color: 'var(--color-primary)' }}>
                        📁 Generated Project Location
                    </h3>
                    <div style={{ fontFamily: 'monospace', fontSize: '0.8125rem', color: 'var(--color-text)', background: 'var(--color-bg-alt)', padding: '0.75rem', borderRadius: 'var(--radius-md)', wordBreak: 'break-all' }}>
                        {generationResult.outputPath}
                    </div>
                </div>
            )}

            {/* Actions */}
            <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', justifyContent: 'center' }}>
                {generationJobId && (
                    <button
                        className="btn btn-primary btn-lg"
                        onClick={handleDownload}
                        style={{ minWidth: '180px' }}
                    >
                        📥 Download Project ZIP
                    </button>
                )}
                <button
                    className="btn btn-secondary btn-lg"
                    onClick={handleOpenReport}
                    style={{ minWidth: '160px' }}
                >
                    📄 Open Report
                </button>
                <button
                    className="btn btn-secondary btn-lg"
                    onClick={handleOpenProject}
                    style={{ minWidth: '160px' }}
                >
                    📁 Open Project Folder
                </button>
                <button
                    className="btn btn-success btn-lg"
                    onClick={handleRunApplication}
                    style={{ minWidth: '180px' }}
                >
                    ▶️ Run Application
                </button>
                <button
                    className="btn btn-secondary"
                    onClick={() => actions.resetWizard()}
                >
                    🔄 Start New Conversion
                </button>
            </div>

            {/* Documentation Link */}
            <div style={{ marginTop: '2rem', paddingTop: '2rem', borderTop: '1px solid var(--color-border)', textAlign: 'center' }}>
                <p style={{ color: 'var(--color-text-muted)', marginBottom: '0.5rem' }}>
                    Need help with the generated project?
                </p>
                <a
                    href="#"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="btn btn-secondary"
                    style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}
                >
                    📖 View Documentation
                </a>
            </div>

            {/* Project Configuration Summary */}
            <details style={{ marginTop: '2rem' }}>
                <summary style={{ cursor: 'pointer', fontWeight: 500, color: 'var(--color-text-muted)' }}>
                    View Configuration Details
                </summary>
                <div style={{ marginTop: '1rem', fontSize: '0.8125rem', color: 'var(--color-text-muted)', fontFamily: 'monospace', background: 'var(--color-bg-alt)', padding: '1rem', borderRadius: 'var(--radius-md)', overflowX: 'auto' }}>
                    <pre>{JSON.stringify({
                        project_name: config.project_name,
                        base_package: config.base_package,
                        java_version: config.java_version,
                        spring_boot_version: config.spring_boot_version,
                        react_version: config.react_version,
                        node_version: config.node_version,
                        postgres_version: config.postgres_version,
                        authentication_strategy: config.authentication_strategy,
                        report_strategy: config.report_strategy,
                        migration_strategy: config.migration_strategy,
                    }, null, 2)}</pre>
                </div>
            </details>
        </div>
    );
}