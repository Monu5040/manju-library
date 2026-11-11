import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach, beforeEach, vi } from 'vitest'

beforeEach(() => {
  document.cookie = 'csrftoken=test-csrf-token'
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})
