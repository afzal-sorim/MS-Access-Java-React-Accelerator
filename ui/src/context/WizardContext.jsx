import React, { createContext, useContext, useReducer, useCallback, useRef } from 'react';

const WizardContext = createContext(null);

/**
 * Initial state for the wizard.
 * Maps to spec section 47 (6 steps) and section 48 (object status model).
 */
const initialState = {
    // Current step (1-6)
    currentStep: 1,

    // Step 1: File selection
    selectedFile: null,
    fileMetadata: null,

    // Step 2: Analysis
    analysisJobId: null,
    analysisProgress: {
        tables: { status: 'pending', count: 0 },
        queries: { status: 'pending', count: 0 },
        forms: { status: 'pending', count: 0 },
        reports: { status: 'pending', count: 0 },
        vba: { status: 'pending', count: 0 },
        macros: { status: 'pending', count: 0 },
        dependencies: { status: 'pending', count: 0 },
    },
    analysisComplete: false,
    analysisResult: null,

    // Step 3: Configuration
    config: {
        project_name: 'ConvertedApplication',
        base_package: 'com.generated.app',
        java_version: 25,
        spring_boot_version: '4.1.0',
        react_version: '19.2.8',
        node_version: 24,
        postgres_version: '18',
        authentication_strategy: 'jwt',
        report_strategy: 'pdf',
        migration_strategy: 'flyway',
    },
    availableVersions: null,

    // Step 4: Review & Map
    reviewData: {
        tables: [],
        queries: [],
        forms: [],
        reports: [],
        modules: [],
        macros: [],
        externalDependencies: [],
    },
    reviewTab: 'tables',
    selectedObjects: new Set(),

    // Step 5: Generation
    generationJobId: null,
    generationProgress: {
        currentStep: 'initializing',
        completedSteps: [],
        failedSteps: [],
        percentage: 0,
        details: [],
    },
    generationComplete: false,
    generationResult: null,

    // Step 6: Summary
    summaryData: {
        coverage: {},
        buildStatus: 'pending',
        testStatus: 'pending',
        generatedPath: null,
    },

    // Error handling
    error: null,

    // Navigation history for back button
    history: [],
};

/**
 * Action types
 */
const ActionTypes = {
    // Step navigation
    SET_STEP: 'SET_STEP',
    NEXT_STEP: 'NEXT_STEP',
    PREV_STEP: 'PREV_STEP',

    // Step 1: File
    SET_FILE: 'SET_FILE',
    SET_FILE_METADATA: 'SET_FILE_METADATA',
    CLEAR_FILE: 'CLEAR_FILE',

    // Step 2: Analysis
    SET_ANALYSIS_JOB: 'SET_ANALYSIS_JOB',
    UPDATE_ANALYSIS_PROGRESS: 'UPDATE_ANALYSIS_PROGRESS',
    SET_ANALYSIS_COMPLETE: 'SET_ANALYSIS_COMPLETE',
    SET_ANALYSIS_RESULT: 'SET_ANALYSIS_RESULT',

    // Step 3: Configuration
    UPDATE_CONFIG: 'UPDATE_CONFIG',
    SET_VERSIONS: 'SET_VERSIONS',

    // Step 4: Review
    SET_REVIEW_DATA: 'SET_REVIEW_DATA',
    SET_REVIEW_TAB: 'SET_REVIEW_TAB',
    TOGGLE_OBJECT_SELECTION: 'TOGGLE_OBJECT_SELECTION',
    SELECT_ALL_OBJECTS: 'SELECT_ALL_OBJECTS',
    DESELECT_ALL_OBJECTS: 'DESELECT_ALL_OBJECTS',
    UPDATE_OBJECT_MAPPING: 'UPDATE_OBJECT_MAPPING',

    // Step 5: Generation
    SET_GENERATION_JOB: 'SET_GENERATION_JOB',
    UPDATE_GENERATION_PROGRESS: 'UPDATE_GENERATION_PROGRESS',
    SET_GENERATION_COMPLETE: 'SET_GENERATION_COMPLETE',
    SET_GENERATION_RESULT: 'SET_GENERATION_RESULT',
    ADD_GENERATION_DETAIL: 'ADD_GENERATION_DETAIL',

    // Step 6: Summary
    SET_SUMMARY_DATA: 'SET_SUMMARY_DATA',

    // Error handling
    SET_ERROR: 'SET_ERROR',
    CLEAR_ERROR: 'CLEAR_ERROR',

    // Reset
    RESET_WIZARD: 'RESET_WIZARD',
};

/**
 * Reducer for wizard state management
 */
function wizardReducer(state, action) {
    switch (action.type) {
        case ActionTypes.SET_STEP: {
            if (action.payload > state.currentStep) {
                return {
                    ...state,
                    history: [...state.history, state.currentStep],
                    currentStep: action.payload,
                };
            }
            return { ...state, currentStep: action.payload };
        }

        case ActionTypes.NEXT_STEP:
            return {
                ...state,
                history: [...state.history, state.currentStep],
                currentStep: Math.min(state.currentStep + 1, 6),
            };

        case ActionTypes.PREV_STEP:
            const previousStep = state.history[state.history.length - 1] || 1;
            return {
                ...state,
                currentStep: previousStep,
                history: state.history.slice(0, -1),
            };

        case ActionTypes.SET_FILE:
            return { ...state, selectedFile: action.payload };

        case ActionTypes.SET_FILE_METADATA:
            return { ...state, fileMetadata: action.payload };

        case ActionTypes.CLEAR_FILE:
            return { ...state, selectedFile: null, fileMetadata: null };

        case ActionTypes.SET_ANALYSIS_JOB:
            return { ...state, analysisJobId: action.payload, analysisComplete: false };

        case ActionTypes.UPDATE_ANALYSIS_PROGRESS:
            return {
                ...state,
                analysisProgress: {
                    ...state.analysisProgress,
                    ...action.payload,
                },
            };

        case ActionTypes.SET_ANALYSIS_COMPLETE:
            return { ...state, analysisComplete: action.payload };

        case ActionTypes.SET_ANALYSIS_RESULT:
            return { ...state, analysisResult: action.payload, analysisComplete: true };

        case ActionTypes.UPDATE_CONFIG:
            return {
                ...state,
                config: { ...state.config, ...action.payload },
            };

        case ActionTypes.SET_VERSIONS:
            return { ...state, availableVersions: action.payload };

        case ActionTypes.SET_REVIEW_DATA:
            return { ...state, reviewData: action.payload };

        case ActionTypes.SET_REVIEW_TAB:
            return { ...state, reviewTab: action.payload };

        case ActionTypes.TOGGLE_OBJECT_SELECTION: {
            const newSelected = new Set(state.selectedObjects);
            if (newSelected.has(action.payload)) {
                newSelected.delete(action.payload);
            } else {
                newSelected.add(action.payload);
            }
            return { ...state, selectedObjects: newSelected };
        }

        case ActionTypes.SELECT_ALL_OBJECTS: {
            const allIds = action.payload.map(obj => obj.id);
            return { ...state, selectedObjects: new Set(allIds) };
        }

        case ActionTypes.DESELECT_ALL_OBJECTS:
            return { ...state, selectedObjects: new Set() };

        case ActionTypes.UPDATE_OBJECT_MAPPING: {
            const { tab, objectId, mapping } = action.payload;
            const tabData = state.reviewData[tab].map(obj =>
                obj.id === objectId ? { ...obj, ...mapping } : obj
            );
            return {
                ...state,
                reviewData: { ...state.reviewData, [tab]: tabData },
            };
        }

        case ActionTypes.SET_GENERATION_JOB:
            return {
                ...state,
                generationJobId: action.payload,
                generationComplete: false,
                generationProgress: {
                    currentStep: 'initializing',
                    completedSteps: [],
                    failedSteps: [],
                    percentage: 0,
                    details: [],
                },
            };

        case ActionTypes.UPDATE_GENERATION_PROGRESS:
            return {
                ...state,
                generationProgress: {
                    ...state.generationProgress,
                    ...action.payload,
                },
            };

        case ActionTypes.ADD_GENERATION_DETAIL: {
            const details = [...state.generationProgress.details, action.payload];
            return {
                ...state,
                generationProgress: {
                    ...state.generationProgress,
                    details,
                },
            };
        }

        case ActionTypes.SET_GENERATION_COMPLETE:
            return { ...state, generationComplete: action.payload };

        case ActionTypes.SET_GENERATION_RESULT:
            return { ...state, generationResult: action.payload, generationComplete: true };

        case ActionTypes.SET_SUMMARY_DATA:
            return { ...state, summaryData: action.payload };

        case ActionTypes.SET_ERROR:
            return { ...state, error: action.payload };

        case ActionTypes.CLEAR_ERROR:
            return { ...state, error: null };

        case ActionTypes.RESET_WIZARD:
            return initialState;

        default:
            return state;
    }
}

/**
 * Wizard provider component
 */
export function WizardProvider({ children }) {
    const [state, dispatch] = useReducer(wizardReducer, initialState);
    const wsRef = useRef(null);

    const actions = {
        setStep: useCallback((step) => dispatch({ type: ActionTypes.SET_STEP, payload: step }), []),
        nextStep: useCallback(() => dispatch({ type: ActionTypes.NEXT_STEP }), []),
        prevStep: useCallback(() => dispatch({ type: ActionTypes.PREV_STEP }), []),

        setFile: useCallback((file) => dispatch({ type: ActionTypes.SET_FILE, payload: file }), []),
        setFileMetadata: useCallback((meta) => dispatch({ type: ActionTypes.SET_FILE_METADATA, payload: meta }), []),
        clearFile: useCallback(() => dispatch({ type: ActionTypes.CLEAR_FILE }), []),

        setAnalysisJob: useCallback((jobId) => dispatch({ type: ActionTypes.SET_ANALYSIS_JOB, payload: jobId }), []),
        updateAnalysisProgress: useCallback((progress) => dispatch({ type: ActionTypes.UPDATE_ANALYSIS_PROGRESS, payload: progress }), []),
        setAnalysisComplete: useCallback((complete) => dispatch({ type: ActionTypes.SET_ANALYSIS_COMPLETE, payload: complete }), []),
        setAnalysisResult: useCallback((result) => dispatch({ type: ActionTypes.SET_ANALYSIS_RESULT, payload: result }), []),

        updateConfig: useCallback((config) => dispatch({ type: ActionTypes.UPDATE_CONFIG, payload: config }), []),
        setVersions: useCallback((versions) => dispatch({ type: ActionTypes.SET_VERSIONS, payload: versions }), []),

        setReviewData: useCallback((data) => dispatch({ type: ActionTypes.SET_REVIEW_DATA, payload: data }), []),
        setReviewTab: useCallback((tab) => dispatch({ type: ActionTypes.SET_REVIEW_TAB, payload: tab }), []),
        toggleObjectSelection: useCallback((id) => dispatch({ type: ActionTypes.TOGGLE_OBJECT_SELECTION, payload: id }), []),
        selectAllObjects: useCallback((objects) => dispatch({ type: ActionTypes.SELECT_ALL_OBJECTS, payload: objects }), []),
        deselectAllObjects: useCallback(() => dispatch({ type: ActionTypes.DESELECT_ALL_OBJECTS }), []),
        updateObjectMapping: useCallback((tab, objectId, mapping) =>
            dispatch({ type: ActionTypes.UPDATE_OBJECT_MAPPING, payload: { tab, objectId, mapping } }), []),

        setGenerationJob: useCallback((jobId) => dispatch({ type: ActionTypes.SET_GENERATION_JOB, payload: jobId }), []),
        updateGenerationProgress: useCallback((progress) => dispatch({ type: ActionTypes.UPDATE_GENERATION_PROGRESS, payload: progress }), []),
        addGenerationDetail: useCallback((detail) => dispatch({ type: ActionTypes.ADD_GENERATION_DETAIL, payload: detail }), []),
        setGenerationComplete: useCallback((complete) => dispatch({ type: ActionTypes.SET_GENERATION_COMPLETE, payload: complete }), []),
        setGenerationResult: useCallback((result) => dispatch({ type: ActionTypes.SET_GENERATION_RESULT, payload: result }), []),

        setSummaryData: useCallback((data) => dispatch({ type: ActionTypes.SET_SUMMARY_DATA, payload: data }), []),

        setError: useCallback((error) => dispatch({ type: ActionTypes.SET_ERROR, payload: error }), []),
        clearError: useCallback(() => dispatch({ type: ActionTypes.CLEAR_ERROR }), []),

        resetWizard: useCallback(() => dispatch({ type: ActionTypes.RESET_WIZARD }), []),
    };

    return (
        <WizardContext.Provider value={{ state, actions, wsRef }}>
            {children}
        </WizardContext.Provider>
    );
}

/**
 * Hook to access wizard context
 */
export function useWizard() {
    const context = useContext(WizardContext);
    if (!context) {
        throw new Error('useWizard must be used within a WizardProvider');
    }
    return context;
}