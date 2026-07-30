import LocalBaserowTableServiceConditionalForm from '@baserow/modules/integrations/localBaserow/components/services/LocalBaserowTableServiceConditionalForm'
import ViewFieldConditionsForm from '@baserow/modules/database/components/view/ViewFieldConditionsForm.vue'
import { TestApp } from '@baserow/test/helpers/testApp'

describe('LocalBaserowTableServiceConditionalForm', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  const fields = [{ id: 1, name: 'Name', type: 'text', primary: true }]

  async function mountComponent(props = {}) {
    return await testApp.mount(LocalBaserowTableServiceConditionalForm, {
      props: {
        modelValue: [],
        filterGroups: [],
        filterType: 'AND',
        fields,
        ...props,
      },
    })
  }

  test('adding a filter group emits a new group and a seeded filter', async () => {
    const wrapper = await mountComponent()
    const child = wrapper.findComponent(ViewFieldConditionsForm)

    child.vm.$emit('addFilterGroup', {
      filterGroupId: 'group-1',
      parentGroupId: null,
    })
    await wrapper.vm.$nextTick()

    const groups = wrapper.emitted('update:filterGroups').at(-1)[0]
    expect(groups).toEqual([
      { id: 'group-1', filter_type: 'AND', parent_group: null },
    ])

    // A first filter is seeded inside the new group.
    const filters = wrapper.emitted('update:modelValue').at(-1)[0]
    expect(filters).toHaveLength(1)
    expect(filters[0].group).toBe('group-1')
    expect(filters[0].field).toBe(fields[0].id)
  })

  test('adding a nested filter group carries the parent group id', async () => {
    const wrapper = await mountComponent({
      filterGroups: [{ id: 'group-1', filter_type: 'AND', parent_group: null }],
    })
    const child = wrapper.findComponent(ViewFieldConditionsForm)

    child.vm.$emit('addFilterGroup', {
      filterGroupId: 'group-2',
      parentGroupId: 'group-1',
    })
    await wrapper.vm.$nextTick()

    const groups = wrapper.emitted('update:filterGroups').at(-1)[0]
    expect(groups).toEqual([
      { id: 'group-1', filter_type: 'AND', parent_group: null },
      { id: 'group-2', filter_type: 'AND', parent_group: 'group-1' },
    ])
  })

  test('deleting a filter group removes it and its filters', async () => {
    const wrapper = await mountComponent({
      modelValue: [
        {
          id: 'f1',
          field: 1,
          type: 'equal',
          value: { formula: 'a', mode: 'raw' },
          value_is_formula: false,
          group: 'group-1',
        },
        {
          id: 'f2',
          field: 1,
          type: 'equal',
          value: { formula: 'b', mode: 'raw' },
          value_is_formula: false,
          group: null,
        },
      ],
      filterGroups: [{ id: 'group-1', filter_type: 'AND', parent_group: null }],
    })
    const child = wrapper.findComponent(ViewFieldConditionsForm)

    child.vm.$emit('deleteFilterGroup', {
      group: { id: 'group-1' },
    })
    await wrapper.vm.$nextTick()

    expect(wrapper.emitted('update:filterGroups').at(-1)[0]).toEqual([])
    // Only the ungrouped filter survives.
    const filters = wrapper.emitted('update:modelValue').at(-1)[0]
    expect(filters.map((f) => f.id)).toEqual(['f2'])
  })

  test('updating a group filter type emits the updated groups', async () => {
    const wrapper = await mountComponent({
      filterGroups: [{ id: 'group-1', filter_type: 'AND', parent_group: null }],
    })
    const child = wrapper.findComponent(ViewFieldConditionsForm)

    child.vm.$emit('updateFilterType', {
      value: 'OR',
      filterGroup: { id: 'group-1' },
    })
    await wrapper.vm.$nextTick()

    expect(wrapper.emitted('update:filterGroups').at(-1)[0]).toEqual([
      { id: 'group-1', filter_type: 'OR', parent_group: null },
    ])
    // The top-level filter type is not touched.
    expect(wrapper.emitted('update:filterType')).toBeFalsy()
  })

  test('updating the top-level filter type emits update:filterType', async () => {
    const wrapper = await mountComponent()
    const child = wrapper.findComponent(ViewFieldConditionsForm)

    child.vm.$emit('updateFilterType', { value: 'OR' })
    await wrapper.vm.$nextTick()

    expect(wrapper.emitted('update:filterType').at(-1)[0]).toBe('OR')
    expect(wrapper.emitted('update:filterGroups')).toBeFalsy()
  })

  test('the formula toggle is rendered for a filter inside a group', async () => {
    // The raw-value/formula toggle (sigma) slot must reach filters nested in a
    // group, not just root-level filters.
    const wrapper = await mountComponent({
      modelValue: [
        {
          id: 'f1',
          field: 1,
          type: 'equal',
          value: { formula: 'a', mode: 'raw' },
          value_is_formula: false,
          group: 'group-1',
        },
      ],
      filterGroups: [{ id: 'group-1', filter_type: 'AND', parent_group: null }],
    })

    expect(
      wrapper
        .find('.filters__group-item .filters__value--formula-toggle')
        .exists()
    ).toBe(true)
  })
})
