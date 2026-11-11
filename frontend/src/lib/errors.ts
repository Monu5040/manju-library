import { ApiError } from './api'

/**
 * Field errors from a DRF 400 response, flattened to "first message per field".
 * Nested objects (for example {"student": {"mobile": [...]}}) become "student.mobile".
 */
export function fieldErrors(error: unknown): Record<string, string> {
  const result: Record<string, string> = {}
  if (!(error instanceof ApiError) || error.status !== 400 || !error.data || typeof error.data !== 'object') {
    return result
  }
  const walk = (value: unknown, prefix: string) => {
    if (Array.isArray(value)) {
      if (typeof value[0] === 'string') {
        result[prefix] = value[0]
      }
      return
    }
    if (typeof value === 'string') {
      result[prefix] = value
      return
    }
    if (value && typeof value === 'object') {
      for (const [key, inner] of Object.entries(value)) {
        walk(inner, prefix ? `${prefix}.${key}` : key)
      }
    }
  }
  walk(error.data, '')
  return result
}

/** Errors under one prefix, with the prefix removed: pick(errors, 'student') */
export function pick(errors: Record<string, string>, prefix: string): Record<string, string> {
  return Object.fromEntries(
    Object.entries(errors)
      .filter(([key]) => key.startsWith(`${prefix}.`))
      .map(([key, value]) => [key.slice(prefix.length + 1), value]),
  )
}
