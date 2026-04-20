/**
 * Django REST API client — thin wrapper around fetch.
 *
 * Auth: Django session cookies. Because the SPA and the API are served
 * from the same origin (topquaranta.cat), we just need
 * `credentials: 'include'` and the CSRF token on mutating requests.
 *
 * CSRF: Django sets a `csrftoken` cookie on first GET; we forward it
 * as the `X-CSRFToken` header on POST/PUT/PATCH/DELETE.
 */

const API_BASE = '/api/v1'

function readCookie(name) {
  const m = document.cookie.match(new RegExp('(?:^|; )' + name + '=([^;]*)'))
  return m ? decodeURIComponent(m[1]) : null
}

async function request(path, { method = 'GET', body, headers = {} } = {}) {
  const isWrite = method !== 'GET' && method !== 'HEAD' && method !== 'OPTIONS'
  const csrf = isWrite ? readCookie('csrftoken') : null

  const res = await fetch(`${API_BASE}${path}`, {
    method,
    credentials: 'include',
    headers: {
      Accept: 'application/json',
      ...(body ? { 'Content-Type': 'application/json' } : {}),
      ...(csrf ? { 'X-CSRFToken': csrf } : {}),
      ...headers,
    },
    body: body ? JSON.stringify(body) : undefined,
  })

  if (!res.ok) {
    const payload = await res.json().catch(() => ({}))
    const err = new Error(payload.detail || payload.error || `HTTP ${res.status}`)
    err.status = res.status
    err.payload = payload
    throw err
  }

  // 204 No Content
  if (res.status === 204) return null
  return res.json()
}

export const api = {
  get:    (path, opts)       => request(path, { ...opts, method: 'GET' }),
  post:   (path, body, opts) => request(path, { ...opts, method: 'POST',   body }),
  put:    (path, body, opts) => request(path, { ...opts, method: 'PUT',    body }),
  patch:  (path, body, opts) => request(path, { ...opts, method: 'PATCH',  body }),
  delete: (path, opts)       => request(path, { ...opts, method: 'DELETE' }),
}

/* ── Endpoints used across the app ── */

export const auth = {
  /** GET /api/v1/auth/me/ → `{ id, email, is_staff, is_authenticated }` */
  me:     () => api.get('/auth/me/'),
  login:  (email, password) => api.post('/auth/login/', { email, password }),
  logout: () => api.post('/auth/logout/', {}),
}
