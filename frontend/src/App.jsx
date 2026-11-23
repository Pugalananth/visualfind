import { Link, Navigate, Outlet, Route, Routes } from 'react-router-dom'
import { PublicOnly, RequireAuth } from './auth'
import { AdminShell, AppShell, Footer, PublicNav } from './components/layout'
import { ForgotPassword, Login, Register, ResetPassword } from './pages/Auth'
import Dashboard from './pages/Dashboard'
import History from './pages/History'
import Home from './pages/Home'
import { Privacy, Terms } from './pages/Legal'
import Match from './pages/Match'
import Profile from './pages/Profile'
import Results from './pages/Results'
import SearchNew from './pages/SearchNew'
import Settings from './pages/Settings'
import AdminOverview from './pages/admin/Overview'
import AdminUsers, { AdminUserDetail } from './pages/admin/Users'
import AdminSearches from './pages/admin/Searches'
import AdminJobs from './pages/admin/Jobs'
import AdminSystem from './pages/admin/System'
import AdminAuditLogs from './pages/admin/AuditLogs'
import AdminSettings from './pages/admin/Settings'

const PublicLayout = () => (<><PublicNav /><Outlet /><Footer /></>)

function NotFound() {
  return (
    <div className="wrap page"><div className="card empty"><h3>Page not found</h3><p>That page does not exist.</p><Link className="btn primary" to="/">Go home</Link></div></div>
  )
}

export default function App() {
  return (
    <Routes>
      <Route element={<PublicLayout />}>
        <Route path="/" element={<Home />} />
        <Route path="/privacy" element={<Privacy />} />
        <Route path="/terms" element={<Terms />} />
      </Route>
      <Route path="/login" element={<PublicOnly><Login /></PublicOnly>} />
      <Route path="/register" element={<PublicOnly><Register /></PublicOnly>} />
      <Route path="/forgot-password" element={<PublicOnly><ForgotPassword /></PublicOnly>} />
      <Route path="/reset-password" element={<PublicOnly><ResetPassword /></PublicOnly>} />

      <Route element={<RequireAuth><AppShell /></RequireAuth>}>
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/search/new" element={<SearchNew />} />
        <Route path="/results" element={<Results />} />
        <Route path="/results/match" element={<Match />} />
        <Route path="/history" element={<History />} />
        <Route path="/profile" element={<Profile />} />
        <Route path="/settings" element={<Settings />} />
      </Route>

      <Route path="/admin" element={<RequireAuth role="ADMIN"><AdminShell /></RequireAuth>}>
        <Route index element={<AdminOverview />} />
        <Route path="users" element={<AdminUsers />} />
        <Route path="users/:id" element={<AdminUserDetail />} />
        <Route path="searches" element={<AdminSearches />} />
        <Route path="history" element={<Navigate to="/admin/searches" replace />} />
        <Route path="jobs" element={<AdminJobs />} />
        <Route path="system" element={<AdminSystem />} />
        <Route path="audit-logs" element={<AdminAuditLogs />} />
        <Route path="settings" element={<AdminSettings />} />
      </Route>
      <Route path="*" element={<NotFound />} />
    </Routes>
  )
}
