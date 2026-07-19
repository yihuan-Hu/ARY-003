(function () {
  function responseData(res) {
    return res?.data !== undefined ? res.data : res;
  }

  function responseItems(res) {
    const data = responseData(res);
    if (Array.isArray(res?.items)) return res.items;
    if (Array.isArray(data?.items)) return data.items;
    if (Array.isArray(data)) return data;
    return [];
  }

  function escapeHtml(str) {
    if (!str) return '';
    if (typeof str !== 'string') str = String(str);
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  function safeUrl(url) {
    if (!url) return '#';
    const trimmed = String(url).trim();
    const lower = trimmed.toLowerCase();
    if (lower.startsWith('javascript:') || lower.startsWith('data:') || lower.startsWith('vbscript:')) {
      return '#';
    }
    if (lower.startsWith('http://') || lower.startsWith('https://') || lower.startsWith('/') || lower.startsWith('#')) {
      return trimmed;
    }
    return '#';
  }

  function sanitizeInput(str, maxLen = 5000) {
    if (!str) return '';
    if (typeof str !== 'string') str = String(str);
    let cleaned = str.replace(/[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]/g, '');
    if (cleaned.length > maxLen) cleaned = cleaned.substring(0, maxLen);
    return cleaned.trim();
  }

  window.ARYUx = { responseData, responseItems, escapeHtml, safeUrl, sanitizeInput };
})();
