import { useState } from 'react'
import * as api from '../../api'
import { ErrorNote, Loading, Pager, useAsync } from '../../components/ui'
import { Head } from './shared'

const LIMIT = 30
const EMPTY = { action: '', actor: '', date_from: '', date_to: '' }

export default function AuditLogs() {
  const [f, setF] = useState(EMPTY); const [applied, setApplied] = useState(EMPTY); const [skip, setSkip] = useState(0)
  const qs = Object.entries(applied).filter(([, v]) => v).map(([k, v]) => `${k}=${encodeURIComponent(v)}`).join('&')
  const { data, error, loading, reload } = useAsync(() => api.get(`/api/admin/audit-logs?skip=${skip}&limit=${LIMIT}${qs ? `&${qs}` : ''}`), [skip, qs])
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })
  return (
    <>
      <Head eyebrow="Administration" title="Audit logs" />
      <form className="filters" onSubmit={(e) => { e.preventDefault(); setSkip(0); setApplied(f) }}>
        <label className="field"><span>Action</span><input value={f.action} onChange={set('action')} placeholder="e.g. user.login" /></label>
        <label className="field"><span>Actor email</span><input value={f.actor} onChange={set('actor')} /></label>
        <label className="field"><span>From</span><input type="date" value={f.date_from} onChange={set('date_from')} /></label>
        <label className="field"><span>To</span><input type="date" value={f.date_to} onChange={set('date_to')} /></label>
        <button className="btn primary">Apply</button>
        <button type="button" className="btn" onClick={() => { setF(EMPTY); setApplied(EMPTY); setSkip(0) }}>Reset</button>
      </form>
      <div className="card flush">
        {loading && !data ? <Loading /> : error ? <div style={{ padding: 18 }}><ErrorNote error={error} onRetry={reload} /></div> :
          data.items.length === 0 ? <div className="empty"><p>No audit events match.</p></div> : (
            <><div className="table-wrap"><table>
              <thead><tr><th>Time</th><th>Actor</th><th>Action</th><th>Target</th><th>Metadata</th></tr></thead>
              <tbody>{data.items.map((l) => (
                <tr key={l.id}><td className="muted" style={{ whiteSpace: 'nowrap' }}>{api.fmtDate(l.timestamp)}</td><td>{l.actor || '—'}{l.actor_role && <> <span className="badge">{l.actor_role}</span></>}</td>
                  <td className="mono">{l.action}</td><td className="mono" style={{ wordBreak: 'break-all' }}>{l.target || '—'}</td>
                  <td className="mono" style={{ maxWidth: 320, wordBreak: 'break-all' }}>{Object.keys(l.metadata || {}).length ? JSON.stringify(l.metadata) : '—'}</td></tr>))}</tbody>
            </table></div><Pager total={data.total} skip={skip} limit={LIMIT} onChange={setSkip} /></>)}
      </div>
    </>
  )
}
