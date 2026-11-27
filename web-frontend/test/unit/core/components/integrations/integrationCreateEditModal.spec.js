import { TestApp } from '@baserow/test/helpers/testApp'
import IntegrationCreateEditModal from '@baserow/modules/core/components/integrations/IntegrationCreateEditModal'
import OAuthAccountForm from '@baserow/modules/integrations/oauthAccount/components/OAuthAccountForm'
import {
  TEST_OAUTH_TYPE,
  TestOAuthIntegrationType,
  registerTestOAuthType,
} from '@baserow/test/unit/integrations/oauthAccount/testIntegrationType'

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

  test('a type whose form creates the integration hides the create button', async () => {
    const unregister = registerTestOAuthType(testApp)
    const application = { id: 1, workspace: { id: 1 }, integrations: [] }
    testApp.mock.onGet('/integrations/oauth/test_oauth/config/').reply(200, {
      configured: true,
      redirect_uri: 'https://b.io/integrations/test_oauth/oauth-callback',
    })
    const wrapper = await testApp.mount(IntegrationCreateEditModal, {
      props: {
        application,
        create: true,
        integrationType: testApp
          .getRegistry()
          .get('integration', TEST_OAUTH_TYPE),
        serviceTypes: ['test_oauth_send_message'],
      },
    })

    wrapper.vm.show()
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    const buttons = document.body.querySelectorAll('.actions--right button')
    expect([...buttons].map((b) => b.textContent.trim())).not.toContain(
      'action.create'
    )
    // The form gets what the sign-in needs.
    const form = wrapper.findComponent(OAuthAccountForm)
    expect(form.props('serviceTypes')).toEqual(['test_oauth_send_message'])
    expect(form.props('integrationType').getType()).toBe(TEST_OAUTH_TYPE)

    const integration = { id: 9, type: TEST_OAUTH_TYPE, name: 'Example' }
    wrapper.vm.createdBySelf(integration)
    expect(wrapper.emitted('created')).toEqual([[integration]])
    unregister()
  })

  test('an account form gets its type even when the integration is saved first', async () => {
    class SaveFirstType extends TestOAuthIntegrationType {
      static getType() {
        return 'test_oauth_save_first'
      }

      get createsItself() {
        return false
      }
    }
    const registry = testApp.getRegistry()
    registry.register('integration', new SaveFirstType({ app: testApp._app }))
    testApp.mock
      .onGet('/integrations/oauth/test_oauth_save_first/config/')
      .reply(200, { configured: true, redirect_uri: '' })
    const application = { id: 1, workspace: { id: 1 }, integrations: [] }
    try {
      const wrapper = await testApp.mount(IntegrationCreateEditModal, {
        props: {
          application,
          create: true,
          integrationType: registry.get('integration', 'test_oauth_save_first'),
        },
      })

      wrapper.vm.show()
      await wrapper.vm.$nextTick()
      await wrapper.vm.$nextTick()

      const form = wrapper.findComponent(OAuthAccountForm)
      expect(form.props('integrationType').getType()).toBe(
        'test_oauth_save_first'
      )
      // It's saved with the modal's button.
      const buttons = document.body.querySelectorAll('.actions--right button')
      expect([...buttons].map((b) => b.textContent.trim())).toContain(
        'action.create'
      )
    } finally {
      registry.unregister('integration', 'test_oauth_save_first')
    }
  })
})
