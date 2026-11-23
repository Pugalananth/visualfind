import { useCallback, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { fetchBlobUrl } from '../api'

export function BrandMark() {
  return (
    <svg className="brand-mark" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M2 8V3h5M22 8V3h-5M2 16v5h5M22 16v5h-5" stroke="#b98a4e" strokeWidth="2" />
      <circle cx="12" cy="12" r="3.2" fill="#ece3d2" />
    </svg>
  )
}

export const Brand = ({ to = '/' }) => (
  <Link to={to} className="brand"><BrandMark />VisualFind</Link>
)

export function useAsync(fn, deps = []) {
  const [state, setState] = useState({ data: null, error: null, loading: true })
  const seq = useRef(0)
  const run = useCallback(async (silent = false) => {
    const id = ++seq.current
    if (!silent) setState((s) => ({ ...s, loading: true, error: null }))
    try {
      const data = await fn()
      if (id === seq.current) setState({ data, error: null, loading: false })
    } catch (e) {
      if (id === seq.current) setState((s) => ({ data: silent ? s.data : null, error: e.message, loading: false }))
    }
  }, deps) // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { run() }, [run])
  useEffect(() => () => { seq.current++ }, [])
  return { ...state, reload: run }
}

export function usePolling(reload, active, ms = 2000) {
  useEffect(() => {
    if (!active) return undefined
    const t = setInterval(() => reload(true), ms)
    return () => clearInterval(t)
  }, [reload, active, ms])
}

export const Spinner = () => <div className="spinner" role="status" aria-label="Loading" />
export const Loading = () => <div className="empty"><Spinner /></div>

export function ErrorNote({ error, onRetry }) {
  if (!error) return null
  return (
    <div className="note error" role="alert">
      {error} {onRetry && <button className="link-btn" onClick={() => onRetry()}>Retry</button>}
    </div>
  )
}

const STATUS_CLASS = {
  completed: 'ok', ONLINE: 'ok', READY: 'ok', CONNECTED: 'ok', active: 'ok',
  failed: 'bad', OFFLINE: 'bad', NOT_READY: 'bad', CONNECTION_FAILED: 'bad', inactive: 'bad',
  processing: 'bronze', queued: 'warn', LOADING: 'warn', UNSUPPORTED: 'warn', NOT_TESTED: '', NOT_CONFIGURED: '',
}
export const StatusBadge = ({ status }) => (
  <span className={`badge ${STATUS_CLASS[status] ?? ''}`}>{String(status).replace(/_/g, ' ')}</span>
)

export function Pager({ total, skip, limit, onChange }) {
  if (total <= limit) return total ? <div className="pager"><span>{total} total</span></div> : null
  const page = Math.floor(skip / limit) + 1
  const pages = Math.ceil(total / limit)
  return (
    <div className="pager">
      <span>{skip + 1}–{Math.min(skip + limit, total)} of {total}</span>
      <span className="row">
        <button className="btn small" disabled={skip === 0} onClick={() => onChange(Math.max(skip - limit, 0))}>Previous</button>
        <span>Page {page} / {pages}</span>
        <button className="btn small" disabled={skip + limit >= total} onClick={() => onChange(skip + limit)}>Next</button>
      </span>
    </div>
  )
}

/** Image behind an authenticated endpoint: fetched with the bearer token and shown from a blob URL. */
export function useAuthedBlob(path) {
  const [state, setState] = useState({ url: null, error: null })
  useEffect(() => {
    if (!path) { setState({ url: null, error: null }); return undefined }
    let alive = true
    let made = null
    setState({ url: null, error: null })
    fetchBlobUrl(path)
      .then((u) => { made = u; if (alive) setState({ url: u, error: null }); else URL.revokeObjectURL(u) })
      .catch((e) => alive && setState({ url: null, error: e.status === 410 ? 'Removed by retention policy' : e.message }))
    return () => { alive = false; if (made) URL.revokeObjectURL(made) }
  }, [path])
  return state
}

export function AuthImage({ path, alt = '', className = '' }) {
  const { url, error } = useAuthedBlob(path)
  if (error) return <div className={`thumb ${className}`} title={error} />
  if (!url) return <div className={`thumb ${className}`} />
  return <img className={className || 'thumb'} src={url} alt={alt} />
}

/** Frame image with the REAL bounding box drawn from backend pixel coordinates. */
export function FrameView({ path, bbox, width, height, label }) {
  const { url, error } = useAuthedBlob(path)
  const box = bbox && width && height ? bbox : null
  return (
    <div className="frameview">
      {url ? <img src={url} alt={label || 'Matched frame'} /> : (
        <div className="ph">{error ? error : <Spinner />}</div>
      )}
      {url && box && (
        <svg viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" aria-hidden="true">
          <rect x={box[0]} y={box[1]} width={box[2] - box[0]} height={box[3] - box[1]} fill="rgba(185,138,78,.10)"
            stroke="#d6a96a" strokeWidth={Math.max(width, height) / 300} vectorEffect="non-scaling-stroke" style={{ strokeWidth: 2 }} />
        </svg>
      )}
    </div>
  )
}

export function Confirm({ text, onConfirm, children, className = 'btn small danger' }) {
  const [arm, setArm] = useState(false)
  if (!arm) return <button className={className} onClick={() => setArm(true)}>{children}</button>
  return (
    <span className="row" style={{ gap: 6 }}>
      <span className="muted" style={{ fontSize: '.8rem' }}>{text}</span>
      <button className="btn small danger" onClick={() => { setArm(false); onConfirm() }}>Confirm</button>
      <button className="btn small" onClick={() => setArm(false)}>Cancel</button>
    </span>
  )
}
