import React, { useEffect, useState } from 'react';
import { useWizard } from '../../../context/WizardContext';
import { formatNumber } from '../../../utils/helpers';

/**
 * Step 3: Conversion Configuration
 * Per spec section 47:
 * - Backend: Spring Boot
 * - Java: 25 LTS default
 * - Frontend: React 19.2
 * - Build: Vite 8.1
 * - Database: PostgreSQL 18.x
 * - Project name
 * - Base package
 * - Authentication strategy
 * - Report strategy
 * - Migration strategy
 */
export default function Step3Configure() {
    const { state, actions } = useWizard();
    const { config, availableVersions, analysisResult } = state;
    const [localConfig, setLocalConfig] = useState(config);
    const [versionsLoaded, setVersionsLoaded] = useState(false);

    // Sync local config with context
    useEffect(() => {
        setLocalConfig(config);
        setVersionsLoaded(true);
    }, [config, versionsLoaded]);

    const handleConfigChange = (key, value) => {
        const newConfig = { ...localConfig, [key]: value };
        setLocalConfig(newConfig);
        actions.updateConfig(newConfig);
    };

    // Java versions
    const javaVersions = [
        { value: 17, label: '17 LTS (Minimum for Spring Boot 4.1)' },
        { value: 21, label: '21 LTS' },
        { value: 25, label: '25 LTS (Recommended)' },
    ];

    // Spring Boot versions (from available versions or defaults)
    const springBootVersions = availableVersions?.backend?.versions || ['4.1.0'];

    // React versions
    const reactVersions = availableVersions?.frontend?.versions || ['19.2.8'];

    // Node versions
    const nodeVersions = availableVersions?.frontend?.node_versions || [20, 22, 24];

    // PostgreSQL versions
    const postgresVersions = availableVersions?.database?.versions || ['16', '17', '18'];

    // Authentication strategies
    const authStrategies = [
        { value: 'jwt', label: 'JWT (JSON Web Tokens)', description: 'Stateless authentication with token-based approach' },
        { value: 'session', label: 'Session/Cookie', description: 'Traditional server-side session management' },
        { value: 'oauth2', label: 'OAuth 2.0 / OIDC', description: 'External identity provider integration' },
    ];

    // Report strategies
    const reportStrategies = [
        { value: 'pdf', label: 'PDF Reports', description: 'Generate PDF reports using iText or similar' },
        { value: 'excel', label: 'Excel Reports', description: 'Generate Excel reports with Apache POI' },
        { value: 'html', label: 'HTML Reports', description: 'Web-based reports with print-to-PDF' },
    ];

    // Migration strategies
    const migrationStrategies = [
        { value: 'flyway', label: 'Flyway', description: 'Versioned database migrations (recommended)' },
        { value: 'liquibase', label: 'Liquibase', description: 'Database schema change management' },
        { value: 'hibernate', label: 'Hibernate Auto DDL', description: 'Automatic schema generation (dev only)' },
    ];

    return (
        <div>
            <div className="card-header">
                <h2 className="card-title">Conversion Configuration</h2>
                <p className="card-subtitle">
                    Configure the target technology stack and project settings for the generated application.
                </p>
            </div>

            <div className="grid grid-2" style={{ gap: '1.5rem' }}>
                {/* Project Settings */}
                <div className="card">
                    <h3 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '1rem', color: 'var(--color-primary)' }}>
                        Project Settings
                    </h3>

                    <div className="form-group">
                        <label className="form-label">Project Name</label>
                        <input
                            type="text"
                            className="form-control"
                            value={localConfig.project_name}
                            onChange={(e) => handleConfigChange('project_name', e.target.value)}
                            placeholder="ConvertedApplication"
                        />
                        <p className="form-hint">Used as the application name in generated code and project directory</p>
                    </div>

                    <div className="form-group">
                        <label className="form-label">Base Java Package</label>
                        <input
                            type="text"
                            className="form-control"
                            value={localConfig.base_package}
                            onChange={(e) => handleConfigChange('base_package', e.target.value)}
                            placeholder="com.generated.app"
                        />
                        <p className="form-hint">Root package for all generated Java classes</p>
                    </div>
                </div>

                {/* Backend Configuration */}
                <div className="card">
                    <h3 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '1rem', color: 'var(--color-primary)' }}>
                        Backend (Spring Boot)
                    </h3>

                    <div className="form-group">
                        <label className="form-label">Framework</label>
                        <select
                            className="form-control"
                            value="spring-boot"
                            disabled
                        >
                            <option>Spring Boot</option>
                        </select>
                        <p className="form-hint">Spring Boot is the only supported backend framework</p>
                    </div>

                    <div className="form-group">
                        <label className="form-label">Spring Boot Version</label>
                        <select
                            className="form-control"
                            value={localConfig.spring_boot_version}
                            onChange={(e) => handleConfigChange('spring_boot_version', e.target.value)}
                        >
                            {springBootVersions.map(v => (
                                <option key={v} value={v}>{v}</option>
                            ))}
                        </select>
                    </div>

                    <div className="form-group">
                        <label className="form-label">Java Version</label>
                        <select
                            className="form-control"
                            value={localConfig.java_version}
                            onChange={(e) => handleConfigChange('java_version', parseInt(e.target.value, 10))}
                        >
                            {javaVersions.map(v => (
                                <option key={v.value} value={v.value}>{v.label}</option>
                            ))}
                        </select>
                        <p className="form-hint">Java 25 LTS is recommended for new projects</p>
                    </div>
                </div>

                {/* Frontend Configuration */}
                <div className="card">
                    <h3 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '1rem', color: 'var(--color-primary)' }}>
                        Frontend (React)
                    </h3>

                    <div className="form-group">
                        <label className="form-label">Framework</label>
                        <select
                            className="form-control"
                            value="react"
                            disabled
                        >
                            <option>React</option>
                        </select>
                        <p className="form-hint">React 19 with Vite is the standard stack</p>
                    </div>

                    <div className="form-group">
                        <label className="form-label">React Version</label>
                        <select
                            className="form-control"
                            value={localConfig.react_version}
                            onChange={(e) => handleConfigChange('react_version', e.target.value)}
                        >
                            {reactVersions.map(v => (
                                <option key={v} value={v}>{v}</option>
                            ))}
                        </select>
                    </div>

                    <div className="form-group">
                        <label className="form-label">Node.js Version</label>
                        <select
                            className="form-control"
                            value={localConfig.node_version}
                            onChange={(e) => handleConfigChange('node_version', parseInt(e.target.value, 10))}
                        >
                            {nodeVersions.map(v => (
                                <option key={v} value={v}>{v} {v === 24 ? '(LTS)' : ''}</option>
                            ))}
                        </select>
                        <p className="form-hint">Node 24 LTS is the recommended version</p>
                    </div>

                    <div className="form-group">
                        <label className="form-label">Build Tool</label>
                        <select
                            className="form-control"
                            value="vite"
                            disabled
                        >
                            <option>Vite 8.1+</option>
                        </select>
                    </div>
                </div>

                {/* Database Configuration */}
                <div className="card">
                    <h3 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '1rem', color: 'var(--color-primary)' }}>
                        Database (PostgreSQL)
                    </h3>

                    <div className="form-group">
                        <label className="form-label">Database Engine</label>
                        <select
                            className="form-control"
                            value="postgresql"
                            disabled
                        >
                            <option>PostgreSQL</option>
                        </select>
                        <p className="form-hint">PostgreSQL is the target database</p>
                    </div>

                    <div className="form-group">
                        <label className="form-label">PostgreSQL Version</label>
                        <select
                            className="form-control"
                            value={localConfig.postgres_version}
                            onChange={(e) => handleConfigChange('postgres_version', e.target.value)}
                        >
                            {postgresVersions.map(v => (
                                <option key={v} value={v}>{v} {v === '18' ? '(Latest)' : ''}</option>
                            ))}
                        </select>
                        <p className="form-hint">PostgreSQL 18 is the current major release</p>
                    </div>
                </div>

                {/* Authentication Strategy */}
                <div className="card">
                    <h3 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '1rem', color: 'var(--color-primary)' }}>
                        Authentication Strategy
                    </h3>

                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                        {authStrategies.map((strategy) => (
                            <label
                                key={strategy.value}
                                style={{
                                    display: 'flex',
                                    alignItems: 'flex-start',
                                    gap: '0.75rem',
                                    padding: '1rem',
                                    border: `2px solid ${localConfig.authentication_strategy === strategy.value ? 'var(--color-primary)' : 'var(--color-border)'}`,
                                    borderRadius: 'var(--radius-md)',
                                    cursor: 'pointer',
                                    background: localConfig.authentication_strategy === strategy.value ? 'rgba(59, 130, 246, 0.05)' : 'transparent',
                                    transition: 'all var(--transition-fast)',
                                }}
                            >
                                <input
                                    type="radio"
                                    name="authentication_strategy"
                                    value={strategy.value}
                                    checked={localConfig.authentication_strategy === strategy.value}
                                    onChange={() => handleConfigChange('authentication_strategy', strategy.value)}
                                    style={{ marginTop: '0.125rem' }}
                                />
                                <div>
                                    <div style={{ fontWeight: 500 }}>{strategy.label}</div>
                                    <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>{strategy.description}</div>
                                </div>
                            </label>
                        ))}
                    </div>
                </div>

                {/* Report & Migration Strategy */}
                <div className="card">
                    <h3 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '1rem', color: 'var(--color-primary)' }}>
                        Reports & Migration
                    </h3>

                    <div className="form-group">
                        <label className="form-label">Report Strategy</label>
                        <select
                            className="form-control"
                            value={localConfig.report_strategy}
                            onChange={(e) => handleConfigChange('report_strategy', e.target.value)}
                        >
                            {reportStrategies.map(s => (
                                <option key={s.value} value={s.value}>{s.label}</option>
                            ))}
                        </select>
                        <p className="form-hint">{reportStrategies.find(s => s.value === localConfig.report_strategy)?.description}</p>
                    </div>

                    <div className="form-group">
                        <label className="form-label">Migration Strategy</label>
                        <select
                            className="form-control"
                            value={localConfig.migration_strategy}
                            onChange={(e) => handleConfigChange('migration_strategy', e.target.value)}
                        >
                            {migrationStrategies.map(s => (
                                <option key={s.value} value={s.value}>{s.label}</option>
                            ))}
                        </select>
                        <p className="form-hint">{migrationStrategies.find(s => s.value === localConfig.migration_strategy)?.description}</p>
                    </div>
                </div>
            </div>

            {/* Preview Summary */}
            <div className="card" style={{ marginTop: '1.5rem' }}>
                <h3 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '1rem' }}>Configuration Summary</h3>
                <div className="grid grid-4">
                    <div className="stat-card">
                        <div className="stat-card-value">{localConfig.project_name}</div>
                        <div className="stat-card-label">Project Name</div>
                    </div>
                    <div className="stat-card">
                        <div className="stat-card-value">{localConfig.spring_boot_version}</div>
                        <div className="stat-card-label">Spring Boot</div>
                    </div>
                    <div className="stat-card">
                        <div className="stat-card-value">Java {localConfig.java_version}</div>
                        <div className="stat-card-label">Java Version</div>
                    </div>
                    <div className="stat-card">
                        <div className="stat-card-value">React {localConfig.react_version}</div>
                        <div className="stat-card-label">React Version</div>
                    </div>
                    <div className="stat-card">
                        <div className="stat-card-value">Node {localConfig.node_version}</div>
                        <div className="stat-card-label">Node.js</div>
                    </div>
                    <div className="stat-card">
                        <div className="stat-card-value">PostgreSQL {localConfig.postgres_version}</div>
                        <div className="stat-card-label">Database</div>
                    </div>
                    <div className="stat-card">
                        <div className="stat-card-value">{localConfig.authentication_strategy.toUpperCase()}</div>
                        <div className="stat-card-label">Auth Strategy</div>
                    </div>
                    <div className="stat-card">
                        <div className="stat-card-value">{localConfig.migration_strategy}</div>
                        <div className="stat-card-label">Migration</div>
                    </div>
                </div>
            </div>
        </div>
    );
}