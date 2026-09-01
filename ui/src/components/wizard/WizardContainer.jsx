import React from 'react';
import { useWizard } from '../../context/WizardContext';
import { WIZARD_STEPS } from '../../utils/constants';
import Step1SelectApplication from './steps/Step1SelectApplication';
import Step2Analyze from './steps/Step2Analyze';
import Step3Configure from './steps/Step3Configure';
import Step4Review from './steps/Step4Review';
import Step5Generate from './steps/Step5Generate';
import Step6Summary from './steps/Step6Summary';

/* ── Per-step SVG icons ─────────────────────────────────────────── */
const STEP_ICONS = [
    /* 1 – Folder */
    <svg key="1" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
    </svg>,
    /* 2 – Search */
    <svg key="2" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
    </svg>,
    /* 3 – Gear */
    <svg key="3" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="3"/>
        <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>
    </svg>,
    /* 4 – Clipboard */
    <svg key="4" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/>
        <rect x="8" y="2" width="8" height="4" rx="1" ry="1"/>
        <line x1="9" y1="12" x2="15" y2="12"/>
        <line x1="9" y1="16" x2="15" y2="16"/>
    </svg>,
    /* 5 – Sparkle/wand */
    <svg key="5" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 3L13.5 8.5L19 10L13.5 11.5L12 17L10.5 11.5L5 10L10.5 8.5Z"/>
        <path d="M5 3L5.8 5.2L8 6L5.8 6.8L5 9L4.2 6.8L2 6L4.2 5.2Z"/>
        <path d="M19 14L19.8 16.2L22 17L19.8 17.8L19 20L18.2 17.8L16 17L18.2 16.2Z"/>
    </svg>,
    /* 6 – Check */
    <svg key="6" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
        <polyline points="20 6 9 17 4 12"/>
    </svg>,
];

const CheckIcon = () => (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
        <polyline points="20 6 9 17 4 12"/>
    </svg>
);

/**
 * Main wizard container with stepper navigation and step rendering.
 * Pixel-perfect implementation matching the AccessMigra reference design.
 */
export default function WizardContainer() {
    const { state, actions } = useWizard();
    const { currentStep } = state;

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

    const handleNext = () => { if (canProceed()) actions.nextStep(); };

    return (
        <div className="wizard-container fade-in wizard-card-entrance">

            {/* ── Stepper Progress Bar Card ── */}
            <div className="card-3d-lift" style={{
                background: '#fff',
                borderRadius: 20,
                boxShadow: '0 4px 16px rgba(55,48,163,0.09)',
                border: '1px solid #C7D2FE',
                padding: '0.75rem 2rem 0 2rem',
            }}>
                <div style={{
                    display: 'flex',
                    alignItems: 'flex-start',
                    justifyContent: 'space-between',
                }} role="navigation" aria-label="Wizard steps">
                    {WIZARD_STEPS.map((step, index) => {
                        const stepNumber = index + 1;
                        const isActive = stepNumber === currentStep;
                        const isCompleted = stepNumber < currentStep;
                        const isFuture = stepNumber > currentStep;

                        return (
                            <React.Fragment key={step.key}>
                                {/* ── Step item ── */}
                                <div
                                    onClick={() => !isFuture && actions.setStep(stepNumber)}
                                    role="button"
                                    aria-current={isActive ? 'step' : undefined}
                                    style={{
                                        display: 'flex',
                                        flexDirection: 'column',
                                        alignItems: 'center',
                                        cursor: isFuture ? 'default' : 'pointer',
                                        flex: 1,
                                        paddingBottom: 0,
                                        position: 'relative',
                                        minWidth: 0,
                                    }}
                                >
                                    {/* Step number above circle */}
                                    <span style={{
                                        fontSize: '0.72rem',
                                        fontWeight: 700,
                                        color: isActive ? '#3730A3' : '#9CA3AF',
                                        marginBottom: '0.45rem',
                                        letterSpacing: '0.03em',
                                    }}>
                                        {stepNumber}
                                    </span>

                                    {/* Icon circle */}
                                    <div style={{
                                        width: 42,
                                        height: 42,
                                        borderRadius: '50%',
                                        display: 'flex',
                                        alignItems: 'center',
                                        justifyContent: 'center',
                                        background: isActive
                                            ? 'linear-gradient(135deg, #3730A3 0%, #4F46E5 100%)'
                                            : isCompleted
                                                ? 'linear-gradient(135deg, #9B5CF6 0%, #D46BE0 100%)'
                                                : '#F8FAFC',
                                        border: isActive || isCompleted ? 'none' : '1.5px solid #C7D2FE',
                                        boxShadow: isActive ? '0 4px 18px rgba(55,48,163,0.32)' : 'none',
                                        transition: 'all 0.25s ease',
                                        opacity: isCompleted ? 0.75 : 1,
                                        color: isActive || isCompleted ? '#fff' : '#3730A3',
                                        flexShrink: 0,
                                        marginBottom: '0.55rem',
                                    }}>
                                        {isCompleted ? <CheckIcon /> : STEP_ICONS[index]}
                                    </div>

                                    {/* Label */}
                                    <span style={{
                                        fontSize: '0.78rem',
                                        fontWeight: isActive ? 700 : 500,
                                        color: isActive ? '#15133A' : '#9CA3AF',
                                        textAlign: 'center',
                                        lineHeight: 1.3,
                                        whiteSpace: 'pre-line',
                                        paddingBottom: '1rem',
                                    }}>
                                        {step.label.replace(' ', '\n')}
                                    </span>

                                    {/* Active underline */}
                                    {isActive && (
                                        <div style={{
                                            position: 'absolute',
                                            bottom: 0,
                                            left: '50%',
                                            transform: 'translateX(-50%)',
                                            width: '100%',
                                            height: 3,
                                            background: 'linear-gradient(90deg, #3730A3, #4F46E5)',
                                            borderRadius: '3px 3px 0 0',
                                        }} />
                                    )}
                                </div>

                                {/* Connector line between steps */}
                                {index < WIZARD_STEPS.length - 1 && (
                                    <div style={{
                                        flex: 1,
                                        height: 1.5,
                                        background: isCompleted ? 'linear-gradient(90deg, #9B5CF6, #D46BE0)' : '#C7D2FE',
                                        marginTop: 33, /* align to center of icon circle (num height ~22px + 0.45rem + half of 42px) */
                                        marginLeft: 2,
                                        marginRight: 2,
                                        flexShrink: 0,
                                        transition: 'background 0.25s ease',
                                    }} />
                                )}
                            </React.Fragment>
                        );
                    })}
                </div>
            </div>

            {/* ── Step Content Card ── */}
            <div className="card-3d-lift" style={{
                background: '#fff',
                borderRadius: 20,
                boxShadow: '0 4px 16px rgba(55,48,163,0.09)',
                border: '1px solid #C7D2FE',
                padding: '1rem 2rem',
            }}>
                {renderStepContent()}
            </div>

            {/* ── Bottom navigation: only Next button, right-aligned ── */}
            <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                {currentStep < 6 && (
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
                )}

                {currentStep === 6 && (
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
                )}
            </div>

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