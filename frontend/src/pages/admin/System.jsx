import * as api from '../../api'
import { ErrorNote, Loading, StatusBadge, useAsync, usePolling } from '../../components/ui'
import { Head } from './shared'

export default function System() {
  const { data, error, loading, reload } = useAsync(() => api.get('/api/admin/system'), [])
  usePolling(reload, true, 10000)
  return (
    <>
      <Head eyebrow="Administration" title="System status"><button className="btn" onClick={() => reload()}>Refresh</button></Head>
      {loading && !data ? <Loading /> : error && !data ? <ErrorNote error={error} onRetry={reload} /> : (
        <div className="card">{data.services.map((s) => (
          <div className="status-row" key={s.name}>
            <div><b>{s.name}</b><br /><span className="hint">{s.detail}{s.latency_ms != null ? ` · ${s.latency_ms} ms` : ''}</span></div>
            <StatusBadge status={s.status} />
          </div>))}</div>)}
    </>
  )
}
