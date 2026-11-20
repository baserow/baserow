import { registerRealtimeEvents } from '@baserow/modules/builder/realtime'
import { TestApp } from '@baserow/test/helpers/testApp'

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
      { page: regularPage, order: [3, 1, 2], elementId: 5 },
    ])
  })

  test('is a no-op when the page is not loaded', () => {
    const handlers = getHandlers()
    const store = buildStore({ selectedPage: regularPage, sharedPage })

    handlers.workflow_actions_reordered(
      { store },
      { page_id: 12345, order: [3, 1, 2] }
    )

    expect(dispatchedWith(store, 'builderWorkflowAction/forceOrder')).toEqual(
      []
    )
  })
})

describe('builder realtime integration events', () => {
  const application = { id: 1, workspace: { id: 2 } }

  const buildAppStore = ({ integration = null } = {}) => ({
    getters: {
      'application/get': (id) =>
        id === application.id ? application : undefined,
      'application/getAllOfWorkspace': () => [application],
      'application/getSharedApplication': () => undefined,
      'integration/getIntegrations': (app) =>
        app === application && integration ? [integration] : [],
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
    // It's in the event's application already.
    expect(dispatchedWith(store, 'integration/forceMoveToApplication')).toEqual(
      []
    )
  })

  test('integration_updated is a no-op when the integration is unknown', () => {
    const handlers = getHandlers()
    const store = buildAppStore({ integration: null })

    handlers.integration_updated(
      { store },
      { integration: { id: 5, application_id: application.id } }
    )

    expect(dispatchedWith(store, 'integration/forceUpdate')).toEqual([])
    expect(dispatchedWith(store, 'integration/forceCreate')).toEqual([])
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

describe('builder realtime identity events', () => {
  const matchingIntegration = {
    id: 5,
    type: 'local_baserow',
    authorized_subject: { id: 10, type: 'auth.User' },
  }
  const builder = {
    id: 1,
    type: 'builder',
    workspace: { id: 2 },
    integrations: [matchingIntegration],
  }

  const buildAppStore = ({ sharedApplication, selectedPage = null } = {}) => ({
    getters: {
      'application/get': (id) => (id === builder.id ? builder : undefined),
      'application/getSharedApplication': (workspace) =>
        workspace.id === sharedApplication?.workspace.id
          ? sharedApplication
          : undefined,
      'page/getSelected': selectedPage,
      'application/getAll': [
        builder,
        {
          id: 2,
          type: 'builder',
          workspace: { id: 3 },
          integrations: [matchingIntegration],
        },
        {
          id: 3,
          type: 'automation',
          workspace: { id: 2 },
          integrations: [matchingIntegration],
        },
        {
          id: 4,
          type: 'builder',
          workspace: { id: 2 },
          integrations: [
            {
              ...matchingIntegration,
              authorized_subject: { id: 11, type: 'auth.User' },
            },
          ],
        },
      ],
    },
    dispatch: vi.fn(),
  })

  test.each([
    ['identity_created', { workspace_id: 2, identity: { id: 10 } }],
    ['identity_deleted', { workspace_id: 2, identity_id: 10 }],
  ])(
    '%s re-dispatches data sources using the authorized identity',
    (event, data) => {
      const handlers = getHandlers()
      const store = buildAppStore()

      handlers[event]({ store }, data)

      expect(
        dispatchedWith(store, 'dataSource/redispatchForIntegration')
      ).toEqual([{ builder, integrationId: matchingIntegration.id }])
    }
  )

  test('a workspace integration authorized as the identity re-dispatches the open builder', () => {
    const handlers = getHandlers()
    const workspaceIntegration = { ...matchingIntegration, id: 6 }
    const store = buildAppStore({
      sharedApplication: {
        id: 99,
        type: 'shared',
        workspace: { id: 2 },
        integrations: [workspaceIntegration],
      },
      selectedPage: { id: 10, builder_id: builder.id },
    })

    handlers.identity_deleted({ store }, { workspace_id: 2, identity_id: 10 })

    expect(
      dispatchedWith(store, 'dataSource/redispatchForIntegration')
    ).toEqual([
      { builder, integrationId: matchingIntegration.id },
      { builder, integrationId: workspaceIntegration.id },
    ])
  })
})

describe('builder realtime workspace integration events', () => {
  const sharedApplication = { id: 99, type: 'shared', workspace: { id: 2 } }
  const builder = { id: 1, type: 'builder', workspace: { id: 2 } }
  const otherWorkspaceBuilder = { id: 3, type: 'builder', workspace: { id: 4 } }
  const applications = [sharedApplication, builder, otherWorkspaceBuilder]

  const buildAppStore = ({ selectedPage }) => ({
    getters: {
      'application/get': (id) => applications.find((app) => app.id === id),
      'page/getSelected': selectedPage,
    },
    dispatch: vi.fn(),
  })

  const restore = (handlers, store) =>
    handlers.integration_created(
      { store },
      { integration: { id: 5, application_id: sharedApplication.id } }
    )
  const trash = (handlers, store) =>
    handlers.integration_deleted(
      { store },
      { integration_id: 5, application_id: sharedApplication.id }
    )

  test.each([
    ['restored', restore],
    ['trashed', trash],
  ])(
    'a %s one re-dispatches the data sources of the open builder',
    (_, event) => {
      const handlers = getHandlers()
      const store = buildAppStore({
        selectedPage: { id: 10, builder_id: builder.id },
      })

      event(handlers, store)

      expect(
        dispatchedWith(store, 'dataSource/redispatchForIntegration')
      ).toEqual([{ builder, integrationId: 5 }])
    }
  )

  test.each([
    ['restored', restore],
    ['trashed', trash],
  ])(
    'a %s one re-dispatches nothing when the open builder is of another workspace',
    (_, event) => {
      const handlers = getHandlers()
      const store = buildAppStore({
        selectedPage: { id: 10, builder_id: otherWorkspaceBuilder.id },
      })

      event(handlers, store)

      expect(
        dispatchedWith(store, 'dataSource/redispatchForIntegration')
      ).toEqual([])
    }
  )

  test('a trashed one re-dispatches nothing when no builder is open', () => {
    const handlers = getHandlers()
    const store = buildAppStore({ selectedPage: null })

    trash(handlers, store)

    expect(dispatchedWith(store, 'integration/forceDelete')).toEqual([
      { application: sharedApplication, integrationId: 5 },
    ])
    expect(
      dispatchedWith(store, 'dataSource/redispatchForIntegration')
    ).toEqual([])
  })
})

describe('builder realtime integration promotion', () => {
  const WORKSPACE_ID = 1
  const SHARED_ID = 99
  const database = (id) => ({
    id,
    name: `Database ${id}`,
    type: 'database',
    workspace: { id: WORKSPACE_ID },
    tables: [],
  })
  const integration = (id, applicationId, name) => ({
    id,
    application_id: applicationId,
    type: 'smtp',
    name,
    order: `${id}`,
  })

  let testApp = null
  let store = null

  beforeEach(async () => {
    testApp = new TestApp()
    store = testApp.store
    await store.dispatch('workspace/forceCreate', {
      id: WORKSPACE_ID,
      name: 'Acme',
    })
    await store.dispatch('application/forceCreate', {
      id: SHARED_ID,
      name: '__shared__',
      type: 'shared',
      order: 0,
      workspace: { id: WORKSPACE_ID },
    })
    await store.dispatch('application/forceCreate', database(100))
    await store.dispatch('application/forceCreate', database(101))
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  const get = (id) => store.getters['application/get'](id)
  const names = (integrations) => integrations.map(({ name }) => name)
  const own = (id) =>
    names(store.getters['integration/getIntegrations'](get(id)))
  const usable = (id) =>
    names(store.getters['integration/getUsableIntegrations'](get(id)))
  const generation = (id) => store.getters['integration/getGeneration'](get(id))
  const add = (applicationId, value) =>
    store.dispatch('integration/forceCreate', {
      application: get(applicationId),
      integration: value,
    })
  const updated = (value) =>
    getHandlers().integration_updated({ store }, { integration: value })

  test('a promotion moves the integration to the shared application, last', async () => {
    await add(SHARED_ID, integration(1, SHARED_ID, 'Team'))
    await add(100, integration(5, 100, 'Mail'))
    const before = [generation(100), generation(SHARED_ID)]

    updated(integration(5, SHARED_ID, 'Mail for everyone'))

    expect(own(100)).toEqual([])
    expect(own(SHARED_ID)).toEqual(['Team', 'Mail for everyone'])
    // Listed once, among the workspace ones, by every application.
    expect(usable(100)).toEqual(['Team', 'Mail for everyone'])
    expect(usable(101)).toEqual(['Team', 'Mail for everyone'])
    expect(
      store.getters['integration/getIntegrationById'](get(100), 5)
    ).toMatchObject({ application_id: SHARED_ID })
    // Both lists changed, so the settings pages listing them refresh.
    expect(generation(100)).toBeGreaterThan(before[0])
    expect(generation(SHARED_ID)).toBeGreaterThan(before[1])
  })

  test('undoing a promotion moves the integration back to its application', async () => {
    await add(100, integration(2, 100, 'Own'))
    await add(SHARED_ID, integration(5, SHARED_ID, 'Mail'))

    updated(integration(5, 100, 'Mail'))

    expect(own(SHARED_ID)).toEqual([])
    expect(own(100)).toEqual(['Own', 'Mail'])
    expect(usable(101)).toEqual([])
  })

  test('a promotion from an application not loaded here adds the integration', async () => {
    await add(SHARED_ID, integration(1, SHARED_ID, 'Team'))

    updated(integration(5, SHARED_ID, 'Mail'))

    expect(own(SHARED_ID)).toEqual(['Team', 'Mail'])
    expect(usable(101)).toEqual(['Team', 'Mail'])
  })

  test('an update of a workspace integration keeps it in place', async () => {
    await add(SHARED_ID, integration(1, SHARED_ID, 'Team'))
    await add(SHARED_ID, integration(5, SHARED_ID, 'Mail'))

    updated(integration(1, SHARED_ID, 'Renamed'))

    expect(own(SHARED_ID)).toEqual(['Renamed', 'Mail'])
    expect(usable(100)).toEqual(['Renamed', 'Mail'])
  })

  test('undoing a promotion to an application not loaded here takes it out of the workspace', async () => {
    await add(SHARED_ID, integration(1, SHARED_ID, 'Team'))
    await add(SHARED_ID, integration(5, SHARED_ID, 'Mail'))
    const before = generation(SHARED_ID)

    // Like a builder of another application: 300 isn't in this store.
    updated(integration(5, 300, 'Mail'))

    expect(own(SHARED_ID)).toEqual(['Team'])
    expect(usable(100)).toEqual(['Team'])
    // So a settings page listing the workspace ones refreshes.
    expect(generation(SHARED_ID)).toBeGreaterThan(before)
  })

  test('an update of an integration this store holds nowhere is ignored', async () => {
    await add(SHARED_ID, integration(1, SHARED_ID, 'Team'))

    updated(integration(5, 300, 'Mail'))

    expect(own(SHARED_ID)).toEqual(['Team'])
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

  const elementsByPage = {
    [contentPage.id]: [{ id: 1, page_id: contentPage.id }],
    [sharedPage.id]: [{ id: 2, page_id: sharedPage.id }],
  }

  const buildStore = (dataSource) => ({
    getters: {
      'page/getSelected': contentPage,
      'application/get': () => builderApp,
      'page/getSharedPage': () => sharedPage,
      'dataSource/getPagesDataSourceById': () => dataSource,
      'element/getElementsOrdered': (page) => elementsByPage[page.id],
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

  test('re-dispatches the collection elements of the updated data source', () => {
    const handlers = getHandlers()
    const dataSource = { id: 5, page_id: contentPage.id }
    const store = buildStore(dataSource)

    handlers.data_source_updated(
      { store },
      { data_source: { id: 5, page_id: contentPage.id, filters: [] } }
    )

    expect(dispatchedWith(store, 'element/emitElementEvent')).toEqual([
      {
        event: 'DATA_SOURCE_AFTER_UPDATE',
        elements: [
          ...elementsByPage[contentPage.id],
          ...elementsByPage[sharedPage.id],
        ],
        dataSourceId: 5,
        builder: builderApp,
      },
    ])
  })
})
