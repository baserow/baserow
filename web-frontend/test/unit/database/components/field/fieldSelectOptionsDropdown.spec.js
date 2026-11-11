import { TestApp } from '@baserow/test/helpers/testApp'
import FieldSelectOptionsDropdown from '@baserow/modules/database/components/field/FieldSelectOptionsDropdown.vue'

describe('FieldSelectOptionsDropdown search', () => {
  let testApp

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  const alpha = { id: 1, value: 'Alpha', color: 'green' }
  const beta = { id: 2, value: 'Beta', color: 'blue' }
  const mountDropdown = () =>
    testApp.mount(FieldSelectOptionsDropdown, {
      props: {
        options: [alpha],
        modelValue: 1,
        allowCreateOption: true,
        showEmptyValue: false,
      },
    })

  const search = async (wrapper, query) => {
    const input = wrapper.get('.select__search-input')
    await input.setValue(query)
    await input.trigger('keyup')
  }

  test('updates the creation action when options change during a search', async () => {
    const wrapper = await mountDropdown()
    await wrapper.get('.dropdown__selected').trigger('click')
    await search(wrapper, 'beta')
    expect(wrapper.get('.select__footer-button').text()).toContain('beta')

    await wrapper.setProps({ options: [alpha, beta] })

    expect(wrapper.find('.select__footer-button').exists()).toBe(false)
    expect(
      wrapper.get('.select-options__dropdown-item:not(.hidden)').text()
    ).toBe('Beta')

    await wrapper.setProps({ options: [alpha] })

    expect(wrapper.get('.select__footer-button').text()).toContain('beta')
  })

  test('creates and selects an option from a search with no matches', async () => {
    const wrapper = await mountDropdown()
    await wrapper.get('.dropdown__selected').trigger('click')
    await search(wrapper, 'Beta')

    await wrapper
      .get('.select__search-input')
      .trigger('keydown', { key: 'Enter' })

    expect(wrapper.emitted('create-option')).toHaveLength(1)
    const { value, done } = wrapper.emitted('create-option')[0][0]
    expect(value).toBe('Beta')
    expect(wrapper.emitted('update:modelValue')).toBeUndefined()

    await wrapper.setProps({ options: [alpha, beta] })
    done(true)

    expect(wrapper.emitted('update:modelValue')).toEqual([[2]])
  })
})
