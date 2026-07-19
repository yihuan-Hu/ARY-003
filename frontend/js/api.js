(function () {
  const API_BASE = window.ARY_API_BASE || '';
  let csrfToken = null;

  function api(path, options = {}) {
    const token = localStorage.getItem('ary_token');
    const headers = { 'Content-Type': 'application/json', ...options.headers };
    if (token) headers.Authorization = `Bearer ${token}`;

    const method = (options.method || 'GET').toUpperCase();
    if (method !== 'GET' && csrfToken) {
      headers['X-CSRF-Token'] = csrfToken;
    }

    return fetch(`${API_BASE}${path}`, { ...options, headers, credentials: 'include' })
      .then(async (r) => {
        if (method === 'GET') {
          const csrfFromHeader = r.headers.get('X-CSRF-Token');
          if (csrfFromHeader) csrfToken = csrfFromHeader;
        }

        const ct = r.headers.get('content-type') || '';
        const isJson = ct.includes('application/json');
        const data = isJson ? await r.json().catch(() => null) : null;
        if (!r.ok || !isJson) {
          const msg =
            data?.error?.message ||
            data?.message ||
            data?.error ||
            (!isJson ? `Unexpected response (status ${r.status})` : `HTTP ${r.status}`);
          const err = new Error(msg);
          err.status = r.status;
          err.data = data;
          throw err;
        }
        return data;
      });
  }

  window.ARYApi = { API_BASE, api };
})();
