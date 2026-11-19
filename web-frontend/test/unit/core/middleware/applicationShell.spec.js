import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'
import { mockNuxtImport } from '@nuxt/test-utils/runtime'
import applicationShell from '@baserow/modules/core/middleware/applicationShell'

const state = vi.hoisted(() => ({ app: null, error: null, navigate: vi.fn() }))
mockNuxtImport('useNuxtApp', (original) => () => state.app || original())
mockNuxtImport(
  'useError',
  (original) => () => (state.app ? { value: state.error } : original())
)
mockNuxtImport(
  'navigateTo',
  (original) =>
    (...args) =>
      state.app ? state.navigate(...args) : original(...args)
)

describe('application shell navigation', () => {
  beforeEach(() => {
    state.app = {
      $isWebFrontendHostname: true,
      $isApplicationShell: true,
      isHydrating: false,
    }
    state.error = null
    state.navigate.mockReset()
  })
  afterEach(() => {
    state.app = null
    state.error = null
  })

  test('reloads when leaving the shell for a published page', () => {
    applicationShell({
      fullPath: '/builder/published/1/',
      meta: { applicationShell: false },
    })
    expect(state.navigate).toHaveBeenCalledWith('/builder/published/1/', {
      external: true,
    })
  })

  test('reloads when leaving a public runtime for the shell', () => {
    state.app.$isApplicationShell = false
    applicationShell({ fullPath: '/all-workspaces', meta: {} })
    expect(state.navigate).toHaveBeenCalledWith('/all-workspaces', {
      external: true,
    })
  })

  test('loads a fresh authentication entry when navigating from a published runtime to login', () => {
    state.app.$isApplicationShell = false
    applicationShell({
      fullPath: '/login',
      meta: { applicationShell: false, authenticationPage: true },
    })
    expect(state.navigate).toHaveBeenCalledWith('/login', { external: true })
  })

  test('loads a fresh application shell after sign-in', () => {
    state.app.$isApplicationShell = false
    state.app.$isAuthenticationPage = true
    applicationShell({ fullPath: '/all-workspaces', meta: {} })
    expect(state.navigate).toHaveBeenCalledWith('/all-workspaces', {
      external: true,
    })
  })

  test('keeps navigation within the same runtime in the current document', () => {
    applicationShell({ fullPath: '/all-workspaces', meta: {} })
    expect(state.navigate).not.toHaveBeenCalled()
  })

  test('does not reload while hydrating an error route with different metadata', () => {
    state.app.isHydrating = true
    applicationShell({
      fullPath: '/__nuxt_error',
      meta: { applicationShell: false },
    })
    expect(state.navigate).not.toHaveBeenCalled()
  })

  test('does not reload an active error page after hydration', () => {
    state.error = { statusCode: 404 }
    applicationShell({
      fullPath: '/__nuxt_error',
      meta: { applicationShell: false },
    })
    expect(state.navigate).not.toHaveBeenCalled()
  })
})
