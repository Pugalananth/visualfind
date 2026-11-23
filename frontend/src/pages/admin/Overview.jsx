import * as api from '../../api'
import { ErrorNote, Loading, useAsync, usePolling } from '../../components/ui'
import { Link } from 'react-router-dom'
import { Head, SearchTable, Stat } from './shared'

export default function Overview() {
  const { data, error, loading, reload } = useAsync(() => api.get('/api/admin/overview'), [])
  usePolling(reload, true, 10000)
  if (loading && !data) return <Loading />
  if (error && !data) return <ErrorNote error={error} onRetry={reload} />
  const s = data.stats
  return (
    <>
      <Head eyebrow="Administration" title="Overview" />
      <div className="metrics">
        <Stat label="Total users" value={s.total_users} /><Stat label="Active users" value={s.active_users} />
        <Stat label="Total searches" value={s.total_searches} /><Stat label="Completed" value={s.completed_searches} />
        <Stat label="Failed" value={s.failed_searches} /><Stat label="Total matches" value={s.total_matches} />
      </div>
      <section className="stack">
        <div className="row between"><h3>Recent searches</h3><Link to="/admin/searches">View all</Link></div>
        <div className="card flush">{data.recent_searches.length ? <SearchTable items={data.recent_searches} /> : <div className="empty"><p>No searches have been run yet.</p></div>}</div>
      </section>
      <section className="stack">
        <div className="row between"><h3>Recent users</h3><Link to="/admin/users">View all</Link></div>
        <div className="card flush"><div className="table-wrap"><table>
          <thead><tr><th>Name</th><th>Email</th><th>Role</th><th>Status</th><th>Created</th></tr></thead>
          <tbody>{data.recent_users.map((u) => (
            <tr key={u.id}><td><Link to={`/admin/users/${u.id}`}>{u.name}</Link></td><td>{u.email}</td><td><span className="badge">{u.role}</span></td>
              <td><span className={`badge ${u.is_active ? 'ok' : 'bad'}`}>{u.is_active ? 'active' : 'inactive'}</span></td><td className="muted">{api.fmtDate(u.created_at)}</td></tr>))}</tbody>
        </table></div></div>
      </section>
    </>
  )
}
