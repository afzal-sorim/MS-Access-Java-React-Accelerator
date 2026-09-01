/**
 * Utility functions for the wizard UI.
 */

/**
 * Format file size in human-readable format.
 */
export function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

/**
 * Format a number with commas.
 */
export function formatNumber(num) {
    return new Intl.NumberFormat().format(num);
}

/**
 * Format percentage with one decimal place.
 */
export function formatPercentage(value) {
    return typeof value === 'number' ? value.toFixed(1) + '%' : 'N/A';
}

/**
 * Truncate text with ellipsis.
 */
export function truncate(text, maxLength = 50) {
    if (!text || text.length <= maxLength) return text;
    return text.substring(0, maxLength - 3) + '...';
}

/**
 * Convert PascalCase to space-separated words.
 */
export function pascalToWords(str) {
    return str.replace(/([A-Z])/g, ' $1').trim();
}

/**
 * Get status badge color.
 */
export function getStatusColor(status) {
    const colors = {
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
        DISCOVERED: '#6b7280',
        ANALYZING: '#3b82f6',
    };
    return colors[status] || '#6b7280';
}

/**
 * Get risk level color.
 */
export function getRiskColor(risk) {
    const colors = {
        LOW: '#10b981',
        MEDIUM: '#f59e0b',
        HIGH: '#ef4444',
        CRITICAL: '#dc2626',
    };
    return colors[risk] || '#6b7280';
}

/**
 * Debounce function.
 */
export function debounce(fn, delay) {
    let timeoutId;
    return (...args) => {
        clearTimeout(timeoutId);
        timeoutId = setTimeout(() => fn(...args), delay);
    };
}

/**
 * Deep clone an object.
 */
export function deepClone(obj) {
    return JSON.parse(JSON.stringify(obj));
}

/**
 * Generate a unique ID.
 */
export function generateId() {
    return Math.random().toString(36).substring(2, 11);
}

/**
 * Get initials from a name.
 */
export function getInitials(name) {
    if (!name) return '?';
    return name
        .split(' ')
        .map((part) => part[0])
        .join('')
        .toUpperCase()
        .substring(0, 2);
}