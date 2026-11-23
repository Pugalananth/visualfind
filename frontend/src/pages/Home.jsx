import { Link } from 'react-router-dom'
import { Footer } from '../components/layout'

const FEATURES = [
  ['Image-to-Video Search', 'Give VisualFind one reference image and it finds the same subject across every sampled frame of your footage.'],
  ['Object Search', 'Restrict detection to non-person objects when the thing you are looking for is a bag, a vehicle or a product.'],
  ['Person Search', 'Detect and track people, then rank each tracked person by how closely they match your reference.'],
  ['Video URL Search', 'Point to an HTTP(S) video instead of uploading. The file is fetched safely, searched, then discarded.'],
  ['Search History', 'Every completed search is stored with its settings and results, visible only to you.'],
  ['Match Inspection', 'Open any match to see the real frame, bounding box, similarity and a timeline of every matching moment.'],
  ['Admin Control', 'Administrators manage users, review all searches and jobs, watch system health and read the audit log.'],
]
const STEPS = [
  ['Reference', 'Upload an image of the subject you want to find.'],
  ['Video', 'Upload a video file or provide a video URL.'],
  ['Visual search', 'Frames are sampled, subjects detected and tracked, then compared to your reference by a learned encoder.'],
  ['Matches', 'Tracks above your similarity threshold are ranked and inspectable down to the frame.'],
]

export default function Home() {
  return (
    <>
      <section className="hero">
        <div className="wrap">
          <span className="eyebrow">Visual search for video</span>
          <h1>Find what matters<br />in your <em>video.</em></h1>
          <p className="lead">VisualFind compares a single reference image against the people and objects in your footage, then shows you where, when and how closely they appear.</p>
          <div className="row">
            <Link className="btn primary big" to="/search/new">Start Searching</Link>
            <a className="btn big" href="#how">How It Works</a>
          </div>
          <div className="flow" role="img" aria-label="Illustration: reference image, video, visual search, matches">
            {[['01', 'Reference image', 'ref'], ['02', 'Video', 'film'], ['03', 'Visual search', 'scan'], ['04', 'Matches', 'match']].map(([n, label, kind]) => (
              <div className="step" key={n}>
                <div className={`frame ${kind === 'film' ? 'film' : ''}`}>
                  {kind === 'ref' && <><span className="dot" /><i style={{ left: '24%', top: '12%', width: '52%', height: '76%' }} /></>}
                  {kind === 'scan' && <><span className="dot" style={{ left: '12%' }} /><span className="dot" style={{ left: '52%', width: '30%', top: '30%' }} /><i style={{ left: '8%', top: '12%', width: '44%', height: '76%', opacity: .45 }} /><i style={{ left: '50%', top: '26%', width: '36%', height: '60%' }} /></>}
                  {kind === 'match' && <><span className="dot" /><i style={{ left: '24%', top: '12%', width: '52%', height: '76%' }} /></>}
                </div>
                <span className="num">{n}</span><b>{label}</b>
              </div>
            ))}
          </div>
          <span className="hint">Illustration only — not application data.</span>
        </div>
      </section>

      <section className="section" id="how">
        <div className="wrap">
          <div className="head"><span className="eyebrow">How it works</span><h2>One image in. Ranked matches out.</h2></div>
          <div className="how">
            {STEPS.map(([t, d], i) => <div key={t}><span className="num mono dim">0{i + 1}</span><h3>{t}</h3><p>{d}</p></div>)}
          </div>
        </div>
      </section>

      <section className="section" id="features">
        <div className="wrap">
          <div className="head"><span className="eyebrow">Features</span><h2>Built for people who review a lot of footage.</h2></div>
          <div className="features">
            {FEATURES.map(([t, d]) => <div className="feature" key={t}><h3>{t}</h3><p>{d}</p></div>)}
          </div>
        </div>
      </section>

      <section className="section" id="about">
        <div className="wrap prose">
          <span className="eyebrow">About</span>
          <h2>Visual intelligence, kept accountable.</h2>
          <p>VisualFind pairs a trained appearance encoder with YOLO detection and tracking. Results come from real model output — similarity, timing and bounding boxes — never placeholders. Accounts are role-based, administrative actions are audit-logged, and you can read exactly how uploads and history are handled in the <Link to="/privacy">privacy and data handling</Link> page.</p>
        </div>
      </section>
      <Footer />
    </>
  )
}
