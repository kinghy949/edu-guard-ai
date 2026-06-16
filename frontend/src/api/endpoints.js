import { http } from './index';
export const authApi = {
    async login(username, password) {
        const form = new URLSearchParams();
        form.append('username', username);
        form.append('password', password);
        const r = await http.post('/auth/login', form, { headers: { 'Content-Type': 'application/x-www-form-urlencoded' } });
        return {
            token: r.data.access_token,
            mustChangePassword: !!r.data.must_change_password,
        };
    },
    me: () => http.get('/auth/me').then((r) => r.data),
    changePassword: (oldPassword, newPassword) => http
        .post('/auth/change-password', {
        old_password: oldPassword,
        new_password: newPassword,
    })
        .then((r) => r.data),
};
export const progressApi = {
    me: () => http.get('/progress/me').then((r) => r.data),
    student: (id) => http.get(`/progress/${id}`).then((r) => r.data),
};
export const warningsApi = {
    list: (params) => http.get('/warnings', { params }).then((r) => r.data),
    get: (id) => http.get(`/warnings/${id}`).then((r) => r.data),
    generate: (payload) => http.post('/warnings/generate', payload).then((r) => r.data),
    resolve: (id, note) => http.post(`/warnings/${id}/resolve`, { note }).then((r) => r.data),
};
export const chatApi = {
    sessions: () => http.get('/chat/sessions').then((r) => r.data),
    createSession: (title) => http.post('/chat/sessions', { title }).then((r) => r.data),
    messages: (sessionId) => http
        .get(`/chat/sessions/${sessionId}/messages`)
        .then((r) => r.data),
    send: (sessionId, content) => http
        .post(`/chat/sessions/${sessionId}/messages`, { content })
        .then((r) => r.data),
    deleteSession: (id) => http.delete(`/chat/sessions/${id}`),
};
export const importsApi = {
    templates: () => http.get('/imports/templates').then((r) => r.data),
    upload: (kind, file) => {
        const fd = new FormData();
        fd.append('file', file);
        return http
            .post(`/imports/${kind}`, fd, {
            headers: { 'Content-Type': 'multipart/form-data' },
        })
            .then((r) => r.data);
    },
};
export const llmConfigApi = {
    get: () => http.get('/admin/llm-config').then((r) => r.data),
    update: (payload) => http.put('/admin/llm-config', payload).then((r) => r.data),
    test: (prompt = '你好，请用一句话介绍你自己。') => http.post('/admin/llm-config/test', { prompt }).then((r) => r.data),
};
export const auditApi = {
    list: (params) => http.get('/admin/audit-logs', { params }).then((r) => r.data),
};
export const notificationsApi = {
    listConfigs: () => http.get('/notifications/configs/all').then((r) => r.data),
    upsertConfig: (channel, payload) => http
        .put(`/notifications/configs/${channel}`, payload)
        .then((r) => r.data),
    test: (payload) => http.post('/notifications/test', payload).then((r) => r.data),
};
