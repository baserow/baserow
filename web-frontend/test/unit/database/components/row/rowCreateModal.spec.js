import { flushPromises } from '@vue/test-utils'

import { TestApp } from '@baserow/test/helpers/testApp'
import RowCreateModal from '@baserow/modules/database/components/row/RowCreateModal'
import { populateField } from '@baserow/modules/database/store/field'

describe('RowCreateModal', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  const database = { id: 1, workspace: { id: 1 } }
  const table = { id: 1 }

  const buildFields = () => {
    const registry = testApp.getRegistry()
    return [
      { id: 1, name: 'Name', type: 'text', primary: true, text_default: '' },
      { id: 2, name: 'URL', type: 'url', primary: false },
    ].map((field) => populateField(field, registry))
  }

  const mountModal = async () => {
    const fields = buildFields()
    const wrapper = await testApp.mount(RowCreateModal, {
      props: {
        database,
        table,
        view: null,
        visibleFields: fields,
        hiddenFields: [],
        allFieldsInTable: fields,
        canModifyFields: false,
      },
      global: { stubs: { FieldContext: true } },
    })
    await wrapper.vm.show()
    await flushPromises()
    return { wrapper, fields }
  }

  const getModalField = (wrapper, type) =>
    wrapper
      .findAllComponents({ name: 'RowEditModalField' })
      .find((component) => component.props('field').type === type)

  test('does not pre-validate fields when the modal is opened', async () => {
    const { wrapper } = await mountModal()

    const urlField = getModalField(wrapper, 'url')
    expect(urlField).toBeDefined()
    expect(urlField.find('.control__messages--error').exists()).toBe(false)
  })

  test('emits created when all field values are valid', async () => {
    const { wrapper } = await mountModal()

    wrapper.vm.create()
    await flushPromises()

    expect(wrapper.emitted('created')).toHaveLength(1)
  })

  test('shows the error and blocks creation for an invalid value', async () => {
    const { wrapper } = await mountModal()

    const urlField = getModalField(wrapper, 'url')
    const input = urlField.find('input')
    await input.trigger('focus')
    await input.setValue('not a valid url')
    await input.trigger('blur')
    await flushPromises()

    expect(urlField.find('.control__messages--error').exists()).toBe(true)

    wrapper.vm.create()
    await flushPromises()

    expect(wrapper.emitted('created')).toBeUndefined()
  })
})
