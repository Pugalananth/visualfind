import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import * as api from '../api'
import { AuthImage, Confirm, ErrorNote, Loading, Pager, StatusBadge, useAsync, usePolling } from '../components/ui'

const LIMIT = 15

export default function History() {
  const nav = useNavigate()
  const [skip, setSkip] = useState(0)
  const [status, setStatus] = useState('')
  const [actionError, setActionError] = useState('')
  const { data, error, loading, reload } = useAsync(() => api.get(`/api/history?skip=${skip}&limit=${LIMIT}${status ? `&status=${status}` : ''}`), [skip, status])
  usePolling(reload, data?.items.some((s) => s.status === 'queued' || s.status === 'processing'), 3000)

  async function remove(id) {
    setActionError('')
    try { await api.del(`/api/history/${id}`); reload() } catch (e) { setActionError(e.message) }
  }
  return (
    <>
      <div className="page-head">
        <div className="stack" style={{ gap: 8 }}><span className="eyebrow">Your searches</span><h1>History</h1></div>
        <div className="row">
          <select value={status} onChange={(e) => { setStatus(e.target.value); setSkip(0) }} aria-label="Filter by status" style={{ width: 160 }}>
            <option value="">All statuses</option><option value="completed">Completed</option><option value="processing">Processing</option><option value="queued">Queued</option><option value="failed">Failed</option>
          </select>
          <Link className="btn primary" to="/search/new">New search</Link>
        </div>
      </div>
      <ErrorNote error={actionError} />
      <div className="card flush">
        {loading && !data ? <Loading /> : error ? <div style={{ padding: 18 }}><ErrorNote error={error} onRetry={reload} /></div> :
          data.items.length === 0 ? <div className="empty"><p>{status ? 'No searches with that status.' : 'Your history is empty.'}</p><Link className="btn primary" to="/search/new">Run a search</Link></div> : (
            <>
              <div className="table-wrap"><table>
                <thead><tr><th /><th>Video</th><th>Mode</th><th>Threshold</th><th>Sampling</th><th>Matches</th><th>Created</th><th>Status</th><th /></tr></thead>
                <tbody>{data.items.map((s) => (
                  <tr key={s.id} className="click" onClick={() => nav(`/results?search=${s.id}`)}>
                    <td>{!s.media_deleted && <AuthImage path={`/api/search/${s.id}/reference`} />}</td>
                    <td style={{ maxWidth: 280, wordBreak: 'break-all' }}>{s.video_url ? <span title={s.video_url}>{s.video_filename || s.video_url}<br /><span className="hint">URL source</span></span> : s.video_filename}</td>
                    <td><span className="badge">{s.detection_mode}</span></td><td className="mono">{s.threshold.toFixed(2)}</td>
                    <td className="mono">{s.sampling_fps_used ? `${s.sampling_fps_used.toFixed(1)} fps` : s.sampling_fps_requested ? `${s.sampling_fps_requested} fps` : 'auto'}</td>
                    <td>{s.status === 'completed' ? s.match_count : '—'}</td><td className="muted">{api.fmtDate(s.created_at)}</td>
                    <td><StatusBadge status={s.status} /></td>
                    <td onClick={(e) => e.stopPropagation()}>{s.status !== 'queued' && s.status !== 'processing' && <Confirm text="Delete?" onConfirm={() => remove(s.id)}>Delete</Confirm>}</td>
                  </tr>))}</tbody>
              </table></div>
              <Pager total={data.total} skip={skip} limit={LIMIT} onChange={setSkip} />
            </>)}
      </div>
    </>
  )
}
