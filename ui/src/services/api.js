/**
 * API service layer for the MS Access Converter Wizard.
 * Communicates with the FastAPI backend.
 */

const API_BASE = import.meta.env.VITE_API_URL
    ? `${import.meta.env.VITE_API_URL}/api`
    : '/api';

/**
 * Helper to get the current token from localStorage.
 */
function getToken() {
    return localStorage.getItem('token');
}

/**
 * Enhanced fetch with authentication headers and error handling.
 */
async function authFetch(endpoint, options = {}) {
    console.log(`Calling API: ${API_BASE}${endpoint}`);
    const token = getToken();
    const headers = {
        ...options.headers,
    };

    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }

    const response = await fetch(`${API_BASE}${endpoint}`, {
        ...options,
        headers,
    });

    if (response.status === 401) {
        // Handle unauthorized (e.g., token expired)
        localStorage.removeItem('token');
        if (!window.location.pathname.includes('/login')) {
            window.location.href = '/login';
        }
    }

    if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }));
        throw new Error(errorData.detail || 'API request failed');
    }

    return response;
}

// --- Auth Endpoints ---

export async function login(email, password) {
    const formData = new FormData();
    formData.append('username', email);
    formData.append('password', password);

    const response = await fetch(`${API_BASE}/auth/login`, {
        method: 'POST',
        body: formData,
    });

    if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Login failed' }));
        throw new Error(errorData.detail || 'Login failed');
    }

    return response.json();
}

export async function signup(email, password, name) {
    const response = await fetch(`${API_BASE}/auth/signup`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password, name }),
    });

    if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Signup failed' }));
        throw new Error(errorData.detail || 'Signup failed');
    }

    return response.json();
}

export async function getMe() {
    const response = await authFetch('/auth/me');
    return response.json();
}

export async function socialCallback(provider, code) {
    const redirectUri = `${window.location.origin}/auth/callback`;
    const response = await fetch(`${API_BASE}/auth/${provider}/callback?code=${code}&redirect_uri=${encodeURIComponent(redirectUri)}`);
    if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: `Failed to complete ${provider} authentication` }));
        throw new Error(errorData.detail || `Failed to complete ${provider} authentication`);
    }
    return response.json();
}

export async function forgotPassword(email) {
    const response = await fetch(`${API_BASE}/auth/forgot-password`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email }),
    });
    return response.json();
}

export async function resetPassword(token, new_password) {
    const response = await fetch(`${API_BASE}/auth/reset-password`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token, new_password }),
    });
    if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Reset failed' }));
        throw new Error(errorData.detail || 'Reset failed');
    }
    return response.json();
}

// --- Job Endpoints ---

export async function getVersions() {
    const response = await authFetch('/versions');
    return response.json();
}

export async function createJob(file, config) {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('project_name', config.project_name || 'ConvertedApplication');
    formData.append('base_package', config.base_package || 'com.generated.app');

    const response = await authFetch(`/jobs?project_name=${encodeURIComponent(config.project_name)}&base_package=${encodeURIComponent(config.base_package)}`, {
        method: 'POST',
        body: formData,
    });

    return response.json();
}

export async function getLocalAccessCapability() {
    const response = await authFetch('/local-access/capability');
    return response.json();
}

export async function listLocalAccessSources() {
    const response = await authFetch('/local-access/sources');
    return response.json();
}

export async function validateLocalPath(path) {
    const response = await authFetch('/local-access/validate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path }),
    });
    return response.json();
}

export async function createLocalJob(path, config) {
    const response = await authFetch('/jobs/local', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            path,
            project_name: config.project_name || 'ConvertedApplication',
            base_package: config.base_package || 'com.generated.app',
        }),
    });
    return response.json();
}

export async function getJob(jobId) {
    const response = await authFetch(`/jobs/${jobId}`);
    return response.json();
}

export async function listJobs(limit = 50) {
    const response = await authFetch(`/jobs?limit=${limit}`);
    return response.json();
}

export async function getReport(jobId) {
    const response = await authFetch(`/jobs/${jobId}/report`);
    return response.json();
}

export function downloadResult(jobId, projectName = 'ConvertedApplication') {
    const token = getToken();
    const url = `${API_BASE}/jobs/${jobId}/download${token ? `?token=${token}` : ''}`;
    window.open(url, '_blank');
}

export function connectProgressWebSocket(jobId, onMessage) {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const backendHost = import.meta.env.VITE_API_URL
        ? import.meta.env.VITE_API_URL.replace(/^https?:\/\//, '')
        : window.location.host;

    const token = getToken();
    const wsUrl = `${protocol}//${backendHost}/ws/jobs/${jobId}${token ? `?token=${token}` : ''}`;
    const ws = new WebSocket(wsUrl);

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
