import { describe, expect, test, vi, beforeEach, afterEach } from 'vitest'
import whiteboardCommentsModule from '@baserow/modules/whiteboard/store/whiteboardComments'
import { TestApp } from '@baserow/test/helpers/testApp'

const mockListComments = vi.fn()
const mockCreateComment = vi.fn()
const mockUpdateComment = vi.fn()
const mockDeleteComment = vi.fn()
const mockResolveComment = vi.fn()

vi.mock('@baserow/modules/whiteboard/services/whiteboardComment', () => {
  return {
    default: () => ({
      listComments: mockListComments,
      createComment: mockCreateComment,
      updateComment: mockUpdateComment,
      deleteComment: mockDeleteComment,
      resolveComment: mockResolveComment,
    }),
  }
})

const _doc = (text = 'hi') => ({
  type: 'doc',
  content: [{ type: 'paragraph', content: [{ type: 'text', text }] }],
})

describe('whiteboardComments store', () => {
  let testApp = null
  let store = null

  beforeEach(() => {
    mockListComments.mockReset()
    mockCreateComment.mockReset()
    mockUpdateComment.mockReset()
    mockDeleteComment.mockReset()
    mockResolveComment.mockReset()
    testApp = new TestApp()
    store = testApp.createStore({
      modules: { whiteboardComments: whiteboardCommentsModule },
    })
  })

  afterEach(() => {
    testApp.afterEach()
  })

  test('fetchAll loads the comment list', async () => {
    mockListComments.mockResolvedValue({
      data: [
        { id: 1, parent_comment_id: null, message: _doc(), resolved: false },
        { id: 2, parent_comment_id: 1, message: _doc(), resolved: false },
      ],
    })
    await store.dispatch('whiteboardComments/fetchAll', { whiteboardId: 7 })
    expect(mockListComments).toHaveBeenCalledWith(7)
    expect(store.getters['whiteboardComments/getComments']).toHaveLength(2)
  })

  test('getThreads always hides resolved threads', () => {
    store.commit('whiteboardComments/SET_COMMENTS', [
      { id: 1, parent_comment_id: null, resolved: false },
      { id: 2, parent_comment_id: null, resolved: true },
    ])
    expect(store.getters['whiteboardComments/getThreads']).toHaveLength(1)
    expect(store.getters['whiteboardComments/getThreads'][0].id).toBe(1)
  })

  test('getThreads attaches replies to their thread root', () => {
    store.commit('whiteboardComments/SET_COMMENTS', [
      {
        id: 10,
        parent_comment_id: null,
        resolved: false,
        created_on: '2026-01-01',
      },
      {
        id: 11,
        parent_comment_id: 10,
        resolved: false,
        created_on: '2026-01-02',
      },
      {
        id: 12,
        parent_comment_id: 10,
        resolved: false,
        created_on: '2026-01-03',
      },
    ])
    const threads = store.getters['whiteboardComments/getThreads']
    expect(threads).toHaveLength(1)
    expect(threads[0].replies.map((r) => r.id)).toEqual([11, 12])
  })

  test('postDraftComment toggles posting flag and upserts on success', async () => {
    store.commit('whiteboardComments/SET_DRAFT_PIN', { x: 5, y: 6 })
    mockCreateComment.mockResolvedValue({
      data: {
        id: 99,
        parent_comment_id: null,
        message: _doc(),
        resolved: false,
        x: 5,
        y: 6,
      },
    })
    const promise = store.dispatch('whiteboardComments/postDraftComment', {
      whiteboardId: 7,
      message: _doc(),
    })
    expect(store.getters['whiteboardComments/isPostingDraft']).toBe(true)
    await promise
    expect(store.getters['whiteboardComments/isPostingDraft']).toBe(false)
    expect(store.getters['whiteboardComments/getComments']).toEqual([
      expect.objectContaining({ id: 99, x: 5, y: 6 }),
    ])
    expect(store.getters['whiteboardComments/getDraftPin']).toBeNull()
  })

  test('handleRemoteCreated upserts idempotently (duplicate id replaces)', async () => {
    store.commit('whiteboardComments/SET_COMMENTS', [
      { id: 1, parent_comment_id: null, message: _doc('old') },
    ])
    await store.dispatch('whiteboardComments/handleRemoteCreated', {
      comment: { id: 1, parent_comment_id: null, message: _doc('new') },
    })
    const comments = store.getters['whiteboardComments/getComments']
    expect(comments).toHaveLength(1)
    expect(comments[0].message.content[0].content[0].text).toBe('new')
  })

  test('handleRemoteDeleted cascades to replies and clears openThread', async () => {
    store.commit('whiteboardComments/SET_COMMENTS', [
      { id: 1, parent_comment_id: null },
      { id: 2, parent_comment_id: 1 },
      { id: 3, parent_comment_id: null },
    ])
    store.commit('whiteboardComments/SET_OPEN_THREAD_ID', 1)
    await store.dispatch('whiteboardComments/handleRemoteDeleted', {
      commentId: 1,
    })
    expect(store.getters['whiteboardComments/getComments']).toEqual([
      expect.objectContaining({ id: 3 }),
    ])
    expect(store.getters['whiteboardComments/getOpenThreadId']).toBeNull()
  })

  test('updateComment sets and clears loadingByCommentId', async () => {
    store.commit('whiteboardComments/SET_COMMENTS', [
      { id: 5, parent_comment_id: null, message: _doc('a') },
    ])
    mockUpdateComment.mockResolvedValue({
      data: { id: 5, parent_comment_id: null, message: _doc('b') },
    })
    const promise = store.dispatch('whiteboardComments/updateComment', {
      commentId: 5,
      message: _doc('b'),
    })
    expect(store.getters['whiteboardComments/getCommentLoadingState'](5)).toBe(
      'updating'
    )
    await promise
    expect(
      store.getters['whiteboardComments/getCommentLoadingState'](5)
    ).toBeNull()
  })

  test('setResolved updates the comment via the resolve endpoint', async () => {
    store.commit('whiteboardComments/SET_COMMENTS', [
      { id: 1, parent_comment_id: null, resolved: false },
    ])
    mockResolveComment.mockResolvedValue({
      data: { id: 1, parent_comment_id: null, resolved: true },
    })
    await store.dispatch('whiteboardComments/setResolved', {
      commentId: 1,
      resolved: true,
    })
    expect(mockResolveComment).toHaveBeenCalledWith(1, true)
    expect(store.getters['whiteboardComments/getComments'][0].resolved).toBe(
      true
    )
  })
})
