import { z } from 'zod'

const MOBILE_PATTERN = /^[6-9]\d{9}$/

/** Same rule as the server: keep 10 digits, dropping spaces, dashes, +91/91 and a leading 0. */
export function normalizeMobile(value: string): string {
  let digits = value.replace(/\D/g, '')
  if (digits.length === 12 && digits.startsWith('91')) {
    digits = digits.slice(2)
  } else if (digits.length === 11 && digits.startsWith('0')) {
    digits = digits.slice(1)
  }
  return digits
}

export function maskMobile(mobile: string): string {
  return `${mobile.slice(0, 2)}XXXXXX${mobile.slice(-2)}`
}

export const mobileSchema = z
  .string()
  .trim()
  .refine((value) => MOBILE_PATTERN.test(normalizeMobile(value)), {
    error: 'Enter a 10-digit mobile number that starts with 6, 7, 8 or 9.',
  })

export const sixDigitCodeSchema = z
  .string()
  .trim()
  .regex(/^\d{6}$/, { error: 'Enter the 6-digit code.' })
