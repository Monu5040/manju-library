import '@testing-library/jest-dom/vitest'
import { cleanup, configure } from '@testing-library/react'
import { afterEach, beforeEach, vi } from 'vitest'

// A busy machine or CI runner can take more than the default second to render a page.
configure({ asyncUtilTimeout: 5000 })

beforeEach(() => {
  document.cookie = 'csrftoken=test-csrf-token'
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})
