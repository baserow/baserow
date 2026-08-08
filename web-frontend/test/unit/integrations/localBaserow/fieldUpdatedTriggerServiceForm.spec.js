import flushPromises from 'flush-promises'

import LocalBaserowFieldsUpdatedTriggerServiceForm from '@baserow/modules/integrations/localBaserow/components/services/LocalBaserowFieldsUpdatedTriggerServiceForm'
import { TestApp } from '@baserow/test/helpers/testApp'

describe('LocalBaserowFieldsUpdatedTriggerServiceForm', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  async function mountComponent(props = {}) {
    return await testApp.mount(LocalBaserowFieldsUpdatedTriggerServiceForm, {
      props: {
        application: { id: 1 },
        // The table selector always renders, so the service type has to
        // return real tables rather than a stub.
        serviceType: { supportedTables: (tables) => tables },
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

  test('saved field_ids are preserved while the table fields load', async () => {
    // The tableFields mixin transiently empties `tableFields` while fetching, so
    // the form must not wipe persisted fields during that window.
    const fields = testApp.mockServer.createFields({ id: 1 }, { id: 1 }, [
      { name: 'Editable name', type: 'text' },
    ])

    const wrapper = await mountComponent({
      defaultValues: {
        table_id: 1,
        integration_id: 1,
        field_ids: [fields[0].id],
      },
    })
    await flushPromises()

    // No emission should have cleared the fields.
    const emissions = wrapper.emitted('values-changed') || []
    const cleared = emissions.some(
      (e) => Array.isArray(e[0].field_ids) && e[0].field_ids.length === 0
    )
    expect(cleared).toBe(false)
  })

  test('changing the table clears the selected fields', async () => {
    testApp.mockServer.createFields({ id: 1 }, { id: 1 }, [
      { name: 'Editable name', type: 'text' },
    ])
    testApp.mockServer.createFields({ id: 1 }, { id: 2 }, [
      { name: 'Other field', type: 'text' },
    ])

    const wrapper = await mountComponent({
      defaultValues: { table_id: 1, integration_id: 1, field_ids: [999] },
    })
    await flushPromises()

    // Simulate the inner table selector switching to a different table.
    const inner = wrapper.findComponent({ name: 'LocalBaserowServiceForm' })
    inner.vm.$emit('values-changed', { table_id: 2, integration_id: 1 })
    await flushPromises()

    const emissions = wrapper.emitted('values-changed') || []
    const last = emissions.at(-1)?.[0]
    expect(last.table_id).toBe(2)
    expect(last.field_ids).toEqual([])
  })

  test('selecting fields emits field_ids as an array', async () => {
    const fields = testApp.mockServer.createFields({ id: 1 }, { id: 1 }, [
      { name: 'First', type: 'text' },
      { name: 'Second', type: 'text' },
    ])

    const wrapper = await mountComponent()
    await flushPromises()

    // The table selector renders its own dropdowns first, so the field one is
    // found by the only thing that distinguishes it: it takes several values.
    const dropdown = wrapper
      .findAllComponents({ name: 'Dropdown' })
      .find((candidate) => candidate.props('multiple'))
    dropdown.vm.$emit('update:modelValue', [fields[0].id, fields[1].id])
    await flushPromises()

    const emissions = wrapper.emitted('values-changed') || []
    const last = emissions.at(-1)?.[0]
    expect(last.field_ids).toEqual([fields[0].id, fields[1].id])
  })
})
