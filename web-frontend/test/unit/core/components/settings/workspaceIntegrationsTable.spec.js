import flushPromises from 'flush-promises'

import WorkspaceIntegrationsTable from '@baserow/modules/core/components/settings/integrations/WorkspaceIntegrationsTable'
import CrudTableSearch from '@baserow/modules/core/components/crudTable/CrudTableSearch'
import { TestApp } from '@baserow/test/helpers/testApp'

const WORKSPACE = { id: 1, name: 'Workspace' }
const DATABASE_ID = 1
const SHARED_ID = 2

const localBaserowIntegration = (values = {}) => ({
  id: 10,
  application_id: SHARED_ID,
  type: 'local_baserow',
  name: 'Shared data',
  authorized_subject: {
    id: 1,
    type: 'auth.User',
    first_name: 'Ada',
    username: 'ada@example.com',
  },
  ...values,
})

const smtpIntegration = (values = {}) => ({
  id: 11,
  application_id: SHARED_ID,
  type: 'smtp',
  name: 'Mail server',
  host: 'smtp.example.com',
  port: 587,
  ...values,
})

const databaseApplication = {
  id: DATABASE_ID,
  type: 'database',
  name: 'Database',
  order: 1,
  workspace: { id: WORKSPACE.id },
  tables: [],
}

const sharedApplication = {
  id: SHARED_ID,
  type: 'shared',
  name: '__shared__',
  order: 0,
  workspace: { id: WORKSPACE.id },
}

// Renders the menus in place, and lets a test see them without positioning.
const contextStub = {
  template: '<div><slot /></div>',
  methods: { show() {}, hide() {}, toggle() {} },
}

describe('WorkspaceIntegrationsTable', () => {
  let testApp = null
  let store = null

  beforeEach(async () => {
    testApp = new TestApp()
    store = testApp.store
    await store.dispatch('application/forceSetAll', {
      applications: [databaseApplication, sharedApplication],
    })
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  const shared = () =>
    store.getters['application/getSharedApplication'](WORKSPACE)

  const mountTable = async (options = {}) => {
    const wrapper = await testApp.mount(WorkspaceIntegrationsTable, {
      props: { workspace: WORKSPACE },
      ...options,
    })
    await flushPromises()
    return wrapper
  }

  const rowNames = (wrapper) =>
    wrapper.findAll('.management-name-field__name').map((name) => name.text())

  test('lists the integrations of the shared application only', async () => {
    testApp.mock
      .onGet(`application/${SHARED_ID}/integrations/`)
      .replyOnce(200, [localBaserowIntegration(), smtpIntegration()])
    await store.dispatch('integration/forceCreate', {
      application: store.getters['application/get'](DATABASE_ID),
      integration: smtpIntegration({
        id: 20,
        application_id: DATABASE_ID,
        name: 'Database mail server',
      }),
    })

    const wrapper = await mountTable()

    expect(rowNames(wrapper)).toEqual(['Shared data', 'Mail server'])
    // A Local Baserow integration says who it runs as in every application.
    expect(wrapper.text()).toContain(
      'localBaserowIntegrationType.localBaserowWorkspaceHint'
    )
  })

  test('fetches the shared application when the store does not have it', async () => {
    // Like a workspace created after the applications were loaded.
    await store.dispatch('application/forceSetAll', {
      applications: [databaseApplication],
    })
    testApp.mock
      .onGet(`/applications/workspace/${WORKSPACE.id}/`)
      .replyOnce(200, [databaseApplication, sharedApplication])
      .onGet(`application/${SHARED_ID}/integrations/`)
      .replyOnce(200, [smtpIntegration()])

    const wrapper = await mountTable()

    expect(shared().id).toBe(SHARED_ID)
    expect(rowNames(wrapper)).toEqual(['Mail server'])
  })

  test('refreshes when a workspace integration changes in the store', async () => {
    testApp.mock
      .onGet(`application/${SHARED_ID}/integrations/`)
      .replyOnce(200, [])
    const wrapper = await mountTable()
    expect(rowNames(wrapper)).toEqual([])

    // What the realtime event of another Admin's new integration does.
    await store.dispatch('integration/forceCreate', {
      application: shared(),
      integration: smtpIntegration(),
    })
    await flushPromises()

    expect(rowNames(wrapper)).toEqual(['Mail server'])
    // The store is read again, the list isn't fetched a second time.
    expect(testApp.mock.history.get).toHaveLength(1)
  })

  test('searches the integrations by name and by type', async () => {
    testApp.mock
      .onGet(`application/${SHARED_ID}/integrations/`)
      .replyOnce(200, [localBaserowIntegration(), smtpIntegration()])
    const wrapper = await mountTable()
    const search = async (term) => {
      wrapper.findComponent(CrudTableSearch).vm.$emit('search-changed', term)
      await flushPromises()
    }

    await search('shared')
    expect(rowNames(wrapper)).toEqual(['Shared data'])

    // The type name, a translation key in tests, has `smtp` in it.
    await search('smtp')
    expect(rowNames(wrapper)).toEqual(['Mail server'])

    await search('')
    expect(rowNames(wrapper)).toEqual(['Shared data', 'Mail server'])
  })

  test('sorts by name from A to Z first, like the paginated tables', async () => {
    testApp.mock
      .onGet(`application/${SHARED_ID}/integrations/`)
      .replyOnce(200, [
        smtpIntegration({ id: 11, name: 'Zeta' }),
        smtpIntegration({ id: 12, name: 'Alpha' }),
      ])
    const wrapper = await mountTable()
    const sortByName = async () => {
      await wrapper.find('.data-table__table-cell-head-link').trigger('click')
      await flushPromises()
    }
    expect(rowNames(wrapper)).toEqual(['Zeta', 'Alpha'])

    await sortByName()
    expect(rowNames(wrapper)).toEqual(['Alpha', 'Zeta'])

    await sortByName()
    expect(rowNames(wrapper)).toEqual(['Zeta', 'Alpha'])
  })

  test.each([
    [['workspace.create_integration'], 1, 3, false, false],
    [['workspace.integration.update'], 0, 4, true, false],
    [['workspace.integration.delete'], 0, 4, false, true],
    [[], 0, 3, false, false],
  ])(
    'shows controls for the workspace integration permissions: %s',
    async (
      permissions,
      createButtonCount,
      columnCount,
      showsEdit,
      showsDelete
    ) => {
      testApp.mock
        .onGet(`application/${SHARED_ID}/integrations/`)
        .replyOnce(200, [smtpIntegration()])
      const hasPermission = (operation) => permissions.includes(operation)

      const wrapper = await mountTable({
        global: {
          mocks: { $hasPermission: hasPermission },
          stubs: { Context: contextStub },
        },
      })

      expect(
        wrapper
          .findAll('button')
          .filter((button) => button.text() === 'workspaceIntegrations.create')
      ).toHaveLength(createButtonCount)
      expect(wrapper.findAll('th.data-table__table-cell--header')).toHaveLength(
        columnCount
      )

      const more = wrapper.find('.data-table__more')
      expect(more.exists()).toBe(showsEdit || showsDelete)
      if (more.exists()) {
        await more.trigger('click')
        await flushPromises()
      }
      expect(wrapper.text().includes('workspaceIntegrations.edit')).toBe(
        showsEdit
      )
      expect(wrapper.text().includes('workspaceIntegrations.delete')).toBe(
        showsDelete
      )
    }
  )

  test('creates an integration of the picked type in the shared application', async () => {
    testApp.mock
      .onGet(`application/${SHARED_ID}/integrations/`)
      .replyOnce(200, [])
    const show = vi.fn()

    const wrapper = await mountTable({
      global: {
        stubs: {
          Context: contextStub,
          IntegrationCreateEditModal: {
            name: 'IntegrationCreateEditModal',
            // `create` is a Boolean like on the real modal, so the bare
            // attribute is cast to true instead of passed as ''.
            props: {
              application: Object,
              integrationType: Object,
              integration: Object,
              create: Boolean,
            },
            template: '<div />',
            methods: { show },
          },
        },
      },
    })
    await wrapper
      .findAll('button')
      .find((button) => button.text() === 'workspaceIntegrations.create')
      .trigger('click')
    await wrapper
      .findAll('.context__menu-item-link')
      .find((link) => link.text() === 'integrationType.smtp')
      .trigger('click')
    await flushPromises()

    const modal = wrapper.findComponent({ name: 'IntegrationCreateEditModal' })
    expect(modal.props('application')).toBe(shared())
    expect(modal.props('integrationType').type).toBe('smtp')
    expect(modal.props('create')).toBe(true)
    expect(show).toHaveBeenCalled()
  })

  test('deletes an integration once the deletion is confirmed', async () => {
    testApp.mock
      .onGet(`application/${SHARED_ID}/integrations/`)
      .replyOnce(200, [smtpIntegration()])
      .onDelete('integration/11/')
      .replyOnce(204)
    const show = vi.fn()
    const hide = vi.fn()

    const wrapper = await mountTable({
      global: {
        mocks: {
          $t: (key, params) => (params?.name ? `${key} ${params.name}` : key),
        },
        stubs: {
          Context: contextStub,
          ConfirmModal: {
            name: 'ConfirmModal',
            props: ['message'],
            emits: ['confirm'],
            template: '<div class="confirm-modal">{{ message }}</div>',
            methods: { show, hide },
          },
        },
      },
    })
    await wrapper.find('.data-table__more').trigger('click')
    await flushPromises()
    await wrapper
      .findAll('.context__menu-item-link')
      .find((link) => link.text() === 'workspaceIntegrations.delete')
      .trigger('click')
    await flushPromises()

    // Nothing is deleted before the confirmation.
    expect(show).toHaveBeenCalled()
    expect(testApp.mock.history.delete).toHaveLength(0)
    expect(wrapper.find('.confirm-modal').text()).toBe(
      'workspaceIntegrations.deleteMessage Mail server'
    )

    wrapper.findComponent({ name: 'ConfirmModal' }).vm.$emit('confirm')
    await flushPromises()

    expect(testApp.mock.history.delete).toHaveLength(1)
    expect(store.getters['integration/getIntegrations'](shared())).toEqual([])
    expect(hide).toHaveBeenCalled()
    expect(rowNames(wrapper)).toEqual([])
  })
})
