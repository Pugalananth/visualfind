import { Link } from 'react-router-dom'
import * as api from '../api'
import { Footer } from '../components/layout'
import { useAsync } from '../components/ui'

export function Privacy() {
  const { data } = useAsync(() => api.get('/api/public/policy', { auth: false }), [])
  const days = data?.retention_days
  const retention = data == null ? 'a configurable period' : days === 0 ? 'indefinitely, until you or an administrator deletes them' : `${days} day${days === 1 ? '' : 's'}`
  return (
    <>
      <main className="wrap page">
        <article className="prose">
          <span className="eyebrow">Privacy &amp; data handling</span>
          <h1 style={{ fontSize: '2.6rem' }}>How VisualFind handles your data</h1>
          <p>This page describes what the application actually does. It is operational information, not legal advice, and the operator of this installation is responsible for its own compliance obligations.</p>
          <h2>What we process</h2>
          <ul>
            <li><b>Reference images</b> you upload (JPG, PNG or WEBP) are stored so a search and its results can be inspected later.</li>
            <li><b>Videos</b> you upload are stored in the application's controlled storage and analysed frame by frame. Videos fetched from a URL are downloaded to a temporary location and deleted as soon as the search finishes; only the URL is recorded.</li>
            <li><b>Derived data</b> — detections, embeddings-based similarity scores, timestamps, bounding boxes and a limited set of saved match frames — is stored with each search.</li>
            <li><b>Account data</b> — name, email, a salted password hash (never the password), role and account status.</li>
          </ul>
          <h2>How long files are kept</h2>
          <p>Uploaded media and saved frames are kept for <b>{retention}</b>. After that period the media is deleted automatically while the search record (settings, counts, timing) remains. You can delete any search, or all of your history, at any time from History and Settings.</p>
          <h2>Search history and who can see it</h2>
          <p>Each search is stored in the database against your account. You can see only your own history. Users with the administrator role can view all searches, including reference images, settings and match frames, for operations, support and abuse prevention. Administrative actions and sign-ins are recorded in an audit log.</p>
          <h2>Account security</h2>
          <ul>
            <li>Passwords are hashed with bcrypt; plaintext passwords are never stored or shown to administrators.</li>
            <li>Sessions use signed tokens; changing your password signs out other sessions.</li>
            <li>Repeated failed sign-ins are temporarily blocked.</li>
          </ul>
          <h2>Your responsibilities</h2>
          <p>Only upload images and videos you have the right to process, and respect the privacy of people who appear in them. Do not use VisualFind to track or identify individuals without a lawful basis and their consent where required.</p>
          <p><Link to="/terms">Terms of use</Link></p>
        </article>
      </main>
      <Footer />
    </>
  )
}

export function Terms() {
  return (
    <>
      <main className="wrap page">
        <article className="prose">
          <span className="eyebrow">Terms</span>
          <h1 style={{ fontSize: '2.6rem' }}>Terms of use</h1>
          <p>By creating an account you agree to the following. These terms are a general template for this installation; its operator may replace them with their own.</p>
          <h2>Acceptable use</h2>
          <ul>
            <li>Upload only content you are entitled to process.</li>
            <li>Do not attempt to access other users' data, administrative functions or internal network resources.</li>
            <li>Do not submit video URLs that point to systems you do not own or have permission to access.</li>
          </ul>
          <h2>Results</h2>
          <p>Matches are statistical similarity estimates produced by a machine-learning model. They can be wrong. Review every match yourself before relying on it, especially where a decision about a person depends on it.</p>
          <h2>Accounts</h2>
          <p>Administrators may deactivate accounts that violate these terms. You are responsible for keeping your credentials confidential.</p>
          <h2>Data handling</h2>
          <p>See <Link to="/privacy">Privacy &amp; data handling</Link> for what is stored and for how long.</p>
        </article>
      </main>
      <Footer />
    </>
  )
}
