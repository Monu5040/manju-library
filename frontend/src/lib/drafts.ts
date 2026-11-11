import { todayIso } from './format'
import type { PaymentMode } from './types'

/** Membership terms as edited in forms (strings, as inputs produce them). */
export interface MembershipDraft {
  plan: string
  shift: string
  seat: string
  start_date: string
  end_date: string
  price: string
  discount: string
}

export function membershipPayload(draft: MembershipDraft) {
  return {
    plan: draft.plan ? Number(draft.plan) : null,
    shift: draft.shift ? Number(draft.shift) : null,
    seat: draft.seat ? Number(draft.seat) : null,
    start_date: draft.start_date || undefined,
    end_date: draft.end_date || undefined,
    price: draft.price === '' ? undefined : Number(draft.price),
    discount: draft.discount === '' ? 0 : Number(draft.discount),
  }
}

export interface PaymentDraft {
  amount: string
  mode: PaymentMode
  paid_on: string
  reference: string
}

export const emptyPayment = (amount = ''): PaymentDraft => ({
  amount,
  mode: 'CASH',
  paid_on: todayIso(),
  reference: '',
})

export function paymentPayload(draft: PaymentDraft) {
  return {
    amount: Number(draft.amount),
    mode: draft.mode,
    paid_on: draft.paid_on || undefined,
    reference: draft.reference,
  }
}
