import { flushPromises } from '@vue/test-utils'
import { TestApp } from '@baserow/test/helpers/testApp'
import WidgetFilterConditions from '@baserow/modules/dashboard/components/widget/WidgetFilterConditions'

let testApp
beforeEach(() => {
  testApp = new TestApp()
  testApp.mock
    .onGet('/database/fields/table/7/')
    .reply(200, [{ id: 99, type: 'text', name: 'Name', primary: true }])
})
afterEach(() => testApp.afterEach())

const group = (filters = []) => ({
  filters,
  filter_groups: [],
  filter_type: 'AND',
})
const mountConditions = async ({ addFirstFilter = true, filters } = {}) => {
  const wrapper = await testApp.mount(WidgetFilterConditions, {
    props: {
      widget: { id: 2, type: 'text_filter', title: 'Region' },
      dashboard: { id: 1 },
      target: { id: 30, type: 'summary' },
      source: { id: 5, table_id: 7, filters: [] },
      link: {
        target_widget_id: 30,
        enabled: true,
        empty_behavior: 'apply_nothing',
        group: group(filters),
      },
      addFirstFilter,
    },
  })
  await flushPromises()
  return wrapper
}

test('starts a link without conditions with one on the first field', async () => {
  const wrapper = await mountConditions()
  expect(wrapper.emitted('update')).toHaveLength(1)
  expect(wrapper.emitted('update')[0][0].group.filters).toEqual([
    expect.objectContaining({
      field: 99,
      type: 'equal',
      value: { formula: "get('widget_data.2')", mode: 'simple' },
    }),
  ])
})

test.each([
  ['it was not asked to', { addFirstFilter: false }],
  [
    'the link already has conditions',
    {
      filters: [
        {
          id: 1,
          field: 99,
          type: 'contains',
          group: null,
          value: { formula: '', mode: 'raw' },
        },
      ],
    },
  ],
])('adds no condition when %s', async (_, options) => {
  const wrapper = await mountConditions(options)
  expect(wrapper.emitted('update')).toBeUndefined()
})
