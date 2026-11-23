import { Link, useNavigate } from 'react-router-dom'
import * as api from '../api'
import { useAuth } from '../auth'
import { AuthImage, ErrorNote, Loading, StatusBadge, useAsync, usePolling } from '../components/ui'

export function SearchRows({ items }) {
  const nav = useNavigate()
  return (
    <div className="table-wrap">
      <table>
        <thead><tr><th /><th>Video</th><th>Mode</th><th>Threshold</th><th>Matches</th><th>Created</th><th>Status</th></tr></thead>
        <tbody>
          {items.map((s) => (
            <tr key={s.id} className="click" onClick={() => nav(`/results?search=${s.id}`)}>
              <td>{!s.media_deleted && <AuthImage path={`/api/search/${s.id}/reference`} />}</td>
              <td style={{ maxWidth: 260, overflow: 'hidden', textOverflow: 'ellipsis' }}><Link to={`/results?search=${s.id}`} onClick={(e) => e.stopPropagation()}>{s.video_filename || s.video_url || '—'}</Link></td>
              <td><span className="badge">{s.detection_mode}</span></td>
              <td className="mono">{s.threshold.toFixed(2)}</td>
              <td>{s.status === 'completed' ? s.match_count : '—'}</td>
              <td className="muted">{api.fmtDate(s.created_at)}</td>
              <td><StatusBadge status={s.status} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default function Dashboard() {
  const { user } = useAuth()
  const recent = useAsync(() => api.get('/api/history?limit=6'), [])
  const running = recent.data?.items.some((s) => s.status === 'queued' || s.status === 'processing')
  usePolling(recent.reload, running, 3000)
  return (
    <>
      <section className="dash-hero">
        <span className="eyebrow">Welcome, {user.name.split(' ')[0]}</span>
        <h1>Search your video.<br />Visually.</h1>
        <div className="row"><Link className="btn primary big" to="/search/new">New Search</Link></div>
      </section>
      <section className="quick">
        <Link to="/search/new"><span className="ico">01 / IMAGE</span><b>Search Image</b><small>Start from a reference image.</small></Link>
        <Link to="/search/new?source=upload"><span className="ico">02 / VIDEO</span><b>Search Video</b><small>Upload a video file to search.</small></Link>
        <Link to="/search/new?source=url"><span className="ico">03 / URL</span><b>Search by URL</b><small>Search a video at an HTTP(S) link.</small></Link>
        <Link to="/history"><span className="ico">04 / HISTORY</span><b>Search History</b><small>Reopen past searches and matches.</small></Link>
      </section>
      <section className="stack">
        <div className="row between"><h3>Recent searches</h3><Link to="/history">View all</Link></div>
        <div className="card flush">
          {recent.loading && !recent.data ? <Loading /> : recent.error ? <div style={{ padding: 18 }}><ErrorNote error={recent.error} onRetry={recent.reload} /></div> :
            recent.data.items.length === 0 ? (
              <div className="empty"><p>You have not run any searches yet.</p><Link className="btn primary" to="/search/new">Run your first search</Link></div>
            ) : <SearchRows items={recent.data.items} />}
        </div>
      </section>
    </>
  )
}
