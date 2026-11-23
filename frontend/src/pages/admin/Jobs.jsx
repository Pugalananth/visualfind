import * as api from '../../api'
import { ErrorNote, Loading, StatusBadge, useAsync, usePolling } from '../../components/ui'
import { Head, SearchTable, Stat } from './shared'

export default function Jobs() {
  const { data, error, loading, reload } = useAsync(() => api.get('/api/admin/jobs'), [])
  usePolling(reload, true, 4000)
  if (loading && !data) return <Loading />
  if (error && !data) return <ErrorNote error={error} onRetry={reload} />
  const c = data.counts
  return (
    <>
      <Head eyebrow="Administration" title="Jobs" />
      <div className="metrics"><Stat label="Queued" value={c.queued} /><Stat label="Processing" value={c.processing} /><Stat label="Completed" value={c.completed} /><Stat label="Failed" value={c.failed} /></div>
      <p className="muted">Searches run in-process on this server, up to {data.concurrency} at a time; extra searches wait as <StatusBadge status="queued" />. States shown here are read from the database.</p>
      <section className="stack"><h3>Active</h3><div className="card flush">{data.active.length ? <SearchTable items={data.active} /> : <div className="empty"><p>No searches are queued or processing.</p></div>}</div></section>
      <section className="stack"><h3>Recent failures</h3><div className="card flush">{data.recent_failed.length ? <SearchTable items={data.recent_failed} /> : <div className="empty"><p>No failed searches.</p></div>}</div></section>
    </>
  )
}
