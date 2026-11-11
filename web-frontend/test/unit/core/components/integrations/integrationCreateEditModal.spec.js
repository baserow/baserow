import { TestApp } from '@baserow/test/helpers/testApp'
import IntegrationCreateEditModal from '@baserow/modules/core/components/integrations/IntegrationCreateEditModal'

describe('IntegrationCreateEditModal', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
    testApp.store.state.auth.user = { id: 1 }
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  test('only sends values changed from the initial form values on update', async () => {
    const application = { id: 1, workspace: { id: 1 }, integrations: [] }
    const integration = {
      id: 1,
      type: 'local_baserow',
      name: 'Teammate integration',
      authorized_subject: {
        id: 2,
        type: 'auth.User',
        first_name: 'Teammate',
        username: 'teammate@example.com',
      },
    }
    application.integrations = [integration]
    testApp.mock.onPatch('/integration/1/').reply((config) => {
      expect(JSON.parse(config.data)).toEqual({ name: 'Renamed integration' })
      return [200, { ...integration, name: 'Renamed integration' }]
    })
    const wrapper = await testApp.mount(IntegrationCreateEditModal, {
      props: { application, integration },
    })

    wrapper.vm.show()
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()
    await wrapper.vm.submit({
      name: 'Renamed integration',
      authorized_subject_id: 2,
      authorized_subject_type: 'auth.User',
    })
  })

  test('sends authorization subject values together when either changes', async () => {
    const application = { id: 1, workspace: { id: 1 }, integrations: [] }
    const integration = {
      id: 1,
      type: 'local_baserow',
      name: 'Teammate integration',
      authorized_subject: {
        id: 2,
        type: 'auth.User',
        first_name: 'Teammate',
        username: 'teammate@example.com',
      },
    }
    application.integrations = [integration]
    testApp.mock.onPatch('/integration/1/').reply((config) => {
      expect(JSON.parse(config.data)).toEqual({
        authorized_subject_id: 1,
        authorized_subject_type: 'auth.User',
      })
      return [200, integration]
    })
    const wrapper = await testApp.mount(IntegrationCreateEditModal, {
      props: { application, integration },
    })

    wrapper.vm.show()
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()
    await wrapper.vm.submit({
      name: 'Teammate integration',
      authorized_subject_id: 1,
      authorized_subject_type: 'auth.User',
    })
  })
})
