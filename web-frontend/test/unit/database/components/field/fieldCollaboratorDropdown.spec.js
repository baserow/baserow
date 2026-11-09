import { TestApp } from '@baserow/test/helpers/testApp'
import { flushPromises } from '@vue/test-utils'
import FieldCollaboratorDropdown from '@baserow/modules/database/components/field/FieldCollaboratorDropdown'

describe('FieldCollaboratorDropdown empty state', () => {
  let testApp

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  test('shows when all collaborators are selected and clears when one is removed', async () => {
    const wrapper = await testApp.mount(FieldCollaboratorDropdown, {
      props: {
        collaborators: [{ id: 1, name: 'Research Agent', type: 'core.Agent' }],
        showEmptyValue: false,
      },
    })
    await wrapper.get('.dropdown__selected').trigger('click')
    await flushPromises()
    expect(wrapper.find('.select__description').exists()).toBe(false)

    await wrapper.setProps({ collaborators: [] })
    await flushPromises()
    expect(wrapper.get('.select__description').text()).toBe(
      'fieldmultipleCollaboratorsDropdown.noneAvailable'
    )

    await wrapper.setProps({
      collaborators: [{ id: 1, name: 'Research Agent', type: 'core.Agent' }],
    })
    await flushPromises()
    expect(wrapper.find('.select__description').exists()).toBe(false)
    expect(wrapper.get('.select-collaborators__dropdown-option').text()).toBe(
      'Research Agent'
    )

    const input = wrapper.get('.select__search-input')
    await input.setValue('missing')
    await input.trigger('keyup')
    await flushPromises()
    expect(wrapper.get('.select__description').text()).toBe(
      'fieldmultipleCollaboratorsDropdown.notFound'
    )
  })
})
