import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import * as api from '../../api'
import { useAuth } from '../../auth'
import { Confirm, ErrorNote, Loading, Pager, useAsync } from '../../components/ui'
import { Head, SearchTable, Stat } from './shared'

const LIMIT = 20

export default function Users() {
  const [q, setQ] = useState(''); const [applied, setApplied] = useState(''); const [skip, setSkip] = useState(0)
  const { data, error, loading, reload } = useAsync(() => api.get(`/api/admin/users?skip=${skip}&limit=${LIMIT}${applied ? `&q=${encodeURIComponent(applied)}` : ''}`), [skip, applied])
  return (
    <>
      <Head eyebrow="Administration" title="Users" />
      <form className="filters" onSubmit={(e) => { e.preventDefault(); setSkip(0); setApplied(q.trim()) }}>
        <label className="field"><span>Search name or email</span><input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search users" /></label>
        <button className="btn primary">Search</button>
        {applied && <button type="button" className="btn" onClick={() => { setQ(''); setApplied(''); setSkip(0) }}>Clear</button>}
      </form>
      <div className="card flush">
        {loading && !data ? <Loading /> : error ? <div style={{ padding: 18 }}><ErrorNote error={error} onRetry={reload} /></div> :
          data.items.length === 0 ? <div className="empty"><p>No users found.</p></div> : (
            <><div className="table-wrap"><table>
              <thead><tr><th>Name</th><th>Email</th><th>Role</th><th>Status</th><th>Searches</th><th>Created</th></tr></thead>
              <tbody>{data.items.map((u) => (
                <tr key={u.id}><td><Link to={`/admin/users/${u.id}`}>{u.name}</Link></td><td>{u.email}</td><td><span className="badge">{u.role}</span></td>
                  <td><span className={`badge ${u.is_active ? 'ok' : 'bad'}`}>{u.is_active ? 'active' : 'inactive'}</span></td><td>{u.search_count}</td><td className="muted">{api.fmtDate(u.created_at)}</td></tr>))}</tbody>
            </table></div><Pager total={data.total} skip={skip} limit={LIMIT} onChange={setSkip} /></>)}
      </div>
    </>
  )
}

export function AdminUserDetail() {
  const { id } = useParams()
  const { user: me } = useAuth()
  const { data, error, loading, reload } = useAsync(() => api.get(`/api/admin/users/${id}`), [id])
  const [err, setErr] = useState('')
  async function change(body) {
    setErr('')
    try { await api.patch(`/api/admin/users/${id}`, body); reload(true) } catch (e) { setErr(e.message) }
  }
  if (loading && !data) return <Loading />
  if (error && !data) return <><ErrorNote error={error} onRetry={reload} /><Link to="/admin/users">Back to users</Link></>
  const self = me.id === data.id
  return (
    <>
      <Head eyebrow="User" title={data.name}><Link className="btn" to="/admin/users">All users</Link></Head>
      <ErrorNote error={err} />
      <div className="metrics">
        <Stat label="Searches" value={data.usage.searches} /><Stat label="Completed" value={data.usage.completed} />
        <Stat label="Failed" value={data.usage.failed} /><Stat label="Matches" value={data.usage.matches} />
      </div>
      <div className="card"><dl className="kv">
        <dt>Email</dt><dd>{data.email}</dd><dt>Role</dt><dd>{data.role}</dd>
        <dt>Status</dt><dd>{data.is_active ? 'active' : 'inactive'}</dd><dt>Account created</dt><dd>{api.fmtDate(data.created_at)}</dd>
      </dl></div>
      <div className="card stack">
        <h3>Account controls</h3>
        {self ? <p className="muted">You cannot change your own status or role.</p> : (
          <div className="row">
            {data.is_active
              ? <Confirm text="Deactivate this account?" onConfirm={() => change({ is_active: false })} className="btn danger">Deactivate</Confirm>
              : <button className="btn primary" onClick={() => change({ is_active: true })}>Activate</button>}
            {data.role === 'USER'
              ? <Confirm text="Grant admin rights?" onConfirm={() => change({ role: 'ADMIN' })} className="btn">Make admin</Confirm>
              : <Confirm text="Remove admin rights?" onConfirm={() => change({ role: 'USER' })} className="btn">Make user</Confirm>}
          </div>)}
        <span className="hint">Passwords are hashed and cannot be viewed. These actions are written to the audit log.</span>
      </div>
      <section className="stack"><h3>Recent searches</h3>
        <div className="card flush">{data.recent_searches.length ? <SearchTable items={data.recent_searches} showUser={false} /> : <div className="empty"><p>This user has not run any searches.</p></div>}</div>
      </section>
    </>
  )
}
