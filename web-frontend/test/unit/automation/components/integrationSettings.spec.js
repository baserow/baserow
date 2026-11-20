import flushPromises from 'flush-promises'

import IntegrationSettings from '@baserow/modules/automation/components/settings/IntegrationSettings'
import { TestApp } from '@baserow/test/helpers/testApp'

const WORKSPACE = { id: 1, name: 'Acme' }
const AUTOMATION_ID = 10

const automationApplication = {
  id: AUTOMATION_ID,
  type: 'automation',
  name: 'Flows',
  order: 1,
  workspace: { id: WORKSPACE.id, name: WORKSPACE.name },
  workflows: [],
}

const smtpIntegration = {
  id: 11,
  application_id: AUTOMATION_ID,
  type: 'smtp',
  name: 'Mail server',
  order: '1',
  host: 'smtp.example.com',
  port: 587,
}

// Every permission is granted in unit tests, so only the workspace being in the
// store decides here.
describe('Automation IntegrationSettings', () => {
  let testApp = null
  let store = null

  beforeEach(async () => {
    testApp = new TestApp()
    store = testApp.store
    await store.dispatch('application/forceSetAll', {
      applications: [automationApplication],
    })
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  const promoteButtons = (wrapper) => wrapper.findAll('.iconoir-community')

  const mountSettings = async (show = () => {}) => {
    testApp.mock
      .onGet(`application/${AUTOMATION_ID}/integrations/`)
      .replyOnce(200, [smtpIntegration])
    testApp.mock
      .onGet(`application/${AUTOMATION_ID}/workspace-integrations/`)
      .replyOnce(200, { shared_application: null, integrations: [] })
    const wrapper = await testApp.mount(IntegrationSettings, {
      props: {
        automation: store.getters['application/get'](AUTOMATION_ID),
      },
      global: {
        stubs: {
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

  test('asks to confirm the promotion of the integration picked', async () => {
    await store.dispatch('workspace/forceCreate', { ...WORKSPACE })
    const show = vi.fn()
    const wrapper = await mountSettings(show)

    await promoteButtons(wrapper)[0].trigger('click')
    await flushPromises()

    const modal = wrapper.findComponent({ name: 'PromoteIntegrationModal' })
    expect(modal.props('application').id).toBe(AUTOMATION_ID)
    expect(modal.props('integration')).toMatchObject({ id: 11 })
    expect(show).toHaveBeenCalled()
    expect(testApp.mock.history.patch).toHaveLength(0)
  })

  test('fetches the workspace integrations again every time it opens', async () => {
    // What a workspace integration can reach, like the tables of a Local
    // Baserow one, changes with no realtime event about it.
    await store.dispatch('workspace/forceCreate', { ...WORKSPACE })
    const workspaceUrl = `application/${AUTOMATION_ID}/workspace-integrations/`
    const sharedApplication = {
      id: 20,
      type: 'shared',
      name: '__shared__',
      order: 0,
      workspace: { id: WORKSPACE.id, name: WORKSPACE.name },
    }
    const answer = (name) => ({
      shared_application: sharedApplication,
      integrations: [{ ...smtpIntegration, id: 21, application_id: 20, name }],
    })
    testApp.mock.onGet(workspaceUrl).replyOnce(200, answer('Team mail'))
    testApp.mock.onGet(workspaceUrl).replyOnce(200, answer('Team mail, now'))

    await mountSettings()
    const wrapper = await mountSettings()

    expect(
      testApp.mock.history.get.filter(({ url }) => url === workspaceUrl)
    ).toHaveLength(2)
    expect(wrapper.text()).toContain('Team mail, now')
  })

  test('offers no promotion outside a workspace of the user', async () => {
    // Like a template preview.
    const wrapper = await mountSettings()

    expect(promoteButtons(wrapper)).toHaveLength(0)
    expect(
      wrapper.findComponent({ name: 'PromoteIntegrationModal' }).exists()
    ).toBe(false)
  })
})
