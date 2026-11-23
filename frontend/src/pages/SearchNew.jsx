import { useEffect, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import * as api from '../api'
import { ErrorNote, useAsync } from '../components/ui'

const MODES = [
  ['person', 'Person', 'Detect and track people only.'],
  ['object', 'Object', 'Detect and track objects other than people.'],
  ['auto', 'Auto', 'Detect every supported class automatically.'],
]
const IMG_OK = ['image/jpeg', 'image/png', 'image/webp']
const IMG_EXT = /\.(jpe?g|png|webp)$/i
const VID_EXT = /\.(mp4|mov|avi|mkv|webm|m4v|mpe?g)$/i

function Drop({ accept, onFile, children, invalid }) {
  const input = useRef(null)
  const [over, setOver] = useState(false)
  return (
    <div className={`drop ${over ? 'over' : ''} ${invalid ? 'bad' : ''}`} role="button" tabIndex={0}
      onClick={() => input.current.click()} onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && input.current.click()}
      onDragOver={(e) => { e.preventDefault(); setOver(true) }} onDragLeave={() => setOver(false)}
      onDrop={(e) => { e.preventDefault(); setOver(false); if (e.dataTransfer.files[0]) onFile(e.dataTransfer.files[0]) }}>
      <input ref={input} type="file" accept={accept} hidden onChange={(e) => { if (e.target.files[0]) onFile(e.target.files[0]); e.target.value = '' }} />
      {children}
    </div>
  )
}

const size = (b) => (b > 1e6 ? `${(b / 1e6).toFixed(1)} MB` : `${Math.ceil(b / 1e3)} KB`)

export default function SearchNew() {
  const nav = useNavigate()
  const [params] = useSearchParams()
  const { data: policy } = useAsync(() => api.get('/api/public/policy', { auth: false }), [])
  const [mode, setMode] = useState('auto')
  const [threshold, setThreshold] = useState(0.7)
  const [ref, setRef] = useState(null)
  const [refUrl, setRefUrl] = useState(null)
  const [source, setSource] = useState(params.get('source') === 'url' ? 'url' : 'upload')
  const [video, setVideo] = useState(null)
  const [url, setUrl] = useState('')
  const [autoFps, setAutoFps] = useState(true)
  const [fps, setFps] = useState('5')
  const [errors, setErrors] = useState({})
  const [submitError, setSubmitError] = useState('')
  const [progress, setProgress] = useState(null)

  useEffect(() => { if (policy) { setThreshold(policy.default_threshold); setMode(policy.default_detection_mode) } }, [policy])
  useEffect(() => () => refUrl && URL.revokeObjectURL(refUrl), [refUrl])

  function pickRef(f) {
    if (!IMG_OK.includes(f.type) && !IMG_EXT.test(f.name)) return setErrors((e) => ({ ...e, ref: 'Reference image must be JPG, PNG or WEBP.' }))
    setErrors((e) => ({ ...e, ref: undefined }))
    setRef(f)
    setRefUrl(URL.createObjectURL(f))
  }
  function pickVideo(f) {
    if (!VID_EXT.test(f.name)) return setErrors((e) => ({ ...e, video: 'Unsupported video type. Use MP4, MOV, AVI, MKV or WEBM.' }))
    setErrors((e) => ({ ...e, video: undefined }))
    setVideo(f)
  }
  function validate() {
    const e = {}
    if (!ref) e.ref = 'Reference image is required.'
    if (source === 'upload' && !video) e.video = 'Choose a video file to search.'
    if (source === 'url') {
      try {
        const u = new URL(url.trim())
        if (!['http:', 'https:'].includes(u.protocol)) e.video = 'Only http and https video URLs are supported.'
      } catch { e.video = 'Enter a valid video URL, e.g. https://example.com/video.mp4' }
    }
    if (!autoFps && !(Number(fps) >= 0.1 && Number(fps) <= 30)) e.fps = 'Sampling FPS must be between 0.1 and 30.'
    return e
  }

  async function submit(ev) {
    ev.preventDefault()
    setSubmitError('')
    const e = validate()
    setErrors(e)
    if (Object.keys(e).length) return
    const form = new FormData()
    form.append('reference_image', ref)
    if (source === 'upload') form.append('video', video)  // exactly one video source is ever sent
    else form.append('video_url', url.trim())
    form.append('detection_mode', mode)
    form.append('similarity_threshold', threshold.toFixed(2))
    form.append('sampling_fps', autoFps ? 'auto' : fps)
    setProgress(0)
    try {
      const res = await api.uploadSearch(form, setProgress)
      nav(`/results?search=${res.id}`)
    } catch (err) {
      setSubmitError(err.message)
      setProgress(null)
    }
  }

  const busy = progress !== null
  return (
    <>
      <div className="page-head"><div className="stack" style={{ gap: 8 }}><span className="eyebrow">Search workspace</span><h1>New search</h1></div></div>
      <form className="ws" onSubmit={submit} noValidate>
        <div className="stack">
          <section className="card stack">
            <div className="label">1 · Search type</div>
            <div className="seg" role="radiogroup" aria-label="Search type">
              {MODES.map(([v, l]) => <button type="button" role="radio" aria-checked={mode === v} key={v} className={mode === v ? 'on' : ''} onClick={() => setMode(v)}>{l}</button>)}
            </div>
            <span className="hint">{MODES.find((m) => m[0] === mode)[2]}</span>
          </section>

          <section className="card stack">
            <div className="label">2 · Reference image <span className="err">(required)</span></div>
            <Drop accept=".jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp" onFile={pickRef} invalid={!!errors.ref}>
              {refUrl ? <div className="file"><img className="preview" src={refUrl} alt="Reference preview" /><span className="muted">{ref.name} · {size(ref.size)} — click or drop to replace</span></div> : (
                <><b>Drop the reference image here</b><span className="muted">or click to browse · JPG, PNG, WEBP</span></>)}
            </Drop>
            {errors.ref && <span className="err" role="alert">{errors.ref}</span>}
          </section>

          <section className="card stack">
            <div className="label">3 · Video source</div>
            <div className="seg two" role="tablist">
              <button type="button" role="tab" aria-selected={source === 'upload'} className={source === 'upload' ? 'on' : ''} onClick={() => setSource('upload')}>Upload video</button>
              <button type="button" role="tab" aria-selected={source === 'url'} className={source === 'url' ? 'on' : ''} onClick={() => setSource('url')}>Video URL</button>
            </div>
            {source === 'upload' ? (
              <Drop accept=".mp4,.mov,.avi,.mkv,.webm,.m4v,video/*" onFile={pickVideo} invalid={!!errors.video}>
                {video ? <div className="file"><b>{video.name}</b><span className="muted">{size(video.size)} — click or drop to replace</span></div> : (
                  <><b>Drag &amp; drop a video here</b><span className="muted">or click to browse · MP4, MOV, AVI, MKV, WEBM</span></>)}
              </Drop>
            ) : (
              <label className="field"><span>Video URL</span>
                <input type="url" inputMode="url" placeholder="https://example.com/video.mp4" value={url} onChange={(e) => setUrl(e.target.value)} />
                <span className="hint" style={{ textTransform: 'none', letterSpacing: 0 }}>HTTP or HTTPS only. The server downloads the file to temporary storage, searches it, then deletes it. Local and internal addresses are blocked.</span>
              </label>
            )}
            {errors.video && <span className="err" role="alert">{errors.video}</span>}
          </section>
        </div>

        <aside className="stack" style={{ position: 'sticky', top: 80 }}>
          <section className="card stack">
            <div className="row between"><span className="label">Similarity threshold</span><span className="big-num">{threshold.toFixed(2)}</span></div>
            <input type="range" min="0.5" max="0.95" step="0.01" value={threshold} onChange={(e) => setThreshold(Number(e.target.value))} aria-label="Similarity threshold" />
            <div className="sliderlabels"><span>0.50</span><span>0.95</span></div>
            <span className="hint">A track is kept when its best-matching moment reaches this similarity. Lower finds more, higher is stricter.</span>
          </section>
          <details className="card">
            <summary className="label" style={{ cursor: 'pointer' }}>Advanced</summary>
            <div className="stack" style={{ marginTop: 14 }}>
              <label className="check"><input type="checkbox" checked={autoFps} onChange={(e) => setAutoFps(e.target.checked)} /><span><b>Sampling FPS: AUTO</b><br /><span className="hint">Chosen from the video length and speed.</span></span></label>
              {!autoFps && <label className="field"><span>Sampling FPS</span><input type="number" min="0.1" max="30" step="0.1" value={fps} onChange={(e) => setFps(e.target.value)} />{errors.fps && <span className="err">{errors.fps}</span>}</label>}
            </div>
          </details>
          <ErrorNote error={submitError} />
          {busy && <div className="stack" style={{ gap: 6 }}><div className="bar"><i style={{ width: `${Math.round(progress * 100)}%` }} /></div><span className="hint">{progress < 1 ? `Uploading ${Math.round(progress * 100)}%` : 'Upload complete — validating…'}</span></div>}
          <button className="btn primary big" disabled={busy}>{busy ? 'Starting…' : 'Run search'}</button>
        </aside>
      </form>
    </>
  )
}
