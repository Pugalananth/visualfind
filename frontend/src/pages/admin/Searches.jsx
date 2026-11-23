import { useState } from 'react'
import * as api from '../../api'
import { ErrorNote, Loading, Pager, useAsync } from '../../components/ui'
import { Head, SearchTable } from './shared'

const LIMIT = 20
const EMPTY = { user: '', status: '', mode: '', date_from: '', date_to: '' }

export default function Searches() {
  const [f, setF] = useState(EMPTY); const [applied, setApplied] = useState(EMPTY); const [skip, setSkip] = useState(0)
  const qs = Object.entries(applied).filter(([, v]) => v).map(([k, v]) => `${k}=${encodeURIComponent(v)}`).join('&')
  const { data, error, loading, reload } = useAsync(() => api.get(`/api/admin/searches?skip=${skip}&limit=${LIMIT}${qs ? `&${qs}` : ''}`), [skip, qs])
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })
  return (
    <>
      <Head eyebrow="Administration" title="Searches" />
      <form className="filters" onSubmit={(e) => { e.preventDefault(); setSkip(0); setApplied(f) }}>
        <label className="field"><span>User</span><input value={f.user} onChange={set('user')} placeholder="Name or email" /></label>
        <label className="field"><span>Status</span><select value={f.status} onChange={set('status')}><option value="">Any</option><option value="completed">Completed</option><option value="processing">Processing</option><option value="queued">Queued</option><option value="failed">Failed</option></select></label>
        <label className="field"><span>Detection mode</span><select value={f.mode} onChange={set('mode')}><option value="">Any</option><option value="person">Person</option><option value="object">Object</option><option value="auto">Auto</option></select></label>
        <label className="field"><span>From</span><input type="date" value={f.date_from} onChange={set('date_from')} /></label>
        <label className="field"><span>To</span><input type="date" value={f.date_to} onChange={set('date_to')} /></label>
        <button className="btn primary">Apply</button>
        <button type="button" className="btn" onClick={() => { setF(EMPTY); setApplied(EMPTY); setSkip(0) }}>Reset</button>
      </form>
      <div className="card flush">
        {loading && !data ? <Loading /> : error ? <div style={{ padding: 18 }}><ErrorNote error={error} onRetry={reload} /></div> :
          data.items.length === 0 ? <div className="empty"><p>No searches match these filters.</p></div> :
            <><SearchTable items={data.items} /><Pager total={data.total} skip={skip} limit={LIMIT} onChange={setSkip} /></>}
      </div>
    </>
  )
}
