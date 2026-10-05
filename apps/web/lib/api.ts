import axios from 'axios';

const api = axios.create({
    baseURL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
});

api.interceptors.request.use((config) => {
    const token = typeof window !== 'undefined' ? localStorage.getItem('token') : null;
    if (token) {
        config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
});

export default api;

// ─── Recommendation API helpers ──────────────────────────────────────────────

export async function fetchRecommendations(projectId: number) {
    const res = await api.get(`/projects/${projectId}/recommendations`);
    return res.data;
}

export async function applyRecommendation(projectId: number, recId: string) {
    const res = await api.post(`/projects/${projectId}/recommendations/${recId}/apply`);
    return res.data;
}

export async function dismissRecommendation(projectId: number, recId: string) {
    const res = await api.post(`/projects/${projectId}/recommendations/${recId}/dismiss`);
    return res.data;
}

export async function fetchFieldHints(tableName: string) {
    const res = await api.get(`/recommendations/field-hints?table_name=${encodeURIComponent(tableName)}`);
    return res.data;
}
