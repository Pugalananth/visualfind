import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import * as api from '../api'
import { useAuth } from '../auth'
import { AuthImage, ErrorNote, FrameView, Loading, StatusBadge, useAsync, usePolling } from '../components/ui'

const STAGES = [
  ['preparing_reference', 'Preparing reference'], ['preparing_video', 'Preparing video'], ['detect', 'Detecting candidates'],
  ['track', 'Tracking subjects'], ['compare', 'Comparing embeddings'], ['ranking', 'Ranking matches'], ['complete', 'Complete'],
]
// The backend runs detection, tracking and embedding comparison in one pass over the video, so those three steps share one real stage.
const ACTIVE_INDEX = { queued: -1, preparing_reference: 0, preparing_video: 1, analysing: 2, ranking: 5, complete: 6 }

function useElapsed(s) {
  const [now, setNow] = useState(Date.now())
  useEffect(() => { const t = setInterval(() => setNow(Date.now()), 1000); return () => clearInterval(t) }, [])
  const start = s.started_at || s.created_at
  return Math.max(0, Math.round((now - new Date(start).getTime()) / 1000))
}

function Processing({ s }) {
  const idx = ACTIVE_INDEX[s.stage] ?? -1
  const elapsed = useElapsed(s)
  const p = s.progress
  const analysing = s.stage === 'analysing'
  return (
    <section className="card stack" style={{ maxWidth: 640 }} aria-live="polite">
      <div className="row between"><h3>{s.stage === 'queued' ? 'Waiting for a free worker' : 'Searching your video'}</h3><span className="mono dim">{elapsed}s</span></div>
      <div className="stages">
        {STAGES.map(([key, label], i) => {
          const analysingStep = i >= 2 && i <= 4
          const active = analysingStep ? analysing : i === idx
          const done = analysingStep ? idx > 2 : i < idx
          return (
            <div key={key} className={`stage ${done ? 'done' : active ? 'active' : ''}`}>
              <span className="pip" /><span>{label}</span>
              <span className="mono dim">{analysingStep && analysing && p?.total ? `${p.processed}/${p.total} frames` : ''}</span>
            </div>
          )
        })}
      </div>
      {analysing && p?.total ? <div className="bar"><i style={{ width: `${Math.round((p.processed / p.total) * 100)}%` }} /></div> : <div className="bar indet"><i /></div>}
      <span className="hint">You can leave this page — the search keeps running and appears in History.</span>
    </section>
  )
}

function SearchMeta({ s }) {
  const m = s.video_meta
  return (
    <section className="card">
      <div className="row" style={{ gap: 22, alignItems: 'flex-start' }}>
        {!s.media_deleted && <div style={{ width: 90 }}><AuthImage path={`/api/search/${s.id}/reference`} className="thumb" /><span className="hint">Reference</span></div>}
        <dl className="kv" style={{ flex: 1, minWidth: 240 }}>
          <dt>Video</dt><dd>{s.video_url || s.video_filename || '—'}</dd>
          <dt>Search type</dt><dd>{s.detection_mode}</dd>
          <dt>Threshold</dt><dd>{s.threshold.toFixed(2)}</dd>
          <dt>Sampling</dt><dd>{s.sampling_fps_used ? `${s.sampling_fps_used.toFixed(2)} fps${s.sampling_fps_requested ? '' : ' (auto)'}` : 'auto'}</dd>
          {m && <><dt>Video length</dt><dd>{api.fmtTime(m.duration)} · {m.width}×{m.height}</dd></>}
          <dt>Created</dt><dd>{api.fmtDate(s.created_at)}</dd>
        </dl>
      </div>
    </section>
  )
}

function MatchCard({ s, r }) {
  const m = s.video_meta
  const to = `/results/match?search=${s.id}&track=${r.track_id}&frame=${r.best_frame_index}`
  return (
    <Link to={to} className="match">
      <div className="shot">
        {s.media_deleted ? <div className="frameview"><div className="ph">Media removed by retention policy</div></div> :
          <FrameView path={`/api/search/${s.id}/frame/${r.best_frame_index}`} bbox={r.best_bbox} width={m?.width} height={m?.height} label={`Best frame of track ${r.track_id}`} />}
      </div>
      <div className="body">
        <div className="head">
          <div><span className="rank">MATCH {String(r.rank).padStart(2, '0')}</span><h3 style={{ marginTop: 6 }}>Track #{r.track_id}</h3></div>
          <span className="badge bronze">{r.class_name}</span>
        </div>
        <div className="metrics">
          <div className="metric hero"><b>{api.pct(r.best_similarity)}</b><span>Best similarity</span></div>
          <div className="metric"><b className="mono">{api.fmtTime(r.first_seen)}</b><span>First seen</span></div>
          <div className="metric"><b className="mono">{api.fmtTime(r.last_seen)}</b><span>Last seen</span></div>
          <div className="metric"><b>{r.match_count}</b><span>Matching samples</span></div>
        </div>
        <div className="metrics">
          <div className="metric"><b>{api.pct(r.track_score)}</b><span>Track score</span></div>
          <div className="metric"><b>{api.pct(r.mean_similarity)}</b><span>Mean</span></div>
          <div className="metric"><b>{api.pct(r.median_similarity)}</b><span>Median</span></div>
          <div className="metric"><b>{api.pct(r.consistency)}</b><span>Consistency</span></div>
        </div>
      </div>
    </Link>
  )
}

export default function Results() {
  const [params] = useSearchParams()
  const id = params.get('search')
  const { role } = useAuth()
  const { data: s, error, loading, reload } = useAsync(() => (id ? api.get(`/api/search/${id}`) : Promise.resolve(null)), [id])
  const running = s && (s.status === 'queued' || s.status === 'processing')
  usePolling(reload, running, 1500)

  if (!id) return <div className="empty card"><p>No search selected.</p><Link className="btn primary" to="/history">Open History</Link></div>
  if (loading && !s) return <Loading />
  if (error && !s) return <><ErrorNote error={error} onRetry={reload} /><Link to="/history">Back to history</Link></>
  return (
    <>
      <div className="page-head">
        <div className="stack" style={{ gap: 8 }}><span className="eyebrow">Search results</span><h1>{s.status === 'completed' ? `${s.match_count} match${s.match_count === 1 ? '' : 'es'}` : s.status === 'failed' ? 'Search failed' : 'Processing'}</h1></div>
        <div className="row">
          <StatusBadge status={s.status} />
          {role === 'ADMIN' && s.user && <span className="muted">{s.user.email}</span>}
          <Link className="btn" to="/history">History</Link>
          <Link className="btn primary" to="/search/new">New search</Link>
        </div>
      </div>
      {running && <Processing s={s} />}
      {s.status === 'failed' && <div className="note error" role="alert"><b>{s.error_code === 'download_failed' || s.error_code === 'invalid_url' ? 'Video download failed. ' : s.error_code === 'invalid_video' ? 'Invalid video. ' : s.error_code === 'invalid_image' ? 'Invalid image. ' : ''}</b>{s.error || 'VisualFind encountered an internal processing error.'}</div>}
      <SearchMeta s={s} />
      {s.status === 'completed' && (s.results.length === 0 ? (
        <div className="card empty">
          <h3>No matches found</h3>
          <p>No tracked {s.detection_mode === 'auto' ? 'subject' : s.detection_mode} reached a similarity of {s.threshold.toFixed(2)}. Try a lower threshold, a clearer reference image, or a different search type.</p>
          <Link className="btn primary" to="/search/new">Adjust and search again</Link>
        </div>
      ) : <div className="stack">{s.results.map((r) => <MatchCard key={r.track_id} s={s} r={r} />)}</div>)}
    </>
  )
}
