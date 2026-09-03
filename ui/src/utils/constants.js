/**
 * Wizard step constants and state machine definitions.
 * Maps to spec section 47 (UI Wizard) and section 48 (Converter UI Status Model).
 */

// Wizard steps (spec section 47)
export const WIZARD_STEPS = [
    { id: 1, key: 'select', label: 'Select Application', icon: '📁' },
    { id: 2, key: 'analyze', label: 'Discovery', icon: '🔍' },
    { id: 3, key: 'configure', label: 'Configure', icon: '⚙️' },
    { id: 4, key: 'review', label: 'Map & Review', icon: '📋' },
    { id: 5, key: 'generate', label: 'Generate', icon: '🏗️' },
    { id: 6, key: 'summary', label: 'Summary', icon: '✅' },
];

// Object status states (spec section 48)
export const OBJECT_STATUS = {
    DISCOVERED: 'DISCOVERED',
    ANALYZING: 'ANALYZING',
    SUPPORTED: 'SUPPORTED',
    SUPPORTED_WITH_REVIEW: 'SUPPORTED_WITH_REVIEW',
    CONVERTING: 'CONVERTING',
    CONVERTED: 'CONVERTED',
    BUILD_ERROR: 'BUILD_ERROR',
    AUTO_REPAIRED: 'AUTO_REPAIRED',
    VALIDATED: 'VALIDATED',
    UNSUPPORTED: 'UNSUPPORTED',
    FAILED: 'FAILED',
};

// Job states from backend (spec section 65)
export const JOB_STATES = {
    CREATED: 'CREATED',
    UPLOADED: 'UPLOADED',
    EXTRACTING: 'EXTRACTING',
    ANALYZING: 'ANALYZING',
    DEPENDENCIES_DISCOVERED: 'DEPENDENCIES_DISCOVERED',
    IR_READY: 'IR_READY',
    SUPPORTABILITY_ANALYZED: 'SUPPORTABILITY_ANALYZED',
    READY_TO_GENERATE: 'READY_TO_GENERATE',
    GENERATING_DATABASE: 'GENERATING_DATABASE',
    GENERATING_BACKEND: 'GENERATING_BACKEND',
    GENERATING_FRONTEND: 'GENERATING_FRONTEND',
    RESOLVING_DEPENDENCIES: 'RESOLVING_DEPENDENCIES',
    BUILDING: 'BUILDING',
    REPAIRING: 'REPAIRING',
    TESTING: 'TESTING',
    VALIDATING: 'VALIDATING',
    COMPLETED: 'COMPLETED',
    FAILED: 'FAILED',
};

// Supportability status categories (spec section 12)
export const SUPPORTABILITY_STATUS = {
    SUPPORTED: 'SUPPORTED',
    SUPPORTED_WITH_TRANSFORMATION: 'SUPPORTED_WITH_TRANSFORMATION',
    SUPPORTED_WITH_REVIEW: 'SUPPORTED_WITH_REVIEW',
    UNSUPPORTED: 'UNSUPPORTED',
    FAILED_EXTRACTION: 'FAILED_EXTRACTION',
};

// Risk levels
export const RISK_LEVELS = {
    LOW: 'LOW',
    MEDIUM: 'MEDIUM',
    HIGH: 'HIGH',
    CRITICAL: 'CRITICAL',
};

// Color mapping for status badges
export const STATUS_COLORS = {
    SUPPORTED: '#10b981',
    SUPPORTED_WITH_REVIEW: '#f59e0b',
    SUPPORTED_WITH_TRANSFORMATION: '#3b82f6',
    UNSUPPORTED: '#ef4444',
    FAILED: '#dc2626',
    CONVERTED: '#10b981',
    CONVERTING: '#3b82f6',
    VALIDATED: '#10b981',
    BUILD_ERROR: '#ef4444',
    AUTO_REPAIRED: '#f59e0b',
};
