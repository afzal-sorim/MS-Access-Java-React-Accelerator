export function getGeneratedCounts(progress = {}) {
    const count = (key) => {
        const value = progress?.[key]?.count;
        return Number.isFinite(value) ? value : progress?.[key]?.items?.length || 0;
    };

    const tables = count('tables');
    const queries = count('queries');
    const forms = count('forms');
    const reports = count('reports');
    const vba = count('vba');

    const frontend = forms + (reports > 0 ? 1 : 0) + 1 + 6;
    const backend = tables + (tables + vba + (queries > 0 ? 1 : 0)) + tables + tables + tables + 6;

    return { backend, frontend, database: 1, total: backend + frontend + 1 };
}
