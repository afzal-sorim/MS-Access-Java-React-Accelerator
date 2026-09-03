
import React, { useState } from 'react';
import { useWizard } from '../../context/WizardContext';
import { WIZARD_STEPS } from '../../utils/constants';
import { parseAccessFile } from '../../utils/accessParser';
import Step1SelectApplication from './steps/Step1SelectApplication';
import Step2Analyze from './steps/Step2Analyze';
import Step3Configure from './steps/Step3Configure';
import Step4Review from './steps/Step4Review';
import Step5Generate from './steps/Step5Generate';
import Step6Summary from './steps/Step6Summary';
import { 
    ChevronRight, ChevronDown, Database, Sparkles, PanelLeftClose, PanelLeftOpen, CheckCircle2, ShieldCheck, Cpu,
    Table, Layout, FileText, PlaySquare, Code, Share2, GitFork, BookOpen, Layers
} from 'lucide-react';

/* ── Per-step SVG icons ─────────────────────────────────────────── */
const STEP_ICONS = [
    /* 1 – Folder */
    <svg key="1" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
    </svg>,
    /* 2 – Search */
    <svg key="2" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
    </svg>,
    /* 3 – Gear */
    <svg key="3" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="3"/>
        <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>
    </svg>,
    /* 4 – Clipboard */
    <svg key="4" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/>
        <rect x="8" y="2" width="8" height="4" rx="1" ry="1"/>
        <line x1="9" y1="12" x2="15" y2="12"/>
        <line x1="9" y1="16" x2="15" y2="16"/>
    </svg>,
    /* 5 – Sparkle/wand */
    <svg key="5" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 3L13.5 8.5L19 10L13.5 11.5L12 17L10.5 11.5L5 10L10.5 8.5Z"/>
        <path d="M5 3L5.8 5.2L8 6L5.8 6.8L5 9L4.2 6.8L2 6L4.2 5.2Z"/>
        <path d="M19 14L19.8 16.2L22 17L19.8 17.8L19 20L18.2 17.8L16 17L18.2 16.2Z"/>
    </svg>,
    /* 6 – Check */
    <svg key="6" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
        <polyline points="20 6 9 17 4 12"/>
    </svg>,
];

const STEP_SUBTITLES = [
    'Upload & Source DB',
    'Analyze & Inventory',
    'Target Stack Config',
    'Review & Map Entities',
    'Code Generation',
    'Build & Artifacts'
];

const CheckIcon = () => (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
        <polyline points="20 6 9 17 4 12"/>
    </svg>
);

export default function WizardContainer() {
    const { state, actions } = useWizard();
    const { currentStep } = state;
    // Sidebar is OPEN by default. Toggles ONLY when clicking the toggle button (hover animation removed).
    const [isCollapsed, setIsCollapsed] = useState(false);
    const isExpanded = !isCollapsed;

    // Discovery components submenu: closed by default ("shows defaultly"), toggles open on click
    const [isDiscoveryOpen, setIsDiscoveryOpen] = useState(false);

    const renderStepContent = () => {
        switch (currentStep) {
            case 1: return <Step1SelectApplication />;
            case 2: return <Step2Analyze />;
            case 3: return <Step3Configure />;
            case 4: return <Step4Review />;
            case 5: return <Step5Generate />;
            case 6: return <Step6Summary />;
            default: return <Step1SelectApplication />;
        }
    };

    const canProceed = () => {
        switch (currentStep) {
            case 1: return !!state.selectedFile || !!state.localSource;
            case 2: return state.analysisComplete;
            case 3: return true;
            case 4: return true;
            case 5: return state.generationComplete;
            default: return false;
        }
    };

    const handleNext = () => {
        if (!canProceed()) return;

        if (currentStep === 1) {
            // Immediately record analysis start timestamp BEFORE discovery starts
            const scanStartTime = Date.now();
            if (typeof actions.startAnalysisTimer === 'function') {
                actions.startAnalysisTimer(scanStartTime);
            } else if (typeof actions.setAnalysisStartTime === 'function') {
                actions.setAnalysisStartTime(scanStartTime);
            }
            actions.nextStep();
        } else {
            actions.nextStep();
        }
    };

    const dbName = state.selectedFile?.name || state.fileMetadata?.name || state.localSource?.path?.split(/[/\\]/).pop() || null;
    const progressPercent = Math.round(((currentStep - 1) / (WIZARD_STEPS.length - 1)) * 100);

    // Show next button only when appropriate (never on the loading state)
    const isStep2Loading = currentStep === 2 && !state.analysisComplete;
    const showNextButton = currentStep < 6 && !isStep2Loading;

    // Discovery Submenu Items
    const discoverySubItems = [
        { label: 'Overview', icon: Layers, count: null },
        { label: 'Tables', icon: Table, count: state.analysisProgress?.tables?.count ?? state.analysisProgress?.tables?.items?.length ?? 0 },
        { label: 'Queries', icon: Database, count: state.analysisProgress?.queries?.count ?? state.analysisProgress?.queries?.items?.length ?? 0 },
        { label: 'Forms', icon: Layout, count: state.analysisProgress?.forms?.count ?? state.analysisProgress?.forms?.items?.length ?? 0 },
        { label: 'Reports', icon: FileText, count: state.analysisProgress?.reports?.count ?? state.analysisProgress?.reports?.items?.length ?? 0 },
        { label: 'Macros', icon: PlaySquare, count: state.analysisProgress?.macros?.count ?? state.analysisProgress?.macros?.items?.length ?? 0 },
        { label: 'Modules', icon: Code, count: state.analysisProgress?.vba?.count ?? state.analysisProgress?.vba?.items?.length ?? 0 },
        { label: 'Relationships', icon: Share2, count: null },
        { label: 'Dependencies', icon: GitFork, count: null },
        { label: 'Data Dictionary', icon: BookOpen, count: null }
    ];

    return (
        <div className="wizard-container fade-in wizard-card-entrance" style={{ 
            display: 'flex', 
            flexDirection: 'row',
            alignItems: 'stretch',
            gap: '0', 
            width: '100%', 
            minWidth: 0,
            minHeight: 'calc(100vh - 68px)',
            background: '#ffffff',
            boxSizing: 'border-box'
        }}>
            {/* ── Stepper Sidebar (Scrolls vertically when needed) ── */}
            <aside 
                className="sidebar-scrollable"
                style={{
                    width: isExpanded ? '290px' : '76px',
                    minWidth: isExpanded ? '290px' : '76px',
                    maxWidth: isExpanded ? '290px' : '76px',
                    flexShrink: 0,
                    background: '#ffffff',
                    borderRight: '1px solid #e2e8f0',
                    padding: isExpanded ? '1.5rem 1.25rem' : '1.5rem 0.6rem',
                    display: 'flex',
                    flexDirection: 'column',
                    justifyContent: 'flex-start',
                    boxSizing: 'border-box',
                    position: 'sticky',
                    top: '0',
                    height: 'calc(100vh - 64px)',
                    zIndex: 100,
                    overflowY: 'auto',
                    overflowX: 'hidden',
                    boxShadow: 'none',
                    transition: 'width 0.25s ease, padding 0.25s ease'
                }}
            >
                <div style={{ display: 'flex', flexDirection: 'column', flex: 1, minWidth: 0 }}>
                    {/* ── Sidebar Header: Progress & Toggle Button (Logo moved to top header) ── */}
                    {isExpanded ? (
                        <div style={{ marginBottom: '1.5rem', paddingBottom: '1.25rem', borderBottom: '1px solid #f1f5f9' }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                                <div>
                                    <span style={{ fontSize: '0.6875rem', textTransform: 'uppercase', letterSpacing: '0.08em', fontWeight: 800, color: '#6366f1' }}>
                                        Workflow Pipeline
                                    </span>
                                    <div style={{ fontSize: '1.15rem', fontWeight: 800, color: '#15133A', marginTop: '0.2rem' }}>
                                        Progress Stepper
                                    </div>
                                </div>
                                <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
                                    <span style={{ fontSize: '0.75rem', fontWeight: 800, color: '#3730A3' }}>
                                        {progressPercent}%
                                    </span>
                                    <button
                                        onClick={(e) => {
                                            e.stopPropagation();
                                            setIsCollapsed(true);
                                        }}
                                        title="Collapse sidebar"
                                        style={{
                                            display: 'flex',
                                            alignItems: 'center',
                                            justifyContent: 'center',
                                            width: '32px',
                                            height: '32px',
                                            borderRadius: '8px',
                                            border: '1px solid #e2e8f0',
                                            backgroundColor: '#ffffff',
                                            color: '#4f46e5',
                                            cursor: 'pointer',
                                            transition: 'all 0.15s ease',
                                            flexShrink: 0
                                        }}
                                        onMouseEnter={e => { e.currentTarget.style.backgroundColor = '#f1f5f9'; }}
                                        onMouseLeave={e => { e.currentTarget.style.backgroundColor = '#ffffff'; }}
                                    >
                                        <PanelLeftClose size={16} />
                                    </button>
                                </div>
                            </div>

                            {/* Top Mini Progress Track */}
                            <div style={{ width: '100%', height: '5px', backgroundColor: '#e2e8f0', borderRadius: '999px', marginTop: '0.75rem', overflow: 'hidden' }}>
                                <div style={{ 
                                    width: `${Math.max(8, progressPercent)}%`, 
                                    height: '100%', 
                                    background: 'linear-gradient(90deg, #6366f1 0%, #3730A3 100%)',
                                    borderRadius: '999px',
                                    transition: 'width 0.3s ease'
                                }} />
                            </div>
                        </div>
                    ) : (
                        <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', paddingBottom: '1.25rem', marginBottom: '1.25rem', borderBottom: '1px solid #f1f5f9' }}>
                            <button
                                onClick={(e) => {
                                    e.stopPropagation();
                                    setIsCollapsed(false);
                                }}
                                title="Expand sidebar"
                                style={{
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'center',
                                    width: '36px',
                                    height: '36px',
                                    borderRadius: '10px',
                                    border: '1px solid #c7d2fe',
                                    backgroundColor: '#f5f3ff',
                                    color: '#4f46e5',
                                    cursor: 'pointer',
                                    transition: 'all 0.2s ease',
                                    boxShadow: '0 2px 8px rgba(99, 102, 241, 0.15)'
                                }}
                                onMouseEnter={e => { e.currentTarget.style.backgroundColor = '#4f46e5'; e.currentTarget.style.color = '#ffffff'; }}
                                onMouseLeave={e => { e.currentTarget.style.backgroundColor = '#f5f3ff'; e.currentTarget.style.color = '#4f46e5'; }}
                            >
                                <PanelLeftOpen size={18} />
                            </button>
                        </div>
                    )}

                    {/* Step Items List with Integrated Submenu Under Discovery */}
                    <nav style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }} aria-label="Wizard steps">
                        {WIZARD_STEPS.map((step, index) => {
                            const stepNum = index + 1;
                            const isActive = currentStep === stepNum;
                            const isCompleted = currentStep > stepNum;
                            const isClickable = isCompleted;

                            // Show Discovery submenu only when hovered AND Discovery step is complete
                            const showDiscoverySubmenu = isExpanded && stepNum === 2 && isDiscoveryOpen && state.analysisComplete;

                            return (
                                <div key={step.id} style={{ display: 'flex', flexDirection: 'column' }}>
                                    {/* Step Item Row */}
                                    <div 
                                        onClick={() => { 
                                            if (isClickable) {
                                                actions.setStep(stepNum);
                                                if (stepNum === 2 && state.analysisComplete) {
                                                    setIsDiscoveryOpen(prev => !prev);
                                                }
                                            }
                                        }}
                                        title={!isExpanded ? `${step.label} (Step ${stepNum})` : ''}
                                        style={{
                                            display: 'flex',
                                            alignItems: 'center',
                                            justifyContent: isExpanded ? 'flex-start' : 'center',
                                            gap: isExpanded ? '0.875rem' : '0',
                                            padding: isExpanded ? '0.75rem 0.875rem' : '0.65rem 0',
                                            borderRadius: '14px',
                                            cursor: isClickable ? 'pointer' : 'default',
                                            backgroundColor: isActive ? '#f5f3ff' : 'transparent',
                                            border: isActive ? '1px solid #c7d2fe' : '1px solid transparent',
                                            boxShadow: isActive ? '0 2px 8px rgba(99, 102, 241, 0.08)' : 'none',
                                            transition: 'all 0.25s ease',
                                            position: 'relative'
                                        }}
                                        onMouseEnter={(e) => {
                                            if (isClickable) e.currentTarget.style.backgroundColor = '#f8fafc';
                                        }}
                                        onMouseLeave={(e) => {
                                            e.currentTarget.style.backgroundColor = isActive ? '#f5f3ff' : 'transparent';
                                        }}
                                    >
                                        {/* Icon Container */}
                                        <div style={{
                                            width: '40px',
                                            height: '40px',
                                            borderRadius: '12px',
                                            display: 'flex',
                                            alignItems: 'center',
                                            justifyContent: 'center',
                                            background: isActive
                                                ? 'linear-gradient(135deg, #3730A3 0%, #4F46E5 100%)'
                                                : isCompleted
                                                    ? 'linear-gradient(135deg, #10b981 0%, #059669 100%)'
                                                    : '#F8FAFC',
                                            border: isActive || isCompleted ? 'none' : '1.5px solid #E2E8F0',
                                            boxShadow: isActive ? '0 4px 14px rgba(55,48,163,0.32)' : 'none',
                                            color: isActive || isCompleted ? '#ffffff' : '#94A3B8',
                                            flexShrink: 0,
                                            transition: 'all 0.2s ease'
                                        }}>
                                            {isCompleted ? <CheckIcon /> : STEP_ICONS[index]}
                                        </div>

                                        {/* Labels (Only rendered when sidebar is hovered) */}
                                        {isExpanded && (
                                            <div style={{ display: 'flex', flexDirection: 'column', minWidth: 0, flex: 1, animation: 'fadeIn 0.2s ease-out' }}>
                                                <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                                                    <span style={{ 
                                                        fontSize: '0.625rem', 
                                                        fontWeight: 800, 
                                                        color: isActive ? '#4f46e5' : isCompleted ? '#059669' : '#94a3b8',
                                                        letterSpacing: '0.04em'
                                                    }}>
                                                        STEP 0{stepNum}
                                                    </span>
                                                    {isCompleted && (
                                                        <span style={{ fontSize: '0.625rem', fontWeight: 700, color: '#10b981' }}>✓</span>
                                                    )}
                                                </div>
                                                <span style={{
                                                    fontSize: '0.875rem',
                                                    fontWeight: isActive ? 800 : isCompleted ? 700 : 600,
                                                    color: isActive ? '#15133A' : isCompleted ? '#334155' : '#64748B',
                                                    whiteSpace: 'nowrap',
                                                    overflow: 'hidden',
                                                    textOverflow: 'ellipsis'
                                                }}>
                                                    {step.label}
                                                </span>
                                                <span style={{
                                                    fontSize: '0.6875rem',
                                                    color: '#94a3b8',
                                                    whiteSpace: 'nowrap',
                                                    overflow: 'hidden',
                                                    textOverflow: 'ellipsis'
                                                }}>
                                                    {STEP_SUBTITLES[index]}
                                                </span>
                                            </div>
                                        )}

                                        {/* Active Right Chevron Indicator / Discovery Submenu Toggle */}
                                        {isExpanded && (
                                            stepNum === 2 && state.analysisComplete ? (
                                                <button
                                                    onClick={(e) => {
                                                        e.stopPropagation();
                                                        if (currentStep !== 2 && isClickable) {
                                                            actions.setStep(2);
                                                        }
                                                        setIsDiscoveryOpen(prev => !prev);
                                                    }}
                                                    title={isDiscoveryOpen ? "Hide discovery components" : "Show discovery components"}
                                                    style={{
                                                        display: 'flex',
                                                        alignItems: 'center',
                                                        justifyContent: 'center',
                                                        width: '26px',
                                                        height: '26px',
                                                        borderRadius: '8px',
                                                        border: isDiscoveryOpen ? '1px solid #4f46e5' : '1px solid #c7d2fe',
                                                        backgroundColor: isDiscoveryOpen ? '#4f46e5' : '#ffffff',
                                                        color: isDiscoveryOpen ? '#ffffff' : '#4f46e5',
                                                        cursor: 'pointer',
                                                        flexShrink: 0,
                                                        transition: 'all 0.2s ease',
                                                        boxShadow: '0 1px 4px rgba(99, 102, 241, 0.15)'
                                                    }}
                                                    onMouseEnter={e => {
                                                        if (!isDiscoveryOpen) {
                                                            e.currentTarget.style.backgroundColor = '#f5f3ff';
                                                        }
                                                    }}
                                                    onMouseLeave={e => {
                                                        if (!isDiscoveryOpen) {
                                                            e.currentTarget.style.backgroundColor = '#ffffff';
                                                        }
                                                    }}
                                                >
                                                    {isDiscoveryOpen ? <ChevronDown size={15} /> : <ChevronRight size={15} />}
                                                </button>
                                            ) : (
                                                isActive && <ChevronRight size={16} color="#4f46e5" style={{ flexShrink: 0 }} />
                                            )
                                        )}
                                    </div>

                                    {/* ── Submenu directly inside the stepper under Discovery ── */}
                                    {showDiscoverySubmenu && (
                                        <div style={{
                                            marginLeft: '20px',
                                            paddingLeft: '14px',
                                            borderLeft: '2px solid #C7D2FE',
                                            marginTop: '0.5rem',
                                            marginBottom: '0.5rem',
                                            display: 'flex',
                                            flexDirection: 'column',
                                            gap: '0.2rem',
                                            animation: 'fadeIn 0.2s ease-out'
                                        }}>
                                            {discoverySubItems.map((subItem) => {
                                                const SubIcon = subItem.icon;
                                                const currentTab = state.discoveryTab || 'Overview';
                                                const isSubActive = currentTab === subItem.label;

                                                return (
                                                    <div 
                                                        key={subItem.label}
                                                        onClick={(e) => {
                                                            e.stopPropagation();
                                                            if (typeof actions.setDiscoveryTab === 'function') {
                                                                actions.setDiscoveryTab(subItem.label);
                                                            }
                                                        }}
                                                        style={{
                                                            display: 'flex',
                                                            alignItems: 'center',
                                                            justifyContent: 'space-between',
                                                            padding: '0.45rem 0.65rem',
                                                            borderRadius: '9px',
                                                            cursor: 'pointer',
                                                            fontSize: '0.78rem',
                                                            fontWeight: isSubActive ? 700 : 500,
                                                            backgroundColor: isSubActive ? '#3730A3' : 'transparent',
                                                            color: isSubActive ? '#ffffff' : '#334155',
                                                            transition: 'all 0.15s ease'
                                                        }}
                                                        onMouseEnter={(e) => {
                                                            if (!isSubActive) {
                                                                e.currentTarget.style.backgroundColor = '#f1f5f9';
                                                                e.currentTarget.style.color = '#15133A';
                                                            }
                                                        }}
                                                        onMouseLeave={(e) => {
                                                            if (!isSubActive) {
                                                                e.currentTarget.style.backgroundColor = 'transparent';
                                                                e.currentTarget.style.color = '#334155';
                                                            }
                                                        }}
                                                    >
                                                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.55rem' }}>
                                                            <SubIcon size={15} color={isSubActive ? '#ffffff' : '#64748B'} />
                                                            <span>{subItem.label}</span>
                                                        </div>
                                                        {subItem.count !== null && (
                                                            <span style={{
                                                                fontSize: '0.6875rem',
                                                                fontWeight: 700,
                                                                color: isSubActive ? '#ffffff' : '#64748B',
                                                                backgroundColor: isSubActive ? 'rgba(255,255,255,0.2)' : '#f1f5f9',
                                                                padding: '0.1rem 0.45rem',
                                                                borderRadius: '6px'
                                                            }}>
                                                                {subItem.count}
                                                            </span>
                                                        )}
                                                    </div>
                                                );
                                            })}
                                        </div>
                                    )}

                                    {/* Vertical Connector Line */}
                                    {index < WIZARD_STEPS.length - 1 && (
                                        <div style={{
                                            width: '2px',
                                            height: '18px',
                                            backgroundColor: isCompleted ? '#10b981' : '#e2e8f0',
                                            marginLeft: isExpanded ? '28px' : 'auto',
                                            marginRight: isExpanded ? '0' : 'auto',
                                            marginTop: '3px',
                                            marginBottom: '3px',
                                            transition: 'all 0.25s ease'
                                        }} />
                                    )}
                                </div>
                            );
                        })}
                    </nav>
                </div>

            </aside>

            {/* ── Main Content Area (Scrolls independently for discovery overview) ── */}
            <main 
                className="content-scrollable"
                style={{ 
                    flex: 1, 
                    minWidth: 0, 
                    height: 'calc(100vh - 64px)',
                    overflowY: 'auto',
                    overflowX: 'hidden',
                    display: 'flex', 
                    flexDirection: 'column', 
                    background: '#ffffff',
                    padding: '1.5rem 2.25rem',
                    gap: '1.25rem', 
                    position: 'relative', 
                    zIndex: 1,
                    boxSizing: 'border-box'
                }}
            >
                {/* Step Content Container */}
                <div style={{
                    background: '#ffffff',
                    width: '100%',
                    flex: 1,
                    minHeight: '650px',
                    boxSizing: 'border-box'
                }}>
                    {renderStepContent()}
                </div>

                {/* Bottom Navigation Row */}
                {showNextButton && (
                    <div style={{ display: 'flex', justifyContent: 'flex-end', alignItems: 'center' }}>
                        <button
                            onClick={handleNext}
                            disabled={!canProceed()}
                            style={{
                                display: 'inline-flex',
                                alignItems: 'center',
                                gap: '0.6rem',
                                padding: '0.75rem 2.25rem',
                                borderRadius: 12,
                                background: 'linear-gradient(135deg, #3730A3 0%, #4F46E5 100%)',
                                color: '#fff',
                                fontWeight: 700,
                                fontSize: '0.9375rem',
                                border: 'none',
                                boxShadow: '0 6px 22px rgba(55,48,163,0.30)',
                                cursor: canProceed() ? 'pointer' : 'not-allowed',
                                opacity: canProceed() ? 1 : 0.45,
                                transition: 'all 0.15s ease',
                                letterSpacing: '0.01em',
                            }}
                            onMouseEnter={e => { if (canProceed()) { e.currentTarget.style.boxShadow = '0 8px 28px rgba(55,48,163,0.42)'; e.currentTarget.style.transform = 'translateY(-2px)'; } }}
                            onMouseLeave={e => { e.currentTarget.style.boxShadow = '0 6px 22px rgba(55,48,163,0.30)'; e.currentTarget.style.transform = 'translateY(0)'; }}
                        >
                            Next
                            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                                <line x1="5" y1="12" x2="19" y2="12"/>
                                <polyline points="12 5 19 12 12 19"/>
                            </svg>
                        </button>
                    </div>
                )}

                {currentStep === 6 && (
                    <div style={{ display: 'flex', justifyContent: 'flex-end', alignItems: 'center' }}>
                        <button
                            onClick={actions.resetWizard}
                            style={{
                                display: 'inline-flex', alignItems: 'center', gap: '0.6rem',
                                padding: '0.75rem 2.25rem', borderRadius: 12,
                                background: 'linear-gradient(135deg, #3730A3 0%, #4F46E5 100%)',
                                color: '#fff', fontWeight: 700, fontSize: '0.9375rem',
                                border: 'none', boxShadow: '0 6px 22px rgba(55,48,163,0.30)', cursor: 'pointer',
                            }}
                        >
                            Start New Conversion
                            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                                <line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/>
                            </svg>
                        </button>
                    </div>
                )}
            </main>

            {/* ── Error Toast ── */}
            {state.error && (
                <div className="alert alert-danger" style={{ marginTop: '1rem', position: 'fixed', bottom: '2rem', right: '2rem', zIndex: 1000, maxWidth: '420px', boxShadow: '0 8px 32px rgba(0,0,0,0.15)' }}>
                    {state.error}
                    <button onClick={actions.clearError} style={{ marginLeft: '1rem', background: 'none', border: 'none', cursor: 'pointer', fontSize: '1.25rem', lineHeight: 1 }}>×</button>
                </div>
            )}
        </div>
    );
}
