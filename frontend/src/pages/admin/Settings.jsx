import { useEffect, useState } from 'react'
import * as api from '../../api'
import { ErrorNote, Loading, StatusBadge, useAsync } from '../../components/ui'
import { Head } from './shared'

const PROVIDERS = [['custom', 'Custom'], ['huggingface', 'Hugging Face'], ['aws_sagemaker', 'AWS SageMaker'], ['azure_ml', 'Azure ML'], ['gcp_vertex', 'Google Vertex AI']]
const TABS = [['application', 'Application'], ['authentication', 'Authentication'], ['storage', 'Storage'], ['model', 'Model'], ['search', 'Search'], ['retention', 'Retention'], ['security', 'Security']]

function Num({ label, hint, value, onChange, min, max, step = 1 }) {
  return <label className="field"><span>{label}</span><input type="number" min={min} max={max} step={step} value={value} onChange={(e) => onChange(e.target.value === '' ? '' : Number(e.target.value))} />{hint && <span className="hint">{hint}</span>}</label>
}

function SettingsForm({ tab, data, reload }) {
  const [s, setS] = useState(data.settings)
  const [msg, setMsg] = useState(''); const [err, setErr] = useState('')
  useEffect(() => setS(data.settings), [data])
  const env = data.environment
  const set = (k) => (v) => setS({ ...s, [k]: v })
  async function save(keys) {
    setMsg(''); setErr('')
    try { await api.put('/api/admin/settings', Object.fromEntries(keys.map((k) => [k, s[k]]))); setMsg('Settings saved.'); reload(true) } catch (e) { setErr(e.message) }
  }
  const Save = ({ keys }) => <><ErrorNote error={err} />{msg && <div className="note ok">{msg}</div>}<div><button type="button" className="btn primary" onClick={() => save(keys)}>Save</button></div></>
  const kv = (rows) => <dl className="kv">{rows.map(([k, v]) => <><dt key={`${k}t`}>{k}</dt><dd key={`${k}d`}>{String(v)}</dd></>)}</dl>
  return (
    <div className="card stack" style={{ maxWidth: 640 }}>
      {tab === 'application' && <>{kv([['Database', env.database], ['Email delivery', env.email_delivery ? 'SMTP configured' : 'not configured'], ['Search concurrency', env.search_concurrency]])}
        <label className="check"><input type="checkbox" checked={s.registration_enabled} onChange={(e) => set('registration_enabled')(e.target.checked)} /><span><b>Allow public registration</b><br /><span className="hint">New accounts are always created with the USER role.</span></span></label><Save keys={['registration_enabled']} /></>}
      {tab === 'authentication' && <>{kv([['Session lifetime', `${env.token_ttl_minutes} minutes`], ['Password hashing', 'bcrypt']])}
        <Num label="Minimum password length" min={8} max={64} value={s.min_password_length} onChange={set('min_password_length')} /><Save keys={['min_password_length']} /></>}
      {tab === 'storage' && <>{kv([['Backend', env.storage_backend]])}
        <Num label="Max uploaded video (MB)" min={1} value={s.max_video_mb} onChange={set('max_video_mb')} />
        <Num label="Max downloaded video from URL (MB)" min={1} value={s.max_url_download_mb} onChange={set('max_url_download_mb')} />
        <Num label="URL download timeout (seconds)" min={5} max={1800} value={s.url_download_timeout_s} onChange={set('url_download_timeout_s')} /><Save keys={['max_video_mb', 'max_url_download_mb', 'url_download_timeout_s']} /></>}
      {tab === 'model' && <>{kv([['Encoder checkpoint', env.encoder_checkpoint], ['YOLO weights', env.yolo_weights]])}<span className="hint">The checkpoint and detector weights are set by the server environment. External model connections are configured below.</span><ModelConnection /></>}
      {tab === 'search' && <>
        <Num label="Default similarity threshold" min={0.5} max={0.95} step={0.01} value={s.default_threshold} onChange={set('default_threshold')} />
        <label className="field"><span>Default search type</span><select value={s.default_detection_mode} onChange={(e) => set('default_detection_mode')(e.target.value)}><option value="auto">Auto</option><option value="person">Person</option><option value="object">Object</option></select></label>
        <Num label="Max sampled frames per search" min={10} value={s.max_sampled_frames} onChange={set('max_sampled_frames')} hint="Sampling FPS is lowered automatically so this is not exceeded." />
        <Save keys={['default_threshold', 'default_detection_mode', 'max_sampled_frames']} /></>}
      {tab === 'retention' && <><Num label="Retention (days)" min={0} max={3650} value={s.retention_days} onChange={set('retention_days')} hint="Stored reference images, videos and frames are deleted after this many days. 0 keeps them until deleted by the user or an admin." /><Save keys={['retention_days']} /></>}
      {tab === 'security' && kv([['Role enforcement', 'server-side on every admin endpoint'], ['Passwords', 'bcrypt hashes only'], ['Model API keys', 'encrypted at rest, never returned'], ['Video URLs', 'HTTP/HTTPS only; private and internal addresses blocked']])}
    </div>
  )
}

function ModelConnection() {
  const { data, error, loading, reload } = useAsync(() => api.get('/api/model'), [])
  const [f, setF] = useState({ provider: 'custom', model_name: '', endpoint_url: '', api_key: '', version: '', options: '' })
  const [result, setResult] = useState(null); const [err, setErr] = useState(''); const [busy, setBusy] = useState(false)
  useEffect(() => {
    if (data?.configured) setF({ provider: data.provider, model_name: data.model_name, endpoint_url: data.endpoint_url, api_key: '', version: data.version || '', options: Object.keys(data.options || {}).length ? JSON.stringify(data.options) : '' })
  }, [data])
  async function save(e) {
    e.preventDefault(); setErr(''); setResult(null)
    let options = null
    if (f.options.trim()) { try { options = JSON.parse(f.options) } catch { return setErr('Optional configuration must be valid JSON.') } }
    setBusy(true)
    try { const r = await api.put('/api/model', { provider: f.provider, model_name: f.model_name, endpoint_url: f.endpoint_url, api_key: f.api_key || null, version: f.version || null, options }); setResult(r.test); setF((x) => ({ ...x, api_key: '' })); reload(true) } catch (x) { setErr(x.message) } finally { setBusy(false) }
  }
  async function test() {
    setErr(''); setBusy(true)
    try { setResult(await api.post('/api/model/test', undefined, { timeout: 30000 })); reload(true) } catch (x) { setErr(x.message) } finally { setBusy(false) }
  }
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })
  if (loading && !data) return <Loading />
  return (
    <form className="stack" onSubmit={save} style={{ borderTop: '1px solid var(--line)', paddingTop: 18 }}>
      <div className="row between"><h3>Model / cloud connection</h3>{data?.configured && <StatusBadge status={data.status} />}</div>
      <ErrorNote error={error} />
      <label className="field"><span>Provider</span><select value={f.provider} onChange={set('provider')}>{PROVIDERS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></label>
      <label className="field"><span>Model name</span><input required value={f.model_name} onChange={set('model_name')} /></label>
      <label className="field"><span>Endpoint URL</span><input type="url" required value={f.endpoint_url} onChange={set('endpoint_url')} placeholder="https://" /></label>
      <label className="field"><span>API key</span><input type="password" autoComplete="off" value={f.api_key} onChange={set('api_key')} placeholder={data?.has_api_key ? 'Saved — leave blank to keep' : ''} /><span className="hint">Stored encrypted. It is never shown again after saving.</span></label>
      <label className="field"><span>Version</span><input value={f.version} onChange={set('version')} /></label>
      <label className="field"><span>Optional configuration (JSON)</span><textarea rows={3} value={f.options} onChange={set('options')} /></label>
      <ErrorNote error={err} />
      {result && <div className={`note ${result.connected ? 'ok' : 'error'}`} role="status"><b>{result.connected ? 'CONNECTED' : String(result.status).replace(/_/g, ' ')}</b> — {result.message}{result.latency_ms != null && ` Latency ${result.latency_ms} ms.`}{result.provider && ` Provider: ${result.provider}. Model: ${result.model}.`}</div>}
      {data?.last_test && !result && <span className="hint">Last test {api.fmtDate(data.last_test.at)}: {data.last_test.message}</span>}
      <div className="row"><button className="btn primary" disabled={busy}>Save &amp; test</button><button type="button" className="btn" disabled={busy || !data?.configured} onClick={test}>Test connection</button></div>
    </form>
  )
}

export default function AdminSettings() {
  const [tab, setTab] = useState('application')
  const { data, error, loading, reload } = useAsync(() => api.get('/api/admin/settings'), [])
  return (
    <>
      <Head eyebrow="Administration" title="Settings" />
      <div className="tabs" role="tablist">{TABS.map(([k, l]) => <button key={k} role="tab" aria-selected={tab === k} className={tab === k ? 'on' : ''} onClick={() => setTab(k)}>{l}</button>)}</div>
      {loading && !data ? <Loading /> : error && !data ? <ErrorNote error={error} onRetry={reload} /> : <SettingsForm tab={tab} data={data} reload={reload} />}
    </>
  )
}
