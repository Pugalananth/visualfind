import { Link, useNavigate } from 'react-router-dom'
import * as api from '../../api'
import { AuthImage, StatusBadge } from '../../components/ui'

export const Head = ({ eyebrow, title, children }) => (
  <div className="page-head">
    <div className="stack" style={{ gap: 8 }}><span className="eyebrow">{eyebrow}</span><h1>{title}</h1></div>
    {children && <div className="row">{children}</div>}
  </div>
)

export const Stat = ({ label, value }) => <div className="stat"><span>{label}</span><b>{value}</b></div>

export function SearchTable({ items, showUser = true }) {
  const nav = useNavigate()
  return (
    <div className="table-wrap"><table>
      <thead><tr><th />{showUser && <th>User</th>}<th>Source</th><th>Mode</th><th>Threshold</th><th>Matches</th><th>Created</th><th>Status</th></tr></thead>
      <tbody>{items.map((s) => (
        <tr key={s.id} className="click" onClick={() => nav(`/results?search=${s.id}`)}>
          <td>{!s.media_deleted && <AuthImage path={`/api/search/${s.id}/reference`} />}</td>
          {showUser && <td>{s.user ? <Link to={`/admin/users/${s.user.id}`} onClick={(e) => e.stopPropagation()}>{s.user.email}</Link> : '—'}</td>}
          <td style={{ maxWidth: 260, wordBreak: 'break-all' }}>{s.video_filename || s.video_url || '—'}{s.video_url && <><br /><span className="hint">URL source</span></>}</td>
          <td><span className="badge">{s.detection_mode}</span></td>
          <td className="mono">{s.threshold.toFixed(2)}</td>
          <td>{s.status === 'completed' ? s.match_count : '—'}</td>
          <td className="muted">{api.fmtDate(s.created_at)}</td>
          <td><StatusBadge status={s.status} /></td>
        </tr>))}</tbody>
    </table></div>
  )
}
