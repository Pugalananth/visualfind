import { useCallback, useEffect, useMemo } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import * as api from '../api'
import { AuthImage, ErrorNote, FrameView, Loading, useAsync } from '../components/ui'

export default function Match() {
  const [params] = useSearchParams()
  const nav = useNavigate()
  const sid = params.get('search')
  const track = Number(params.get('track'))
  const frameParam = params.get('frame')
  const search = useAsync(() => api.get(`/api/search/${sid}`), [sid])
  const frames = useAsync(() => api.get(`/api/search/${sid}/frames?track_id=${track}`), [sid, track])

  const list = frames.data?.frames || []
  const result = search.data?.results.find((r) => r.track_id === track)
  const idx = useMemo(() => {
    const i = list.findIndex((f) => String(f.frame_index) === frameParam)
    return i >= 0 ? i : Math.max(list.findIndex((f) => result && f.frame_index === result.best_frame_index), 0)
  }, [list, frameParam, result])
  const cur = list[idx]

  const go = useCallback((i) => {
    if (i < 0 || i >= list.length) return
    nav(`/results/match?search=${sid}&track=${track}&frame=${list[i].frame_index}`, { replace: true })
  }, [list, nav, sid, track])

  useEffect(() => {
    const onKey = (e) => {
      if (e.target.matches('input,textarea,select')) return
      if (e.key === 'ArrowLeft') go(idx - 1)
      if (e.key === 'ArrowRight') go(idx + 1)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [go, idx])

  if (!sid || !track) return <div className="empty card"><p>No match selected.</p><Link className="btn primary" to="/history">Open History</Link></div>
  if (search.loading || frames.loading) return <Loading />
  if (search.error || frames.error) return <><ErrorNote error={search.error || frames.error} onRetry={() => { search.reload(); frames.reload() }} /><Link to="/history">Back to history</Link></>
  const s = search.data
  if (!result) return <div className="empty card"><p>Track #{track} is not part of this search.</p><Link className="btn" to={`/results?search=${sid}`}>Back to results</Link></div>
  const m = s.video_meta
  const maxSim = Math.max(...list.map((f) => f.similarity), 0.0001)
  const minSim = Math.min(...list.map((f) => f.similarity))

  return (
    <>
      <div className="page-head">
        <div className="stack" style={{ gap: 8 }}><span className="eyebrow"><Link to={`/results?search=${sid}`}>← Results</Link> · Match {String(result.rank).padStart(2, '0')}</span><h1>Track #{track}</h1></div>
        <div className="row"><span className="badge bronze">{result.class_name}</span><span className="big-num">{api.pct(result.best_similarity)}</span><span className="muted">best similarity</span></div>
      </div>
      <div className="inspect">
        <div className="stack">
          <section className="card stack"><span className="label">Reference image</span>
            {s.media_deleted ? <div className="muted">Removed by retention policy.</div> : <AuthImage path={`/api/search/${sid}/reference`} className="" />}
          </section>
          <section className="card"><span className="label">Track summary</span>
            <dl className="kv" style={{ marginTop: 12 }}>
              <dt>Track score</dt><dd>{api.pct(result.track_score)}</dd><dt>Mean / median</dt><dd>{api.pct(result.mean_similarity)} / {api.pct(result.median_similarity)}</dd>
              <dt>Consistency</dt><dd>{api.pct(result.consistency)}</dd><dt>First – last seen</dt><dd>{api.fmtTime(result.first_seen)} – {api.fmtTime(result.last_seen)}</dd>
              <dt>Matching samples</dt><dd>{result.match_count} of {result.total_samples}</dd>
            </dl>
          </section>
        </div>
        <div className="stack">
          <section className="card stack">
            <div className="row between"><span className="label">Matched video frame</span><span className="mono dim">{list.length ? `${idx + 1} / ${list.length}` : ''}</span></div>
            {cur ? (
              <>
                {cur.has_image && !s.media_deleted ? <FrameView path={`/api/search/${sid}/frame/${cur.frame_index}`} bbox={cur.bbox} width={cur.width || m?.width} height={cur.height || m?.height} /> :
                  <div className="frameview"><div className="ph">{s.media_deleted ? 'Frame removed by retention policy.' : 'No image was saved for this frame.'}</div></div>}
                <div className="row between">
                  <button className="btn" onClick={() => go(idx - 1)} disabled={idx === 0}>← Previous frame</button>
                  <button className="btn" onClick={() => go(idx + 1)} disabled={idx >= list.length - 1}>Next frame →</button>
                </div>
                <div className="metrics three">
                  <div className="metric"><b>{api.pct(cur.similarity)}</b><span>Frame similarity</span></div>
                  <div className="metric"><b className="mono">{api.fmtTime(cur.timestamp)}</b><span>Timestamp</span></div>
                  <div className="metric"><b>{api.pct(cur.confidence)}</b><span>Detection confidence</span></div>
                </div>
                <dl className="kv"><dt>Bounding box (x1, y1, x2, y2)</dt><dd>{cur.bbox.map((v) => Math.round(v)).join(', ')}</dd><dt>Frame index</dt><dd>{cur.frame_index}</dd><dt>Class</dt><dd>{cur.class_name}</dd></dl>
              </>
            ) : <div className="muted">No saved frames for this track.</div>}
          </section>
          {list.length > 0 && (
            <section className="card stack"><div className="row between"><span className="label">Timeline of matching frames</span><span className="hint">Bar height = similarity · ← → keys also work</span></div>
              <div className="timeline" role="listbox" aria-label="Matching frames">
                {list.map((f, i) => (
                  <button key={f.frame_index} role="option" aria-selected={i === idx} className={i === idx ? 'on' : ''} onClick={() => go(i)}
                    style={{ height: `${20 + 80 * ((f.similarity - minSim) / Math.max(maxSim - minSim, 1e-6))}%` }}
                    title={`${api.fmtTime(f.timestamp)} · ${api.pct(f.similarity)}`} aria-label={`${api.fmtTime(f.timestamp)} similarity ${api.pct(f.similarity)}`} />
                ))}
              </div>
              <div className="row between mono dim"><span>{api.fmtTime(list[0].timestamp)}</span><span>{api.fmtTime(list[list.length - 1].timestamp)}</span></div>
              {result.match_count > list.length && <span className="hint">Showing {list.length} saved samples, evenly spread across {result.match_count} matching samples.</span>}
            </section>
          )}
        </div>
      </div>
    </>
  )
}
