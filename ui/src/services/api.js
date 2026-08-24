/**
 * API service layer for the MS Access Converter Wizard.
 * Communicates with the FastAPI backend defined in converter/app/api/main.py.
 */

const API_BASE = '/api';

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
 * Get job details by ID.
 * Corresponds to GET /api/jobs/{job_id}
 */
export async function getJob(jobId) {
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
 * Connect to WebSocket for real-time job progress.
 * Corresponds to WS /ws/jobs/{job_id}
 *
 * @param {string} jobId
 * @param {function} onMessage - Callback for incoming messages
 * @returns {WebSocket}
 */
export function connectProgressWebSocket(jobId, onMessage) {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const ws = new WebSocket(`${protocol}//${window.location.host}/ws/jobs/${jobId}`);

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