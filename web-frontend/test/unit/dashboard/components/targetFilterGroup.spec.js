import { reactive, nextTick, ref } from 'vue'
import { TestApp } from '@baserow/test/helpers/testApp'
import TargetFilterGroup from '@baserow/modules/dashboard/components/widget/TargetFilterGroup'

let testApp
beforeEach(() => {
  testApp = new TestApp()
})
afterEach(() => testApp.afterEach())

test('adding a nested group preserves its seeded condition in the same update', async () => {
  const group = reactive({ filters: [], filter_groups: [], filter_type: 'OR' })
  const wrapper = await testApp.mount(TargetFilterGroup, {
    props: {
      group,
      fields: [{ id: 99, type: 'text', name: 'Name' }],
      dashboard: { id: 1 },
      owner: { id: 2, type: 'text_filter' },
    },
  })
  await wrapper
    .findAll('button')
    .find(
      (button) =>
        button.text() ===
        'localBaserowTableServiceConditionalForm.addFilterGroup'
    )
    .trigger('click')
  // A permanent source must receive the group and its first condition atomically.
  expect(wrapper.emitted('update')).toHaveLength(1)
  const updated = wrapper.emitted('update').at(-1)[0]
  expect(updated.filter_type).toBe('OR')
  expect(updated.filter_groups).toHaveLength(1)
  expect(updated.filters).toHaveLength(1)
  expect(updated.filters[0].group).toBe(updated.filter_groups[0].id)
  // A service response updates the same source object with persistent group IDs.
  Object.assign(group, {
    ...updated,
    filters: [{ ...updated.filters[0], id: 10, group: '20' }],
    filter_groups: [{ ...updated.filter_groups[0], id: '20' }],
  })
  await nextTick()
  await wrapper
    .findAll('button')
    .find(
      (button) =>
        button.text() ===
        'localBaserowTableServiceConditionalForm.addFilterGroup'
    )
    .trigger('click')
  const next = wrapper.emitted('update').at(-1)[0]
  expect(next.filter_groups).toHaveLength(2)
  expect(next.filters).toHaveLength(2)
  expect(next.filters[0].id).toBe(10)
  expect(next.filters[0].group).toBe('20')
})

test('uses the injected prefix for owning-widget formula labels and follows updates', async () => {
  testApp.store.commit('dashboardApplication/SET_WIDGETS', [
    { id: 2, type: 'text_filter', title: 'Private input' },
  ])
  testApp.store.commit('template/dashboardApplication/SET_WIDGETS', [
    { id: 2, type: 'text_filter', title: 'Template input' },
  ])
  const storePrefix = ref('template/')
  const wrapper = await testApp.mount(TargetFilterGroup, {
    props: {
      group: {
        filter_type: 'AND',
        filter_groups: [],
        filters: [
          {
            id: 'condition',
            field: 99,
            type: 'equal',
            group: null,
            value: {
              formula: "get('widget_data.2')",
              mode: 'simple',
              version: '0.1',
            },
          },
        ],
      },
      fields: [{ id: 99, type: 'text', name: 'Name' }],
      dashboard: { id: 1 },
      owner: { id: 2, type: 'text_filter' },
    },
    global: { provide: { storePrefix } },
  })
  expect(wrapper.text()).toContain('Template input')
  expect(wrapper.text()).not.toContain('Private input')
  storePrefix.value = ''
  await nextTick()
  expect(wrapper.text()).toContain('Private input')
  expect(wrapper.text()).not.toContain('Template input')
})

test('adding conditions after a permanent group is saved keeps its persistent group ID', async () => {
  const group = reactive({ filters: [], filter_groups: [], filter_type: 'AND' })
  const wrapper = await testApp.mount(TargetFilterGroup, {
    props: {
      group,
      fields: [{ id: 99, type: 'text', name: 'Name' }],
      dashboard: { id: 1 },
    },
  })
  await wrapper
    .findAll('button')
    .find(
      (button) =>
        button.text() ===
        'localBaserowTableServiceConditionalForm.addFilterGroup'
    )
    .trigger('click')
  const created = wrapper.emitted('update').at(-1)[0]
  Object.assign(group, {
    ...created,
    filters: [{ ...created.filters[0], id: 10, group: '20' }],
    filter_groups: [{ ...created.filter_groups[0], id: '20' }],
  })
  await nextTick()
  await wrapper.find('.filters__group-item-action--add-filter').trigger('click')
  const updated = wrapper.emitted('update').at(-1)[0]
  expect(updated.filters.map((filter) => filter.group)).toEqual(['20', '20'])
  expect(wrapper.findAll('.filters__item--level-1')).toHaveLength(0)
  expect(wrapper.findAll('.filters__item--level-2')).toHaveLength(2)
  expect(wrapper.html()).toMatchSnapshot()
})

test('read-only groups keep constants, formulas and nested conditions locked', async () => {
  const wrapper = await testApp.mount(TargetFilterGroup, {
    props: {
      group: {
        filter_type: 'OR',
        filter_groups: [
          { id: 'nested', parent_group: null, filter_type: 'AND' },
        ],
        filters: [
          {
            id: 1,
            field: 99,
            type: 'equal',
            group: null,
            value: { formula: 'Permanent', mode: 'raw' },
          },
          {
            id: 2,
            field: 99,
            type: 'equal',
            group: 'nested',
            value: { formula: "concat('A', 'B')", mode: 'simple' },
          },
        ],
      },
      fields: [{ id: 99, type: 'text', name: 'Name' }],
      dashboard: { id: 1 },
      readOnly: true,
    },
  })
  expect(wrapper.findAll('.filters__add')).toHaveLength(0)
  expect(wrapper.findAll('.filters__group-item-actions')).toHaveLength(0)
  expect(
    wrapper
      .findAll('.filters__value input')
      .every(
        (input) =>
          input.attributes('disabled') !== undefined ||
          input.attributes('readonly') !== undefined
      )
  ).toBe(true)
  expect(wrapper.find('[contenteditable=true]').exists()).toBe(false)
  expect(wrapper.find('.filters__remove').exists()).toBe(false)
  expect(wrapper.emitted('update')).toBeUndefined()
  expect(wrapper.html()).toMatchSnapshot()
})
