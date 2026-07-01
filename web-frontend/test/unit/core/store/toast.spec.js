import { describe, test, expect } from 'vitest'

import {
  state as makeState,
  mutations,
  actions,
} from '@baserow/modules/core/store/toast'

function commitTracker(currentState) {
  return (type, value) => {
    const mutation = mutations[type]
    if (mutation) {
      mutation(currentState, value)
    }
  }
}

describe('toast store — connection state mutual exclusivity', () => {
  test('setFailedConnecting(true) clears reconnecting', () => {
    const s = makeState()
    s.reconnecting = true
    const commit = commitTracker(s)

    actions.setFailedConnecting({ commit }, true)

    expect(s.failedConnecting).toBe(true)
    expect(s.reconnecting).toBe(false)
  })

  test('setReconnecting(true) clears failedConnecting', () => {
    const s = makeState()
    s.failedConnecting = true
    const commit = commitTracker(s)

    actions.setReconnecting({ commit }, true)

    expect(s.reconnecting).toBe(true)
    expect(s.failedConnecting).toBe(false)
  })

  test('setFailedConnecting(false) does not touch reconnecting', () => {
    const s = makeState()
    s.reconnecting = true
    const commit = commitTracker(s)

    actions.setFailedConnecting({ commit }, false)

    expect(s.failedConnecting).toBe(false)
    expect(s.reconnecting).toBe(true)
  })

  test('setReconnecting(false) does not touch failedConnecting', () => {
    const s = makeState()
    s.failedConnecting = true
    const commit = commitTracker(s)

    actions.setReconnecting({ commit }, false)

    expect(s.reconnecting).toBe(false)
    expect(s.failedConnecting).toBe(true)
  })
})

describe('toast store — workspaceOutdated', () => {
  test('setWorkspaceOutdated sets and clears the flag', () => {
    const s = makeState()
    const commit = commitTracker(s)

    actions.setWorkspaceOutdated({ commit }, true)
    expect(s.workspaceOutdated).toBe(true)

    actions.setWorkspaceOutdated({ commit }, false)
    expect(s.workspaceOutdated).toBe(false)
  })
})

describe('toast store — userLoggedOut', () => {
  test('userLoggedOut clears reconnecting, failedConnecting, and workspaceOutdated', () => {
    const s = makeState()
    s.reconnecting = true
    s.failedConnecting = true
    s.workspaceOutdated = true
    s.copying = true
    const commit = commitTracker(s)

    actions.userLoggedOut({ commit })

    expect(s.reconnecting).toBe(false)
    expect(s.failedConnecting).toBe(false)
    expect(s.workspaceOutdated).toBe(false)
    expect(s.copying).toBe(false)
  })
})
