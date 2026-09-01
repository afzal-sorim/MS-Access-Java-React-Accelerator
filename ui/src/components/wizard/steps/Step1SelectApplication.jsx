import React, { useRef, useCallback, useState, useEffect } from 'react';
import { useWizard } from '../../../context/WizardContext';
import { formatFileSize } from '../../../utils/helpers';
import {
    getLocalAccessCapability,
    listLocalAccessSources,
    validateLocalPath,
} from '../../../services/api';

/* ════════════════════════════════════════════════════════════════
   CSS ANIMATIONS
   ════════════════════════════════════════════════════════════════ */
const ANIM_STYLE = `
@keyframes floatDocA {
  0%,100% { transform: rotate(-12deg) translateY(0px); }
  50%      { transform: rotate(-10deg) translateY(-8px); }
}
@keyframes floatDocB {
  0%,100% { transform: rotate(11deg) translateY(0px); }
  50%      { transform: rotate(9deg) translateY(-6px); }
}
@keyframes floatDocC {
  0%,100% { transform: rotate(-3deg) translateY(0px); }
  50%      { transform: rotate(-1deg) translateY(-10px); }
}
@keyframes pulseDot {
  0%,100% { opacity:0.35; transform:scale(1); }
  50%      { opacity:0.85; transform:scale(1.5); }
}
@keyframes rotatePlus {
  0%,100% { opacity:0.45; transform:rotate(0deg) scale(1); }
  50%      { opacity:1; transform:rotate(45deg) scale(1.3); }
}
@keyframes folderGlow {
  0%,100% { filter: drop-shadow(0 10px 22px rgba(55,48,163,0.45)) drop-shadow(0 2px 8px rgba(79,70,229,0.25)); }
  50%      { filter: drop-shadow(0 14px 32px rgba(79,70,229,0.60)) drop-shadow(0 2px 8px rgba(55,48,163,0.35)); }
}
@keyframes cloudArrow {
  0%,100% { transform: translateY(0px); }
  35%      { transform: translateY(-6px); }
  65%      { transform: translateY(-4px); }
}
@keyframes floatIllustration {
  0%, 100% { transform: translateY(0px); }
  50%      { transform: translateY(-10px); }
}
@keyframes pulseBrowse {
  0%, 100% { filter: brightness(1); transform: scale(1); }
  50%      { filter: brightness(1.2) saturate(1.2); transform: scale(1.03); }
}
.dz-doc-a { animation: floatDocA 3.2s ease-in-out infinite; transform-origin: 100px 90px; }
.dz-doc-b { animation: floatDocB 2.9s ease-in-out infinite 0.5s; transform-origin: 215px 88px; }
.dz-doc-c { animation: floatDocC 3.7s ease-in-out infinite 0.9s; transform-origin: 160px 82px; }
.dz-dot1  { animation: pulseDot 2.1s ease-in-out infinite; }
.dz-dot2  { animation: pulseDot 2.1s ease-in-out infinite 0.55s; }
.dz-dot3  { animation: pulseDot 2.1s ease-in-out infinite 1.1s; }
.dz-dot4  { animation: pulseDot 2.1s ease-in-out infinite 1.65s; }
.dz-plus1 { animation: rotatePlus 2.5s ease-in-out infinite; transform-box: fill-box; transform-origin: center; }
.dz-plus2 { animation: rotatePlus 2.5s ease-in-out infinite 0.85s; transform-box: fill-box; transform-origin: center; }
.dz-plus3 { animation: rotatePlus 2.5s ease-in-out infinite 1.7s; transform-box: fill-box; transform-origin: center; }
.dz-folder { animation: folderGlow 3s ease-in-out infinite; }
.dz-cloud-arrow { animation: cloudArrow 1.7s ease-in-out infinite; }
.dz-illustration-container { animation: floatIllustration 4s ease-in-out infinite; }
.browse-pulse { animation: pulseBrowse 2s ease-in-out infinite; display: inline-block; }
`;

/* ════════════════════════════════════════════════════════════════
   DROPZONE ILLUSTRATION
   Exact replica of reference: open gradient folder, white cloud
   icon, fanned doc pages behind, sparkle decoratives, ground ellipse
   ════════════════════════════════════════════════════════════════ */
const DropzoneIllustration = () => (
    <>
        <style>{ANIM_STYLE}</style>
        <svg
            width="320" height="160"
            viewBox="0 0 320 160"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
            style={{ display: 'block', margin: '0 auto 24px', overflow: 'visible' }}
            aria-hidden="true"
        >
            <defs>
                {/* Main folder gradient: violet → purple-magenta */}
                <linearGradient id="folderBodyGrad" x1="0.1" y1="0" x2="0.9" y2="1">
                    <stop offset="0%"   stopColor="#3730A3"/>
                    <stop offset="50%"  stopColor="#4338CA"/>
                    <stop offset="100%" stopColor="#4F46E5"/>
                </linearGradient>
                {/* Front flap gradient: slightly brighter for 3D depth */}
                <linearGradient id="folderFrontGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%"   stopColor="#6366F1"/>
                    <stop offset="100%" stopColor="#4F46E5"/>
                </linearGradient>
                {/* Folder tab: slightly deeper */}
                <linearGradient id="folderTabGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%"   stopColor="#312E81"/>
                    <stop offset="100%" stopColor="#3730A3"/>
                </linearGradient>
                {/* Top shine strip */}
                <linearGradient id="folderShineGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%"   stopColor="#ffffff" stopOpacity="0.25"/>
                    <stop offset="100%" stopColor="#ffffff" stopOpacity="0"/>
                </linearGradient>
                {/* Ground ellipse */}
                <radialGradient id="gnd" cx="50%" cy="50%" r="50%">
                    <stop offset="0%"   stopColor="#818CF8" stopOpacity="0.22"/>
                    <stop offset="100%" stopColor="#818CF8" stopOpacity="0"/>
                </radialGradient>
                {/* Folder drop-shadow */}
                <filter id="folderShadow" x="-40%" y="-40%" width="180%" height="180%">
                    <feDropShadow dx="0" dy="10" stdDeviation="14" floodColor="#3730A3" floodOpacity="0.42"/>
                </filter>
                {/* Doc soft shadow */}
                <filter id="docShadow" x="-30%" y="-30%" width="160%" height="160%">
                    <feDropShadow dx="0" dy="4" stdDeviation="7" floodColor="#4F46E5" floodOpacity="0.13"/>
                </filter>
            </defs>

            <g className="dz-illustration-container">
                {/* ── Animated plus signs ── */}
                <g className="dz-plus1" transform="translate(0, -5)">
                    <line x1="33" y1="30" x2="33" y2="40" stroke="#818CF8" strokeWidth="2.2" strokeLinecap="round"/>
                    <line x1="28" y1="35" x2="38" y2="35" stroke="#818CF8" strokeWidth="2.2" strokeLinecap="round"/>
                </g>
                <g className="dz-plus2" transform="translate(0, -10)">
                    <line x1="217" y1="42" x2="217" y2="50" stroke="#A5B4FC" strokeWidth="2" strokeLinecap="round"/>
                    <line x1="213" y1="46" x2="221" y2="46" stroke="#A5B4FC" strokeWidth="2" strokeLinecap="round"/>
                </g>
                <g className="dz-plus3" transform="translate(0, -15)">
                    <line x1="50" y1="118" x2="50" y2="126" stroke="#A5B4FC" strokeWidth="1.8" strokeLinecap="round"/>
                    <line x1="46" y1="122" x2="54" y2="122" stroke="#A5B4FC" strokeWidth="1.8" strokeLinecap="round"/>
                </g>

                {/* ── Doc 1 – back-left (white card with lines) ── */}
                <g className="dz-doc1" filter="url(#docShadow)" transform="translate(0, -12)">
                    <rect x="52" y="28" width="58" height="74" rx="8" fill="white" opacity="0.92"/>
                    {/* doc lines */}
                    <rect x="63" y="44" width="36" height="4" rx="2" fill="#E0E7FF"/>
                    <rect x="63" y="53" width="28" height="4" rx="2" fill="#EEF2FF"/>
                    <rect x="63" y="62" width="32" height="4" rx="2" fill="#EEF2FF"/>
                    <rect x="63" y="71" width="24" height="4" rx="2" fill="#F5F3FF"/>
                    {/* doc corner fold */}
                    <path d="M98 28 L110 40 L98 40 Z" fill="#EEF2FF"/>
                </g>

                {/* ── Doc 2 – back-right (slightly lighter) ── */}
                <g className="dz-doc2" filter="url(#docShadow)" transform="translate(0, -12)">
                    <rect x="152" y="22" width="56" height="70" rx="8" fill="white" opacity="0.88"/>
                    <rect x="162" y="38" width="34" height="4" rx="2" fill="#EEF2FF"/>
                    <rect x="162" y="47" width="26" height="4" rx="2" fill="#EEF2FF"/>
                    <rect x="162" y="56" width="30" height="4" rx="2" fill="#EEF2FF"/>
                    <rect x="162" y="65" width="22" height="4" rx="2" fill="#F5F3FF"/>
                    <path d="M196 22 L208 34 L196 34 Z" fill="#EEF2FF"/>
                </g>

                {/* ── Doc 3 – center top (small, slightly behind folder) ── */}
                <g className="dz-doc3" filter="url(#docShadow)" transform="translate(0, -4)">
                    <rect x="108" y="14" width="46" height="58" rx="7" fill="white" opacity="0.80"/>
                    <rect x="117" y="28" width="28" height="3.5" rx="1.75" fill="#E0E7FF"/>
                    <rect x="117" y="36" width="20" height="3.5" rx="1.75" fill="#E0E7FF"/>
                    <rect x="117" y="44" width="24" height="3.5" rx="1.75" fill="#E0E7FF"/>
                    <path d="M142 14 L154 26 L142 26 Z" fill="#EEF2FF"/>
                </g>

                {/* ── Open Folder ── */}
                <g className="dz-folder-wrap" filter="url(#folderShadow)" transform="translate(0, -5)">
                    {/* Folder body (main) */}
                    <rect x="72" y="82" width="116" height="72" rx="10" fill="url(#folderBodyGrad)"/>
                    {/* Folder tab (top-left) */}
                    <path d="M72 82 L72 72 Q72 68 76 68 L106 68 Q110 68 112 72 L118 82 Z" fill="url(#folderTabGrad)"/>
                    {/* Inner folder depth (open look) */}
                    <rect x="78" y="88" width="104" height="60" rx="7" fill="#4F46E5" opacity="0.35"/>
                    {/* Front Flap (angled for 3D effect) */}
                    <path
                        d="M72 105 L188 105 L184 149 Q182 153 178 153 L82 153 Q78 153 76 149 Z"
                        fill="url(#folderFrontGrad)"
                        stroke="#6366F1" strokeWidth="1"
                    />
                    {/* Shine overlay */}
                    <rect x="72" y="82" width="116" height="36" rx="10" fill="url(#folderShineGrad)"/>

                    {/* Cloud upload icon inside folder */}
                    <g className="dz-upload-arrow">
                        {/* Cloud shape */}
                        <path
                            d="M116 112 Q112 112 110 108 Q107 101 113 97 Q113 91 119 90 Q123 85 130 87 Q136 82 141 87 Q148 87 148 94 Q154 95 153 102 Q153 108 147 108 Z"
                            fill="white" opacity="0.95"
                        />
                        {/* Up arrow */}
                        <polyline
                            points="124,118 130,112 136,118"
                            stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" fill="none"
                        />
                        <line x1="130" y1="112" x2="130" y2="124" stroke="white" strokeWidth="2.5" strokeLinecap="round"/>
                    </g>
                </g>
            </g>
        </svg>
    </>
);

/* ════════════════════════════════════════════════════════════════
   INPUT MODE ICONS  – exactly matching the reference screenshots
   ════════════════════════════════════════════════════════════════ */

/* Single page doc with corner fold */
const FileModeIcon = () => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8L14 2Z" fill="#EEF2FF" stroke="#3730A3" strokeWidth="1.5" strokeLinejoin="round"/>
        <polyline points="14 2 14 8 20 8" stroke="#3730A3" strokeWidth="1.5" strokeLinejoin="round"/>
        <line x1="8" y1="13" x2="16" y2="13" stroke="#3730A3" strokeWidth="1.5" strokeLinecap="round"/>
        <line x1="8" y1="17" x2="14" y2="17" stroke="#3730A3" strokeWidth="1.5" strokeLinecap="round"/>
    </svg>
);

/* 6-dot grid (2x3) – split application */
const GridModeIcon = () => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <rect x="3" y="3" width="7" height="7" rx="1.5" fill="#EEF2FF" stroke="#3730A3" strokeWidth="1.5"/>
        <rect x="14" y="3" width="7" height="7" rx="1.5" fill="#EEF2FF" stroke="#3730A3" strokeWidth="1.5"/>
        <rect x="3" y="14" width="7" height="7" rx="1.5" fill="#EEF2FF" stroke="#3730A3" strokeWidth="1.5"/>
        <rect x="14" y="14" width="7" height="7" rx="1.5" fill="#EEF2FF" stroke="#3730A3" strokeWidth="1.5"/>
    </svg>
);

/* Stacked layers – access project package */
const LayersModeIcon = () => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        {/* Bottom layer */}
        <path d="M2 17L12 22L22 17" stroke="#3730A3" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" fill="#EEF2FF"/>
        {/* Middle layer */}
        <path d="M2 12L12 17L22 12" stroke="#3730A3" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" fill="#E0D0FA"/>
        {/* Top layer */}
        <polygon points="12 2 2 7 12 12 22 7 12 2" fill="#D4BAFF" stroke="#3730A3" strokeWidth="1.5" strokeLinejoin="round"/>
    </svg>
);

/* Upload tray / source export */
const PackageModeIcon = () => (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        {/* Tray base */}
        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" stroke="#3730A3" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" fill="#EEF2FF"/>
        {/* Up arrow */}
        <polyline points="17 8 12 3 7 8" stroke="#3730A3" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
        <line x1="12" y1="3" x2="12" y2="15" stroke="#3730A3" strokeWidth="1.5" strokeLinecap="round"/>
    </svg>
);

/* ── Utility icons ── */
const UploadBtnIcon = () => (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
        <polyline points="16 16 12 12 8 16"/><line x1="12" y1="12" x2="12" y2="21"/>
        <path d="M20.39 18.39A5 5 0 0 0 18 9h-1.26A8 8 0 1 0 3 16.3"/>
    </svg>
);
const DesktopBtnIcon = () => (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <rect x="2" y="3" width="20" height="14" rx="2" ry="2"/>
        <line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/>
    </svg>
);
const CheckCircleIcon = () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/>
    </svg>
);
const XIcon = () => (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
        <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
    </svg>
);

/**
 * Step 1: Select Access Application
 * Per spec section 47 – drag/drop .accdb/.mdb; two input modes: upload vs local.
 * Visual design matches AccessMigra reference image with animated illustration.
 */
export default function Step1SelectApplication() {
    const { state, actions } = useWizard();
    const { sourceMode, selectedFile, fileMetadata, localSource } = state;
    const fileInputRef = useRef(null);
    const [isDragging, setIsDragging] = useState(false);
    const [fileError, setFileError] = useState(null);

    const [capability, setCapability]   = useState(null);
    const [sources, setSources]         = useState({ open: [], recent: [], errors: [] });
    const [loadingSources, setLoadingSources] = useState(false);
    const [manualPath, setManualPath]   = useState('');
    const [localError, setLocalError]   = useState(null);
    const [validating, setValidating]   = useState(false);

    /* ── file handling ── */
    const handleFileSelect = useCallback((file) => {
        if (!file) return;
        const validExtensions = ['.accdb', '.mdb'];
        const fileName = file.name.toLowerCase();
        if (!validExtensions.some(ext => fileName.endsWith(ext))) {
            setFileError('Please select a valid Microsoft Access file (.accdb or .mdb)');
            return;
        }
        setFileError(null);
        actions.setFile(file);
        actions.setFileMetadata({
            name: file.name, size: file.size,
            formattedSize: formatFileSize(file.size),
            extension: fileName.endsWith('.accdb') ? '.accdb' : '.mdb',
            format: fileName.endsWith('.accdb') ? 'Access 2007-2016+ (.accdb)' : 'Access 2000-2003 (.mdb)',
            lastModified: new Date(file.lastModified).toLocaleDateString(),
        });
    }, [actions]);

    const handleDragOver  = useCallback(e => { e.preventDefault(); e.stopPropagation(); setIsDragging(true); }, []);
    const handleDragLeave = useCallback(e => { e.preventDefault(); e.stopPropagation(); setIsDragging(false); }, []);
    const handleDrop      = useCallback(e => {
        e.preventDefault(); e.stopPropagation(); setIsDragging(false);
        if (e.dataTransfer.files.length > 0) handleFileSelect(e.dataTransfer.files[0]);
    }, [handleFileSelect]);
    const handleFileInputChange = useCallback(e => { if (e.target.files[0]) handleFileSelect(e.target.files[0]); }, [handleFileSelect]);
    const handleRemoveFile = useCallback(() => {
        actions.clearFile(); setFileError(null);
        if (fileInputRef.current) fileInputRef.current.value = '';
    }, [actions]);

    /* ── local-mode ── */
    useEffect(() => {
        let cancelled = false;
        getLocalAccessCapability()
            .then(r  => { if (!cancelled) setCapability(r); })
            .catch(e => { if (!cancelled) setCapability({ available: false, reason: e.message }); });
        return () => { cancelled = true; };
    }, []);

    const refreshSources = useCallback(async () => {
        setLoadingSources(true); setLocalError(null);
        try   { setSources(await listLocalAccessSources()); }
        catch (e) { setLocalError(e.message); }
        finally   { setLoadingSources(false); }
    }, []);

    useEffect(() => {
        if (sourceMode === 'local' && capability !== null) refreshSources();
    }, [sourceMode, capability, refreshSources]);

    const selectLocalPath = useCallback(async (path) => {
        setValidating(true); setLocalError(null);
        try   { const info = await validateLocalPath(path); actions.setLocalSource(info); setManualPath(info.path); }
        catch (e) { setLocalError(e.message); actions.setLocalSource(null); }
        finally   { setValidating(false); }
    }, [actions]);

    const handleModeChange = useCallback((mode) => {
        if (mode === sourceMode) return;
        setFileError(null); setLocalError(null);
        actions.setSourceMode(mode);
        if (fileInputRef.current) fileInputRef.current.value = '';
    }, [sourceMode, actions]);

    const renderSourceRow = (source, key) => (
        <button key={key} className="btn btn-secondary" onClick={() => selectLocalPath(source.path)} disabled={validating}
            style={{ display:'flex', alignItems:'center', gap:'0.75rem', width:'100%', textAlign:'left', justifyContent:'flex-start', padding:'0.75rem', marginBottom:'0.5rem', border: localSource?.path === source.path ? '2px solid var(--color-success)' : '1.5px solid #C7D2FE' }}>
            <span style={{ fontSize:'1.5rem' }}>{source.extension === '.accdb' ? '🗃️' : '📄'}</span>
            <span style={{ flex:1, minWidth:0 }}>
                <span style={{ display:'block', fontWeight:600, fontSize:'0.9375rem' }}>{source.name}</span>
                <span style={{ display:'block', fontSize:'0.75rem', color:'#6B6B8A', overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>{source.path}</span>
            </span>
            {source.formatted_size && <span style={{ fontSize:'0.75rem', color:'#6B6B8A' }}>{source.formatted_size}</span>}
        </button>
    );

    /* ── button styles ── */
    const btnPrimary = {
        display:'inline-flex', alignItems:'center', gap:'0.5rem',
        padding:'0.6rem 1.35rem', borderRadius:10,
        fontWeight:700, fontSize:'0.875rem', border:'none',
        background:'linear-gradient(135deg,#3730A3 0%,#4F46E5 100%)',
        color:'#fff', boxShadow:'0 4px 14px rgba(55,48,163,0.28)', cursor:'pointer',
        transition:'all 0.15s ease',
    };
    const btnSecondary = {
        display:'inline-flex', alignItems:'center', gap:'0.5rem',
        padding:'0.6rem 1.35rem', borderRadius:10,
        fontWeight:700, fontSize:'0.875rem',
        background:'#fff', color:'#15133A',
        border:'1.5px solid #C7D2FE', cursor:'pointer',
        transition:'all 0.15s ease',
    };

    return (
        <div style={{ width: '100%' }}>
            {/* ── Card Header ── */}
            <div style={{ display:'flex', alignItems:'flex-start', gap:'1rem', marginBottom:'1rem', paddingBottom:'1rem', borderBottom:'1px solid #C7D2FE' }}>
                {/* Yellow folder in lavender box */}
                <div style={{ width:58, height:58, background:'linear-gradient(135deg,#EEF2FF 0%,#E0D0FA 100%)', borderRadius:14, display:'flex', alignItems:'center', justifyContent:'center', flexShrink:0, border:'1.5px solid #A5B4FC' }}>
                    <svg width="36" height="30" viewBox="0 0 36 30" fill="none">
                        {/* Folder body */}
                        <rect x="1" y="11" width="34" height="18" rx="3" fill="#FFD54F"/>
                        {/* Folder tab */}
                        <path d="M1 11 L1 8 Q1 6 3 6 L13 6 Q15 6 16 8 L18 11 Z" fill="#FFC107"/>
                        {/* Shine */}
                        <rect x="1" y="11" width="34" height="8" rx="3" fill="white" opacity="0.15"/>
                    </svg>
                </div>
                <div>
                    <h2 style={{ fontSize:'1.4rem', fontWeight:800, color:'#15133A', letterSpacing:'-0.02em', lineHeight:1.2 }}>
                        Select Access Application
                    </h2>
                    <p style={{ fontSize:'0.875rem', color:'#6B6B8A', marginTop:'0.4rem', lineHeight:1.6 }}>
                        Choose the Microsoft Access database to convert. Upload a file, or read it
                        directly from MS Access on this machine.
                    </p>
                </div>
            </div>

            {/* ── Mode buttons ── */}
            <div style={{ display:'flex', gap:'0.75rem', marginBottom:'1.25rem', flexWrap:'wrap' }}>
                <button style={sourceMode==='upload' ? btnPrimary : btnSecondary} onClick={() => handleModeChange('upload')}>
                    <UploadBtnIcon /> Upload a file
                </button>
                <button style={sourceMode==='local' ? btnPrimary : btnSecondary} onClick={() => handleModeChange('local')}
                    title={capability && !capability.available ? capability.reason : undefined}>
                    <DesktopBtnIcon /> Direct from local MS Access
                </button>
            </div>

            {/* ══════════ UPLOAD MODE ══════════ */}
            {sourceMode === 'upload' && (
                <>
                    {fileError && <div className="alert alert-danger" style={{ marginBottom:'1.25rem' }}>{fileError}</div>}

                    {!selectedFile ? (
                        <>
                            {/* ── Drag & Drop Zone ── */}
                            <div
                                onDragOver={handleDragOver} onDragLeave={handleDragLeave} onDrop={handleDrop}
                                onClick={() => fileInputRef.current?.click()}
                                role="button" tabIndex={0}
                                onKeyDown={e => e.key==='Enter' && fileInputRef.current?.click()}
                                style={{
                                    border: isDragging ? '2.5px dashed #3730A3' : '2px dashed #A5B4FC',
                                    borderRadius: 18,
                                    padding: '0.5rem 2rem 1.5rem',
                                    textAlign: 'center',
                                    background: isDragging ? '#EEF2FF' : '#F8FAFC',
                                    cursor: 'pointer',
                                    transition: 'all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275)',
                                    animation: 'dzHighlight 3s ease-in-out infinite',
                                    marginBottom: '1rem',
                                    position: 'relative',
                                    overflow: 'hidden',
                                    perspective: '1000px',
                                    transformStyle: 'preserve-3d'
                                }}
                                onMouseEnter={e => { e.currentTarget.style.transform = 'translateY(-2px) rotateX(2deg)'; e.currentTarget.style.boxShadow = '0 12px 24px rgba(55,48,163,0.12)'; }}
                                onMouseLeave={e => { e.currentTarget.style.transform = 'translateY(0) rotateX(0)'; e.currentTarget.style.boxShadow = 'none'; }}
                            >
                                <input ref={fileInputRef} type="file" accept=".accdb,.mdb" onChange={handleFileInputChange} style={{ display:'none' }} />

                                {/* Animated illustration */}
                                <DropzoneIllustration />

                                <p style={{ fontSize:'1.05rem', fontWeight:700, color:'#15133A', marginBottom:'0.2rem' }}>
                                    Drag and drop your Access file here
                                </p>
                                <p style={{ fontSize:'1rem', marginBottom:'0.5rem', color:'#15133A' }}>
                                    or{' '}
                                    <span onClick={e => { e.stopPropagation(); fileInputRef.current?.click(); }}
                                        className="browse-pulse"
                                        style={{ color:'#4F46E5', fontWeight:800, cursor:'pointer', textDecoration:'underline', textDecorationColor:'#4F46E5', textUnderlineOffset:'3px' }}>
                                        click to browse
                                    </span>
                                </p>
                                <p style={{ fontSize:'0.8rem', color:'#6B6B8A' }}>
                                    Supported formats: <strong style={{ color:'#15133A' }}>.accdb</strong> (Access 2007+) or <strong style={{ color:'#15133A' }}>.mdb</strong> (Access 2000-2003)
                                </p>
                            </div>

                            {/* ── Input Modes strip ── */}
                            <div style={{ background:'#F8FAFC', border:'1.5px solid #C7D2FE', borderRadius:14, padding:'0.875rem 1.5rem', display:'flex', alignItems:'center', flexWrap:'wrap' }}>
                                <span style={{ fontSize:'0.82rem', fontWeight:700, color:'#15133A', marginRight:'1.25rem', whiteSpace:'nowrap', flexShrink:0 }}>
                                    Input Modes Supported:
                                </span>
                                <div style={{ display:'flex', flex:1, alignItems:'center', flexWrap:'wrap', gap:0 }}>
                                    {/* Item 1 */}
                                    <div style={{ display:'flex', alignItems:'center', gap:'0.55rem', flex:1, padding:'0 1rem', minWidth:140 }}>
                                        <div style={{ width:34, height:34, background:'#fff', border:'1.5px solid #C7D2FE', borderRadius:8, display:'flex', alignItems:'center', justifyContent:'center', flexShrink:0 }}>
                                            <FileModeIcon />
                                        </div>
                                        <div>
                                            <div style={{ fontSize:'0.8rem', fontWeight:700, color:'#15133A', lineHeight:1.2 }}>Single Access file</div>
                                            <div style={{ fontSize:'0.7rem', color:'#6B6B8A', lineHeight:1.3 }}>(.accdb / .mdb)</div>
                                        </div>
                                    </div>
                                    <div style={{ width:'1.5px', height:36, background:'#C7D2FE', flexShrink:0 }}/>
                                    {/* Item 2 */}
                                    <div style={{ display:'flex', alignItems:'center', gap:'0.55rem', flex:1, padding:'0 1rem', minWidth:155 }}>
                                        <div style={{ width:34, height:34, background:'#fff', border:'1.5px solid #C7D2FE', borderRadius:8, display:'flex', alignItems:'center', justifyContent:'center', flexShrink:0 }}>
                                            <GridModeIcon />
                                        </div>
                                        <div>
                                            <div style={{ fontSize:'0.8rem', fontWeight:700, color:'#15133A', lineHeight:1.2 }}>Split application</div>
                                            <div style={{ fontSize:'0.7rem', color:'#6B6B8A', lineHeight:1.3 }}>Frontend + Backend</div>
                                        </div>
                                    </div>
                                    <div style={{ width:'1.5px', height:36, background:'#C7D2FE', flexShrink:0 }}/>
                                    {/* Item 3 */}
                                    <div style={{ display:'flex', alignItems:'center', gap:'0.55rem', flex:1, padding:'0 1rem', minWidth:160 }}>
                                        <div style={{ width:34, height:34, background:'#fff', border:'1.5px solid #C7D2FE', borderRadius:8, display:'flex', alignItems:'center', justifyContent:'center', flexShrink:0 }}>
                                            <LayersModeIcon />
                                        </div>
                                        <div>
                                            <div style={{ fontSize:'0.8rem', fontWeight:700, color:'#15133A', lineHeight:1.2 }}>Access project package</div>
                                        </div>
                                    </div>
                                    <div style={{ width:'1.5px', height:36, background:'#C7D2FE', flexShrink:0 }}/>
                                    {/* Item 4 */}
                                    <div style={{ display:'flex', alignItems:'center', gap:'0.55rem', flex:1, padding:'0 1rem', minWidth:155 }}>
                                        <div style={{ width:34, height:34, background:'#fff', border:'1.5px solid #C7D2FE', borderRadius:8, display:'flex', alignItems:'center', justifyContent:'center', flexShrink:0 }}>
                                            <PackageModeIcon />
                                        </div>
                                        <div>
                                            <div style={{ fontSize:'0.8rem', fontWeight:700, color:'#15133A', lineHeight:1.2 }}>Source export package</div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </>
                    ) : (
                        /* ── File selected ── */
                        <div style={{ background:'#F8FAFC', border:'1.5px solid var(--color-success)', borderRadius:16, padding:'1.5rem' }}>
                            <div style={{ display:'flex', alignItems:'flex-start', justifyContent:'space-between', gap:'1rem', flexWrap:'wrap' }}>
                                <div style={{ display:'flex', alignItems:'center', gap:'1rem' }}>
                                    <div style={{ width:52, height:52, borderRadius:12, background:'linear-gradient(135deg,#3730A3 0%,#4F46E5 100%)', display:'flex', alignItems:'center', justifyContent:'center', flexShrink:0 }}>
                                        <span style={{ color:'white', display:'flex', alignItems:'center', width:24, height:24 }}><CheckCircleIcon/></span>
                                    </div>
                                    <div>
                                        <h3 style={{ fontSize:'1rem', fontWeight:700, color:'#15133A' }}>{fileMetadata?.name}</h3>
                                        <p style={{ color:'#6B6B8A', fontSize:'0.85rem', marginTop:2 }}>{fileMetadata?.formattedSize} • {fileMetadata?.format}</p>
                                    </div>
                                </div>
                                <button onClick={handleRemoveFile} style={{ display:'inline-flex', alignItems:'center', gap:'0.375rem', padding:'0.375rem 0.875rem', borderRadius:8, fontSize:'0.8rem', fontWeight:600, background:'#fff', border:'1.5px solid #C7D2FE', color:'#15133A', cursor:'pointer' }}>
                                    <XIcon/> Remove
                                </button>
                            </div>
                            {fileMetadata && (
                                <div className="grid grid-3" style={{ marginTop:'1.5rem', paddingTop:'1.5rem', borderTop:'1px solid #C7D2FE' }}>
                                    <div className="stat-card"><div className="stat-card-value">{fileMetadata.formattedSize}</div><div className="stat-card-label">File Size</div></div>
                                    <div className="stat-card"><div className="stat-card-value">{fileMetadata.format.split(' ')[0]}</div><div className="stat-card-label">Access Format</div></div>
                                    <div className="stat-card"><div className="stat-card-value">{fileMetadata.lastModified}</div><div className="stat-card-label">Last Modified</div></div>
                                </div>
                            )}
                            <div className="alert alert-info" style={{ marginTop:'1.5rem', marginBottom:0 }}>
                                <strong>Note:</strong> For split databases, select the frontend .accdb. The converter auto-detects linked backend tables.
                            </div>
                        </div>
                    )}
                </>
            )}

            {/* ══════════ LOCAL DIRECT MODE ══════════ */}
            {sourceMode === 'local' && (
                <>
                    {capability === null && (
                        <div className="alert alert-info" style={{ marginBottom:'1.5rem' }}>
                            <div style={{ display:'flex', alignItems:'center', gap:'0.75rem' }}>
                                <div className="spinner" style={{ width:20, height:20, borderWidth:2 }}/><span>Checking for MS Access on the converter machine...</span>
                            </div>
                        </div>
                    )}
                    {capability && !capability.available && (
                        <div className="alert alert-warning" style={{ marginBottom:'1.5rem' }}>
                            <strong>MS Access COM automation not detected.</strong>
                            <div style={{ marginTop:'0.5rem', fontSize:'0.875rem' }}>{capability.reason}</div>
                            <div style={{ marginTop:'0.5rem', fontSize:'0.875rem' }}>You can still pick a database below, but extraction will fail unless MS Access is available.</div>
                        </div>
                    )}
                    {capability?.available && (
                        <div className="alert alert-success" style={{ marginBottom:'1.5rem' }}>
                            <strong>MS Access detected</strong>
                            {capability.access_version && ` (version ${capability.access_version})`}
                            {capability.access_running ? ' — currently running.' : ' — installed and available.'}
                        </div>
                    )}
                    {localError && <div className="alert alert-danger" style={{ marginBottom:'1.5rem' }}>{localError}</div>}
                    {sources.errors?.map((e,i) => <div key={i} className="alert alert-warning" style={{ marginBottom:'1rem' }}>{e}</div>)}

                    {capability !== null && (
                        <>
                            {sources.open?.length > 0 && (
                                <div style={{ marginBottom:'1.5rem' }}>
                                    <h4 style={{ fontSize:'0.875rem', fontWeight:600, marginBottom:'0.75rem', color:'#15133A' }}>Currently open in MS Access</h4>
                                    {sources.open.map((s,i) => renderSourceRow(s,`open-${i}`))}
                                </div>
                            )}
                            <div style={{ marginBottom:'1.5rem' }}>
                                <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', marginBottom:'0.75rem' }}>
                                    <h4 style={{ fontSize:'0.875rem', fontWeight:600, color:'#15133A' }}>Recently opened in MS Access</h4>
                                    <button className="btn btn-secondary btn-sm" onClick={refreshSources} disabled={loadingSources}>{loadingSources ? 'Refreshing...' : '↻ Refresh'}</button>
                                </div>
                                {loadingSources && sources.recent.length === 0
                                    ? <p style={{ fontSize:'0.8125rem', color:'#6B6B8A' }}>Looking for databases...</p>
                                    : sources.recent?.length > 0
                                        ? sources.recent.map((s,i) => renderSourceRow(s,`recent-${i}`))
                                        : <p style={{ fontSize:'0.8125rem', color:'#6B6B8A' }}>No recent databases found. Enter a full path below instead.</p>
                                }
                            </div>
                            <div style={{ marginBottom:'1.5rem' }}>
                                <h4 style={{ fontSize:'0.875rem', fontWeight:600, marginBottom:'0.75rem', color:'#15133A' }}>Or enter a full path on the converter machine</h4>
                                <div style={{ display:'flex', gap:'0.5rem', flexWrap:'wrap' }}>
                                    <input type="text" className="form-control" placeholder="C:\path\to\YourDatabase.accdb" value={manualPath}
                                        onChange={e => setManualPath(e.target.value)}
                                        onKeyDown={e => { if (e.key==='Enter' && manualPath.trim()) selectLocalPath(manualPath.trim()); }}
                                        style={{ flex:1, minWidth:260 }}/>
                                    <button className="btn btn-primary" onClick={() => selectLocalPath(manualPath.trim())} disabled={validating || !manualPath.trim()}>
                                        {validating ? 'Checking...' : 'Validate'}
                                    </button>
                                </div>
                            </div>
                        </>
                    )}

                    {localSource && (
                        <div style={{ background:'#F8FAFC', border:'1.5px solid var(--color-success)', borderRadius:16, padding:'1.5rem' }}>
                            <div style={{ display:'flex', alignItems:'flex-start', justifyContent:'space-between', gap:'1rem', flexWrap:'wrap' }}>
                                <div style={{ display:'flex', alignItems:'center', gap:'1rem' }}>
                                    <div style={{ fontSize:'3rem' }}>{localSource.extension==='.accdb' ? '🗃️' : '📄'}</div>
                                    <div style={{ minWidth:0 }}>
                                        <h3 style={{ fontSize:'1rem', fontWeight:700, color:'#15133A' }}>{localSource.name}</h3>
                                        <p style={{ color:'#6B6B8A', fontSize:'0.85rem', marginTop:2 }}>{localSource.formatted_size} • {localSource.format}</p>
                                        <p style={{ color:'#6B6B8A', fontSize:'0.75rem', wordBreak:'break-all', marginTop:2 }}>{localSource.path}</p>
                                    </div>
                                </div>
                                <button onClick={() => { actions.setLocalSource(null); setLocalError(null); }}
                                    style={{ display:'inline-flex', alignItems:'center', gap:'0.375rem', padding:'0.375rem 0.875rem', borderRadius:8, fontSize:'0.8rem', fontWeight:600, background:'#fff', border:'1.5px solid #C7D2FE', color:'#15133A', cursor:'pointer' }}>
                                    <XIcon/> Remove
                                </button>
                            </div>
                            <div className="grid grid-3" style={{ marginTop:'1.5rem', paddingTop:'1.5rem', borderTop:'1px solid #C7D2FE' }}>
                                <div className="stat-card"><div className="stat-card-value">{localSource.formatted_size}</div><div className="stat-card-label">File Size</div></div>
                                <div className="stat-card"><div className="stat-card-value">{localSource.format.split(' ')[0]}</div><div className="stat-card-label">Access Format</div></div>
                                <div className="stat-card"><div className="stat-card-value">{localSource.last_modified?.split(' ')[0]}</div><div className="stat-card-label">Last Modified</div></div>
                            </div>
                            {localSource.warnings?.map((w,i) => <div key={i} className="alert alert-warning" style={{ marginTop:'1rem' }}>{w}</div>)}
                            <div className="alert alert-info" style={{ marginTop:'1rem', marginBottom:0 }}>
                                <strong>Your database is not modified.</strong> The converter copies it into its own workspace and reads the copy.
                            </div>
                        </div>
                    )}
                </>
            )}
        </div>
    );
}
