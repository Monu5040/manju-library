import { lazy, Suspense } from 'react'
import { Route, Routes } from 'react-router'
import { AppShell } from '@/components/layout/AppShell'
import { PublicLayout } from '@/components/layout/PublicLayout'
import { RequireRole } from '@/components/RequireRole'
import HomePage from '@/pages/HomePage'
import NotFoundPage from '@/pages/NotFoundPage'
import PortalHomePage from '@/pages/PortalHomePage'
import StaffLoginPage from '@/pages/StaffLoginPage'
import StudentLoginPage from '@/pages/StudentLoginPage'
import { FullPageSpinner } from '@/components/ui/spinner'

// The admin area loads only when an admin opens it; students and visitors never download it.
const AdminHomePage = lazy(() => import('@/pages/AdminHomePage'))
const AccountPage = lazy(() => import('@/pages/admin/AccountPage'))
const AdmissionPage = lazy(() => import('@/pages/admin/AdmissionPage'))
const PaymentsPage = lazy(() => import('@/pages/admin/PaymentsPage'))
const ReceiptPage = lazy(() => import('@/pages/admin/ReceiptPage'))
const RenewalsPage = lazy(() => import('@/pages/admin/RenewalsPage'))
const SeatMapPage = lazy(() => import('@/pages/admin/SeatMapPage'))
const SettingsPage = lazy(() => import('@/pages/admin/SettingsPage'))
const StaffPage = lazy(() => import('@/pages/admin/StaffPage'))
const StudentDetailPage = lazy(() => import('@/pages/admin/StudentDetailPage'))
const StudentsPage = lazy(() => import('@/pages/admin/StudentsPage'))
const WaitlistPage = lazy(() => import('@/pages/admin/WaitlistPage'))
const ImportPage = lazy(() => import('@/pages/admin/ImportPage'))
const ImportJobPage = lazy(() => import('@/pages/admin/ImportJobPage'))
const NoticesPage = lazy(() => import('@/pages/admin/NoticesPage'))
const AnalyticsPage = lazy(() => import('@/pages/admin/AnalyticsPage'))
const ExpensesPage = lazy(() => import('@/pages/admin/ExpensesPage'))
const LedgerPage = lazy(() => import('@/pages/admin/LedgerPage'))
const LedgerImportPage = lazy(() => import('@/pages/admin/LedgerImportPage'))
const CashBookPage = lazy(() => import('@/pages/admin/CashBookPage'))
const PortalPaymentsPage = lazy(() => import('@/pages/portal/PortalPaymentsPage'))
const PortalReceiptPage = lazy(() => import('@/pages/portal/PortalReceiptPage'))
const PortalProfilePage = lazy(() => import('@/pages/portal/PortalProfilePage'))
const PortalFeesPage = lazy(() => import('@/pages/portal/PortalFeesPage'))

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
        <Route path="payments" element={<PortalPaymentsPage />} />
        <Route path="receipts/:id" element={<PortalReceiptPage />} />
        <Route path="profile" element={<PortalProfilePage />} />
        <Route path="fees" element={<PortalFeesPage />} />
      </Route>

      <Route
        path="admin"
        element={
          <RequireRole roles={['SUPER_ADMIN', 'STAFF']}>
            <Suspense fallback={<FullPageSpinner />}>
              <AppShell area="admin" />
            </Suspense>
          </RequireRole>
        }
      >
        <Route index element={<AdminHomePage />} />
        <Route path="students" element={<StudentsPage />} />
        <Route path="students/new" element={<AdmissionPage />} />
        <Route path="students/:id" element={<StudentDetailPage />} />
        <Route path="seats" element={<SeatMapPage />} />
        <Route path="renewals" element={<RenewalsPage />} />
        <Route path="payments" element={<PaymentsPage />} />
        <Route path="payments/:id/receipt" element={<ReceiptPage />} />
        <Route path="waitlist" element={<WaitlistPage />} />
        <Route path="notices" element={<NoticesPage />} />
        <Route path="expenses" element={<ExpensesPage />} />
        <Route path="cash" element={<CashBookPage />} />
        <Route
          path="ledger"
          element={
            <RequireRole roles={['SUPER_ADMIN']}>
              <LedgerPage />
            </RequireRole>
          }
        />
        <Route
          path="ledger/import"
          element={
            <RequireRole roles={['SUPER_ADMIN']}>
              <LedgerImportPage />
            </RequireRole>
          }
        />
        <Route
          path="analytics"
          element={
            <RequireRole roles={['SUPER_ADMIN']}>
              <AnalyticsPage />
            </RequireRole>
          }
        />
        <Route
          path="import"
          element={
            <RequireRole roles={['SUPER_ADMIN']}>
              <ImportPage />
            </RequireRole>
          }
        />
        <Route
          path="import/:id"
          element={
            <RequireRole roles={['SUPER_ADMIN']}>
              <ImportJobPage />
            </RequireRole>
          }
        />
        <Route path="settings" element={<SettingsPage />} />
        <Route
          path="staff"
          element={
            <RequireRole roles={['SUPER_ADMIN']}>
              <StaffPage />
            </RequireRole>
          }
        />
        <Route path="account" element={<AccountPage />} />
      </Route>

      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  )
}
