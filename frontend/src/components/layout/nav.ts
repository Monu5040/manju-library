import {
  Activity,
  Armchair,
  BellRing,
  BookOpen,
  CalendarClock,
  ChartColumn,
  Clock,
  CreditCard,
  House,
  IdCard,
  IndianRupee,
  LayoutDashboard,
  ListOrdered,
  type LucideIcon,
  Megaphone,
  ReceiptText,
  Settings,
  Upload,
  UserCog,
  Users,
  Wallet,
} from 'lucide-react'
import type { Role } from '@/lib/auth'

export interface NavItem {
  to: string
  label: string
  icon: LucideIcon
  end?: boolean
  roles?: Role[]
  /** Shows how many reminders are waiting. */
  counter?: boolean
}

export interface NavGroup {
  title?: string
  items: NavItem[]
}

/** The front desk's menu, grouped the way the work is: the day, students, money, the library. */
export const ADMIN_NAV: NavGroup[] = [
  {
    items: [
      { to: '/admin', label: 'Overview', icon: LayoutDashboard, end: true },
      { to: '/admin/reminders', label: 'Reminders', icon: BellRing, counter: true },
      { to: '/admin/analytics', label: 'Analytics', icon: ChartColumn, roles: ['SUPER_ADMIN'] },
    ],
  },
  {
    title: 'Students',
    items: [
      { to: '/admin/students', label: 'Students', icon: Users },
      { to: '/admin/seats', label: 'Seat map', icon: Armchair },
      { to: '/admin/renewals', label: 'Renewals', icon: CalendarClock },
      { to: '/admin/waitlist', label: 'Waiting list', icon: ListOrdered },
    ],
  },
  {
    title: 'Money',
    items: [
      { to: '/admin/payments', label: 'Payments', icon: IndianRupee },
      { to: '/admin/expenses', label: 'Expenses', icon: ReceiptText },
      { to: '/admin/cash', label: 'Cash book', icon: Wallet },
      { to: '/admin/ledger', label: 'Ledger', icon: BookOpen, roles: ['SUPER_ADMIN'] },
    ],
  },
  {
    title: 'Library',
    items: [
      { to: '/admin/notices', label: 'Notices', icon: Megaphone },
      { to: '/admin/import', label: 'Import', icon: Upload, roles: ['SUPER_ADMIN'] },
      { to: '/admin/settings', label: 'Settings', icon: Settings },
      { to: '/admin/staff', label: 'Staff', icon: UserCog, roles: ['SUPER_ADMIN'] },
      { to: '/admin/system', label: 'System status', icon: Activity, roles: ['SUPER_ADMIN'] },
    ],
  },
]

export const PORTAL_NAV: NavItem[] = [
  { to: '/portal', label: 'Home', icon: House, end: true },
  { to: '/portal/payments', label: 'Payments', icon: CreditCard },
  { to: '/portal/profile', label: 'My details', icon: IdCard },
  { to: '/portal/fees', label: 'Fees and timings', icon: Clock },
]

export function visibleGroups(role: Role | undefined): NavGroup[] {
  return ADMIN_NAV.map((group) => ({
    ...group,
    items: group.items.filter((item) => !item.roles || (role && item.roles.includes(role))),
  })).filter((group) => group.items.length > 0)
}
