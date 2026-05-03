import { describe, expect, test, vi, beforeEach } from 'vitest'
import whiteboardModule from '@baserow/modules/whiteboard/store/whiteboardApplication'
import { TestApp } from '@baserow/test/helpers/testApp'

const mockGetContent = vi.fn()
const mockSaveContent = vi.fn()
const mockRealtimeSend = vi.fn()

vi.mock('@baserow/modules/whiteboard/services/whiteboard', () => {
  return {
    default: () => ({
      getContent: mockGetContent,
      saveContent: mockSaveContent,
    }),
  }
})

describe('whiteboardApplication store', () => {
  let testApp = null
  let store = null

  beforeEach(() => {
    mockGetContent.mockReset()
    mockSaveContent.mockReset()
    mockRealtimeSend.mockReset()
    testApp = new TestApp()
    store = testApp.createStore({
      modules: { whiteboardApplication: whiteboardModule },
    })
    // Stub $realtime on the store's Nuxt app — the broadcastChanges
    // action sends ephemeral collab payloads through the existing WS
    // connection instead of an HTTP request, accessed via
    // `this.app.$realtime`.
    store.app = { ...(store.app || {}), $realtime: { send: mockRealtimeSend } }
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

  test('broadcastChanges sends an inbound WS message wrapped with whiteboard_id', async () => {
    mockGetContent.mockResolvedValue({
      data: { content: { elements: [], appState: {}, files: {} } },
    })
    await store.dispatch('whiteboardApplication/fetchInitial', {
      whiteboardId: 17,
    })

    store.dispatch('whiteboardApplication/broadcastChanges', {
      type: 'scene_update',
      elements: [{ id: 'x' }],
    })
    expect(mockRealtimeSend).toHaveBeenCalledWith({
      type: 'broadcast_whiteboard_changes',
      whiteboard_id: 17,
      payload: { type: 'scene_update', elements: [{ id: 'x' }] },
    })
  })

  test('broadcastChanges is a no-op before the whiteboard id is loaded', () => {
    store.dispatch('whiteboardApplication/broadcastChanges', { type: 'noop' })
    expect(mockRealtimeSend).not.toHaveBeenCalled()
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

  test('setCollaboratorViewport attaches viewport bounds to an existing collaborator', () => {
    store.dispatch('whiteboardApplication/setCollaborator', {
      id: 11,
      username: 'Alice',
      color: '#abc',
    })
    store.dispatch('whiteboardApplication/setCollaboratorViewport', {
      id: 11,
      scrollX: 50,
      scrollY: 60,
      zoom: 2,
      width: 1920,
      height: 1080,
    })
    expect(
      store.getters['whiteboardApplication/getCollaborators'][11].viewport
    ).toEqual({
      scrollX: 50,
      scrollY: 60,
      zoom: 2,
      width: 1920,
      height: 1080,
    })
  })

  test('noteViewportRequest increments the request counter', () => {
    const before =
      store.getters['whiteboardApplication/getViewportRequestSeq']
    store.dispatch('whiteboardApplication/noteViewportRequest')
    store.dispatch('whiteboardApplication/noteViewportRequest')
    const after =
      store.getters['whiteboardApplication/getViewportRequestSeq']
    expect(after).toBe(before + 2)
  })

  test('setCollaboratorViewport is a no-op when collaborator is unknown', () => {
    // Avoid creating a partial entry with no name/colour, which would
    // render as an unnamed avatar in Excalidraw's collaborator strip.
    store.dispatch('whiteboardApplication/setCollaboratorViewport', {
      id: 99,
      scrollX: 0,
      scrollY: 0,
      zoom: 1,
      width: 0,
      height: 0,
    })
    expect(store.getters['whiteboardApplication/getCollaborators']).toEqual({})
  })
})
