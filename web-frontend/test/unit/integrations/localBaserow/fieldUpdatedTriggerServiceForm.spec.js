import flushPromises from 'flush-promises'

import LocalBaserowFieldUpdatedTriggerServiceForm from '@baserow/modules/integrations/localBaserow/components/services/LocalBaserowFieldUpdatedTriggerServiceForm'
import { TestApp } from '@baserow/test/helpers/testApp'

describe('LocalBaserowFieldUpdatedTriggerServiceForm', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  async function mountComponent(props = {}) {
    return await testApp.mount(LocalBaserowFieldUpdatedTriggerServiceForm, {
      props: {
        application: { id: 1 },
        serviceType: {},
        defaultValues: { table_id: 1, integration_id: 1 },
        ...props,
      },
    })
  }

  test('the field dropdown excludes read-only field types', async () => {
    // A user-editable field and a read-only field (formula) on the same table.
    testApp.mockServer.createFields({ id: 1 }, { id: 1 }, [
      { name: 'Editable name', type: 'text' },
      { name: 'Computed total', type: 'formula', read_only: true },
    ])

    const wrapper = await mountComponent()
    await flushPromises()

    const optionNames = wrapper
      .findAllComponents({ name: 'DropdownItem' })
      .map((item) => item.props('name'))

    expect(optionNames).toContain('Editable name')
    expect(optionNames).not.toContain('Computed total')
  })

  test('a saved field_id is preserved while the table fields load', async () => {
    // The tableFields mixin transiently empties `tableFields` while fetching, so
    // the form must not wipe a persisted field during that window.
    const fields = testApp.mockServer.createFields({ id: 1 }, { id: 1 }, [
      { name: 'Editable name', type: 'text' },
    ])

    const wrapper = await mountComponent({
      defaultValues: { table_id: 1, integration_id: 1, field_id: fields[0].id },
    })
    await flushPromises()

    // No emission should have cleared the field back to null.
    const emissions = wrapper.emitted('values-changed') || []
    const clearedToNull = emissions.some((e) => e[0].field_id === null)
    expect(clearedToNull).toBe(false)
  })

  test('changing the table clears the selected field', async () => {
    testApp.mockServer.createFields({ id: 1 }, { id: 1 }, [
      { name: 'Editable name', type: 'text' },
    ])
    testApp.mockServer.createFields({ id: 1 }, { id: 2 }, [
      { name: 'Other field', type: 'text' },
    ])

    const wrapper = await mountComponent({
      defaultValues: { table_id: 1, integration_id: 1, field_id: 999 },
    })
    await flushPromises()

    // Simulate the inner table selector switching to a different table.
    const inner = wrapper.findComponent({ name: 'LocalBaserowServiceForm' })
    inner.vm.$emit('values-changed', { table_id: 2, integration_id: 1 })
    await flushPromises()

    const emissions = wrapper.emitted('values-changed') || []
    const last = emissions.at(-1)?.[0]
    expect(last.table_id).toBe(2)
    expect(last.field_id).toBe(null)
  })
})
