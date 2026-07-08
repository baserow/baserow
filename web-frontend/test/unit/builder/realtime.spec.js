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

describe('builder realtime workflow_actions_reordered', () => {
  const regularPage = { id: 10, builder_id: builder.id }
  const sharedPage = { id: 99, builder_id: builder.id }

  test('dispatches forceOrder for the reordered page', () => {
    const handlers = getHandlers()
    const store = buildStore({ selectedPage: regularPage, sharedPage })

    handlers.workflow_actions_reordered(
      { store },
      { page_id: regularPage.id, element_id: 5, order: [3, 1, 2] }
    )

    expect(dispatchedWith(store, 'builderWorkflowAction/forceOrder')).toEqual([
      { page: regularPage, order: [3, 1, 2] },
    ])
  })

  test('is a no-op when the page is not loaded', () => {
    const handlers = getHandlers()
    const store = buildStore({ selectedPage: regularPage, sharedPage })

    handlers.workflow_actions_reordered(
      { store },
      { page_id: 12345, order: [3, 1, 2] }
    )

    expect(dispatchedWith(store, 'builderWorkflowAction/forceOrder')).toEqual([])
  })
})

describe('builder realtime integration events', () => {
  const application = { id: 1 }

  const buildAppStore = ({ integration = null } = {}) => ({
    getters: {
      'application/get': (id) =>
        id === application.id ? application : undefined,
      'integration/getIntegrationById': () => integration,
    },
    dispatch: vi.fn(),
  })

  test('integration_created dispatches forceCreate', () => {
    const handlers = getHandlers()
    const store = buildAppStore()
    const integration = { id: 5, application_id: application.id }

    handlers.integration_created({ store }, { integration, before_id: 3 })

    expect(dispatchedWith(store, 'integration/forceCreate')).toEqual([
      { application, integration, beforeId: 3 },
    ])
    // Restoring an integration re-dispatches its data sources so collection
    // elements repopulate.
    expect(
      dispatchedWith(store, 'dataSource/redispatchForIntegration')
    ).toEqual([{ builder: application, integrationId: 5 }])
  })

  test('integration_updated dispatches forceUpdate for a known integration', () => {
    const handlers = getHandlers()
    const existing = { id: 5, application_id: application.id, name: 'Old' }
    const store = buildAppStore({ integration: existing })
    const values = { id: 5, application_id: application.id, name: 'New' }

    handlers.integration_updated({ store }, { integration: values })

    expect(dispatchedWith(store, 'integration/forceUpdate')).toEqual([
      { application, integration: existing, values },
    ])
  })

  test('integration_updated is a no-op when the integration is unknown', () => {
    const handlers = getHandlers()
    const store = buildAppStore({ integration: null })

    handlers.integration_updated(
      { store },
      { integration: { id: 5, application_id: application.id } }
    )

    expect(dispatchedWith(store, 'integration/forceUpdate')).toEqual([])
  })

  test('integration_deleted dispatches forceDelete', () => {
    const handlers = getHandlers()
    const store = buildAppStore()

    handlers.integration_deleted(
      { store },
      { integration_id: 5, application_id: application.id }
    )

    expect(dispatchedWith(store, 'integration/forceDelete')).toEqual([
      { application, integrationId: 5 },
    ])
    // Trashing an integration re-dispatches its data sources so collection
    // elements bound to them reset their content.
    expect(
      dispatchedWith(store, 'dataSource/redispatchForIntegration')
    ).toEqual([{ builder: application, integrationId: 5 }])
  })

  test('integration events are a no-op when the application is not loaded', () => {
    const handlers = getHandlers()
    const store = buildAppStore()

    handlers.integration_created(
      { store },
      { integration: { id: 5, application_id: 999 }, before_id: null }
    )
    handlers.integration_deleted(
      { store },
      { integration_id: 5, application_id: 999 }
    )

    expect(dispatchedWith(store, 'integration/forceCreate')).toEqual([])
    expect(dispatchedWith(store, 'integration/forceDelete')).toEqual([])
  })
})

describe('builder realtime user source events', () => {
  const application = { id: 1 }

  const buildAppStore = ({ userSource = null } = {}) => ({
    getters: {
      'application/get': (id) =>
        id === application.id ? application : undefined,
      'userSource/getUserSourceById': () => userSource,
    },
    dispatch: vi.fn(),
  })

  test('user_source_created dispatches forceCreate', () => {
    const handlers = getHandlers()
    const store = buildAppStore()
    const userSource = { id: 7, application_id: application.id }

    handlers.user_source_created(
      { store },
      { user_source: userSource, before_id: 2 }
    )

    expect(dispatchedWith(store, 'userSource/forceCreate')).toEqual([
      { application, userSource, beforeId: 2 },
    ])
  })

  test('user_source_updated dispatches forceUpdate for a known user source', () => {
    const handlers = getHandlers()
    const existing = { id: 7, application_id: application.id, name: 'Old' }
    const store = buildAppStore({ userSource: existing })
    const values = { id: 7, application_id: application.id, name: 'New' }

    handlers.user_source_updated({ store }, { user_source: values })

    expect(dispatchedWith(store, 'userSource/forceUpdate')).toEqual([
      { application, userSource: existing, values },
    ])
  })

  test('user_source_deleted dispatches forceDelete', () => {
    const handlers = getHandlers()
    const store = buildAppStore()

    handlers.user_source_deleted(
      { store },
      { user_source_id: 7, application_id: application.id }
    )

    expect(dispatchedWith(store, 'userSource/forceDelete')).toEqual([
      { application, userSourceId: 7 },
    ])
  })
})

describe('builder realtime data_source_updated relocation', () => {
  const builderApp = { id: 1 }
  const contentPage = { id: 10, builder_id: builderApp.id }
  const sharedPage = { id: 99, builder_id: builderApp.id }

  const buildStore = (dataSource) => ({
    getters: {
      'page/getSelected': contentPage,
      'application/get': () => builderApp,
      'page/getSharedPage': () => sharedPage,
      'dataSource/getPagesDataSourceById': () => dataSource,
    },
    dispatch: vi.fn(),
  })

  test('relocates the data source when its page changed (un-share via undo)', () => {
    const handlers = getHandlers()
    // The data source currently lives on the shared page in the store...
    const dataSource = { id: 5, page_id: sharedPage.id }
    const store = buildStore(dataSource)

    // ...but the event says it now belongs to the content page.
    handlers.data_source_updated(
      { store },
      { data_source: { id: 5, page_id: contentPage.id, name: 'DS' } }
    )

    expect(dispatchedWith(store, 'dataSource/forcePageMove')).toEqual([
      { pageSource: sharedPage, pageDest: contentPage, dataSourceId: 5 },
    ])
    expect(dispatchedWith(store, 'dataSource/forceUpdate')).toEqual([
      {
        page: contentPage,
        dataSource,
        values: { id: 5, page_id: contentPage.id, name: 'DS' },
      },
    ])
  })

  test('does not relocate when the page is unchanged', () => {
    const handlers = getHandlers()
    const dataSource = { id: 5, page_id: contentPage.id }
    const store = buildStore(dataSource)

    handlers.data_source_updated(
      { store },
      { data_source: { id: 5, page_id: contentPage.id, name: 'DS' } }
    )

    expect(dispatchedWith(store, 'dataSource/forcePageMove')).toEqual([])
    expect(dispatchedWith(store, 'dataSource/forceUpdate')).toEqual([
      {
        page: contentPage,
        dataSource,
        values: { id: 5, page_id: contentPage.id, name: 'DS' },
      },
    ])
  })
})
