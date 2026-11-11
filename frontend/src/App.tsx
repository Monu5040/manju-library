import { Route, Routes } from 'react-router'
import { AppShell } from '@/components/layout/AppShell'
import { PublicLayout } from '@/components/layout/PublicLayout'
import { RequireRole } from '@/components/RequireRole'
import AdminHomePage from '@/pages/AdminHomePage'
import HomePage from '@/pages/HomePage'
import NotFoundPage from '@/pages/NotFoundPage'
import PortalHomePage from '@/pages/PortalHomePage'
import StaffLoginPage from '@/pages/StaffLoginPage'
import StudentLoginPage from '@/pages/StudentLoginPage'

export default function App() {
  return (
    <Routes>
      <Route element={<PublicLayout />}>
        <Route index element={<HomePage />} />
        <Route path="login" element={<StudentLoginPage />} />
        <Route path="staff/login" element={<StaffLoginPage />} />
      </Route>

      <Route
        path="portal"
        element={
          <RequireRole roles={['STUDENT']}>
            <AppShell area="portal" />
          </RequireRole>
        }
      >
        <Route index element={<PortalHomePage />} />
      </Route>

      <Route
        path="admin"
        element={
          <RequireRole roles={['SUPER_ADMIN', 'STAFF']}>
            <AppShell area="admin" />
          </RequireRole>
        }
      >
        <Route index element={<AdminHomePage />} />
      </Route>

      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  )
}
