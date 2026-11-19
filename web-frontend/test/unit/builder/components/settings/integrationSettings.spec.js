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

  const mountSettings = async ({ permissions, show = () => {} }) => {
    testApp.mock
      .onGet(`application/${BUILDER_ID}/integrations/`)
      .replyOnce(200, [smtpIntegration])
    const wrapper = await testApp.mount(IntegrationSettings, {
      props: { builder: store.getters['application/get'](BUILDER_ID) },
      global: {
        mocks: {
          $hasPermission: (operation) => permissions.includes(operation),
        },
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
})
