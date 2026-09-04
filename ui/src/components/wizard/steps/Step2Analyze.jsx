import React, { useEffect, useState, useCallback, useRef, useMemo } from 'react';
import { useWizard } from '../../../context/WizardContext';
import { createJob, createLocalJob, connectProgressWebSocket, getJob, getJobDiscovery, generateBrdReport, getBrdPreviewUrl, getBrdDownloadUrl } from '../../../services/api';
import { parseAccessFile } from '../../../utils/accessParser';
import Access2JavaLoader from '../Access2JavaLoader';
// import DiscoverySidebar from './discovery/DiscoverySidebar';
import StatCard from './discovery/StatCard';
import ObjectDistributionChart from './discovery/ObjectDistributionChart';
import ComplexityScore from './discovery/ComplexityScore';
import KeyInsights from './discovery/KeyInsights';
import ModernizedOutput from './discovery/ModernizedOutput';
import FileGenerationChart from './discovery/FileGenerationChart';
import TopComplexObjects from './discovery/TopComplexObjects';
import TopTablesList from './discovery/TopTablesList';
import DiscoverySummary from './discovery/DiscoverySummary';
import DiscoveryDetailView from './discovery/DiscoveryDetailView';
import { Database, Layout, FileText, PlaySquare, Code, CheckCircle2, PanelLeftOpen, Maximize2, Minimize2 } from 'lucide-react';

// Exact duration formatter: HH:MM:SS
function formatDuration(totalSeconds) {
    const s = Math.max(0, Math.floor(totalSeconds));
    const hrs = String(Math.floor(s / 3600)).padStart(2, '0');
    const mins = String(Math.floor((s % 3600) / 60)).padStart(2, '0');
    const secs = String(s % 60).padStart(2, '0');
    return `${hrs}:${mins}:${secs}`;
}

export default function Step2Analyze() {
    const { state, actions } = useWizard();
    const { analysisProgress, analysisResult, selectedFile, localSource, fileMetadata } = state;
    const activeTab = state.discoveryTab || 'Overview';
    const setActiveTab = (tab) => {
        if (typeof actions.setDiscoveryTab === 'function') {
            actions.setDiscoveryTab(tab);
        }
    };
    const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
    const [isAutoFit, setIsAutoFit] = useState(false);
    const [parsedData, setParsedData] = useState(null);

    const startedRef = useRef(false);
    const hasFetchedDiscoveryRef = useRef(false);
    const [ws, setWs] = useState(null);
    const [isAnalyzing, setIsAnalyzing] = useState(true);
    const [analysisError, setAnalysisError] = useState(null);
    const [brdLoading, setBrdLoading] = useState(false);
    const [brdError, setBrdError] = useState(null);
    const [liveStatusText, setLiveStatusText] = useState('Connecting to backend analysis engine...');
    const [dynamicTimeDisplay, setDynamicTimeDisplay] = useState('');
    const analysisStartTimestampRef = useRef(state.analysisStartTime || Date.now());

    const getDbName = () => {
        if (selectedFile?.name) return selectedFile.name;
        if (fileMetadata?.name) return fileMetadata.name;
        if (localSource?.path) {
            const parts = localSource.path.split(/[/\\]/);
            return parts[parts.length - 1];
        }
        return 'AccessDatabase.accdb';
    };

    const dbName = getDbName();

    const handleGenerateBrd = async () => {
        if (!state.analysisJobId || brdLoading) return;
        setBrdLoading(true);
        setBrdError(null);
        try {
            await generateBrdReport(state.analysisJobId);
            window.open(getBrdPreviewUrl(state.analysisJobId), '_blank', 'noopener,noreferrer');
        } catch (error) {
            setBrdError(error.message || 'Unable to generate the BRD report.');
        } finally {
            setBrdLoading(false);
        }
    };

    const getFileSize = () => {
        if (selectedFile?.size) {
            return (selectedFile.size / (1024 * 1024)).toFixed(2) + ' MB';
        }
        if (fileMetadata?.size) {
            return (fileMetadata.size / (1024 * 1024)).toFixed(2) + ' MB';
        }
        if (fileMetadata?.formattedSize) return fileMetadata.formattedSize;
        return '3.23 MB';
    };

    // Client-side quick binary parser for immediate baseline discovery
    useEffect(() => {
        if (selectedFile && !parsedData) {
            parseAccessFile(selectedFile).then(data => {
                if (data) {
                    setParsedData(data);
                    if (!state.analysisComplete) {
                        actions.updateAnalysisProgress(data);
                    }
                }
            }).catch(e => console.warn('Binary parser notice:', e));
        }
    }, [selectedFile, parsedData, actions, state.analysisComplete]);

    // Finalize discovery completion and freeze exact duration
    const finalizeAnalysisCompletion = useCallback((jobId) => {
        const completedAt = Date.now();
        const startedAt = state.analysisStartedAt || state.analysisStartTime || analysisStartTimestampRef.current;
        const durationSecs = Math.max(0, Math.floor((completedAt - startedAt) / 1000));
        const finalDuration = formatDuration(durationSecs);

        if (typeof actions.completeAnalysisTimer === 'function') {
            actions.completeAnalysisTimer(completedAt, finalDuration);
        } else if (typeof actions.setAnalysisDuration === 'function') {
            actions.setAnalysisDuration(finalDuration);
            actions.setAnalysisComplete(true);
        }
        setDynamicTimeDisplay(finalDuration);
        setIsAnalyzing(false);

        if (jobId) {
            getJobDiscovery(jobId).then(discovery => {
                if (discovery) {
                    actions.setAnalysisResult(discovery);
                    actions.updateAnalysisProgress({
                        tables: { count: discovery.statistics.tables, status: 'completed', items: discovery.tables },
                        queries: { count: discovery.statistics.queries, status: 'completed', items: discovery.queries },
                        forms: { count: discovery.statistics.forms, status: 'completed', items: discovery.forms },
                        reports: { count: discovery.statistics.reports, status: 'completed', items: discovery.reports },
                        macros: { count: discovery.statistics.macros, status: 'completed', items: discovery.macros },
                        vba: { count: discovery.statistics.vba_modules, status: 'completed', items: discovery.modules },
                        dependencies: { count: discovery.statistics.dependencies, status: 'completed' },
                    });
                }
            }).catch(() => {});
        }
    }, [state.analysisStartedAt, state.analysisStartTime, actions]);

    // Live ticking timer that reflects exact elapsed time from Next click to completion
    useEffect(() => {
        // STOP IMMEDIATELY if analysis is complete or completed duration is present
        if (state.analysisComplete || state.analysisStatus === 'COMPLETED' || state.analysisDuration) {
            if (state.analysisDuration) {
                setDynamicTimeDisplay(state.analysisDuration);
            } else {
                const completedAt = state.analysisCompletedAt || Date.now();
                const startedAt = state.analysisStartedAt || state.analysisStartTime || analysisStartTimestampRef.current;
                const finalDuration = formatDuration(Math.max(1, Math.floor((completedAt - startedAt) / 1000)));
                setDynamicTimeDisplay(finalDuration);
                if (typeof actions.completeAnalysisTimer === 'function') {
                    actions.completeAnalysisTimer(completedAt, finalDuration);
                }
            }
            return;
        }

        // If analysis failed, do not tick
        if (state.analysisStatus === 'FAILED') {
            return;
        }

        const startedAt = state.analysisStartedAt || state.analysisStartTime || analysisStartTimestampRef.current;

        const updateTimer = () => {
            const diffSecs = Math.max(0, Math.floor((Date.now() - startedAt) / 1000));
            setDynamicTimeDisplay(formatDuration(diffSecs));
        };

        updateTimer();
        const interval = setInterval(updateTimer, 1000);
        return () => clearInterval(interval);
    }, [state.analysisComplete, state.analysisStatus, state.analysisDuration, state.analysisStartedAt, state.analysisStartTime, actions]);

    // Handle WebSocket & polling progress messages from backend conversion engine
    const processJobUpdate = useCallback((message) => {
        const { state: jobState, statistics, result, message: statusMsg, stage } = message;
        const normalizedJobState = String(jobState || '').toLowerCase();

        if (statusMsg || stage) {
            setLiveStatusText(statusMsg || `Analyzing ${stage}...`);
        }

        if (statistics) {
            const buildItems = (arr) => (Array.isArray(arr) && arr.length > 0 ? arr : undefined);
            actions.updateAnalysisProgress({
                tables: { count: statistics.tables ?? 0, status: 'completed', items: buildItems(statistics.table_names) },
                queries: { count: statistics.queries ?? 0, status: 'completed', items: buildItems(statistics.query_names) },
                forms: { count: statistics.forms ?? 0, status: 'completed', items: buildItems(statistics.form_names) },
                reports: { count: statistics.reports ?? 0, status: 'completed', items: buildItems(statistics.report_names) },
                macros: { count: statistics.macros ?? 0, status: 'completed', items: buildItems(statistics.macro_names) },
                vba: { count: statistics.vba_modules ?? 0, status: 'completed', items: buildItems(statistics.module_names) },
                dependencies: { count: statistics.dependencies ?? 0, status: 'completed' },
            });
        }

        if (normalizedJobState === 'supportability_analyzed' || normalizedJobState === 'completed') {
            finalizeAnalysisCompletion(message.id || state.analysisJobId);
        } else if (statistics && Object.keys(statistics).length > 0 && !state.analysisComplete) {
            // intermediate progress
        }

        if (normalizedJobState === 'failed') {
            setAnalysisError(message.error || 'Analysis failed');
            setIsAnalyzing(false);
        }
    }, [actions]);

    // Start the analysis job on mount and hold loader until ready
    useEffect(() => {
        let pollingInterval = null;

        const startAnalysis = async () => {
            if (startedRef.current) return;
            startedRef.current = true;
            setIsAnalyzing(true);
            setAnalysisError(null);

            try {
                const config = state.config || {};
                const job = localSource
                    ? await createLocalJob(localSource.path, config)
                    : selectedFile
                        ? await createJob(selectedFile, config)
                        : null;

                if (job && job.id) {
                    actions.setAnalysisJob(job.id);
                    
                    // 1. WebSocket stream connection
                    const websocket = connectProgressWebSocket(job.id, processJobUpdate);
                    setWs(websocket);

                    // 2. Reliable backup polling every 1.5s
                    pollingInterval = setInterval(async () => {
                        try {
                            const updatedJob = await getJob(job.id);
                            if (updatedJob) {
                                processJobUpdate(updatedJob);
                                const normalizedJobState = String(updatedJob.state || '').toLowerCase();
                                if (normalizedJobState === 'completed' || normalizedJobState === 'supportability_analyzed') {
                                    clearInterval(pollingInterval);
                                    finalizeAnalysisCompletion(job.id);
                                } else if (normalizedJobState === 'failed') {
                                    clearInterval(pollingInterval);
                                    if (typeof actions.failAnalysisTimer === 'function') {
                                        actions.failAnalysisTimer(updatedJob.error || 'Analysis failed');
                                    }
                                    setAnalysisError(updatedJob.error || 'Analysis failed');
                                    setIsAnalyzing(false);
                                }
                            }
                        } catch (e) {
                            // ignore transient polling errors
                        }
                    }, 1500);

                } else {
                    // Fallback to local parsing completion if no backend is running
                    setTimeout(() => {
                        actions.setAnalysisComplete(true);
                        setIsAnalyzing(false);
                    }, 4000);
                }
            } catch (err) {
                console.warn('Backend job notice (using local binary scan):', err.message);
                setTimeout(() => {
                    actions.setAnalysisComplete(true);
                    setIsAnalyzing(false);
                }, 4000);
            }
        };

        if (state.analysisJobId && state.analysisComplete && !hasFetchedDiscoveryRef.current && !analysisResult?.tables) {
            hasFetchedDiscoveryRef.current = true;
            getJobDiscovery(state.analysisJobId).then(discovery => {
                if (discovery) {
                    actions.setAnalysisResult(discovery);
                    actions.updateAnalysisProgress({
                        tables: { count: discovery.statistics.tables, status: 'completed', items: discovery.tables },
                        queries: { count: discovery.statistics.queries, status: 'completed', items: discovery.queries },
                        forms: { count: discovery.statistics.forms, status: 'completed', items: discovery.forms },
                        reports: { count: discovery.statistics.reports, status: 'completed', items: discovery.reports },
                        macros: { count: discovery.statistics.macros, status: 'completed', items: discovery.macros },
                        vba: { count: discovery.statistics.vba_modules, status: 'completed', items: discovery.modules },
                        dependencies: { count: discovery.statistics.dependencies, status: 'completed' },
                    });
                }
            }).catch(() => {});
        }

        if ((selectedFile || localSource) && !state.analysisJobId) {
            startAnalysis();
        } else if (state.analysisComplete) {
            setIsAnalyzing(false);
        }

        return () => { 
            if (ws) ws.close(); 
            if (pollingInterval) clearInterval(pollingInterval);
        };
    }, [selectedFile, localSource, processJobUpdate, state.analysisJobId, state.analysisComplete, actions]);

    // Dynamic counts
    const getCount = (key) => {
        if (analysisProgress?.[key]?.count !== undefined && analysisProgress[key].count !== 0) {
            return analysisProgress[key].count;
        }
        if (analysisProgress?.[key]?.items && Array.isArray(analysisProgress[key].items) && analysisProgress[key].items.length > 0) {
            return analysisProgress[key].items.length;
        }
        if (parsedData?.[key]?.count !== undefined) {
            return parsedData[key].count;
        }
        if (analysisResult?.[key] && Array.isArray(analysisResult[key]) && analysisResult[key].length > 0) {
            return analysisResult[key].length;
        }
        if (analysisResult?.statistics?.[key] !== undefined) {
            return analysisResult.statistics[key];
        }
        return 0;
    };

    const getItems = (key) => {
        if (analysisResult?.[key] && Array.isArray(analysisResult[key]) && analysisResult[key].length > 0) {
            return analysisResult[key];
        }
        if (analysisProgress?.[key]?.items && Array.isArray(analysisProgress[key].items) && analysisProgress[key].items.length > 0) {
            return analysisProgress[key].items;
        }
        if (parsedData?.[key]?.items && Array.isArray(parsedData[key].items) && parsedData[key].items.length > 0) {
            return parsedData[key].items;
        }
        return [];
    };

    const effectiveProgress = {
        tables: {
            count: getCount('tables'),
            items: getItems('tables')
        },
        queries: {
            count: getCount('queries'),
            items: getItems('queries')
        },
        forms: {
            count: getCount('forms'),
            items: getItems('forms')
        },
        reports: {
            count: getCount('reports'),
            items: getItems('reports')
        },
        macros: {
            count: getCount('macros'),
            items: getItems('macros')
        },
        vba: {
            count: getCount('vba'),
            items: getItems('vba')
        }
    };

    const totalObjectsCount = effectiveProgress.tables.count + effectiveProgress.queries.count + effectiveProgress.forms.count + effectiveProgress.reports.count + effectiveProgress.macros.count + effectiveProgress.vba.count;

    const getAnalysisTime = () => {
        if (state.analysisDuration) return state.analysisDuration;
        if (state.analysisComplete || state.analysisStatus === 'COMPLETED') {
            if (dynamicTimeDisplay) return dynamicTimeDisplay;
            const completedAt = state.analysisCompletedAt || Date.now();
            const startedAt = state.analysisStartedAt || state.analysisStartTime || analysisStartTimestampRef.current;
            return formatDuration(Math.max(1, Math.floor((completedAt - startedAt) / 1000)));
        }
        if (dynamicTimeDisplay) return dynamicTimeDisplay;
        if (state.analysisStartedAt || state.analysisStartTime) {
            const startedAt = state.analysisStartedAt || state.analysisStartTime;
            const diffSecs = Math.max(0, Math.floor((Date.now() - startedAt) / 1000));
            return formatDuration(diffSecs);
        }
        return '00:00:00';
    };

    const getLastScanned = () => {
        const d = new Date();
        const month = d.toLocaleString('en-US', { month: 'short' });
        const day = d.getDate();
        const year = d.getFullYear();
        let hours = d.getHours();
        const minutes = String(d.getMinutes()).padStart(2, '0');
        const ampm = hours >= 12 ? 'PM' : 'AM';
        hours = hours % 12;
        hours = hours ? hours : 12;
        return `${month} ${day}, ${year}, ${String(hours).padStart(2, '0')}:${minutes} ${ampm}`;
    };

    effectiveProgress.dbName = dbName;
    effectiveProgress.fileSize = getFileSize();
    effectiveProgress.lastScan = getLastScanned();
    effectiveProgress.analysisTime = getAnalysisTime();
    effectiveProgress.scanDuration = getAnalysisTime();

    const isStillWaiting = !state.analysisComplete && isAnalyzing;

    if (isStillWaiting && (selectedFile || localSource)) {
        return (
            <div style={{ width: '100%', height: '100%', minHeight: '500px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <Access2JavaLoader 
                    isVisible={true}
                    databaseName={dbName}
                    fileSize={getFileSize()}
                    scannedData={effectiveProgress}
                    isComplete={state.analysisComplete}
                />
            </div>
        );
    }

    return (
        <div style={{ display: 'flex', flexDirection: 'column', height: '100%', width: '100%', overflow: 'hidden', boxSizing: 'border-box' }}>
            {/* Main Content Dashboard with Dynamic Auto-Fit Zooming */}
            <div style={{ 
                display: 'flex', flexDirection: 'column', gap: isAutoFit ? '0.75rem' : '1.25rem', flex: 1, 
                padding: '0.25rem 0.5rem 1.5rem 0.5rem', 
                overflowY: 'auto', overflowX: 'hidden', width: '100%', boxSizing: 'border-box',
                zoom: isAutoFit ? '85%' : '100%',
                transition: 'all 0.25s ease'
            }}>
                {activeTab !== 'Overview' ? (
                    <DiscoveryDetailView 
                        activeTab={activeTab} 
                        onBack={() => setActiveTab('Overview')} 
                        progress={effectiveProgress} 
                        result={analysisResult} 
                    />
                ) : (
                    <>
                        {/* Top Header Row */}
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.75rem', width: '100%' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                                {isSidebarCollapsed && (
                                    <button 
                                        onClick={() => setIsSidebarCollapsed(false)}
                                        title="Show Sidebar"
                                        style={{ display: 'flex', alignItems: 'center', gap: '0.375rem', padding: '0.5rem 0.75rem', borderRadius: '10px', border: '1px solid #e2e8f0', backgroundColor: '#ffffff', color: '#4f46e5', fontWeight: 600, fontSize: '0.8125rem', cursor: 'pointer', boxShadow: '0 2px 4px rgba(0,0,0,0.02)' }}
                                    >
                                        <PanelLeftOpen size={16} /> Show Sidebar
                                    </button>
                                )}
                                <div>
                                    <h2 style={{ fontSize: 'clamp(1.125rem, 2vw, 1.375rem)', fontWeight: 800, color: '#15133A', marginBottom: '0.125rem' }}>Discovery Overview</h2>
                                    <p style={{ color: '#64748B', fontSize: 'clamp(0.75rem, 1.2vw, 0.8125rem)' }}>Complete inventory of your MS Access application</p>
                                </div>
                            </div>
                            
                            {/* Horizontal metadata pill cards */}
                            <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', flexWrap: 'nowrap' }}>
                                <div className="card" style={{ padding: '0.4rem 0.875rem', borderRadius: '12px', border: '1px solid #e2e8f0', backgroundColor: '#ffffff', display: 'flex', flexDirection: 'column', width: 'auto', flexShrink: 0 }}>
                                    <span style={{ fontSize: '0.625rem', color: '#64748B', textTransform: 'uppercase', letterSpacing: '0.04em' }}>Database</span>
                                    <span style={{ fontSize: '0.8125rem', fontWeight: 700, color: '#15133A', whiteSpace: 'nowrap' }}>{dbName}</span>
                                </div>
                                <div className="card" style={{ padding: '0.4rem 0.875rem', borderRadius: '12px', border: '1px solid #e2e8f0', backgroundColor: '#ffffff', display: 'flex', flexDirection: 'column', width: 'auto', flexShrink: 0 }}>
                                    <span style={{ fontSize: '0.625rem', color: '#64748B', textTransform: 'uppercase', letterSpacing: '0.04em' }}>File Size</span>
                                    <span style={{ fontSize: '0.8125rem', fontWeight: 700, color: '#15133A', whiteSpace: 'nowrap' }}>{getFileSize()}</span>
                                </div>
                                <div className="card" style={{ padding: '0.4rem 0.875rem', borderRadius: '12px', border: '1px solid #e2e8f0', backgroundColor: '#ffffff', display: 'flex', flexDirection: 'column', width: 'auto', flexShrink: 0 }}>
                                    <span style={{ fontSize: '0.625rem', color: '#64748B', textTransform: 'uppercase', letterSpacing: '0.04em' }}>Analysis Time</span>
                                    <span style={{ fontSize: '0.8125rem', fontWeight: 700, color: '#3730A3', whiteSpace: 'nowrap' }}>{getAnalysisTime()}</span>
                                </div>
                                <div className="card" style={{ padding: '0.4rem 0.875rem', borderRadius: '12px', border: '1px solid #e2e8f0', backgroundColor: '#ffffff', display: 'flex', flexDirection: 'column', width: 'auto', flexShrink: 0 }}>
                                    <span style={{ fontSize: '0.625rem', color: '#64748B', textTransform: 'uppercase', letterSpacing: '0.04em' }}>Last Scanned</span>
                                    <span style={{ fontSize: '0.8125rem', fontWeight: 700, color: '#15133A', whiteSpace: 'nowrap' }}>{getLastScanned()}</span>
                                </div>
                                <button 
                                    onClick={() => setIsAutoFit(!isAutoFit)}
                                    title={isAutoFit ? "Reset Zoom to 100%" : "Fit Dashboard to Screen"}
                                    style={{ 
                                        display: 'flex', alignItems: 'center', gap: '0.375rem', 
                                        backgroundColor: isAutoFit ? '#3730A3' : '#ffffff', 
                                        color: isAutoFit ? '#ffffff' : '#3730A3', 
                                        borderRadius: '12px', border: '1px solid #e2e8f0', 
                                        padding: '0.55rem 0.875rem', fontSize: '0.8125rem', fontWeight: 700, 
                                        cursor: 'pointer', whiteSpace: 'nowrap', flexShrink: 0,
                                        boxShadow: isAutoFit ? '0 4px 12px rgba(55, 48, 163, 0.3)' : '0 2px 4px rgba(0,0,0,0.02)',
                                        transition: 'all 0.15s ease'
                                    }}
                                >
                                    {isAutoFit ? <Minimize2 size={15} /> : <Maximize2 size={15} />}
                                    <span>{isAutoFit ? 'Reset View' : 'Fit to Screen'}</span>
                                </button>
                            </div>
                        </div>

                        {/* Stat Cards Grid - 100% Dynamic */}
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: isAutoFit ? '0.625rem' : '0.875rem', width: '100%' }}>
                            <StatCard title="Tables" value={effectiveProgress.tables.count} subtitle="Total Tables" icon={Database} iconColor="#6366f1" items={effectiveProgress.tables.items} onSelectTab={setActiveTab} />
                            <StatCard title="Queries" value={effectiveProgress.queries.count} subtitle="Total Queries" icon={Database} iconColor="#10b981" items={effectiveProgress.queries.items} onSelectTab={setActiveTab} />
                            <StatCard title="Forms" value={effectiveProgress.forms.count} subtitle="Total Forms" icon={Layout} iconColor="#f59e0b" items={effectiveProgress.forms.items} onSelectTab={setActiveTab} />
                            <StatCard title="Reports" value={effectiveProgress.reports.count} subtitle="Total Reports" icon={FileText} iconColor="#3b82f6" items={effectiveProgress.reports.items} onSelectTab={setActiveTab} />
                            <StatCard title="Macros" value={effectiveProgress.macros.count} subtitle="Total Macros" icon={PlaySquare} iconColor="#ec4899" items={effectiveProgress.macros.items} onSelectTab={setActiveTab} />
                            <StatCard title="Modules" value={effectiveProgress.vba.count} subtitle="Total VBA Modules" icon={Code} iconColor="#6366f1" items={effectiveProgress.vba.items} onSelectTab={setActiveTab} />
                        </div>

                        {/* Middle Cards Grid */}
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: isAutoFit ? '0.75rem' : '1rem', width: '100%' }}>
                            <ObjectDistributionChart data={effectiveProgress} />
                            <ComplexityScore progress={effectiveProgress} />
                            <KeyInsights progress={effectiveProgress} result={analysisResult} />
                        </div>

                        {/* Lower Middle Cards Grid */}
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(230px, 1fr))', gap: isAutoFit ? '0.75rem' : '1rem', width: '100%' }}>
                            <ModernizedOutput type="frontend" progress={effectiveProgress} />
                            <ModernizedOutput type="backend" progress={effectiveProgress} />
                            <FileGenerationChart progress={effectiveProgress} />
                            <TopComplexObjects progress={effectiveProgress} result={analysisResult} />
                        </div>

                        {/* Bottom Row Grid */}
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: isAutoFit ? '0.75rem' : '1rem', width: '100%' }}>
                            <TopTablesList progress={effectiveProgress} result={analysisResult} />
                            <DiscoverySummary 
                                progress={effectiveProgress}
                                onContinue={() => actions.nextStep()}
                            />
                        </div>
                        
                        {/* Status Success Banner */}
                        <div style={{ width: '100%', boxSizing: 'border-box', padding: '1rem 1.25rem', backgroundColor: '#fff7ed', border: '1px solid #fed7aa', borderRadius: '12px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '1rem', flexWrap: 'wrap' }}>
                            <div>
                                <div style={{ fontWeight: 700, fontSize: '0.875rem', color: '#9a3412' }}>Business Requirements Document</div>
                                <div style={{ fontSize: '0.75rem', color: '#7c2d12', marginTop: '0.2rem' }}>Generate a detailed report from the completed discovery analysis.</div>
                                {brdError && <div style={{ fontSize: '0.75rem', color: '#b91c1c', marginTop: '0.35rem' }}>{brdError}</div>}
                            </div>
                            <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                                <button className="btn btn-primary" onClick={handleGenerateBrd} disabled={brdLoading || !state.analysisJobId}>
                                    {brdLoading ? 'Generating...' : 'View BRD'}
                                </button>
                                <a className="btn btn-secondary" href={state.analysisJobId ? getBrdDownloadUrl(state.analysisJobId) : '#'} target="_blank" rel="noreferrer" style={{ pointerEvents: state.analysisJobId ? 'auto' : 'none', opacity: state.analysisJobId ? 1 : 0.5 }}>
                                    Download BRD
                                </a>
                            </div>
                        </div>

                        <div style={{ width: '100%', boxSizing: 'border-box', marginTop: '0.25rem', padding: '0.875rem 1.25rem', backgroundColor: '#ecfdf5', border: '1px solid #a7f3d0', borderRadius: '12px', display: 'flex', alignItems: 'center', gap: '0.75rem', color: '#065f46' }}>
                            <CheckCircle2 size={18} color="#10b981" />
                            <div>
                                <div style={{ fontWeight: 700, fontSize: '0.8125rem' }}>Discovery Completed Successfully!</div>
                                <div style={{ fontSize: '0.725rem', marginTop: '0.125rem' }}>
                                    Found {totalObjectsCount} total objects in {dbName}
                                </div>
                            </div>
                        </div>
                    </>
                )}
            </div>
        </div>
    );
}
