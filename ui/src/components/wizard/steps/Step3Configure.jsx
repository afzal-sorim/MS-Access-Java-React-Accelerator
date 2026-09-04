import React, { useEffect, useState } from 'react';
import { useWizard } from '../../../context/WizardContext';

/**
 * Step 3: Conversion Configuration
 */
export default function Step3Configure() {
    const { state, actions } = useWizard();
    const { config, availableVersions } = state;
    const [localConfig, setLocalConfig] = useState(config);
    const [activeSection, setActiveSection] = useState('backend');

    // Sync local config with context
    useEffect(() => {
        setLocalConfig(config);
    }, [config]);

    const handleConfigChange = (key, value) => {
        const newConfig = { ...localConfig, [key]: value };
        setLocalConfig(newConfig);
        actions.updateConfig(newConfig);
    };

    // Java versions
    const javaVersions = [
        { value: 17, label: '17 LTS' },
        { value: 21, label: '21 LTS' },
        { value: 25, label: '25 LTS (Recommended)' },
    ];

    // Version lists
    const springBootVersions = availableVersions?.backend?.versions || ['4.1.0'];
    const reactVersions = availableVersions?.frontend?.versions || ['19.2.8'];
    const nodeVersions = availableVersions?.frontend?.node_versions || [20, 22, 24];
    const postgresVersions = availableVersions?.database?.versions || ['16', '17', '18'];

    return (
        <div className="strategy-page" style={{ paddingBottom: '2rem' }}>
            <div className="card-header strategy-heading" style={{ marginBottom: '1.5rem' }}>
                <h2 className="card-title">Conversion Configuration</h2>
                <p className="card-subtitle">
                    Choose the target stack for the generated application. Each choice below updates the build plan.
                </p>
            </div>
            
            {/* Configuration Summary Banner — Stepper style */}
            <div style={{ marginTop: '1rem', padding: '1.5rem 2rem 1rem', borderRadius: '16px', background: '#f8fafc', border: '1px solid #e2e8f0' }}>
                <h3 style={{ fontSize: '0.75rem', fontWeight: 800, color: '#3730a3', marginBottom: '1.75rem', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                    ● Configuration Summary
                </h3>
                <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', position: 'relative' }}>

                    {[
                        { icon: '🛡️', value: localConfig.project_name, label: 'Project Name', color: '#4338ca', bg: '#e0e7ff' },
                        { icon: '⚙️', value: localConfig.spring_boot_version, label: 'Spring Boot', color: '#0f766e', bg: '#ccfbf1' },
                        { icon: '☕', value: `Java ${localConfig.java_version}`, label: 'Java Version', color: '#b45309', bg: '#fef3c7' },
                        { icon: '⚛️', value: `React ${localConfig.react_version}`, label: 'React Version', color: '#0369a1', bg: '#e0f2fe' },
                        { icon: '🟢', value: `Node ${localConfig.node_version}`, label: 'Node.js', color: '#15803d', bg: '#dcfce7' },
                        { icon: '🐘', value: `PostgreSQL ${localConfig.postgres_version}`, label: 'Database', color: '#6d28d9', bg: '#ede9fe' },
                        { icon: '🔐', value: (localConfig.authentication_strategy || 'JWT').toUpperCase(), label: 'Auth Strategy', color: '#be123c', bg: '#ffe4e6' },
                        { icon: '🔄', value: (localConfig.migration_strategy || 'flyway').charAt(0).toUpperCase() + (localConfig.migration_strategy || 'flyway').slice(1), label: 'Migration', color: '#0f766e', bg: '#ccfbf1' },
                    ].map((item, idx, arr) => (
                        <div key={item.label} style={{ display: 'flex', alignItems: 'flex-start', flex: 1 }}>
                            {/* Step Item */}
                            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center', flex: 1 }}>
                                {/* Circle */}
                                <div style={{
                                    width: '54px', height: '54px', borderRadius: '50%',
                                    background: item.bg, display: 'flex', alignItems: 'center', justifyContent: 'center',
                                    fontSize: '1.4rem', marginBottom: '0.6rem',
                                    border: `2px solid ${item.color}22`,
                                    boxShadow: `0 4px 12px ${item.color}22`
                                }}>
                                    {item.icon}
                                </div>
                                {/* Value */}
                                <div style={{ fontSize: '0.8rem', fontWeight: 700, color: item.color, marginBottom: '2px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: '90px' }}>
                                    {item.value}
                                </div>
                                {/* Label */}
                                <div style={{ fontSize: '0.65rem', color: '#94a3b8', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                                    {item.label}
                                </div>
                            </div>

                            {/* Arrow connector */}
                            {idx < arr.length - 1 && (
                                <div style={{ display: 'flex', alignItems: 'center', paddingTop: '16px', color: '#cbd5e1', flexShrink: 0 }}>
                                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                        <polyline points="9 18 15 12 9 6" />
                                    </svg>
                                </div>
                            )}
                        </div>
                    ))}
                </div>
            </div>

            <div className="strategy-layout" style={{ display: 'grid', gridTemplateColumns: '280px minmax(0, 1fr)', gap: 0, marginTop: '1.5rem' }}>
                <nav className="strategy-nav" aria-label="Configuration sections">
                    {[
                        ['project', '▤', 'Project settings'],
                        ['backend', '⚙', 'Backend (Spring Boot)'],
                        ['frontend', '◫', 'Frontend (React)'],
                        ['database', '▦', 'Database (PostgreSQL)'],
                        ['auth', '▣', 'Authentication strategy'],
                        ['reports', '↔', 'Reports & migration'],
                    ].map(([key, icon, label]) => (
                        <button
                            key={key}
                            type="button"
                            className={`strategy-nav-item ${activeSection === key ? 'active' : ''}`}
                            onClick={() => setActiveSection(key)}
                        >
                            <span className="strategy-nav-icon">{icon}</span>
                            <span>{label}</span>
                            <span className="strategy-nav-status" aria-hidden="true">●</span>
                        </button>
                    ))}
                </nav>
                <div className="strategy-panel">
                    <div className="strategy-panel-header">
                        <h3>{[
                            ['project', 'Project settings'],
                            ['backend', 'Backend - Spring Boot'],
                            ['frontend', 'Frontend - React'],
                            ['database', 'Database - PostgreSQL'],
                            ['auth', 'Authentication strategy'],
                            ['reports', 'Reports & migration'],
                        ].find(([key]) => key === activeSection)?.[1]}</h3>
                        <p>Configure the selected target for your generated application.</p>
                    </div>
                {/* Project Settings */}
                {activeSection === 'project' && <div className="card" style={{ padding: '1.5rem', borderRadius: '12px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1.5rem', color: '#4338ca' }}>
                        <span style={{ fontSize: '1.25rem' }}>📝</span>
                        <h3 style={{ fontSize: '1rem', fontWeight: 700, margin: 0 }}>Project Settings</h3>
                    </div>

                    <div className="form-group">
                        <label className="form-label" style={{ fontWeight: 600, fontSize: '0.85rem', color: '#64748b' }}>Project Name</label>
                        <input
                            type="text"
                            className="form-control"
                            value={localConfig.project_name}
                            onChange={(e) => handleConfigChange('project_name', e.target.value)}
                            placeholder="ConvertedApplication"
                            style={{ padding: '0.6rem 0.85rem' }}
                        />
                    </div>

                    <div className="form-group" style={{ marginBottom: 0 }}>
                        <label className="form-label" style={{ fontWeight: 600, fontSize: '0.85rem', color: '#64748b' }}>Base Java Package</label>
                        <input
                            type="text"
                            className="form-control"
                            value={localConfig.base_package}
                            onChange={(e) => handleConfigChange('base_package', e.target.value)}
                            placeholder="com.generated.app"
                            style={{ padding: '0.6rem 0.85rem' }}
                        />
                    </div>
                </div>}

                {/* Backend Configuration */}
                {activeSection === 'backend' && <div className="card" style={{ padding: '1.5rem', borderRadius: '12px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1.5rem', color: '#4338ca' }}>
                        <span style={{ fontSize: '1.25rem' }}>☕</span>
                        <h3 style={{ fontSize: '1rem', fontWeight: 700, margin: 0 }}>Backend (Spring Boot)</h3>
                    </div>

                    <div className="form-group" style={{ display: 'grid', gridTemplateColumns: '1fr 1.5fr', alignItems: 'center' }}>
                        <label className="form-label" style={{ fontWeight: 600, fontSize: '0.85rem', color: '#64748b', marginBottom: 0 }}>Framework</label>
                        <select className="form-control" value="spring-boot" disabled style={{ background: '#f8fafc' }}>
                            <option>Spring Boot</option>
                        </select>
                    </div>

                    <div className="form-group" style={{ display: 'grid', gridTemplateColumns: '1fr 1.5fr', alignItems: 'center' }}>
                        <label className="form-label" style={{ fontWeight: 600, fontSize: '0.85rem', color: '#64748b', marginBottom: 0 }}>Spring Boot Version</label>
                        <select
                            className="form-control"
                            value={localConfig.spring_boot_version}
                            onChange={(e) => handleConfigChange('spring_boot_version', e.target.value)}
                        >
                            {springBootVersions.map(v => <option key={v} value={v}>{v}</option>)}
                        </select>
                    </div>

                    <div className="form-group" style={{ display: 'grid', gridTemplateColumns: '1fr 1.5fr', alignItems: 'center', marginBottom: 0 }}>
                        <label className="form-label" style={{ fontWeight: 600, fontSize: '0.85rem', color: '#64748b', marginBottom: 0 }}>Java Version</label>
                        <select
                            className="form-control"
                            value={localConfig.java_version}
                            onChange={(e) => handleConfigChange('java_version', parseInt(e.target.value, 10))}
                        >
                            {javaVersions.map(v => <option key={v.value} value={v.value}>{v.label}</option>)}
                        </select>
                    </div>
                </div>}

                {/* Frontend Configuration */}
                {activeSection === 'frontend' && <div className="card" style={{ padding: '1.5rem', borderRadius: '12px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1.5rem', color: '#4338ca' }}>
                        <span style={{ fontSize: '1.25rem' }}>⚛️</span>
                        <h3 style={{ fontSize: '1rem', fontWeight: 700, margin: 0 }}>Frontend (React)</h3>
                    </div>

                    <div className="form-group" style={{ display: 'grid', gridTemplateColumns: '1fr 1.5fr', alignItems: 'center' }}>
                        <label className="form-label" style={{ fontWeight: 600, fontSize: '0.85rem', color: '#64748b', marginBottom: 0 }}>Framework</label>
                        <select className="form-control" value="react" disabled style={{ background: '#f8fafc' }}>
                            <option>React</option>
                        </select>
                    </div>

                    <div className="form-group" style={{ display: 'grid', gridTemplateColumns: '1fr 1.5fr', alignItems: 'center' }}>
                        <label className="form-label" style={{ fontWeight: 600, fontSize: '0.85rem', color: '#64748b', marginBottom: 0 }}>React Version</label>
                        <select
                            className="form-control"
                            value={localConfig.react_version}
                            onChange={(e) => handleConfigChange('react_version', e.target.value)}
                        >
                            {reactVersions.map(v => <option key={v} value={v}>{v}</option>)}
                        </select>
                    </div>

                    <div className="form-group" style={{ display: 'grid', gridTemplateColumns: '1fr 1.5fr', alignItems: 'center' }}>
                        <label className="form-label" style={{ fontWeight: 600, fontSize: '0.85rem', color: '#64748b', marginBottom: 0 }}>Node.js Version</label>
                        <select
                            className="form-control"
                            value={localConfig.node_version}
                            onChange={(e) => handleConfigChange('node_version', parseInt(e.target.value, 10))}
                        >
                            {nodeVersions.map(v => <option key={v} value={v}>{v} {v === 24 ? '(LTS)' : ''}</option>)}
                        </select>
                    </div>

                    <div className="form-group" style={{ display: 'grid', gridTemplateColumns: '1fr 1.5fr', alignItems: 'center', marginBottom: 0 }}>
                        <label className="form-label" style={{ fontWeight: 600, fontSize: '0.85rem', color: '#64748b', marginBottom: 0 }}>Build Tool</label>
                        <select className="form-control" value="vite" disabled style={{ background: '#f8fafc' }}>
                            <option>Vite 8.1+</option>
                        </select>
                    </div>
                </div>}

                {/* Database Configuration */}
                {activeSection === 'database' && <div className="card" style={{ padding: '1.5rem', borderRadius: '12px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1.5rem', color: '#4338ca' }}>
                        <span style={{ fontSize: '1.25rem' }}>🗄️</span>
                        <h3 style={{ fontSize: '1rem', fontWeight: 700, margin: 0 }}>Database (PostgreSQL)</h3>
                    </div>

                    <div className="form-group" style={{ display: 'grid', gridTemplateColumns: '1fr 1.5fr', alignItems: 'center' }}>
                        <label className="form-label" style={{ fontWeight: 600, fontSize: '0.85rem', color: '#64748b', marginBottom: 0 }}>Database Engine</label>
                        <select className="form-control" value="postgresql" disabled style={{ background: '#f8fafc' }}>
                            <option>PostgreSQL</option>
                        </select>
                    </div>

                    <div className="form-group" style={{ display: 'grid', gridTemplateColumns: '1fr 1.5fr', alignItems: 'center', marginBottom: 0 }}>
                        <label className="form-label" style={{ fontWeight: 600, fontSize: '0.85rem', color: '#64748b', marginBottom: 0 }}>PostgreSQL Version</label>
                        <select
                            className="form-control"
                            value={localConfig.postgres_version}
                            onChange={(e) => handleConfigChange('postgres_version', e.target.value)}
                        >
                            {postgresVersions.map(v => <option key={v} value={v}>{v} {v === '18' ? '(Latest)' : ''}</option>)}
                        </select>
                    </div>
                </div>}

                {/* Authentication Strategy */}
                {activeSection === 'auth' && <div className="card" style={{ padding: '1.5rem', borderRadius: '12px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1.5rem', color: '#4338ca' }}>
                        <span style={{ fontSize: '1.25rem' }}>🔗</span>
                        <h3 style={{ fontSize: '1rem', fontWeight: 700, margin: 0 }}>Authentication Strategy</h3>
                    </div>

                    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                        {[
                            { value: 'jwt', label: 'JWT (JSON Web Tokens)' },
                            { value: 'session', label: 'Session/Cookie' },
                            { value: 'oauth2', label: 'OAuth 2.0 / OIDC' }
                        ].map((strategy) => (
                            <label key={strategy.value} style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', cursor: 'pointer' }}>
                                <input
                                    type="radio"
                                    name="auth"
                                    checked={localConfig.authentication_strategy === strategy.value}
                                    onChange={() => handleConfigChange('authentication_strategy', strategy.value)}
                                    style={{ width: '18px', height: '18px', accentColor: '#4338ca' }}
                                />
                                <span style={{ fontSize: '0.9rem', fontWeight: 500, color: '#1e293b' }}>{strategy.label}</span>
                            </label>
                        ))}
                    </div>
                </div>}

                {/* Reports & Migration Strategy */}
                {activeSection === 'reports' && <div className="card" style={{ padding: '1.5rem', borderRadius: '12px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1.5rem', color: '#4338ca' }}>
                        <span style={{ fontSize: '1.25rem' }}>🔄</span>
                        <h3 style={{ fontSize: '1rem', fontWeight: 700, margin: 0 }}>Reports & Migration</h3>
                    </div>

                    <div className="form-group" style={{ display: 'grid', gridTemplateColumns: '1fr 1.5fr', alignItems: 'center' }}>
                        <label className="form-label" style={{ fontWeight: 600, fontSize: '0.85rem', color: '#64748b', marginBottom: 0 }}>Report Strategy</label>
                        <select
                            className="form-control"
                            value={localConfig.report_strategy}
                            onChange={(e) => handleConfigChange('report_strategy', e.target.value)}
                        >
                            <option value="pdf">PDF Reports</option>
                            <option value="excel">Excel Reports</option>
                            <option value="html">HTML Reports</option>
                        </select>
                    </div>

                    <div className="form-group" style={{ display: 'grid', gridTemplateColumns: '1fr 1.5fr', alignItems: 'center', marginBottom: 0 }}>
                        <label className="form-label" style={{ fontWeight: 600, fontSize: '0.85rem', color: '#64748b', marginBottom: 0 }}>Migration Strategy</label>
                        <select
                            className="form-control"
                            value={localConfig.migration_strategy}
                            onChange={(e) => handleConfigChange('migration_strategy', e.target.value)}
                        >
                            <option value="flyway">Flyway</option>
                            <option value="liquibase">Liquibase</option>
                            <option value="hibernate">Hibernate Auto</option>
                        </select>
                    </div>
                </div>}
            </div>
            </div>

        </div>
    );
}