import flushPromises from 'flush-promises'

import IntegrationSettings from '@baserow/modules/builder/components/settings/IntegrationSettings'
import Modal from '@baserow/modules/core/components/Modal'
import { TestApp } from '@baserow/test/helpers/testApp'

const WORKSPACE = { id: 1, name: 'Acme' }
const BUILDER_ID = 10
const SHARED_ID = 20

const builderApplication = {
  id: BUILDER_ID,
  type: 'builder',
  name: 'Portal',
  order: 1,
  workspace: { id: WORKSPACE.id, name: WORKSPACE.name },
  pages: [],
}

const sharedApplication = {
  id: SHARED_ID,
  type: 'shared',
  name: '__shared__',
  order: 0,
  workspace: { id: WORKSPACE.id, name: WORKSPACE.name },
}

const smtpIntegration = {
  id: 11,
  application_id: BUILDER_ID,
  type: 'smtp',
  name: 'Mail server',
  order: '1',
  host: 'smtp.example.com',
  port: 587,
}

const workspaceSmtpIntegration = {
  ...smtpIntegration,
  id: 21,
  application_id: SHARED_ID,
  name: 'Team mail',
}

// Renders the row menu in place, and lets a test see it without positioning.
const contextStub = {
  template: '<div><slot /></div>',
  methods: { show() {}, hide() {}, toggle() {} },
}

describe('Builder IntegrationSettings', () => {
  let testApp = null
  let store = null

  beforeEach(async () => {
    testApp = new TestApp()
    store = testApp.store
    await store.dispatch('workspace/forceCreate', { ...WORKSPACE })
    await store.dispatch('application/forceSetAll', {
      applications: [builderApplication, sharedApplication],
    })
  })

  afterEach(async () => {
    vi.useRealTimers()
    await testApp.afterEach()
  })

  const menuButtons = (wrapper) =>
    wrapper.findAll('.workspace-integrations-table__more')
  const openMenu = async (wrapper) => {
    await menuButtons(wrapper)[0].trigger('click')
    await flushPromises()
  }
  const menuItem = (wrapper, label) =>
    wrapper
      .findAll('.context__menu-item-link')
      .find((link) => link.text() === label)

  const mountSettings = async ({
    permissions,
    show = () => {},
    workspaceIntegrations = [],
    inModal = false,
  }) => {
    testApp.mock
      .onGet(`application/${BUILDER_ID}/integrations/`)
      .replyOnce(200, [smtpIntegration])
    testApp.mock
      .onGet(`application/${BUILDER_ID}/workspace-integrations/`)
      .replyOnce(200, {
        shared_application: sharedApplication,
        integration_types: ['local_baserow', 'smtp'],
        integrations: workspaceIntegrations,
      })
    const component = inModal
      ? {
          components: { IntegrationSettings, Modal },
          props: ['builder'],
          template: `<div>
            <button @click="$refs.modal.show()">Open settings</button>
            <Modal ref="modal"><IntegrationSettings :builder="builder" /></Modal>
          </div>`,
        }
      : IntegrationSettings
    testApp.mock
      .onGet(`application/${SHARED_ID}/integrations/`)
      .reply(200, workspaceIntegrations)
    const wrapper = await testApp.mount(component, {
      props: { builder: store.getters['application/get'](BUILDER_ID) },
      global: {
        mocks: {
          $hasPermission: (operation) => permissions.includes(operation),
        },
        stubs: {
          Context: contextStub,
          NuxtLink: {
            name: 'NuxtLink',
            props: ['to'],
            template: '<a><slot /></a>',
          },
          PromoteIntegrationModal: {
            name: 'PromoteIntegrationModal',
            props: ['application', 'integration'],
            template: '<div />',
            methods: { show },
          },
        },
      },
    })
    if (inModal) {
      await wrapper.get('button').trigger('click')
    }
    await flushPromises()
    return wrapper
  }

  test.each([
    [['workspace.create_integration'], true],
    [[], false],
  ])(
    'offers promotion to users who can create workspace integrations: %s',
    async (permissions, offered) => {
      const wrapper = await mountSettings({ permissions })
      await openMenu(wrapper)

      expect(!!menuItem(wrapper, 'workspaceIntegrations.edit')).toBe(true)
      expect(!!menuItem(wrapper, 'promoteIntegration.action')).toBe(offered)
      expect(!!menuItem(wrapper, 'workspaceIntegrations.delete')).toBe(true)
      expect(
        wrapper.findComponent({ name: 'PromoteIntegrationModal' }).exists()
      ).toBe(offered)
    }
  )

  test('asks to confirm the promotion of the integration picked', async () => {
    const show = vi.fn()
    const wrapper = await mountSettings({
      permissions: ['workspace.create_integration'],
      show,
    })

    await openMenu(wrapper)
    await menuItem(wrapper, 'promoteIntegration.action').trigger('click')
    await flushPromises()

    const modal = wrapper.findComponent({ name: 'PromoteIntegrationModal' })
    expect(modal.props('application').id).toBe(BUILDER_ID)
    expect(modal.props('integration')).toMatchObject({ id: 11 })
    expect(show).toHaveBeenCalled()
    // Nothing moves before the confirmation.
    expect(testApp.mock.history.patch).toHaveLength(0)
  })

  const sectionTitles = (wrapper) =>
    wrapper
      .findAll('.integration-settings__group-title')
      .map((title) => title.text())
  const rows = (wrapper) =>
    wrapper.findAll('.integration-settings__integration')

  test('lists its own integrations above the read-only workspace ones', async () => {
    const wrapper = await mountSettings({
      permissions: ['workspace.create_integration'],
      workspaceIntegrations: [workspaceSmtpIntegration],
    })

    expect(sectionTitles(wrapper)).toEqual([
      'applicationIntegrationSettings.applicationIntegrations',
      'applicationIntegrationSettings.workspaceIntegrations',
    ])
    const [ownRow, workspaceRow] = rows(wrapper)
    expect(workspaceRow.text()).toContain('Team mail')
    expect(
      workspaceRow.find('.workspace-integrations-table__more').exists()
    ).toBe(false)
    expect(ownRow.text()).toContain('Mail server')
    expect(ownRow.find('.workspace-integrations-table__more').exists()).toBe(
      true
    )
    // The hint to share one is only for applications with no workspace ones.
    expect(wrapper.find('.integration-settings__hint').exists()).toBe(false)
  })

  test('has no groups while the workspace has no integrations', async () => {
    const wrapper = await mountSettings({ permissions: [] })

    expect(sectionTitles(wrapper)).toEqual([])
    expect(rows(wrapper)).toHaveLength(1)
  })

  test.each([
    [
      ['workspace.create_integration', 'workspace.list_integrations'],
      true,
      true,
    ],
    [['workspace.create_integration'], true, false],
    [[], false, false],
  ])(
    'hints at sharing with the workspace when it has none: %s',
    async (permissions, hinted, linked) => {
      const wrapper = await mountSettings({ permissions })

      const hint = wrapper.find('.integration-settings__hint')
      expect(hint.exists()).toBe(hinted)
      expect(
        hint.exists() &&
          hint.text().includes('applicationIntegrationSettings.shareHint')
      ).toBe(hinted)
      expect(hint.exists() && hint.find('button').exists()).toBe(linked)
    }
  )

  test('opens the edit modal of the integration from its menu', async () => {
    const wrapper = await mountSettings({ permissions: [] })
    await openMenu(wrapper)

    await menuItem(wrapper, 'workspaceIntegrations.edit').trigger('click')
    await flushPromises()

    const modal = wrapper.findComponent({
      name: 'IntegrationCreateEditModal',
    })
    expect(modal.props('integration')).toMatchObject({ id: 11 })
    expect(document.body.textContent).toContain('Mail server')
  })

  test('deletes the integration from its menu', async () => {
    testApp.mock.onDelete('integration/11/').replyOnce(204)
    const wrapper = await mountSettings({ permissions: [] })
    await openMenu(wrapper)

    await menuItem(wrapper, 'workspaceIntegrations.delete').trigger('click')
    await flushPromises()

    expect(testApp.mock.history.delete).toHaveLength(1)
    expect(rows(wrapper)).toHaveLength(0)
    expect(wrapper.text()).toContain('integrationSettings.noIntegrationMessage')
  })

  test('only says there are no integrations when there are none', async () => {
    testApp.mock
      .onGet(`application/${BUILDER_ID}/integrations/`)
      .replyOnce(200, [])
    const wrapper = await mountSettings({ permissions: [] })

    expect(wrapper.find('table').exists()).toBe(false)
    expect(wrapper.text()).toContain('integrationSettings.noIntegrationMessage')
  })

  test.each([
    [['workspace.list_integrations'], true],
    [[], false],
  ])(
    'links to the workspace settings for who can open them: %s',
    async (permissions, linked) => {
      const wrapper = await mountSettings({
        permissions,
        workspaceIntegrations: [workspaceSmtpIntegration],
      })

      const link = wrapper
        .findAll('button')
        .find(
          (button) =>
            button.text() === 'applicationIntegrationSettings.manageInWorkspace'
        )
      expect(!!link).toBe(linked)
    }
  )

  test('opens the workspace integrations tab from the application settings modal', async () => {
    const wrapper = await mountSettings({
      permissions: ['workspace.list_integrations'],
      workspaceIntegrations: [workspaceSmtpIntegration],
      inModal: true,
    })
    const button = wrapper
      .findAll('button')
      .find(
        (button) =>
          button.text() === 'applicationIntegrationSettings.manageInWorkspace'
      )
    await button.trigger('click')
    await flushPromises()

    const modal = document.body.querySelector('.modal__box--with-sidebar')
    expect(
      modal.querySelector('.modal-sidebar__nav-link.active').textContent.trim()
    ).toBe('workspaceIntegrations.tabTitle')
    expect(modal.textContent).toContain('Team mail')
    expect(modal.textContent).not.toContain('workspaceSettingType.aiProviders')
  })

  test('fetches the workspace integrations again every time it opens', async () => {
    // What a workspace integration can reach, like the tables of a Local
    // Baserow one, changes with no realtime event about it, so the second
    // opening must not keep the first answer. A new name stands in for that.
    await mountSettings({
      permissions: [],
      workspaceIntegrations: [workspaceSmtpIntegration],
    })
    const wrapper = await mountSettings({
      permissions: [],
      workspaceIntegrations: [
        { ...workspaceSmtpIntegration, name: 'Team mail, now' },
      ],
    })

    const workspaceRequests = testApp.mock.history.get.filter(
      ({ url }) => url === `application/${BUILDER_ID}/workspace-integrations/`
    )
    expect(workspaceRequests).toHaveLength(2)
    expect(rows(wrapper)[1].text()).toContain('Team mail, now')
  })

  test('shows a promoted integration in the workspace section', async () => {
    const wrapper = await mountSettings({
      permissions: ['workspace.create_integration'],
    })

    await store.dispatch('integration/forceMoveToApplication', {
      applicationSource: store.getters['application/get'](BUILDER_ID),
      applicationDest: store.getters['application/get'](SHARED_ID),
      integrationId: smtpIntegration.id,
    })
    await flushPromises()

    expect(sectionTitles(wrapper)).toHaveLength(2)
    expect(rows(wrapper)).toHaveLength(1)
    expect(rows(wrapper)[0].text()).toContain('Mail server')
    expect(menuButtons(wrapper)).toHaveLength(0)
    expect(wrapper.text()).toContain('integrationSettings.noIntegrationMessage')
  })
})
