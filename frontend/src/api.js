/**
 * API utility functions with authentication
 */

const API_TIMEOUT_MS = 20000;

/**
 * Get authorization header with JWT token
 */
function getAuthHeaders() {
  const token = localStorage.getItem('token')
  const headers = {
    'Content-Type': 'application/json',
  }
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }
  return headers
}

function apiErrorMessage(err, url) {
  if (err?.name === 'AbortError') {
    return `请求超时（${API_TIMEOUT_MS / 1000}s）：无法连接后端。请确认 uvicorn 已启动，且端口与 frontend/.env.development 中 VITE_DEV_BACKEND 一致（当前代理见 vite.config.js）。`
  }
  if (err?.message?.includes('Failed to fetch') || err?.message?.includes('NetworkError')) {
    return `网络错误：无法访问 ${url}。请确认后端已启动（默认 http://127.0.0.1:8001）。`
  }
  return err?.message || String(err);
}

/**
 * Fetch with authentication
 */
export async function authFetch(url, options = {}) {
  const headers = {
    ...getAuthHeaders(),
    ...(options.headers || {}),
  }

  const timeoutMs = options.timeout ?? API_TIMEOUT_MS;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  let response;
  try {
    response = await fetch(url, {
      ...options,
      headers,
      signal: controller.signal,
    });
  } catch (err) {
    const msg = apiErrorMessage(err, url);
    console.error('[api] ✗', url, msg);
    throw new Error(msg);
  } finally {
    clearTimeout(timer);
  }

  // Handle 401 Unauthorized — 勿 reload 死循环，交给页面展示错误/回登录
  if (response.status === 401) {
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    let detail = '认证已过期，请重新登录'
    try {
      const data = await response.json()
      if (data.detail) detail = typeof data.detail === 'string' ? data.detail : detail
    } catch {
      /* ignore */
    }
    throw new Error(detail)
  }

  return response
}

/**
 * Download file with authentication (for export endpoints)
 */
export async function authDownload(url, filename, options = {}) {
  const response = await authFetch(url, {
    method: options.method || 'GET',
    body: options.body,
    headers: options.body ? { 'Content-Type': 'application/json', ...(options.headers || {}) } : options.headers,
    timeout: options.timeout ?? 120000,
  });

  if (!response.ok) {
    let detail = '下载失败';
    try {
      const data = await response.json();
      if (data.detail) {
        detail = typeof data.detail === 'string' ? data.detail : detail;
      }
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }

  const blob = await response.blob();
  let name = filename;
  if (!name) {
    const disposition = response.headers.get('Content-Disposition') || '';
    const match = disposition.match(/filename\*?=(?:UTF-8''|"?)([^";]+)/i);
    name = match ? decodeURIComponent(match[1].replace(/"/g, '')) : 'download.xlsx';
  }

  const link = document.createElement('a');
  link.href = URL.createObjectURL(blob);
  link.download = name;
  link.click();
  URL.revokeObjectURL(link.href);
}

/**
 * Upload file with authentication
 */
export async function uploadFile(url, file) {
  const token = localStorage.getItem('token')
  const formData = new FormData()
  formData.append('file', file)

  const headers = {}
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 120000);

  try {
    const response = await fetch(url, {
      method: 'POST',
      headers,
      body: formData,
      signal: controller.signal,
    });

    if (response.status === 401) {
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      throw new Error('认证已过期，请重新登录')
    }

    return response
  } catch (err) {
    throw new Error(apiErrorMessage(err, url));
  } finally {
    clearTimeout(timer);
  }
}

/**
 * Get current user info from localStorage
 */
export function getCurrentUser() {
  const userStr = localStorage.getItem('user')
  if (!userStr) return null
  try {
    return JSON.parse(userStr)
  } catch {
    return null
  }
}

/**
 * Persist current user snapshot (login / profile refresh).
 */
export function saveCurrentUser(user) {
  if (!user) {
    localStorage.removeItem('user')
    return null
  }
  localStorage.setItem('user', JSON.stringify(user))
  return user
}

/**
 * Refresh current user from server (admin may have changed username/profile).
 */
export async function refreshCurrentUser() {
  const response = await authFetch('/api/auth/me')
  const data = await response.json()
  if (!response.ok) {
    throw new Error(typeof data.detail === 'string' ? data.detail : '获取用户信息失败')
  }
  return saveCurrentUser(data)
}

/**
 * Check if user is authenticated
 */
export function isAuthenticated() {
  return !!localStorage.getItem('token')
}

/**
 * Logout user
 */
export function logout() {
  localStorage.removeItem('token')
  localStorage.removeItem('user')
  window.location.reload()
}
