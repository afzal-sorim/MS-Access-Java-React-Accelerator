import React, { useEffect } from 'react';
import { useWizard } from '../../context/WizardContext';
import { WIZARD_STEPS } from '../../utils/constants';
import { formatNumber } from '../../utils/helpers';
import Step1SelectApplication from './steps/Step1SelectApplication';
import Step2Analyze from './steps/Step2Analyze';
import Step3Configure from './steps/Step3Configure';
import Step4Review from './steps/Step4Review';
import Step5Generate from './steps/Step5Generate';
import Step6Summary from './steps/Step6Summary';

/**
 * Main wizard container with stepper navigation and step rendering.
 * Implements the 6-step wizard per spec section 47.
 */
export default function WizardContainer() {
    const { state, actions } = useWizard();
    const { currentStep } = state;

    // Render step content based on current step
    const renderStepContent = () => {
        switch (currentStep) {
            case 1:
                return <Step1SelectApplication />;
            case 2:
                return <Step2Analyze />;
            case 3:
                return <Step3Configure />;
            case 4:
                return <Step4Review />;
            case 5:
                return <Step5Generate />;
            case 6:
                return <Step6Summary />;
            default:
                return <Step1SelectApplication />;
        }
    };

    // Determine if next step should be enabled
    const canProceed = () => {
        switch (currentStep) {
            case 1:
                return !!state.selectedFile || !!state.localSource;
            case 2:
                return state.analysisComplete;
            case 3:
                return true; // Config is always valid with defaults
            case 4:
                return true; // Review is optional to complete
            case 5:
                return state.generationComplete;
            default:
                return false;
        }
    };

    const handleNext = () => {
        if (canProceed()) {
            actions.nextStep();
        }
    };

    const handlePrev = () => {
        actions.prevStep();
    };

    return (
        <div className="wizard-container fade-in">
            {/* Stepper Navigation */}
            <div className="wizard-stepper" role="navigation" aria-label="Wizard steps">
                {WIZARD_STEPS.map((step, index) => {
                    const stepNumber = index + 1;
                    const isActive = stepNumber === currentStep;
                    const isCompleted = stepNumber < currentStep;
                    const isFuture = stepNumber > currentStep;

                    return (
                        <React.Fragment key={step.key}>
                            <div
                                className={`wizard-step ${isActive ? 'active' : ''} ${isCompleted ? 'completed' : ''}`}
                                onClick={() => !isFuture && actions.setStep(stepNumber)}
                                style={{ cursor: isFuture ? 'not-allowed' : 'pointer' }}
                            >
                                <div className="wizard-step-icon">
                                    {isCompleted ? (
                                        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                                            <polyline points="20 6 9 17 4 12" />
                                        </svg>
                                    ) : (
                                        step.icon
                                    )}
                                </div>
                                <span className="wizard-step-label">{step.label}</span>
                            </div>
                            {index < WIZARD_STEPS.length - 1 && (
                                <div
                                    className={`wizard-step-connector ${isCompleted ? 'completed' : ''}`}
                                />
                            )}
                        </React.Fragment>
                    );
                })}
            </div>

            {/* Step Content */}
            <div className="card">
                {renderStepContent()}
            </div>

            {/* Navigation Buttons */}
            <div style={{ display: 'flex', justifyContent: 'space-between', paddingTop: '1rem' }}>
                <button
                    className="btn btn-secondary"
                    onClick={handlePrev}
                    disabled={currentStep === 1}
                >
                    ← Back
                </button>

                <div style={{ display: 'flex', gap: '0.75rem' }}>
                    {currentStep < 6 && (
                        <button
                            className="btn btn-primary"
                            onClick={handleNext}
                            disabled={!canProceed()}
                        >
                            Next →
                        </button>
                    )}

                    {currentStep === 6 && (
                        <button
                            className="btn btn-success"
                            onClick={actions.resetWizard}
                        >
                            Start New Conversion
                        </button>
                    )}
                </div>
            </div>

            {/* Error Toast */}
            {state.error && (
                <div className="alert alert-danger" style={{ marginTop: '1rem', position: 'fixed', bottom: '2rem', right: '2rem', zIndex: 1000, maxWidth: '400px' }}>
                    {state.error}
                    <button
                        onClick={actions.clearError}
                        style={{ marginLeft: '1rem', background: 'none', border: 'none', cursor: 'pointer', fontSize: '1.25rem', lineHeight: 1 }}
                    >
                        ×
                    </button>
                </div>
            )}
        </div>
    );
}