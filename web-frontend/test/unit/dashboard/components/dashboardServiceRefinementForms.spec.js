import { DOMWrapper, flushPromises } from '@vue/test-utils'
import { TestApp } from '@baserow/test/helpers/testApp'
import DashboardServiceRefinementForms from '@baserow/modules/dashboard/components/data_source/DashboardServiceRefinementForms'

let testApp
beforeEach(() => {
  testApp = new TestApp()
})
afterEach(() => testApp.afterEach())

const emptyGroup = () => ({
  filters: [],
  filter_groups: [],
  filter_type: 'AND',
})
const conditionGroup = (value) => ({
  ...emptyGroup(),
  filters: [
    {
      id: 1,
      field: 7,
      type: 'equal',
      group: null,
      value: { formula: value, mode: 'raw' },
    },
  ],
})
const owner = (overrides = {}) => ({
  id: 2,
  type: 'text_filter',
  title: 'Country',
  target_filters: [
    {
      target_widget_id: 5,
      group: conditionGroup('France'),
      empty_behavior: 'apply_nothing',
    },
  ],
  ...overrides,
})

async function mountRefinements(props = {}) {
  const wrapper = await testApp.mount(DashboardServiceRefinementForms, {
    props: {
      values: { table_id: 2, ...emptyGroup() },
      tableFields: [{ id: 7, name: 'Country', type: 'text' }],
      widget: { id: 5, type: 'summary' },
      dashboard: { id: 1 },
      small: true,
      showFilter: true,
      ...props,
    },
    global: { stubs: { Teleport: false } },
  })
  if (props.small !== false) {
    await wrapper.find('.header__filter-link').trigger('click')
  }
  await flushPromises()
  const filters =
    props.small === false
      ? wrapper.find('.service-form__condition-form-tab')
      : new DOMWrapper(document.body).find('.service-form__context--filter')
  return { wrapper, filters }
}

test.each([true, false])(
  'shows inherited nested and empty-state conditions read-only when small=%s',
  async (small) => {
    const country = owner()
    const link = country.target_filters[0]
    link.group.filter_groups = [
      { id: 10, parent_group: null, filter_type: 'OR' },
    ]
    link.group.filters.push({
      ...link.group.filters[0],
      id: 2,
      group: 10,
      value: { formula: 'Belgium', mode: 'raw' },
    })
    link.empty_behavior = 'apply_alternative'
    link.alternative_group = conditionGroup('Fallback')
    testApp.store.commit('dashboardApplication/SET_WIDGETS', [
      country,
      owner({
        id: 3,
        title: 'Unrelated',
        target_filters: [{ ...link, target_widget_id: 6 }],
      }),
      owner({
        id: 4,
        title: 'Unconfigured',
        target_filters: [
          { ...link, group: emptyGroup(), empty_behavior: 'apply_nothing' },
        ],
      }),
    ])
    const dispatch = vi.spyOn(testApp.store, 'dispatch')
    const { wrapper, filters } = await mountRefinements({ small })
    if (small) {
      expect(wrapper.find('.header__filter-name').text()).toBe(
        'serviceRefinementForms.filterTabTitle - 3'
      )
      expect(wrapper.find('.header__filter-link').classes()).toContain('active')
    }
    expect(filters.text()).toContain(
      'localBaserowTableServiceConditionalForm.noFilterTitle'
    )
    expect(filters.text()).toContain(
      'localBaserowTableServiceConditionalForm.noFilterText'
    )
    const inherited = filters.find('.dashboard-widget-filters__other')
    expect(inherited.findAll('.dashboard-widget-filters__source')).toHaveLength(
      1
    )
    expect(inherited.text()).toContain('Country')
    expect(inherited.text()).not.toContain('Unrelated')
    expect(inherited.text()).not.toContain('Unconfigured')
    expect(
      inherited.find('.dashboard-widget-filters__other-header .badge').text()
    ).toBe('3')
    expect(inherited.text()).toContain('textFilterWidget.withValue')
    expect(inherited.text()).toContain('textFilterWidget.whenEmpty')
    expect(
      inherited.findAll('input[disabled]').map((input) => input.element.value)
    ).toEqual(['France', 'Belgium', 'Fallback'])
    expect(inherited.findAll('input[disabled]')).toHaveLength(3)
    expect(inherited.findAll('.filters__item--level-2')).toHaveLength(1)
    expect(inherited.find('.filters__add').exists()).toBe(false)
    expect(inherited.find('.filters__remove').exists()).toBe(false)
    expect(
      inherited.find('.dashboard-widget-filters__source-lock').classes()
    ).toContain('iconoir-lock')
    expect(filters.find('.filters__add').exists()).toBe(true)
    expect(dispatch).not.toHaveBeenCalled()
  }
)

test('follows owner renames, condition changes, unlinking and deletion', async () => {
  const country = owner()
  testApp.store.commit('dashboardApplication/SET_WIDGETS', [country])
  const { wrapper, filters } = await mountRefinements()
  testApp.store.commit('dashboardApplication/UPDATE_WIDGET', {
    widgetId: 2,
    values: {
      title: 'Region',
      target_filters: [
        { ...country.target_filters[0], group: conditionGroup('Europe') },
      ],
    },
  })
  await flushPromises()
  expect(filters.find('.dashboard-widget-filters__source-toggle').text()).toBe(
    'Region'
  )
  expect(
    filters.find('.dashboard-widget-filters__source input[disabled]').element
      .value
  ).toBe('Europe')

  testApp.store.commit('dashboardApplication/UPDATE_WIDGET', {
    widgetId: 2,
    values: { target_filters: [] },
  })
  await flushPromises()
  expect(filters.find('.dashboard-widget-filters__other').exists()).toBe(false)
  expect(wrapper.find('.header__filter-name').text()).toBe(
    'serviceRefinementForms.filterTabTitle - 0'
  )
  expect(wrapper.find('.header__filter-link').classes()).not.toContain('active')
  expect(filters.text()).toContain(
    'localBaserowTableServiceConditionalForm.noFilterTitle'
  )

  testApp.store.commit('dashboardApplication/UPDATE_WIDGET', {
    widgetId: 2,
    values: { target_filters: owner().target_filters },
  })
  await flushPromises()
  expect(filters.find('.dashboard-widget-filters__source').exists()).toBe(true)
  testApp.store.commit('dashboardApplication/DELETE_WIDGET', 2)
  await flushPromises()
  expect(filters.find('.dashboard-widget-filters__other').exists()).toBe(false)
  expect(wrapper.find('.header__filter-name').text()).toBe(
    'serviceRefinementForms.filterTabTitle - 0'
  )
})

test('uses the current store prefix for inherited groups and their formula labels', async () => {
  const country = owner({ title: 'Private country' })
  country.target_filters[0].group.filters[0].value = {
    formula: "get('widget_data.2')",
    mode: 'simple',
    version: '0.1',
  }
  testApp.store.commit('dashboardApplication/SET_WIDGETS', [country])
  testApp.store.commit('template/dashboardApplication/SET_WIDGETS', [
    { ...country, title: 'Template country' },
  ])
  const { wrapper, filters } = await mountRefinements({
    storePrefix: 'template/',
  })
  expect(filters.text()).toContain('Template country')
  expect(filters.text()).not.toContain('Private country')
  expect(filters.find('.tiptap').text()).toContain('Template country')
  await wrapper.setProps({ storePrefix: '' })
  await flushPromises()
  expect(filters.text()).toContain('Private country')
  expect(filters.text()).not.toContain('Template country')
  expect(filters.find('.tiptap').text()).toContain('Private country')
})
