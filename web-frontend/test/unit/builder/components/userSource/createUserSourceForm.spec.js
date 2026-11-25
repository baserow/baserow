import { flushPromises } from '@vue/test-utils'
import { TestApp } from '@baserow/test/helpers/testApp'
import { UserSourceType } from '@baserow/modules/core/userSourceTypes'
import CreateUserSourceForm from '@baserow/modules/builder/components/userSource/CreateUserSourceForm'
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

describe('CreateUserSourceForm integration default', () => {
  let testApp
  beforeEach(() => {
    testApp = new TestApp()
    testApp.store.$registry.register(
      'userSource',
      new TestUserSourceType({ app: testApp.getApp() })
    )
  })
  afterEach(async () => {
    testApp.getRegistry().unregister('userSource', 'test_source')
    await testApp.afterEach()
  })

  test('waits for the source type and ignores integrations of other types', async () => {
    const builder = {
      id: 1,
      type: 'builder',
      integrations: [
        { id: 11, application_id: 1, type: 'local_baserow', name: 'Tables' },
        { id: 12, application_id: 1, type: 'smtp', name: 'Email' },
      ],
      user_sources: [],
    }
    const wrapper = await testApp.mount(CreateUserSourceForm, {
      props: { builder },
    })
    expect(wrapper.findComponent(IntegrationDropdown).props('modelValue')).toBe(
      null
    )

    wrapper
      .findComponent({ name: 'Dropdown' })
      .vm.$emit('update:modelValue', 'test_source')
    await flushPromises()

    expect(wrapper.findComponent(IntegrationDropdown).props('modelValue')).toBe(
      11
    )
    expect(
      wrapper
        .findComponent(IntegrationDropdown)
        .props('integrations')
        .map(({ id }) => id)
    ).toEqual([11])
  })
})
