import flushPromises from 'flush-promises'

import LocalBaserowForm from '@baserow/modules/integrations/localBaserow/components/integrations/LocalBaserowForm'
import { TestApp } from '@baserow/test/helpers/testApp'

describe('LocalBaserowForm', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
    testApp.mock.onGet('/agents/workspace/1/').reply(200, {
      count: 2,
      next: null,
      previous: null,
      results: [
        { id: 10, name: 'Writer agent' },
        { id: 11, name: 'Reader agent' },
      ],
    })
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  async function mountComponent(defaultValues = {}) {
    return await testApp.mount(LocalBaserowForm, {
      props: {
        application: { id: 2, workspace: { id: 1 } },
        defaultValues,
      },
    })
  }

  test('lists agents and emits the selected agent id', async () => {
    const wrapper = await mountComponent()
    await flushPromises()

    const items = wrapper.findAllComponents({ name: 'DropdownItem' })
    expect(items.map((item) => item.props('name'))).toEqual([
      'localBaserowForm.currentUser',
      'Writer agent',
      'Reader agent',
    ])

    await items.at(1).find('.select__item-link').trigger('click')
    await flushPromises()

    expect(wrapper.emitted('values-changed').at(-1)[0]).toEqual({
      authorized_agent_id: 10,
    })
  })

  test('shows the saved agent as selected', async () => {
    const wrapper = await mountComponent({
      authorized_agent: { id: 11, name: 'Reader agent' },
    })
    await flushPromises()

    expect(wrapper.find('.dropdown__selected-text').text()).toBe('Reader agent')
  })
})
