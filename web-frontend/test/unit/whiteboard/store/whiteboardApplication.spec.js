import whiteboardApplicationStore from '@baserow/modules/whiteboard/store/whiteboardApplication'
import { TestApp } from '@baserow/test/helpers/testApp'
import { expect, test, vi } from 'vitest'

describe('Whiteboard application store', () => {
  let testApp = null
  let store = null

  beforeEach(() => {
    testApp = new TestApp()
    store = testApp.createStore({
      modules: {
        whiteboardApplication: whiteboardApplicationStore,
      },
    })
  })

  afterEach(() => {
    testApp.afterEach()
  })

  test('initial state is correct', () => {
    expect(store.getters['whiteboardApplication/getWhiteboardId']).toBe(null)
    expect(store.getters['whiteboardApplication/isLoading']).toBe(false)
    expect(store.getters['whiteboardApplication/getContent']).toEqual({})
    expect(
      store.getters['whiteboardApplication/getPendingRemoteChanges']
    ).toEqual([])
  })

  test('setLoading sets loading state', async () => {
    await store.dispatch('whiteboardApplication/setLoading', true)
    expect(store.getters['whiteboardApplication/isLoading']).toBe(true)

    await store.dispatch('whiteboardApplication/setLoading', false)
    expect(store.getters['whiteboardApplication/isLoading']).toBe(false)
  })

  test('reset clears all state', async () => {
    store.commit('whiteboardApplication/SET_WHITEBOARD_ID', 42)
    store.commit('whiteboardApplication/SET_CONTENT', { test: true })
    store.commit('whiteboardApplication/SET_LOADING', true)

    await store.dispatch('whiteboardApplication/reset')

    expect(store.getters['whiteboardApplication/getWhiteboardId']).toBe(null)
    expect(store.getters['whiteboardApplication/isLoading']).toBe(false)
    expect(store.getters['whiteboardApplication/getContent']).toEqual({})
  })

  test('applyRemoteChanges pushes to pending changes', async () => {
    const changes = {
      added: { 'shape:1': { id: 'shape:1' } },
      updated: {},
      removed: {},
    }

    await store.dispatch('whiteboardApplication/applyRemoteChanges', changes)

    const pending =
      store.getters['whiteboardApplication/getPendingRemoteChanges']
    expect(pending).toHaveLength(1)
    expect(pending[0]).toEqual(changes)
  })

  test('clearRemoteChanges empties the pending queue', async () => {
    await store.dispatch('whiteboardApplication/applyRemoteChanges', {
      added: {},
    })
    await store.dispatch('whiteboardApplication/applyRemoteChanges', {
      added: {},
    })

    expect(
      store.getters['whiteboardApplication/getPendingRemoteChanges']
    ).toHaveLength(2)

    await store.dispatch('whiteboardApplication/clearRemoteChanges')

    expect(
      store.getters['whiteboardApplication/getPendingRemoteChanges']
    ).toHaveLength(0)
  })

  test('updateContent sets content', async () => {
    const content = { store: { shapes: [] } }
    await store.dispatch('whiteboardApplication/updateContent', content)

    expect(store.getters['whiteboardApplication/getContent']).toEqual(content)
  })
})
