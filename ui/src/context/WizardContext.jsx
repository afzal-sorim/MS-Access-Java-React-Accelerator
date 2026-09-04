import React, { createContext, useContext, useReducer, useRef, useMemo } from 'react';

function formatDuration(totalSeconds) {
    const s = Math.max(0, Math.floor(totalSeconds));
    const hrs = String(Math.floor(s / 3600)).padStart(2, '0');
    const mins = String(Math.floor((s % 3600) / 60)).padStart(2, '0');
    const secs = String(s % 60).padStart(2, '0');
    return `${hrs}:${mins}:${secs}`;
}

const WizardContext = createContext(null);

// Timing persistence helper for Discovery Analysis Time
const TIMING_STORAGE_KEY = 'msaccess_wizard_analysis_timing';

function loadStoredTiming() {
    try {
        if (typeof window !== 'undefined' && window.sessionStorage) {
            const stored = window.sessionStorage.getItem(TIMING_STORAGE_KEY);
            if (stored) {
                return JSON.parse(stored);
            }
        }
    } catch (e) {}
    return null;
}

const savedTiming = loadStoredTiming();

/**
 * Initial state for the wizard.
 * Maps to spec section 47 (6 steps) and section 48 (object status model).
 */
const initialState = {
    // Current step (1-6)
    currentStep: 1,

    // Step 1: File selection
    // Two input modes: 'upload' posts a File through multipart; 'local' points
    // the backend at a database already on the machine running MS Access.
    sourceMode: 'upload',
    selectedFile: null,
    fileMetadata: null,
    localSource: null,

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
    analysisComplete: savedTiming?.analysisStatus === 'COMPLETED',
    analysisResult: null,
    analysisStartedAt: savedTiming?.analysisStartedAt || null,
    analysisCompletedAt: savedTiming?.analysisCompletedAt || null,
    analysisDuration: savedTiming?.analysisDuration || null,
    analysisStatus: savedTiming?.analysisStatus || 'IDLE',
    analysisStartTime: savedTiming?.analysisStartedAt || null,
    discoveryTab: 'Overview',

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
    SET_SOURCE_MODE: 'SET_SOURCE_MODE',
    SET_LOCAL_SOURCE: 'SET_LOCAL_SOURCE',

    // Step 2: Analysis
    SET_ANALYSIS_JOB: 'SET_ANALYSIS_JOB',
    UPDATE_ANALYSIS_PROGRESS: 'UPDATE_ANALYSIS_PROGRESS',
    SET_ANALYSIS_COMPLETE: 'SET_ANALYSIS_COMPLETE',
    SET_ANALYSIS_RESULT: 'SET_ANALYSIS_RESULT',
    SET_ANALYSIS_START_TIME: 'SET_ANALYSIS_START_TIME',
    SET_ANALYSIS_DURATION: 'SET_ANALYSIS_DURATION',
    START_ANALYSIS_TIMER: 'START_ANALYSIS_TIMER',
    COMPLETE_ANALYSIS_TIMER: 'COMPLETE_ANALYSIS_TIMER',
    FAIL_ANALYSIS_TIMER: 'FAIL_ANALYSIS_TIMER',
    RESET_ANALYSIS_TIMER: 'RESET_ANALYSIS_TIMER',
    SET_DISCOVERY_TAB: 'SET_DISCOVERY_TAB',

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

        case ActionTypes.SET_FILE: {
            try {
                if (typeof window !== 'undefined' && window.sessionStorage) {
                    window.sessionStorage.removeItem(TIMING_STORAGE_KEY);
                }
            } catch (e) {}
            return { 
                ...state, 
                selectedFile: action.payload,
                analysisStartedAt: null,
                analysisCompletedAt: null,
                analysisDuration: null,
                analysisStatus: 'IDLE',
                analysisComplete: false,
            };
        }

        case ActionTypes.SET_FILE_METADATA:
            return { ...state, fileMetadata: action.payload };

        case ActionTypes.CLEAR_FILE:
            return { ...state, selectedFile: null, fileMetadata: null, localSource: null };

        case ActionTypes.SET_SOURCE_MODE:
            // The two modes are mutually exclusive — switching clears the
            // other mode's selection so Step 2 can never see both.
            return {
                ...state,
                sourceMode: action.payload,
                selectedFile: null,
                fileMetadata: null,
                localSource: null,
            };

        case ActionTypes.SET_LOCAL_SOURCE:
            return { ...state, localSource: action.payload };

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

        case ActionTypes.SET_ANALYSIS_COMPLETE: {
            const isComplete = Boolean(action.payload);
            if (isComplete && !state.analysisDuration) {
                const completedAt = state.analysisCompletedAt || Date.now();
                const startedAt = state.analysisStartedAt || state.analysisStartTime || Date.now();
                const durationSecs = Math.max(1, Math.floor((completedAt - startedAt) / 1000));
                const finalDuration = formatDuration(durationSecs);
                try {
                    if (typeof window !== 'undefined' && window.sessionStorage) {
                        window.sessionStorage.setItem(TIMING_STORAGE_KEY, JSON.stringify({
                            analysisStartedAt: startedAt,
                            analysisCompletedAt: completedAt,
                            analysisDuration: finalDuration,
                            analysisStatus: 'COMPLETED',
                        }));
                    }
                } catch (e) {}
                return {
                    ...state,
                    analysisComplete: true,
                    analysisStatus: 'COMPLETED',
                    analysisCompletedAt: completedAt,
                    analysisDuration: finalDuration,
                };
            }
            return { 
                ...state, 
                analysisComplete: isComplete,
                analysisStatus: isComplete ? 'COMPLETED' : state.analysisStatus,
            };
        }

        case ActionTypes.SET_ANALYSIS_RESULT:
            return { ...state, analysisResult: action.payload, analysisComplete: true };

        case ActionTypes.SET_DISCOVERY_TAB:
            return { ...state, discoveryTab: action.payload };

        case ActionTypes.START_ANALYSIS_TIMER: {
            const startedAt = action.payload || Date.now();
            const updated = {
                ...state,
                analysisStartedAt: startedAt,
                analysisStartTime: startedAt,
                analysisCompletedAt: null,
                analysisDuration: null,
                analysisStatus: 'RUNNING',
                analysisComplete: false,
            };
            try {
                if (typeof window !== 'undefined' && window.sessionStorage) {
                    window.sessionStorage.setItem(TIMING_STORAGE_KEY, JSON.stringify({
                        analysisStartedAt: startedAt,
                        analysisCompletedAt: null,
                        analysisDuration: null,
                        analysisStatus: 'RUNNING',
                    }));
                }
            } catch (e) {}
            return updated;
        }

        case ActionTypes.COMPLETE_ANALYSIS_TIMER: {
            const { completedAt, duration } = action.payload;
            const updated = {
                ...state,
                analysisCompletedAt: completedAt,
                analysisDuration: duration,
                analysisStatus: 'COMPLETED',
                analysisComplete: true,
            };
            try {
                if (typeof window !== 'undefined' && window.sessionStorage) {
                    window.sessionStorage.setItem(TIMING_STORAGE_KEY, JSON.stringify({
                        analysisStartedAt: state.analysisStartedAt || state.analysisStartTime,
                        analysisCompletedAt: completedAt,
                        analysisDuration: duration,
                        analysisStatus: 'COMPLETED',
                    }));
                }
            } catch (e) {}
            return updated;
        }

        case ActionTypes.FAIL_ANALYSIS_TIMER: {
            const updated = {
                ...state,
                analysisStatus: 'FAILED',
                analysisComplete: false,
                error: action.payload || 'Analysis failed',
            };
            try {
                if (typeof window !== 'undefined' && window.sessionStorage) {
                    window.sessionStorage.setItem(TIMING_STORAGE_KEY, JSON.stringify({
                        analysisStartedAt: state.analysisStartedAt || state.analysisStartTime,
                        analysisCompletedAt: null,
                        analysisDuration: null,
                        analysisStatus: 'FAILED',
                    }));
                }
            } catch (e) {}
            return updated;
        }

        case ActionTypes.RESET_ANALYSIS_TIMER: {
            try {
                if (typeof window !== 'undefined' && window.sessionStorage) {
                    window.sessionStorage.removeItem(TIMING_STORAGE_KEY);
                }
            } catch (e) {}
            return {
                ...state,
                analysisStartedAt: null,
                analysisCompletedAt: null,
                analysisDuration: null,
                analysisStatus: 'IDLE',
                analysisStartTime: null,
            };
        }

        case ActionTypes.SET_ANALYSIS_START_TIME: {
            const time = action.payload;
            return { ...state, analysisStartTime: time, analysisStartedAt: time, analysisStatus: 'RUNNING' };
        }

        case ActionTypes.SET_ANALYSIS_DURATION:
            return { ...state, analysisDuration: action.payload };

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
            const newSelected = new Set(state.selectedObjects);
            action.payload.forEach(obj => newSelected.add(obj.id));
            return { ...state, selectedObjects: newSelected };
        }

        case ActionTypes.DESELECT_ALL_OBJECTS: {
            if (action.payload && action.payload.length > 0) {
                const newSelected = new Set(state.selectedObjects);
                action.payload.forEach(id => newSelected.delete(id));
                return { ...state, selectedObjects: newSelected };
            }
            return { ...state, selectedObjects: new Set() };
        }

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

    // NOTE: every function below is individually memoized with useCallback,
    // but without wrapping the container itself in useMemo, `actions` was a
    // brand-new object literal on every render. Any consumer effect with
    // `actions` (or a callback derived from it) in its dependency array -
    // e.g. Step2Analyze's "fetch versions on mount" effect - saw a "changed"
    // dependency on every single render and re-ran, which called
    // actions.setVersions(), which dispatched a state update, which
    // re-rendered the provider, which created a new `actions` object again -
    // an infinite loop that hammered GET /api/versions (1000+ requests) and
    // starved the browser, which is why the Step 2 wizard page looked stuck.
    const actions = useMemo(() => ({
        setStep: (step) => dispatch({ type: ActionTypes.SET_STEP, payload: step }),
        nextStep: () => dispatch({ type: ActionTypes.NEXT_STEP }),
        prevStep: () => dispatch({ type: ActionTypes.PREV_STEP }),

        setFile: (file) => dispatch({ type: ActionTypes.SET_FILE, payload: file }),
        setFileMetadata: (meta) => dispatch({ type: ActionTypes.SET_FILE_METADATA, payload: meta }),
        clearFile: () => dispatch({ type: ActionTypes.CLEAR_FILE }),
        setSourceMode: (mode) => dispatch({ type: ActionTypes.SET_SOURCE_MODE, payload: mode }),
        setLocalSource: (source) => dispatch({ type: ActionTypes.SET_LOCAL_SOURCE, payload: source }),

        setAnalysisJob: (jobId) => dispatch({ type: ActionTypes.SET_ANALYSIS_JOB, payload: jobId }),
        updateAnalysisProgress: (progress) => dispatch({ type: ActionTypes.UPDATE_ANALYSIS_PROGRESS, payload: progress }),
        setAnalysisComplete: (complete) => dispatch({ type: ActionTypes.SET_ANALYSIS_COMPLETE, payload: complete }),
        setAnalysisResult: (result) => dispatch({ type: ActionTypes.SET_ANALYSIS_RESULT, payload: result }),
        setAnalysisStartTime: (time) => dispatch({ type: ActionTypes.SET_ANALYSIS_START_TIME, payload: time }),
        setAnalysisDuration: (duration) => dispatch({ type: ActionTypes.SET_ANALYSIS_DURATION, payload: duration }),
        startAnalysisTimer: (timestamp) => dispatch({ type: ActionTypes.START_ANALYSIS_TIMER, payload: timestamp }),
        completeAnalysisTimer: (completedAt, duration) => dispatch({ type: ActionTypes.COMPLETE_ANALYSIS_TIMER, payload: { completedAt, duration } }),
        failAnalysisTimer: (error) => dispatch({ type: ActionTypes.FAIL_ANALYSIS_TIMER, payload: error }),
        resetAnalysisTimer: () => dispatch({ type: ActionTypes.RESET_ANALYSIS_TIMER }),
        setDiscoveryTab: (tab) => dispatch({ type: ActionTypes.SET_DISCOVERY_TAB, payload: tab }),

        updateConfig: (config) => dispatch({ type: ActionTypes.UPDATE_CONFIG, payload: config }),
        setVersions: (versions) => dispatch({ type: ActionTypes.SET_VERSIONS, payload: versions }),

        setReviewData: (data) => dispatch({ type: ActionTypes.SET_REVIEW_DATA, payload: data }),
        setReviewTab: (tab) => dispatch({ type: ActionTypes.SET_REVIEW_TAB, payload: tab }),
        toggleObjectSelection: (id) => dispatch({ type: ActionTypes.TOGGLE_OBJECT_SELECTION, payload: id }),
        selectAllObjects: (objects) => dispatch({ type: ActionTypes.SELECT_ALL_OBJECTS, payload: objects }),
        deselectAllObjects: (ids) => dispatch({ type: ActionTypes.DESELECT_ALL_OBJECTS, payload: ids }),
        updateObjectMapping: (tab, objectId, mapping) =>
            dispatch({ type: ActionTypes.UPDATE_OBJECT_MAPPING, payload: { tab, objectId, mapping } }),

        setGenerationJob: (jobId) => dispatch({ type: ActionTypes.SET_GENERATION_JOB, payload: jobId }),
        updateGenerationProgress: (progress) => dispatch({ type: ActionTypes.UPDATE_GENERATION_PROGRESS, payload: progress }),
        addGenerationDetail: (detail) => dispatch({ type: ActionTypes.ADD_GENERATION_DETAIL, payload: detail }),
        setGenerationComplete: (complete) => dispatch({ type: ActionTypes.SET_GENERATION_COMPLETE, payload: complete }),
        setGenerationResult: (result) => dispatch({ type: ActionTypes.SET_GENERATION_RESULT, payload: result }),

        setSummaryData: (data) => dispatch({ type: ActionTypes.SET_SUMMARY_DATA, payload: data }),

        setError: (error) => dispatch({ type: ActionTypes.SET_ERROR, payload: error }),
        clearError: () => dispatch({ type: ActionTypes.CLEAR_ERROR }),

        resetWizard: () => dispatch({ type: ActionTypes.RESET_WIZARD }),
    }), []);

    const contextValue = useMemo(() => ({ state, actions, wsRef }), [state, actions]);

    return (
        <WizardContext.Provider value={contextValue}>
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