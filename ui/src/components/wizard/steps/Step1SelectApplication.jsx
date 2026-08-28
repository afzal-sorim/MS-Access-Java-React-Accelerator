import React, { useRef, useCallback, useState, useEffect } from 'react';
import { useWizard } from '../../../context/WizardContext';
import { formatFileSize } from '../../../utils/helpers';
import {
    getLocalAccessCapability,
    listLocalAccessSources,
    validateLocalPath,
} from '../../../services/api';

/**
 * Step 1: Select Access Application
 * Per spec section 47:
 * - Allow drag/drop .accdb, browse, .mdb, project package, frontend/backend pairing
 * - Show: file name, file size, Access format, detected version, encryption status
 *
 * Two input modes (spec sections 4-5):
 * - 'upload': post the file through multipart, for a database on the user's
 *   own machine when that differs from the backend host.
 * - 'local': point the backend at a database already on the machine running
 *   MS Access. This is the preferred Windows path - no upload round-trip, and
 *   it can pick up whatever is currently open in Access.
 */
export default function Step1SelectApplication() {
    const { state, actions } = useWizard();
    const { sourceMode, selectedFile, fileMetadata, localSource } = state;
    const fileInputRef = useRef(null);
    const [isDragging, setIsDragging] = useState(false);
    const [fileError, setFileError] = useState(null);

    // --- Direct-from-local state
    const [capability, setCapability] = useState(null);
    const [sources, setSources] = useState({ open: [], recent: [], errors: [] });
    const [loadingSources, setLoadingSources] = useState(false);
    const [manualPath, setManualPath] = useState('');
    const [localError, setLocalError] = useState(null);
    const [validating, setValidating] = useState(false);

    const handleFileSelect = useCallback((file) => {
        if (!file) return;

        // Validate file type
        const validExtensions = ['.accdb', '.mdb'];
        const fileName = file.name.toLowerCase();
        const isValid = validExtensions.some(ext => fileName.endsWith(ext));

        if (!isValid) {
            setFileError('Please select a valid Microsoft Access file (.accdb or .mdb)');
            return;
        }

        setFileError(null);
        actions.setFile(file);

        // Extract basic metadata
        const metadata = {
            name: file.name,
            size: file.size,
            formattedSize: formatFileSize(file.size),
            extension: fileName.endsWith('.accdb') ? '.accdb' : '.mdb',
            format: fileName.endsWith('.accdb') ? 'Access 2007-2016+ (.accdb)' : 'Access 2000-2003 (.mdb)',
            lastModified: new Date(file.lastModified).toLocaleDateString(),
        };

        actions.setFileMetadata(metadata);
    }, [actions]);

    const handleDragOver = useCallback((e) => {
        e.preventDefault();
        e.stopPropagation();
        setIsDragging(true);
    }, []);

    const handleDragLeave = useCallback((e) => {
        e.preventDefault();
        e.stopPropagation();
        setIsDragging(false);
    }, []);

    const handleDrop = useCallback((e) => {
        e.preventDefault();
        e.stopPropagation();
        setIsDragging(false);

        const files = e.dataTransfer.files;
        if (files.length > 0) {
            handleFileSelect(files[0]);
        }
    }, [handleFileSelect]);

    const handleFileInputChange = useCallback((e) => {
        const file = e.target.files[0];
        if (file) {
            handleFileSelect(file);
        }
    }, [handleFileSelect]);

    const handleRemoveFile = useCallback(() => {
        actions.clearFile();
        setFileError(null);
        if (fileInputRef.current) {
            fileInputRef.current.value = '';
        }
    }, [actions]);

    // ---------------------------------------------------------------- local mode

    // Probe capability once, on mount. Deliberately not gated on sourceMode so
    // the toggle can show up-front whether the direct mode will work.
    useEffect(() => {
        let cancelled = false;
        getLocalAccessCapability()
            .then(result => { if (!cancelled) setCapability(result); })
            .catch(err => {
                if (!cancelled) {
                    setCapability({ available: false, reason: err.message });
                }
            });
        return () => { cancelled = true; };
    }, []);

    const refreshSources = useCallback(async () => {
        setLoadingSources(true);
        setLocalError(null);
        try {
            setSources(await listLocalAccessSources());
        } catch (err) {
            setLocalError(err.message);
        } finally {
            setLoadingSources(false);
        }
    }, []);

    // Load the discovery lists when the user switches to the direct mode.
    // Deliberately not gated on capability.available: the recent-files list and
    // manual path entry are registry/filesystem reads that work even when COM
    // automation is unavailable, and hiding them on a failed probe left the
    // pane empty with nothing the user could do.
    useEffect(() => {
        if (sourceMode === 'local' && capability !== null) {
            refreshSources();
        }
    }, [sourceMode, capability, refreshSources]);

    // Validate a path and, on success, record it as the wizard's source.
    const selectLocalPath = useCallback(async (path) => {
        setValidating(true);
        setLocalError(null);
        try {
            const info = await validateLocalPath(path);
            actions.setLocalSource(info);
            setManualPath(info.path);
        } catch (err) {
            setLocalError(err.message);
            actions.setLocalSource(null);
        } finally {
            setValidating(false);
        }
    }, [actions]);

    const handleModeChange = useCallback((mode) => {
        if (mode === sourceMode) return;
        setFileError(null);
        setLocalError(null);
        actions.setSourceMode(mode);
        if (fileInputRef.current) {
            fileInputRef.current.value = '';
        }
    }, [sourceMode, actions]);

    const renderSourceRow = (source, key) => (
        <button
            key={key}
            className="btn btn-secondary"
            onClick={() => selectLocalPath(source.path)}
            disabled={validating}
            style={{
                display: 'flex', alignItems: 'center', gap: '0.75rem',
                width: '100%', textAlign: 'left', justifyContent: 'flex-start',
                padding: '0.75rem', marginBottom: '0.5rem',
                border: localSource?.path === source.path
                    ? '2px solid var(--color-success)' : '1px solid var(--color-border)',
            }}
        >
            <span style={{ fontSize: '1.5rem' }}>
                {source.extension === '.accdb' ? '🗃️' : '📄'}
            </span>
            <span style={{ flex: 1, minWidth: 0 }}>
                <span style={{ display: 'block', fontWeight: 600, fontSize: '0.9375rem' }}>
                    {source.name}
                </span>
                <span style={{
                    display: 'block', fontSize: '0.75rem',
                    color: 'var(--color-text-muted)',
                    overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                }}>
                    {source.path}
                </span>
            </span>
            {source.formatted_size && (
                <span style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>
                    {source.formatted_size}
                </span>
            )}
        </button>
    );

    return (
        <div>
            <div className="card-header">
                <h2 className="card-title">Select Access Application</h2>
                <p className="card-subtitle">
                    Choose the Microsoft Access database to convert. Upload a file, or read it
                    directly from MS Access on this machine.
                </p>
            </div>

            {/* Input mode toggle */}
            <div style={{ display: 'flex', gap: '0.75rem', marginBottom: '1.5rem', flexWrap: 'wrap' }}>
                <button
                    className={`btn ${sourceMode === 'upload' ? 'btn-primary' : 'btn-secondary'}`}
                    onClick={() => handleModeChange('upload')}
                >
                    📤 Upload a file
                </button>
                <button
                    className={`btn ${sourceMode === 'local' ? 'btn-primary' : 'btn-secondary'}`}
                    onClick={() => handleModeChange('local')}
                    title={capability && !capability.available ? capability.reason : undefined}
                >
                    🖥️ Direct from local MS Access
                </button>
            </div>

            {/* ============================================ UPLOAD MODE */}
            {sourceMode === 'upload' && (
                <>
                    {fileError && (
                        <div className="alert alert-danger" style={{ marginBottom: '1.5rem' }}>
                            {fileError}
                        </div>
                    )}

                    {!selectedFile ? (
                        <div
                            className={`dropzone ${isDragging ? 'dragover' : ''}`}
                            onDragOver={handleDragOver}
                            onDragLeave={handleDragLeave}
                            onDrop={handleDrop}
                            onClick={() => fileInputRef.current?.click()}
                            role="button"
                            tabIndex={0}
                            onKeyDown={(e) => e.key === 'Enter' && fileInputRef.current?.click()}
                        >
                            <input
                                ref={fileInputRef}
                                type="file"
                                accept=".accdb,.mdb"
                                onChange={handleFileInputChange}
                                style={{ display: 'none' }}
                            />

                            <div className="dropzone-icon">📁</div>
                            <p className="dropzone-text">Drag and drop your Access file here</p>
                            <p className="dropzone-text">or click to browse</p>
                            <p className="dropzone-hint">
                                Supported formats: <strong>.accdb</strong> (Access 2007+) or <strong>.mdb</strong> (Access 2000-2003)
                            </p>
                        </div>
                    ) : (
                        <div className="card" style={{ border: '2px solid var(--color-success)', background: '#f0fdf4' }}>
                            <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '1rem', flexWrap: 'wrap' }}>
                                <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                                    <div style={{ fontSize: '3rem' }}>
                                        {fileMetadata?.extension === '.accdb' ? '🗃️' : '📄'}
                                    </div>
                                    <div>
                                        <h3 style={{ fontSize: '1.125rem', fontWeight: 600 }}>{fileMetadata?.name}</h3>
                                        <p style={{ color: 'var(--color-text-muted)', fontSize: '0.875rem' }}>
                                            {fileMetadata?.formattedSize} • {fileMetadata?.format}
                                        </p>
                                    </div>
                                </div>
                                <button
                                    className="btn btn-secondary btn-sm"
                                    onClick={handleRemoveFile}
                                >
                                    Remove
                                </button>
                            </div>

                            {fileMetadata && (
                                <div className="grid grid-3" style={{ marginTop: '1.5rem', paddingTop: '1.5rem', borderTop: '1px solid var(--color-border)' }}>
                                    <div className="stat-card">
                                        <div className="stat-card-value">{fileMetadata.formattedSize}</div>
                                        <div className="stat-card-label">File Size</div>
                                    </div>
                                    <div className="stat-card">
                                        <div className="stat-card-value">{fileMetadata.format.split(' ')[0]}</div>
                                        <div className="stat-card-label">Access Format</div>
                                    </div>
                                    <div className="stat-card">
                                        <div className="stat-card-value">{fileMetadata.lastModified}</div>
                                        <div className="stat-card-label">Last Modified</div>
                                    </div>
                                </div>
                            )}

                            <div className="alert alert-info" style={{ marginTop: '1.5rem' }}>
                                <strong>Note:</strong> For split databases (frontend/backend), select the frontend .accdb file.
                                The converter will automatically detect linked backend tables. For project packages,
                                select the main frontend file.
                            </div>
                        </div>
                    )}

                    {!selectedFile && (
                        <div style={{ marginTop: '1.5rem', padding: '1rem', background: 'var(--color-bg-alt)', borderRadius: 'var(--radius-md)' }}>
                            <h4 style={{ fontSize: '0.875rem', fontWeight: 600, marginBottom: '0.5rem' }}>Input Modes Supported:</h4>
                            <ul style={{ fontSize: '0.8125rem', color: 'var(--color-text-muted)', paddingLeft: '1.25rem', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '0.25rem' }}>
                                <li>Single Access file (.accdb / .mdb)</li>
                                <li>Split application: Frontend + Backend</li>
                                <li>Access project package</li>
                                <li>Source export package</li>
                            </ul>
                        </div>
                    )}
                </>
            )}

            {/* ============================================ LOCAL DIRECT MODE */}
            {sourceMode === 'local' && (
                <>
                    {/* Capability banner */}
                    {capability === null && (
                        <div className="alert alert-info" style={{ marginBottom: '1.5rem' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                                <div className="spinner" style={{ width: 20, height: 20, borderWidth: 2 }} />
                                <span>Checking for MS Access on the converter machine...</span>
                            </div>
                        </div>
                    )}

                    {capability && !capability.available && (
                        <div className="alert alert-warning" style={{ marginBottom: '1.5rem' }}>
                            <strong>MS Access COM automation not detected.</strong>
                            <div style={{ marginTop: '0.5rem', fontSize: '0.875rem' }}>
                                {capability.reason}
                            </div>
                            <div style={{ marginTop: '0.5rem', fontSize: '0.875rem' }}>
                                You can still pick a database below, but extraction will fail
                                unless MS Access is available on the converter machine.
                            </div>
                        </div>
                    )}

                    {capability?.available && (
                        <div className="alert alert-success" style={{ marginBottom: '1.5rem' }}>
                            <strong>MS Access detected</strong>
                            {capability.access_version && ` (version ${capability.access_version})`}
                            {capability.access_running
                                ? ' — currently running.'
                                : ' — installed and available.'}
                        </div>
                    )}

                    {localError && (
                        <div className="alert alert-danger" style={{ marginBottom: '1.5rem' }}>
                            {localError}
                        </div>
                    )}

                    {sources.errors?.map((err, i) => (
                        <div key={i} className="alert alert-warning" style={{ marginBottom: '1rem' }}>
                            {err}
                        </div>
                    ))}

                    {capability !== null && (
                        <>
                            {/* Currently open in Access */}
                            {sources.open?.length > 0 && (
                                <div style={{ marginBottom: '1.5rem' }}>
                                    <h4 style={{ fontSize: '0.875rem', fontWeight: 600, marginBottom: '0.75rem' }}>
                                        Currently open in MS Access
                                    </h4>
                                    {sources.open.map((s, i) => renderSourceRow(s, `open-${i}`))}
                                </div>
                            )}

                            {/* Recent databases */}
                            <div style={{ marginBottom: '1.5rem' }}>
                                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.75rem' }}>
                                    <h4 style={{ fontSize: '0.875rem', fontWeight: 600 }}>
                                        Recently opened in MS Access
                                    </h4>
                                    <button
                                        className="btn btn-secondary btn-sm"
                                        onClick={refreshSources}
                                        disabled={loadingSources}
                                    >
                                        {loadingSources ? 'Refreshing...' : '↻ Refresh'}
                                    </button>
                                </div>
                                {loadingSources && sources.recent.length === 0 ? (
                                    <p style={{ fontSize: '0.8125rem', color: 'var(--color-text-muted)' }}>
                                        Looking for databases...
                                    </p>
                                ) : sources.recent?.length > 0 ? (
                                    sources.recent.map((s, i) => renderSourceRow(s, `recent-${i}`))
                                ) : (
                                    <p style={{ fontSize: '0.8125rem', color: 'var(--color-text-muted)' }}>
                                        No recent databases found. Enter a full path below instead.
                                    </p>
                                )}
                            </div>

                            {/* Manual path entry */}
                            <div style={{ marginBottom: '1.5rem' }}>
                                <h4 style={{ fontSize: '0.875rem', fontWeight: 600, marginBottom: '0.75rem' }}>
                                    Or enter a full path on the converter machine
                                </h4>
                                <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                                    <input
                                        type="text"
                                        className="form-control"
                                        placeholder="C:\path\to\YourDatabase.accdb"
                                        value={manualPath}
                                        onChange={(e) => setManualPath(e.target.value)}
                                        onKeyDown={(e) => {
                                            if (e.key === 'Enter' && manualPath.trim()) {
                                                selectLocalPath(manualPath.trim());
                                            }
                                        }}
                                        style={{ flex: 1, minWidth: 260 }}
                                    />
                                    <button
                                        className="btn btn-primary"
                                        onClick={() => selectLocalPath(manualPath.trim())}
                                        disabled={validating || !manualPath.trim()}
                                    >
                                        {validating ? 'Checking...' : 'Validate'}
                                    </button>
                                </div>
                            </div>
                        </>
                    )}

                    {/* Selected local source */}
                    {localSource && (
                        <div className="card" style={{ border: '2px solid var(--color-success)', background: '#f0fdf4' }}>
                            <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '1rem', flexWrap: 'wrap' }}>
                                <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                                    <div style={{ fontSize: '3rem' }}>
                                        {localSource.extension === '.accdb' ? '🗃️' : '📄'}
                                    </div>
                                    <div style={{ minWidth: 0 }}>
                                        <h3 style={{ fontSize: '1.125rem', fontWeight: 600 }}>{localSource.name}</h3>
                                        <p style={{ color: 'var(--color-text-muted)', fontSize: '0.875rem' }}>
                                            {localSource.formatted_size} • {localSource.format}
                                        </p>
                                        <p style={{ color: 'var(--color-text-muted)', fontSize: '0.75rem', wordBreak: 'break-all' }}>
                                            {localSource.path}
                                        </p>
                                    </div>
                                </div>
                                <button
                                    className="btn btn-secondary btn-sm"
                                    onClick={() => { actions.setLocalSource(null); setLocalError(null); }}
                                >
                                    Remove
                                </button>
                            </div>

                            <div className="grid grid-3" style={{ marginTop: '1.5rem', paddingTop: '1.5rem', borderTop: '1px solid var(--color-border)' }}>
                                <div className="stat-card">
                                    <div className="stat-card-value">{localSource.formatted_size}</div>
                                    <div className="stat-card-label">File Size</div>
                                </div>
                                <div className="stat-card">
                                    <div className="stat-card-value">{localSource.format.split(' ')[0]}</div>
                                    <div className="stat-card-label">Access Format</div>
                                </div>
                                <div className="stat-card">
                                    <div className="stat-card-value">{localSource.last_modified?.split(' ')[0]}</div>
                                    <div className="stat-card-label">Last Modified</div>
                                </div>
                            </div>

                            {localSource.warnings?.map((w, i) => (
                                <div key={i} className="alert alert-warning" style={{ marginTop: '1rem' }}>
                                    {w}
                                </div>
                            ))}

                            <div className="alert alert-info" style={{ marginTop: '1rem' }}>
                                <strong>Your database is not modified.</strong> Extraction opens forms and
                                VBA modules, which writes to whichever file it opens — so the converter
                                copies this database into its own workspace first and reads the copy.
                            </div>
                        </div>
                    )}
                </>
            )}
        </div>
    );
}
