const WorkspaceAPI = (() => {
  const BASE = '/api/oworkspace/files';

  async function request(url, opts = {}) {
    const defaults = {
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' }
    };
    if (opts.method && opts.method !== 'GET') {
      defaults.headers['X-CSRF-Token'] = getCsrfToken();
    }
    const res = await fetch(url, { ...defaults, ...opts, headers: { ...defaults.headers, ...opts.headers } });
    if (!res.ok) {
      if (res.status === 401 && typeof window !== 'undefined') {
        window.location.href = '/login.html';
        return null;
      }
      let detail = `HTTP ${res.status}`;
      try { const j = await res.json(); detail = j.detail || j.error || detail; } catch {}
      if (typeof showToast === 'function') showToast(detail, 'error');
      return null;
    }
    return res.json();
  }

  return {
    async listFiles(kind = '') {
      const q = kind ? `?kind=${encodeURIComponent(kind)}` : '';
      return request(BASE + q);
    },
    async createFile(name, kind) {
      return request(BASE, { method: 'POST', body: JSON.stringify({ name, kind }) });
    },
    async readFile(filename) {
      return request(`${BASE}/${encodeURIComponent(filename)}`);
    },
    async saveFile(filename, data) {
      return request(`${BASE}/${encodeURIComponent(filename)}`, { method: 'PUT', body: JSON.stringify({ data }) });
    },
    async deleteFile(filename) {
      return request(`${BASE}/${encodeURIComponent(filename)}`, { method: 'DELETE' });
    },
    async renameFile(filename, newName) {
      return request(`${BASE}/${encodeURIComponent(filename)}/rename`, { method: 'POST', body: JSON.stringify({ name: newName }) });
    }
  };
})();
