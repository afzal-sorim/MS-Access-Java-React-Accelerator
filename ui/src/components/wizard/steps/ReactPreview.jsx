import React, { useState, useEffect, useMemo, useCallback } from 'react';
import {
    SandpackProvider,
    SandpackLayout,
    SandpackPreview,
    SandpackCodeEditor,
} from '@codesandbox/sandpack-react';
import { getJobFrontendFiles } from '../../../services/api';

export default function ReactPreview({ jobId }) {
    const [rawFiles, setRawFiles] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [reloadKey, setReloadKey] = useState(0);

    // Toolbar states
    const [device, setDevice] = useState('desktop');
    const [viewMode, setViewMode] = useState('preview');

    const loadData = useCallback(async () => {
        if (!jobId) return;
        setLoading(true);
        setError(null);

        try {
            const fetchedFiles = await getJobFrontendFiles(jobId);
            
            if (!fetchedFiles || Object.keys(fetchedFiles).length === 0) {
                setError('No frontend source files found for this job. Make sure code generation completed.');
            } else {
                setRawFiles(fetchedFiles);
            }
        } catch (err) {
            console.error('Failed to prepare React preview:', err);
            setError(err.message || 'Failed to load frontend files for preview');
        } finally {
            setLoading(false);
        }
    }, [jobId]);

    useEffect(() => {
        loadData();
    }, [loadData, reloadKey]);

    const sandpackFiles = useMemo(() => {
        if (!rawFiles) return null;
        
        const files = { ...rawFiles };

        // For Sandpack's reliable "react" template to work without NodeBox shell bugs,
        // we map the Vite structure to what CRA expects:
        
        // Proxy Sandpack's default /index.js to our real generated Vite entry point
        if (files['/src/main.jsx']) {
            files['/index.js'] = `import "./src/main.jsx";`;
        }
        
        // Blank out Sandpack's default /App.js so it doesn't render "Hello World"
        files['/App.js'] = `export default function App() { return null; }`;
        
        if (files['/index.html']) {
            files['/public/index.html'] = files['/index.html'];
            delete files['/index.html'];
        }

        // We explicitly delete package.json and vite.config.js so Sandpack uses its default
        // reliable browser bundler behavior for the "react" template, passing deps via customSetup.
        delete files['/package.json'];
        delete files['/vite.config.js'];
        
        return files;
    }, [rawFiles]);

    // Device container widths
    const deviceStyles = {
        desktop: { width: '100%', height: '700px', borderRadius: '12px' },
        laptop: { maxWidth: '1024px', width: '100%', height: '680px', borderRadius: '14px', margin: '0 auto', boxShadow: '0 20px 25px -5px rgba(0,0,0,0.15), 0 10px 10px -5px rgba(0,0,0,0.08)' },
        tablet: { maxWidth: '768px', width: '100%', height: '680px', borderRadius: '24px', border: '10px solid #1e293b', margin: '0 auto', boxShadow: '0 25px 35px -5px rgba(0,0,0,0.2)' },
        mobile: { maxWidth: '380px', width: '100%', height: '680px', borderRadius: '36px', border: '12px solid #1e293b', margin: '0 auto', boxShadow: '0 25px 40px -5px rgba(0,0,0,0.25)' },
    };

    if (loading) {
        return (
            <div style={{
                background: '#fff',
                borderRadius: '16px',
                border: '1px solid #e2e8f0',
                padding: '4rem 2rem',
                textAlign: 'center',
                boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.05)',
            }}>
                <div className="spinner" style={{ width: '40px', height: '40px', borderWidth: '3px', margin: '0 auto 1.5rem', borderColor: '#e0e7ff', borderTopColor: '#4f46e5' }} />
                <h3 style={{ fontSize: '1.25rem', fontWeight: 700, color: '#1e293b', margin: '0 0 0.5rem 0' }}>
                    Loading Real Generated UI
                </h3>
                <p style={{ color: '#64748b', fontSize: '0.9rem', maxWidth: '460px', margin: '0 auto 1.5rem', lineHeight: 1.6 }}>
                    Fetching the exact React pages, components, and CSS styles generated for this job...
                </p>
            </div>
        );
    }

    if (error || !sandpackFiles) {
        return (
            <div style={{
                background: '#fff',
                borderRadius: '16px',
                border: '1px solid #fee2e2',
                padding: '3rem 2rem',
                textAlign: 'center',
                boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.05)',
            }}>
                <div style={{ width: '52px', height: '52px', borderRadius: '50%', background: '#fee2e2', color: '#ef4444', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '1.5rem', margin: '0 auto 1rem' }}>
                    ⚠️
                </div>
                <h3 style={{ fontSize: '1.2rem', fontWeight: 700, color: '#991b1b', margin: '0 0 0.5rem 0' }}>
                    Preview Not Ready
                </h3>
                <p style={{ color: '#64748b', fontSize: '0.9rem', maxWidth: '500px', margin: '0 auto 1.5rem' }}>
                    {error || 'Generated frontend components could not be loaded.'}
                </p>
                <button
                    onClick={() => setReloadKey(k => k + 1)}
                    className="btn btn-primary"
                    style={{ padding: '0.6rem 1.5rem' }}
                >
                    🔄 Retry Loading Preview
                </button>
            </div>
        );
    }

    const fileCount = Object.keys(sandpackFiles).length;

    return (
        <div style={{
            background: '#0f172a',
            borderRadius: '18px',
            border: '1px solid #334155',
            overflow: 'hidden',
            boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.3), 0 8px 10px -6px rgba(0, 0, 0, 0.2)',
            marginTop: '1.5rem',
            animation: 'fadeIn 0.3s ease-out',
        }}>
            {/* ── Sleek Glassmorphic Toolbar ── */}
            <div style={{
                background: 'rgba(15, 23, 42, 0.92)',
                backdropFilter: 'blur(12px)',
                padding: '0.85rem 1.5rem',
                borderBottom: '1px solid #334155',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                flexWrap: 'wrap',
                gap: '1rem',
            }}>
                {/* Left: Info badge */}
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.85rem' }}>
                    <div style={{
                        width: '34px',
                        height: '34px',
                        borderRadius: '9px',
                        background: 'linear-gradient(135deg, #0ea5e9, #6366f1)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        fontSize: '1.1rem',
                        boxShadow: '0 4px 10px rgba(99, 102, 241, 0.35)',
                    }}>
                        ⚙️
                    </div>
                    <div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                            <span style={{ fontWeight: 800, fontSize: '0.95rem', color: '#f8fafc', letterSpacing: '-0.01em' }}>
                                Real Generated UI
                            </span>
                        </div>
                        <div style={{ fontSize: '0.72rem', color: '#94a3b8', marginTop: '2px' }}>
                            {fileCount} files loaded · Direct Vite output
                        </div>
                    </div>
                </div>

                {/* Center: Responsive Device Toggles */}
                <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    background: '#1e293b',
                    padding: '3px',
                    borderRadius: '10px',
                    border: '1px solid #334155',
                }}>
                    {[
                        { key: 'desktop', label: 'Desktop', icon: '🖥️' },
                        { key: 'laptop', label: 'Laptop', icon: '💻' },
                        { key: 'tablet', label: 'Tablet', icon: '📱' },
                        { key: 'mobile', label: 'Mobile', icon: '📲' },
                    ].map(d => (
                        <button
                            key={d.key}
                            onClick={() => setDevice(d.key)}
                            style={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: '0.35rem',
                                padding: '0.4rem 0.75rem',
                                border: 'none',
                                borderRadius: '7px',
                                cursor: 'pointer',
                                fontSize: '0.75rem',
                                fontWeight: 600,
                                background: device === d.key ? '#3b82f6' : 'transparent',
                                color: device === d.key ? '#fff' : '#94a3b8',
                                transition: 'all 0.15s ease',
                                boxShadow: device === d.key ? '0 2px 6px rgba(59, 130, 246, 0.4)' : 'none',
                            }}
                        >
                            <span style={{ fontSize: '0.85rem' }}>{d.icon}</span>
                            <span>{d.label}</span>
                        </button>
                    ))}
                </div>

                {/* Right: View Mode & Controls */}
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
                    <div style={{
                        display: 'flex',
                        background: '#1e293b',
                        padding: '3px',
                        borderRadius: '10px',
                        border: '1px solid #334155',
                    }}>
                        {[
                            { key: 'preview', label: 'Preview', icon: '👁️' },
                            { key: 'split', label: 'Split', icon: '◫' },
                            { key: 'code', label: 'Code', icon: '💻' },
                        ].map(m => (
                            <button
                                key={m.key}
                                onClick={() => setViewMode(m.key)}
                                style={{
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: '0.35rem',
                                    padding: '0.4rem 0.75rem',
                                    border: 'none',
                                    borderRadius: '7px',
                                    cursor: 'pointer',
                                    fontSize: '0.75rem',
                                    fontWeight: 600,
                                    background: viewMode === m.key ? '#4f46e5' : 'transparent',
                                    color: viewMode === m.key ? '#fff' : '#94a3b8',
                                    transition: 'all 0.15s ease',
                                    boxShadow: viewMode === m.key ? '0 2px 6px rgba(79, 70, 229, 0.4)' : 'none',
                                }}
                            >
                                <span>{m.icon}</span>
                                <span>{m.label}</span>
                            </button>
                        ))}
                    </div>

                    <button
                        onClick={() => setReloadKey(k => k + 1)}
                        style={{
                            background: '#1e293b',
                            border: '1px solid #334155',
                            borderRadius: '10px',
                            color: '#94a3b8',
                            padding: '0.45rem 0.75rem',
                            cursor: 'pointer',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '0.35rem',
                            fontSize: '0.75rem',
                            fontWeight: 600,
                        }}
                    >
                        <span>↺</span>
                        <span>Reset</span>
                    </button>
                </div>
            </div>

            {/* ── Sandbox Body & Frame ── */}
            <div style={{
                background: '#090d16',
                padding: device === 'desktop' ? '0' : '2rem 1.5rem',
                minHeight: '700px',
                display: 'flex',
                justifyContent: 'center',
                alignItems: 'center',
                overflowX: 'auto',
                transition: 'padding 0.3s ease',
            }}>
                <div style={{
                    ...deviceStyles[device],
                    transition: 'all 0.3s cubic-bezier(0.16, 1, 0.3, 1)',
                    background: '#fff',
                    overflow: 'hidden',
                }}>
                    <SandpackProvider
                        key={`${jobId}-${reloadKey}`}
                        template="react"
                        theme="dark"
                        files={sandpackFiles}
                        customSetup={{
                            dependencies: {
                                "react": "^18.2.0",
                                "react-dom": "^18.2.0",
                                "react-router-dom": "^6.22.3"
                            },
                        }}
                        options={{
                            recompileMode: 'delayed',
                            recompileDelay: 400,
                        }}
                    >
                        <SandpackLayout style={{
                            height: '100%',
                            minHeight: deviceStyles[device].height,
                            border: 'none',
                            borderRadius: device === 'desktop' ? '0' : 'inherit',
                        }}>
                            {(viewMode === 'code' || viewMode === 'split') && (
                                <SandpackCodeEditor
                                    showLineNumbers
                                    showInlineErrors
                                    showTabs
                                    closableTabs
                                    style={{
                                        height: deviceStyles[device].height,
                                        width: viewMode === 'code' ? '100%' : '48%',
                                    }}
                                />
                            )}
                            {(viewMode === 'preview' || viewMode === 'split') && (
                                <SandpackPreview
                                    showNavigator
                                    showRefreshButton
                                    showOpenInCodeSandbox={false}
                                    style={{
                                        height: deviceStyles[device].height,
                                        width: viewMode === 'preview' ? '100%' : '52%',
                                        background: '#fff',
                                    }}
                                />
                            )}
                        </SandpackLayout>
                    </SandpackProvider>
                </div>
            </div>
        </div>
    );
}
