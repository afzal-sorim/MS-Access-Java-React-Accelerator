/**
 * API service layer for the MS Access Converter Wizard.
 * Communicates with the FastAPI backend defined in converter/app/api/main.py.
 */

const API_BASE = import.meta.env.VITE_API_URL
    ? `${import.meta.env.VITE_API_URL}/api`
    : '/api';

/**
 * Get supported technology versions from the backend.
 * Corresponds to GET /api/versions
 */
export async function getVersions() {
    const response = await fetch(`${API_BASE}/versions`);
    if (!response.ok) {
        throw new Error('Failed to fetch supported versions');
    }
    return response.json();
}

/**
 * Create a new conversion job by uploading an Access file.
 * Corresponds to POST /api/jobs
 *
 * @param {File} file - The .accdb or .mdb file
 * @param {object} config - ConversionConfig { project_name, base_package, ... }
 * @returns {Promise<object>} JobResponse
 */
export async function createJob(file, config) {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('project_name', config.project_name || 'ConvertedApplication');
    formData.append('base_package', config.base_package || 'com.generated.app');

    const response = await fetch(`${API_BASE}/jobs`, {
        method: 'POST',
        body: formData,
    });

    if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
        throw new Error(error.detail || 'Failed to create conversion job');
    }

    return response.json();
}

/**
 * Read a JSON error body and throw it as an Error.
 * The backend reports failures as { detail: "..." } (FastAPI HTTPException).
 */
async function throwApiError(response, fallback) {
    const error = await response.json().catch(() => ({ detail: fallback }));
    throw new Error(error.detail || fallback);
}

/**
 * Check whether the backend can extract directly from local MS Access.
 * Corresponds to GET /api/local-access/capability
 *
 * Returns { available, access_version, access_running, reason, ... }.
 * `available: false` is a normal answer (no Access installed / not Windows),
 * not an error - the reason explains why the direct mode is unavailable.
 */
export async function getLocalAccessCapability() {
    const response = await fetch(`${API_BASE}/local-access/capability`);
    if (!response.ok) {
        await throwApiError(response, 'Failed to check local MS Access availability');
    }
    return response.json();
}

/**
 * List Access databases discoverable on the backend machine.
 * Corresponds to GET /api/local-access/sources
 *
 * Returns { open: [...], recent: [...], errors: [...] }.
 */
export async function listLocalAccessSources() {
    const response = await fetch(`${API_BASE}/local-access/sources`);
    if (!response.ok) {
        await throwApiError(response, 'Failed to discover local Access databases');
    }
    return response.json();
}

/**
 * Validate a local path and get its database metadata.
 * Corresponds to POST /api/local-access/validate
 *
 * @param {string} path - Absolute path on the backend machine
 */
export async function validateLocalPath(path) {
    const response = await fetch(`${API_BASE}/local-access/validate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path }),
    });
    if (!response.ok) {
        await throwApiError(response, 'That path is not a usable Access database');
    }
    return response.json();
}

/**
 * Create a conversion job from a database already on the backend machine.
 * Corresponds to POST /api/jobs/local
 *
 * The backend copies the file before extraction, so the user's original
 * database is never opened by the extractor.
 *
 * @param {string} path - Absolute path on the backend machine
 * @param {object} config - ConversionConfig { project_name, base_package, ... }
 * @returns {Promise<object>} JobResponse - same shape as createJob()
 */
export async function createLocalJob(path, config) {
    const response = await fetch(`${API_BASE}/jobs/local`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            path,
            project_name: config.project_name || 'ConvertedApplication',
            base_package: config.base_package || 'com.generated.app',
        }),
    });
    if (!response.ok) {
        await throwApiError(response, 'Failed to create conversion job');
    }
    return response.json();
}

/**
 * Get job details by ID.
 * Corresponds to GET /api/jobs/{job_id}
 */export async function getJob(jobId) {
    const response = await fetch(`${API_BASE}/jobs/${jobId}`);
    if (!response.ok) {
        throw new Error('Failed to fetch job');
    }
    return response.json();
}

/**
 * List all jobs.
 * Corresponds to GET /api/jobs
 */
export async function listJobs(limit = 50) {
    const response = await fetch(`${API_BASE}/jobs?limit=${limit}`);
    if (!response.ok) {
        throw new Error('Failed to fetch jobs');
    }
    return response.json();
}

/**
 * Get the migration report for a completed job.
 * Corresponds to GET /api/jobs/{job_id}/report
 */
export async function getReport(jobId) {
    const response = await fetch(`${API_BASE}/jobs/${jobId}/report`);
    if (!response.ok) {
        throw new Error('Failed to fetch report');
    }
    return response.json();
}

/**
 * Download the generated project as a ZIP file.
 * Corresponds to GET /api/jobs/{job_id}/download
 */
export function downloadResult(jobId, projectName = 'ConvertedApplication') {
    window.open(`${API_BASE}/jobs/${jobId}/download`, '_blank');
}

/**
 * List all generated files for a job.
 */
export async function listJobFiles(jobId) {
    const response = await fetch(`${API_BASE}/jobs/${jobId}/files`);
    if (!response.ok) {
        throw new Error('Failed to fetch job files');
    }
    return response.json();
}

/**
 * Get content of a specific generated file.
 */
export async function getFileContent(jobId, path) {
    const response = await fetch(`${API_BASE}/jobs/${jobId}/file-content?path=${encodeURIComponent(path)}`);
    if (!response.ok) {
        throw new Error('Failed to fetch file content');
    }
    return response.json();
}

/**
 * Get database schema for ER diagram.
 */
export async function getJobDbSchema(jobId) {
    const response = await fetch(`${API_BASE}/jobs/${jobId}/db-schema`);
    if (!response.ok) {
        throw new Error('Failed to fetch DB schema');
    }
    return response.json();
}

/**
 * Connect to WebSocket for real-time job progress.
 * Corresponds to WS /ws/jobs/{job_id}
 *
 * @param {string} jobId
 * @param {function} onMessage - Callback for incoming messages
 * @returns {WebSocket}
 */
export function connectProgressWebSocket(jobId, onMessage) {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const backendHost = import.meta.env.VITE_API_URL
        ? import.meta.env.VITE_API_URL.replace(/^https?:\/\//, '')
        : window.location.host;
    const ws = new WebSocket(`${protocol}//${backendHost}/ws/jobs/${jobId}`);

    ws.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            onMessage(data);
        } catch (err) {
            console.error('Failed to parse WebSocket message:', err);
        }
    };

    return ws;
}