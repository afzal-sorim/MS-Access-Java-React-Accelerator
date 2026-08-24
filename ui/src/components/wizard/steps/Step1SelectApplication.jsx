import React, { useRef, useCallback, useState } from 'react';
import { useWizard } from '../../../context/WizardContext';
import { formatFileSize } from '../../../utils/helpers';

/**
 * Step 1: Select Access Application
 * Per spec section 47:
 * - Allow drag/drop .accdb, browse, .mdb, project package, frontend/backend pairing
 * - Show: file name, file size, Access format, detected version, encryption status
 */
export default function Step1SelectApplication() {
    const { state, actions } = useWizard();
    const { selectedFile, fileMetadata } = state;
    const fileInputRef = useRef(null);
    const [isDragging, setIsDragging] = useState(false);
    const [fileError, setFileError] = useState(null);

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

    return (
        <div>
            <div className="card-header">
                <h2 className="card-title">Select Access Application</h2>
                <p className="card-subtitle">
                    Choose the Microsoft Access database file to convert. Supports .accdb and .mdb formats.
                </p>
            </div>

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
        </div>
    );
}