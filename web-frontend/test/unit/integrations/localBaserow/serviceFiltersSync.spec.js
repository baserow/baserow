import { defineComponent, inject } from 'vue'

import form from '@baserow/modules/core/mixins/form'
import serviceFiltersSync from '@baserow/modules/integrations/localBaserow/mixins/serviceFiltersSync'
import { TestApp } from '@baserow/test/helpers/testApp'

const Child = defineComponent({
  name: 'Child',
  setup() {
    return { serviceFilters: inject('serviceFilters') }
  },
  template: '<span />',
})

const Host = defineComponent({
  name: 'Host',
  components: { Child },
  mixins: [form, serviceFiltersSync],
  props: {
    service: { type: Object, required: true },
  },
  data() {
    return {
      allowedValues: ['name', 'filters', 'filter_groups', 'filter_type'],
      values: { name: '', filters: [], filter_groups: [], filter_type: 'AND' },
    }
  },
  template: '<div><Child /></div>',
})

const filter = (id, value) => ({
  id,
  field: 1,
  type: 'equal',
  value: { formula: value, mode: 'raw' },
  group: null,
})

const savedService = (filters, extra = {}) => ({
  name: 'Tasks',
  filters,
  filter_groups: [],
  filter_type: 'AND',
  ...extra,
})

describe('serviceFiltersSync', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  async function mountHost(service) {
    return await testApp.mount(Host, {
      props: { service, defaultValues: service },
    })
  }

  test('copies saved filters into an unedited form', async () => {
    const wrapper = await mountHost(savedService([filter(1, 'a')]))
    wrapper.vm.values.name = 'Unsaved name'
    await wrapper.vm.$nextTick()
    const emittedBefore = wrapper.emitted('values-changed')?.length ?? 0

    await wrapper.setProps({
      service: savedService([filter(1, 'a'), filter(2, 'b')], {
        filter_type: 'OR',
      }),
    })

    expect(wrapper.vm.values.filters).toEqual([filter(1, 'a'), filter(2, 'b')])
    expect(wrapper.vm.values.filter_type).toBe('OR')
    // Other unsaved values are left alone.
    expect(wrapper.vm.values.name).toBe('Unsaved name')
    // The values now match what's saved, so nothing is emitted to save again.
    expect(wrapper.emitted('values-changed')?.length ?? 0).toBe(emittedBefore)
  })

  test('keeps filters the user edited', async () => {
    const wrapper = await mountHost(savedService([filter(1, 'a')]))
    wrapper.vm.values.filters = [filter(1, 'edited')]
    await wrapper.vm.$nextTick()

    await wrapper.setProps({ service: savedService([filter(2, 'b')]) })

    expect(wrapper.vm.values.filters).toEqual([filter(1, 'edited')])
  })

  test('reports unsaved filter changes', async () => {
    const wrapper = await mountHost(savedService([filter(1, 'a')]))
    const { serviceFilters } = wrapper.findComponent(Child).vm

    expect(serviceFilters.hasUnsavedChanges()).toBe(false)

    wrapper.vm.values.filters = [filter(1, 'edited')]
    expect(serviceFilters.hasUnsavedChanges()).toBe(true)
  })

  test('reports the table picked or changed in the form', async () => {
    const wrapper = await mountHost(savedService([], { table_id: null }))
    const { serviceFilters } = wrapper.findComponent(Child).vm
    wrapper.vm.values.table_id = null
    expect(serviceFilters.getUnsavedTableId()).toBe(null)

    // Picked for a data source without a table: sent along to be saved.
    wrapper.vm.values.table_id = 7
    expect(serviceFilters.getUnsavedTableId()).toBe(7)
    expect(serviceFilters.hasUnsavedTableChange()).toBe(false)

    await wrapper.setProps({ service: savedService([], { table_id: 7 }) })
    expect(serviceFilters.getUnsavedTableId()).toBe(null)

    // Another table than the saved one: it must be saved first.
    wrapper.vm.values.table_id = 8
    expect(serviceFilters.hasUnsavedTableChange()).toBe(true)
    expect(serviceFilters.getUnsavedTableId()).toBe(null)
  })

  test('copies the filters saved with the picked table', async () => {
    const wrapper = await mountHost(savedService([], { table_id: null }))
    wrapper.vm.values.table_id = 7
    await wrapper.vm.$nextTick()

    await wrapper.setProps({
      service: savedService([filter(1, 'a')], { table_id: 7 }),
    })

    expect(wrapper.vm.values.filters).toEqual([filter(1, 'a')])
  })
})
