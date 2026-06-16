import { registerRealtimeEvents } from '@baserow/modules/builder/realtime'

// Capture the handlers registered by registerRealtimeEvents so we can invoke
// individual realtime events directly.
const getHandlers = () => {
  const handlers = {}
  registerRealtimeEvents({
    registerEvent: (name, fn) => {
      handlers[name] = fn
    },
  })
  return handlers
}

const builder = { id: 1 }

// selectedPage is the page the client is currently viewing; sharedPage always
// exists in the store. getPageContext resolves page ids against these two.
const buildStore = ({ selectedPage, sharedPage }) => ({
  getters: {
    'page/getSelected': selectedPage,
    'application/get': () => builder,
    'page/getSharedPage': () => sharedPage,
  },
  dispatch: vi.fn(),
})

const dispatchedWith = (store, action) =>
  store.dispatch.mock.calls
    .filter(([name]) => name === action)
    .map(([, p]) => p)

describe('builder realtime element_moved', () => {
  const regularPage = { id: 10, builder_id: builder.id }
  const sharedPage = { id: 99, builder_id: builder.id }

  test('same-page move only updates the graph', () => {
    const handlers = getHandlers()
    const store = buildStore({ selectedPage: regularPage, sharedPage })

    handlers.element_moved(
      { store },
      { page_id: regularPage.id, graph: { 0: 1 } }
    )

    expect(dispatchedWith(store, 'page/forceUpdate')).toEqual([
      { page: regularPage, values: { graph: { 0: 1 } } },
    ])
    expect(dispatchedWith(store, 'element/refreshCachedValues')).toEqual([
      { page: regularPage },
    ])
    // No relocation for a same-page move.
    expect(dispatchedWith(store, 'element/forceDelete')).toEqual([])
    expect(dispatchedWith(store, 'element/forceCreate')).toEqual([])
  })

  test('cross-page move (viewing the source page) relocates the element', () => {
    const handlers = getHandlers()
    const store = buildStore({ selectedPage: regularPage, sharedPage })

    const element = { id: 5, page_id: sharedPage.id, type: 'heading' }
    handlers.element_moved(
      { store },
      {
        source_page_id: regularPage.id,
        source_graph: { source: true },
        page_id: sharedPage.id,
        graph: { target: true },
        elements: [element],
      }
    )

    // Removed from the source page, source graph refreshed.
    expect(dispatchedWith(store, 'element/forceDelete')).toEqual([
      { builder, page: regularPage, elementId: 5 },
    ])
    // Added to the target page, both graphs applied.
    expect(dispatchedWith(store, 'element/forceCreate')).toEqual([
      { page: sharedPage, element },
    ])
    expect(dispatchedWith(store, 'page/forceUpdate')).toEqual([
      { page: regularPage, values: { graph: { source: true } } },
      { page: sharedPage, values: { graph: { target: true } } },
    ])
  })

  test('cross-page move relocates the workflow actions too', () => {
    const handlers = getHandlers()
    const store = buildStore({ selectedPage: regularPage, sharedPage })

    const element = { id: 5, page_id: sharedPage.id, type: 'button' }
    const workflowAction = { id: 9, element_id: 5 }
    handlers.element_moved(
      { store },
      {
        source_page_id: regularPage.id,
        source_graph: { source: true },
        page_id: sharedPage.id,
        graph: { target: true },
        elements: [element],
        workflow_actions: [workflowAction],
      }
    )

    // Removed from the source page's workflow action store...
    expect(dispatchedWith(store, 'builderWorkflowAction/forceDelete')).toEqual([
      { page: regularPage, workflowActionId: 9 },
    ])
    // ...and re-created on the target page.
    expect(dispatchedWith(store, 'builderWorkflowAction/forceCreate')).toEqual([
      { page: sharedPage, workflowAction },
    ])
  })

  test('delete removes the records and applies the relinked graph', () => {
    const handlers = getHandlers()
    const store = buildStore({ selectedPage: regularPage, sharedPage })

    // Delete a container that had a sibling; the relinked graph keeps the sibling.
    handlers.element_deleted(
      { store },
      {
        element_id: 2,
        element_ids: [2],
        page_id: regularPage.id,
        graph: { relinked: true },
      }
    )

    expect(dispatchedWith(store, 'element/forceDelete')).toEqual([
      { builder, page: regularPage, elementId: 2 },
    ])
    expect(dispatchedWith(store, 'page/forceUpdate')).toEqual([
      { page: regularPage, values: { graph: { relinked: true } } },
    ])
  })

  test('delete removes a whole container subtree (all element_ids)', () => {
    const handlers = getHandlers()
    const store = buildStore({ selectedPage: regularPage, sharedPage })

    handlers.element_deleted(
      { store },
      {
        element_id: 2,
        element_ids: [2, 3, 4],
        page_id: regularPage.id,
        graph: { relinked: true },
      }
    )

    expect(dispatchedWith(store, 'element/forceDelete')).toEqual([
      { builder, page: regularPage, elementId: 2 },
      { builder, page: regularPage, elementId: 3 },
      { builder, page: regularPage, elementId: 4 },
    ])
  })

  test('cross-page move (viewing an unrelated page) still adds to the target', () => {
    const handlers = getHandlers()
    // The client is viewing a different page; the source page isn't loaded.
    const otherPage = { id: 20, builder_id: builder.id }
    const store = buildStore({ selectedPage: otherPage, sharedPage })

    const element = { id: 5, page_id: sharedPage.id, type: 'heading' }
    handlers.element_moved(
      { store },
      {
        source_page_id: regularPage.id,
        source_graph: { source: true },
        page_id: sharedPage.id,
        graph: { target: true },
        elements: [element],
      }
    )

    // Source page not loaded: nothing removed.
    expect(dispatchedWith(store, 'element/forceDelete')).toEqual([])
    // Target (shared) page still receives the element.
    expect(dispatchedWith(store, 'element/forceCreate')).toEqual([
      { page: sharedPage, element },
    ])
    expect(dispatchedWith(store, 'page/forceUpdate')).toEqual([
      { page: sharedPage, values: { graph: { target: true } } },
    ])
  })
})
