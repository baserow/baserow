import { TestApp } from '@baserow/test/helpers/testApp'
import { UserSourceType } from '@baserow/modules/core/userSourceTypes'
import UpdateUserSourceForm from '@baserow/modules/builder/components/userSource/UpdateUserSourceForm'
import IntegrationDropdown from '@baserow/modules/core/components/integrations/IntegrationDropdown'

class TestUserSourceType extends UserSourceType {
  static getType() {
    return 'test_source'
  }

  get name() {
    return 'Test source'
  }

  get integrationType() {
    return this.app.$registry.get('integration', 'local_baserow')
  }

  get image() {
    return ''
  }
}

describe('UpdateUserSourceForm integration filter', () => {
  let testApp
  beforeEach(() => {
    testApp = new TestApp()
  })
  afterEach(async () => {
    await testApp.afterEach()
  })

  test('only offers the integrations of the user source integration type', async () => {
    const builder = {
      id: 1,
      type: 'builder',
      workspace: { id: 1 },
      integrations: [
        { id: 11, application_id: 1, type: 'local_baserow', name: 'Tables' },
        { id: 12, application_id: 1, type: 'smtp', name: 'Email' },
        { id: 13, application_id: 1, type: 'ai', name: 'AI' },
      ],
      user_sources: [],
    }
    const wrapper = await testApp.mount(UpdateUserSourceForm, {
      props: {
        builder,
        userSourceType: new TestUserSourceType({ app: testApp.getApp() }),
        defaultValues: { name: 'Users', integration_id: null },
      },
    })

    expect(
      wrapper
        .findComponent(IntegrationDropdown)
        .props('integrations')
        .map(({ id }) => id)
    ).toEqual([11])
  })
})
