/**
 * Small fetch wrapper for the Django API.
 *
 * - Same-origin requests with the session cookie (Nginx in production, the Vite proxy locally).
 * - Every non-GET request carries Django's CSRF token from the `csrftoken` cookie; the cookie
 *   is fetched once from /api/auth/csrf/ if the browser does not have it yet.
 * - Non-2xx answers throw ApiError with the parsed JSON body.
 */

export class ApiError extends Error {
  readonly status: number
  readonly data: unknown

  constructor(status: number, data: unknown) {
    super(`Request failed with status ${status}`)
    this.name = 'ApiError'
    this.status = status
    this.data = data
  }
}

type Method = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'

interface RequestOptions {
  method?: Method
  body?: unknown
  signal?: AbortSignal
}

function readCookie(name: string): string | null {
  const prefix = `${name}=`
  const part = document.cookie.split('; ').find((item) => item.startsWith(prefix))
  return part ? decodeURIComponent(part.slice(prefix.length)) : null
}

async function csrfToken(): Promise<string> {
  let token = readCookie('csrftoken')
  if (!token) {
    await fetch('/api/auth/csrf/', { credentials: 'same-origin' })
    token = readCookie('csrftoken')
  }
  return token ?? ''
}

export async function api<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, signal } = options
  const headers: Record<string, string> = { Accept: 'application/json' }
  if (method !== 'GET') {
    headers['X-CSRFToken'] = await csrfToken()
  }
  if (body !== undefined) {
    headers['Content-Type'] = 'application/json'
  }

  const response = await fetch(`/api${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
    credentials: 'same-origin',
    signal,
  })

  const data: unknown = response.status === 204 ? null : await response.json().catch(() => null)
  if (!response.ok) {
    throw new ApiError(response.status, data)
  }
  return data as T
}

/** A sentence that can be shown to the person, from any error the API layer throws. */
export function errorMessage(error: unknown, fallback = 'Something went wrong. Please try again.') {
  if (error instanceof ApiError) {
    if (error.status === 429) {
      return 'Too many tries. Please wait a few minutes and try again.'
    }
    if (error.data && typeof error.data === 'object') {
      const record = error.data as Record<string, unknown>
      if (typeof record.detail === 'string') {
        return record.detail
      }
      for (const value of Object.values(record)) {
        if (Array.isArray(value) && typeof value[0] === 'string') {
          return value[0]
        }
      }
    }
    if (error.status >= 500) {
      return 'The server had a problem. Please try again in a minute.'
    }
  }
  if (error instanceof TypeError) {
    return 'Could not reach the server. Check your internet connection and try again.'
  }
  return fallback
}
