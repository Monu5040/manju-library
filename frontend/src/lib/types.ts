/** Shapes returned by the Django admin API (/api/admin/...). */

export interface Paginated<T> {
  count: number
  next: string | null
  previous: string | null
  results: T[]
}

export interface Branch {
  id: number
  name: string
  code: string
  address: string
  phone: string
  allow_seat_sharing: boolean
  is_active: boolean
}

export interface Shift {
  id: number
  name: string
  start_time: string
  end_time: string
  sort_order: number
  is_active: boolean
  hours: number
  time_label: string
}

export interface Seat {
  id: number
  number: string
  label: string
  is_active: boolean
}

export interface Plan {
  id: number
  name: string
  duration_months: number
  shift: number | null
  shift_name: string | null
  price: number
  is_active: boolean
}

export type MembershipState = 'UPCOMING' | 'ACTIVE' | 'EXPIRED' | 'CANCELLED'

export interface MembershipSummary {
  id: number
  seat_number: string | null
  shift_name: string | null
  time_label: string
  plan_name: string | null
  start_date: string
  end_date: string
  days_left: number
  state: MembershipState
  due_total: number
}

export interface Student {
  id: number
  roll_no: number
  full_name: string
  gender: '' | 'F' | 'M' | 'O'
  father_name: string
  mobile: string
  alt_mobile: string
  aadhaar_masked: string
  address: string
  admission_date: string | null
  status: 'ACTIVE' | 'LEFT'
  notes: string
  created_at: string
  current_membership: MembershipSummary | null
  total_due: number
}

export interface Membership {
  id: number
  student: number
  student_name: string
  roll_no: number
  plan: number | null
  plan_name: string | null
  shift: number | null
  shift_name: string | null
  custom_start_time: string | null
  custom_end_time: string | null
  time_label: string
  seat: number | null
  seat_number: string | null
  start_date: string
  end_date: string
  price: number
  discount: number
  net_fee: number
  paid_total: number
  due_total: number
  status: 'ACTIVE' | 'CANCELLED'
  state: MembershipState
  days_left: number
  renewed_from: number | null
  notes: string
  created_at: string
}

export type PaymentMode = 'CASH' | 'UPI' | 'CARD' | 'BANK' | 'OTHER'

export interface Payment {
  id: number
  receipt_no: number
  student: number
  student_name: string
  roll_no: number
  membership: number | null
  amount: number
  mode: PaymentMode
  mode_label: string
  paid_on: string
  reference: string
  notes: string
  collected_by_name: string | null
  is_void: boolean
  void_reason: string
  voided_at: string | null
  created_at: string
}

export interface PaymentSummary {
  total: number
  count: number
  by_mode: { mode: PaymentMode; total: number; count: number }[]
}

export interface Overview {
  users: { students: number; staff: number; super_admins: number }
  library: {
    active_members: number
    seats: number
    occupied_seats: number
    occupancy_percent: number
    expiring_in_7_days: number
    outstanding_dues: number
    collected_today: number
    collected_this_month: number
    waiting: number
  }
}

export interface SeatBooking {
  membership: number
  student: number
  student_name: string
  roll_no: number
  shift_name: string | null
  time_label: string
  start_minute: number
  end_minute: number
  end_date: string
  days_left: number
}

export interface SeatMap {
  date: string
  allow_seat_sharing: boolean
  shifts: { id: number; name: string; time_label: string; minutes: [number, number] }[]
  seats: { id: number; number: string; is_active: boolean; bookings: SeatBooking[] }[]
  summary: { seats: number; occupied: number; free: number }
}

export interface WaitlistEntry {
  id: number
  student: number
  student_name: string
  roll_no: number
  mobile: string
  preferred_shift: number | null
  preferred_shift_name: string | null
  position: number
  status: 'WAITING' | 'SEATED' | 'REMOVED'
  note: string
  created_at: string
}

export interface StaffAccount {
  id: number
  full_name: string
  mobile: string
  email: string | null
  role: 'SUPER_ADMIN' | 'STAFF'
  can_export: boolean
  is_active: boolean
  last_login: string | null
  date_joined: string
  has_authenticator: boolean
}

export const PAYMENT_MODES: { value: PaymentMode; label: string }[] = [
  { value: 'CASH', label: 'Cash' },
  { value: 'UPI', label: 'UPI' },
  { value: 'CARD', label: 'Card' },
  { value: 'BANK', label: 'Bank transfer' },
  { value: 'OTHER', label: 'Other' },
]

export interface ImportRowInfo {
  row_number: number
  raw: Record<string, string>
  result: 'READY' | 'ERROR' | 'IMPORTED' | 'SKIPPED'
  errors: string[]
  warnings: string[]
}

export interface ImportJob {
  id: number
  file_name: string
  file_format: 'xlsx' | 'xls' | 'csv'
  sheet: string
  header_row: number
  mapping: Record<string, number>
  options: { create_missing?: boolean; day_first?: boolean }
  status: 'CHECKED' | 'IMPORTED' | 'UNDONE'
  summary: {
    rows: number
    ready: number
    errors: number
    with_warnings: number
    imported: number
    skipped: number
    memberships: number
    payments: number
    waiting_list: number
    amount_paid: string
  }
  created_by_name: string | null
  created_at: string
  imported_at: string | null
  undone_at: string | null
  can_undo: boolean
}

export interface ImportJobDetail extends ImportJob {
  sheets: string[]
  encoding: string
  delimiter: string
  columns: { index: number; header: string; field: string | null; ignored: boolean }[]
  fields: { key: string; label: string }[]
  preview: string[][]
  problem_rows: ImportRowInfo[]
  warning_rows: ImportRowInfo[]
  duplicate_of?: { id: number; imported_at: string }
}

// --- student portal --------------------------------------------------------------

export interface PortalMembership {
  id: number
  seat_number: string | null
  shift_name: string | null
  plan_name: string | null
  time_label: string
  start_date: string
  end_date: string
  state: MembershipState
  days_left: number
  price: number
  discount: number
  net_fee: number
  paid_total: number
  due_total: number
}

export interface PortalStudent {
  id: number
  roll_no: number
  full_name: string
  father_name: string
  mobile: string
  alt_mobile: string
  address: string
  aadhaar_masked: string
  admission_date: string | null
  status: 'ACTIVE' | 'LEFT'
  branch_name: string
  current_membership: PortalMembership | null
  total_due: number
}

export interface PortalPayment {
  id: number
  receipt_no: number
  paid_on: string
  amount: number
  mode_label: string
  reference: string
  is_void: boolean
}

export interface Notice {
  id: number
  title: string
  body: string
  starts_on: string
  ends_on: string | null
  is_pinned: boolean
  created_by_name?: string | null
  created_at?: string
}

export interface LibraryInfo {
  name: string
  address: string
  phone: string
}

export interface PortalHome {
  profiles: PortalStudent[]
  library: LibraryInfo | null
  notices: Notice[]
  shifts: { id: number; name: string; time_label: string; hours: number }[]
  plans: { id: number; name: string; duration_months: number; shift_name: string | null; price: number }[]
}

export interface PortalStudentDetail extends PortalStudent {
  memberships: PortalMembership[]
  payments: PortalPayment[]
}

export interface PortalReceipt extends PortalPayment {
  student_name: string
  roll_no: number
  library: LibraryInfo
}
