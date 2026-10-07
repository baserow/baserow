import flushPromises from 'flush-promises'

import LocalBaserowForm from '@baserow/modules/integrations/localBaserow/components/integrations/LocalBaserowForm'
import { TestApp } from '@baserow/test/helpers/testApp'

describe('LocalBaserowForm', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
    testApp.store.state.auth.user = { id: 1 }
    testApp.mock.onGet('/subjects/').reply(200, {
      count: 2,
      next: null,
      previous: null,
      results: [
        {
          id: 'core.Agent:10',
          subject_id: 10,
          subject_type: 'core.Agent',
          name: 'Writer agent',
        },
        {
          id: 'core.Agent:11',
          subject_id: 11,
          subject_type: 'core.Agent',
          name: 'Reader agent',
        },
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

  test('lists agents and emits the selected typed subject', async () => {
    const wrapper = await mountComponent()
    await wrapper.find('.dropdown__selected').trigger('click')
    await flushPromises()

    expect(testApp.mock.history.get.at(-1).params).toEqual({
      workspace_id: 1,
      page: 1,
      search: '',
      subject_types: 'core.Agent',
      size: 100,
    })

    const items = wrapper.findAllComponents({ name: 'DropdownItem' })
    expect(items.map((item) => item.props('name'))).toEqual([
      'localBaserowForm.currentUser',
      'Writer agent',
      'Reader agent',
    ])

    await items.at(1).find('.select__item-link').trigger('click')
    await flushPromises()

    expect(wrapper.emitted('values-changed').at(-1)[0]).toEqual({
      authorized_subject_id: 10,
      authorized_subject_type: 'core.Agent',
    })
  })

  test('shows the saved agent as selected', async () => {
    const wrapper = await mountComponent({
      authorized_subject: { id: 11, type: 'core.Agent', name: 'Reader agent' },
    })
    await flushPromises()

    expect(wrapper.find('.dropdown__selected-text').text()).toBe('Reader agent')
  })

  test('emits the current user as an explicit authorization subject', async () => {
    const wrapper = await mountComponent({
      authorized_subject: { id: 11, type: 'core.Agent', name: 'Reader agent' },
    })
    await flushPromises()

    await wrapper
      .findComponent({ name: 'DropdownItem', props: { value: 'user' } })
      .find('.select__item-link')
      .trigger('click')
    await flushPromises()

    expect(wrapper.emitted('values-changed').at(-1)[0]).toEqual({
      authorized_subject_id: 1,
      authorized_subject_type: 'auth.User',
    })
  })
})
