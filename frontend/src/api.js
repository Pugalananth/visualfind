const BASE = import.meta.env.VITE_API_URL || ''
const TOKEN_KEY = 'vf_token'

let token = null
try { token = localStorage.getItem(TOKEN_KEY) } catch { /* storage unavailable */ }
let onUnauthorized = () => {}

export const getToken = () => token
export function setToken(t) {
  token = t
  try { t ? localStorage.setItem(TOKEN_KEY, t) : localStorage.removeItem(TOKEN_KEY) } catch { /* ignore */ }
}
export const setUnauthorizedHandler = (fn) => { onUnauthorized = fn }

export class ApiError extends Error {
  constructor(message, status, kind) {
    super(message)
    this.status = status
    this.kind = kind
  }
}

export const MSG = {
  offline: 'VisualFind API is unavailable. Check that the backend is running.',
  timeout: 'The request timed out. Please try again.',
  403: 'You do not have permission to access this resource.',
  422: 'Please check the search inputs.',
  500: 'VisualFind encountered an internal processing error.',
}

function detailText(body) {
  const d = body && body.detail
  if (typeof d === 'string') return d
  if (Array.isArray(d)) return d.map((e) => e.msg).join('; ')
  return null
}

function toError(status, body) {
  const d = detailText(body)
  if (status === 401) return new ApiError(d || 'Please sign in again.', 401, 'auth')
  if (status === 403) return new ApiError(d && d !== 'Not authenticated' && !d.startsWith('You do not have') ? d : MSG[403], 403, 'forbidden')
  if (status === 404) return new ApiError(d || 'The requested item was not found.', 404, 'notfound')
  if (status === 422) return new ApiError(d || MSG[422], 422, 'validation')
  if (status >= 500) return new ApiError(MSG[500], status, 'server')
  return new ApiError(d || `Request failed (HTTP ${status}).`, status, 'other')
}

export async function request(path, { method = 'GET', json, form, timeout = 30000, raw = false, auth = true } = {}) {
  const headers = {}
  if (auth && token) headers.Authorization = `Bearer ${token}`
  let body
  if (json !== undefined) { headers['Content-Type'] = 'application/json'; body = JSON.stringify(json) }
  if (form) body = form
  const ctl = new AbortController()
  const timer = setTimeout(() => ctl.abort(), timeout)
  let res
  try {
    res = await fetch(BASE + path, { method, headers, body, signal: ctl.signal })
  } catch (e) {
    throw new ApiError(e.name === 'AbortError' ? MSG.timeout : MSG.offline, 0, e.name === 'AbortError' ? 'timeout' : 'offline')
  } finally {
    clearTimeout(timer)
  }
  if (!res.ok) {
    let data = null
    try { data = await res.json() } catch { /* not json */ }
    const err = toError(res.status, data)
    if (res.status === 401 && auth && token) onUnauthorized()
    throw err
  }
  if (raw) return res
  if (res.status === 204) return null
  return res.json()
}

export const get = (p, o) => request(p, o)
export const post = (p, json, o) => request(p, { method: 'POST', json, ...o })
export const put = (p, json, o) => request(p, { method: 'PUT', json, ...o })
export const patch = (p, json, o) => request(p, { method: 'PATCH', json, ...o })
export const del = (p, o) => request(p, { method: 'DELETE', ...o })

export async function fetchBlobUrl(path) {
  const res = await request(path, { raw: true, timeout: 60000 })
  return URL.createObjectURL(await res.blob())
}

/** Multipart upload with real upload-progress events. */
export function uploadSearch(form, onProgress) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open('POST', BASE + '/api/search')
    if (token) xhr.setRequestHeader('Authorization', `Bearer ${token}`)
    xhr.upload.onprogress = (e) => { if (e.lengthComputable && onProgress) onProgress(e.loaded / e.total) }
    xhr.onerror = () => reject(new ApiError(MSG.offline, 0, 'offline'))
    xhr.ontimeout = () => reject(new ApiError(MSG.timeout, 0, 'timeout'))
    xhr.timeout = 15 * 60 * 1000
    xhr.onload = () => {
      let data = null
      try { data = JSON.parse(xhr.responseText) } catch { /* ignore */ }
      if (xhr.status >= 200 && xhr.status < 300) return resolve(data)
      if (xhr.status === 401) onUnauthorized()
      reject(toError(xhr.status, data))
    }
    xhr.send(form)
  })
}

export const fmtTime = (s) => {
  if (s == null) return '—'
  const m = Math.floor(s / 60)
  const rest = s - m * 60
  return `${String(m).padStart(2, '0')}:${rest.toFixed(2).padStart(5, '0')}`
}
export const pct = (v) => (v == null ? '—' : `${(v * 100).toFixed(1)}%`)
export const fmtDate = (iso) => (iso ? new Date(iso).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' }) : '—')
export const fmtDay = (iso) => (iso ? new Date(iso).toLocaleDateString(undefined, { dateStyle: 'medium' }) : '—')
