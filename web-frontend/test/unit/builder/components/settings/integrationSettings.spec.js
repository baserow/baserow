import flushPromises from 'flush-promises'

import IntegrationSettings from '@baserow/modules/builder/components/settings/IntegrationSettings'
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
    await testApp.afterEach()
  })

  const promoteButtons = (wrapper) => wrapper.findAll('.iconoir-community')

  const mountSettings = async ({
    permissions,
    show = () => {},
    workspaceIntegrations = [],
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
    const wrapper = await testApp.mount(IntegrationSettings, {
      props: { builder: store.getters['application/get'](BUILDER_ID) },
      global: {
        mocks: {
          $hasPermission: (operation) => permissions.includes(operation),
        },
        stubs: {
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
    await flushPromises()
    return wrapper
  }

  test.each([
    [['workspace.create_integration'], 1],
    [[], 0],
  ])(
    'offers promotion to users who can create workspace integrations: %s',
    async (permissions, buttonCount) => {
      const wrapper = await mountSettings({ permissions })

      expect(promoteButtons(wrapper)).toHaveLength(buttonCount)
      expect(
        wrapper.findComponent({ name: 'PromoteIntegrationModal' }).exists()
      ).toBe(buttonCount > 0)
    }
  )

  test('asks to confirm the promotion of the integration picked', async () => {
    const show = vi.fn()
    const wrapper = await mountSettings({
      permissions: ['workspace.create_integration'],
      show,
    })

    await promoteButtons(wrapper)[0].trigger('click')
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
      .findAll('.integration-settings__section-title')
      .map((title) => title.text())
  const rows = (wrapper) =>
    wrapper.findAll('.integration-settings__integration')

  test('lists the workspace integrations read-only above its own', async () => {
    const wrapper = await mountSettings({
      permissions: ['workspace.create_integration'],
      workspaceIntegrations: [workspaceSmtpIntegration],
    })

    expect(sectionTitles(wrapper)).toEqual([
      'applicationIntegrationSettings.workspaceIntegrations',
      'applicationIntegrationSettings.applicationIntegrations',
    ])
    const [workspaceRow, ownRow] = rows(wrapper)
    expect(workspaceRow.text()).toContain('Team mail')
    expect(
      workspaceRow.find('.integration-settings__integration-actions').exists()
    ).toBe(false)
    expect(ownRow.text()).toContain('Mail server')
    expect(
      ownRow.find('.integration-settings__integration-actions').exists()
    ).toBe(true)
    // Only its own can be made available to the whole workspace.
    expect(promoteButtons(wrapper)).toHaveLength(1)
  })

  test('has no sections while the workspace has no integrations', async () => {
    const wrapper = await mountSettings({ permissions: [] })

    expect(sectionTitles(wrapper)).toEqual([])
    expect(rows(wrapper)).toHaveLength(1)
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

      const link = wrapper.findComponent({ name: 'NuxtLink' })
      expect(link.exists()).toBe(linked)
      if (linked) {
        expect(link.props('to')).toEqual({
          name: 'settings-integrations',
          params: { workspaceId: WORKSPACE.id },
        })
      }
    }
  )

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
    expect(rows(wrapper)[0].text()).toContain('Team mail, now')
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
    expect(promoteButtons(wrapper)).toHaveLength(0)
    expect(wrapper.text()).toContain('integrationSettings.noIntegrationMessage')
  })
})
