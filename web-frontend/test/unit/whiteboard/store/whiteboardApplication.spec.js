import { describe, expect, test, vi, beforeEach } from 'vitest'
import whiteboardModule from '@baserow/modules/whiteboard/store/whiteboardApplication'
import { TestApp } from '@baserow/test/helpers/testApp'

const mockGetContent = vi.fn()
const mockSaveContent = vi.fn()
const mockBroadcastChanges = vi.fn()

vi.mock('@baserow/modules/whiteboard/services/whiteboard', () => {
  return {
    default: () => ({
      getContent: mockGetContent,
      saveContent: mockSaveContent,
      broadcastChanges: mockBroadcastChanges,
    }),
  }
})

describe('whiteboardApplication store', () => {
  let testApp = null
  let store = null

  beforeEach(() => {
    mockGetContent.mockReset()
    mockSaveContent.mockReset()
    mockBroadcastChanges.mockReset()
    testApp = new TestApp()
    store = testApp.createStore({
      modules: { whiteboardApplication: whiteboardModule },
    })
  })

  afterEach(() => {
    testApp.afterEach()
  })

  test('fetchInitial loads content from the API', async () => {
    mockGetContent.mockResolvedValue({
      data: { content: { elements: [{ id: 'a' }], appState: {}, files: {} } },
    })

    await store.dispatch('whiteboardApplication/fetchInitial', {
      whiteboardId: 17,
    })

    expect(mockGetContent).toHaveBeenCalledWith(17)
    expect(store.getters['whiteboardApplication/getWhiteboardId']).toBe(17)
    expect(store.getters['whiteboardApplication/getContent']).toEqual({
      elements: [{ id: 'a' }],
      appState: {},
      files: {},
    })
    expect(store.getters['whiteboardApplication/isLoading']).toBe(false)
  })

  test('saveContent forwards the snapshot to the service', async () => {
    mockGetContent.mockResolvedValue({
      data: { content: { elements: [], appState: {}, files: {} } },
    })
    mockSaveContent.mockResolvedValue({ data: { content: {} } })
    await store.dispatch('whiteboardApplication/fetchInitial', {
      whiteboardId: 17,
    })

    const snapshot = { elements: [{ id: 'b' }], appState: {}, files: {} }
    await store.dispatch('whiteboardApplication/saveContent', snapshot)

    expect(mockSaveContent).toHaveBeenCalledWith(17, snapshot)
  })

  test('broadcastChanges sends payload and never throws on errors', async () => {
    mockGetContent.mockResolvedValue({
      data: { content: { elements: [], appState: {}, files: {} } },
    })
    mockBroadcastChanges.mockRejectedValueOnce(new Error('boom'))
    await store.dispatch('whiteboardApplication/fetchInitial', {
      whiteboardId: 17,
    })

    await expect(
      store.dispatch('whiteboardApplication/broadcastChanges', {
        type: 'scene_update',
      })
    ).resolves.toBeUndefined()
    expect(mockBroadcastChanges).toHaveBeenCalledWith(17, {
      type: 'scene_update',
    })
  })

  test('queue and clear remote updates', () => {
    store.dispatch('whiteboardApplication/queueRemoteUpdate', {
      kind: 'scene',
      elements: [{ id: 'x' }],
      files: {},
    })
    expect(
      store.getters['whiteboardApplication/getPendingRemoteUpdates']
    ).toHaveLength(1)
    store.dispatch('whiteboardApplication/clearRemoteUpdates')
    expect(
      store.getters['whiteboardApplication/getPendingRemoteUpdates']
    ).toHaveLength(0)
  })

  test('setCollaborator and removeCollaborator manage the collaborators map', () => {
    store.dispatch('whiteboardApplication/setCollaborator', {
      id: 11,
      username: 'Alice',
      color: '#abc',
      pointer: { x: 1, y: 2 },
    })
    expect(store.getters['whiteboardApplication/getCollaborators']).toEqual({
      11: { id: 11, username: 'Alice', color: '#abc', pointer: { x: 1, y: 2 } },
    })

    store.dispatch('whiteboardApplication/removeCollaborator', 11)
    expect(store.getters['whiteboardApplication/getCollaborators']).toEqual({})
  })
})
