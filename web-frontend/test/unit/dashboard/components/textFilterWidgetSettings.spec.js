import { flushPromises } from '@vue/test-utils'
import { TestApp } from '@baserow/test/helpers/testApp'
import TextFilterWidgetSettings from '@baserow/modules/dashboard/components/widget/TextFilterWidgetSettings'

let testApp
beforeEach(() => {
  testApp = new TestApp()
})
afterEach(() => testApp.afterEach())

describe('TextFilterWidgetSettings', () => {
  test('offers single or multiple selection only for dropdowns', async () => {
    const widget = {
      id: 2,
      mode: 'input',
      multiple: false,
      placeholder: '',
      default_value: '',
    }
    const dispatch = vi.spyOn(testApp.store, 'dispatch').mockResolvedValue()
    const wrapper = await testApp.mount(TextFilterWidgetSettings, {
      props: { dashboard: { id: 1 }, widget },
    })
    expect(wrapper.findAll('.segment-control')).toHaveLength(1)
    await wrapper.setProps({ widget: { ...widget, mode: 'dropdown' } })
    const selections = wrapper.findAll('.segment-control')[1].findAll('button')
    expect(selections.map((button) => button.text())).toEqual([
      'textFilterWidget.singleValue',
      'textFilterWidget.multipleValues',
    ])
    await selections[1].trigger('click')
    expect(dispatch).toHaveBeenCalledWith(
      'dashboardApplication/updateWidget',
      expect.objectContaining({
        values: expect.objectContaining({ mode: 'dropdown', multiple: true }),
      })
    )
    dispatch.mockRestore()
  })
  test('renders literal settings and saves clearing through the widget store', async () => {
    const dispatch = vi.spyOn(testApp.store, 'dispatch').mockResolvedValue()
    const wrapper = await testApp.mount(TextFilterWidgetSettings, {
      props: {
        dashboard: { id: 1 },
        widget: { id: 2, placeholder: 'Type here', default_value: 'Initial' },
      },
    })
    expect(wrapper.html()).toMatchSnapshot()
    const inputs = wrapper
      .findAll('.control input')
      .filter((input) => !input.classes().includes('select__search-input'))
    expect(inputs).toHaveLength(2)
    await inputs[0].setValue('')
    await inputs[0].trigger('blur')
    await flushPromises()
    expect(dispatch).toHaveBeenCalledWith('dashboardApplication/updateWidget', {
      widgetId: 2,
      values: {
        mode: 'input',
        multiple: false,
        options: {},
        placeholder: '',
        default_value: 'Initial',
        target_filters: [],
      },
      originalValues: {
        mode: 'input',
        multiple: false,
        options: {},
        placeholder: 'Type here',
        default_value: 'Initial',
        target_filters: [],
      },
    })
    await inputs[1].setValue("get('literal')")
    await inputs[1].trigger('blur')
    await flushPromises()
    expect(dispatch).toHaveBeenCalledWith('dashboardApplication/updateWidget', {
      widgetId: 2,
      values: {
        mode: 'input',
        multiple: false,
        options: {},
        placeholder: 'Type here',
        default_value: "get('literal')",
        target_filters: [],
      },
      originalValues: {
        mode: 'input',
        multiple: false,
        options: {},
        placeholder: 'Type here',
        default_value: 'Initial',
        target_filters: [],
      },
    })
    dispatch.mockRestore()
  })
})

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
      field: 99,
      type: 'equal',
      group: null,
      value: { formula: value, mode: 'raw' },
    },
  ],
})
async function mountTargets({ linked = false, prefix = '' } = {}) {
  const namespace = `${prefix}dashboardApplication`
  const store = testApp.store
  store.commit(`${namespace}/SET_DASHBOARD_ID`, 1)
  store.commit(`${namespace}/SET_WIDGETS`, [
    {
      id: 2,
      type: 'text_filter',
      title: 'Country',
      target_filters: linked
        ? [
            {
              target_widget_id: 3,
              group: emptyGroup(),
              empty_behavior: 'apply_nothing',
            },
          ]
        : [],
    },
    { id: 3, type: 'summary', title: 'Revenue', data_source_id: 4 },
    { id: 5, type: 'summary', title: 'Orders', data_source_id: 4 },
    { id: 7, type: 'summary', title: 'New widget', data_source_id: 8 },
    {
      id: 9,
      type: 'text_filter',
      title: 'Other filter',
      target_filters: [
        {
          target_widget_id: 3,
          group: conditionGroup('Other'),
          empty_behavior: 'apply_nothing',
        },
      ],
    },
  ])
  store.commit(`${namespace}/SET_DATA_SOURCES`, [
    { id: 4, table_id: 1, ...conditionGroup('Permanent') },
    { id: 8, table_id: null, ...emptyGroup() },
  ])
  store.commit(`${namespace}/SELECT_WIDGET`, 2)
  const fetch = vi
    .spyOn(store.$client, 'get')
    .mockResolvedValue({ data: [{ id: 99, name: 'Country', type: 'text' }] })
  const dispatch = vi
    .spyOn(store, 'dispatch')
    .mockImplementation(async (action, payload) => {
      if (action === `${namespace}/updateWidget`)
        store.commit(`${namespace}/UPDATE_WIDGET`, payload)
    })
  const widget = store.getters[`${namespace}/getWidgets`].find(
    (w) => w.id === 2
  )
  const wrapper = await testApp.mount(TextFilterWidgetSettings, {
    props: { widget, dashboard: { id: 1 }, storePrefix: prefix },
  })
  dispatch.mockClear()
  return { wrapper, widget, dispatch, fetch, namespace }
}
const button = (wrapper, text) =>
  wrapper.findAll('button').find((b) => b.text() === text)
const option = (wrapper, text) =>
  wrapper
    .findAll('.select__item-link')
    .find((item) => item.text().includes(text))

test('adds eligible widgets together, keeps existing conditions and isolates template saves', async () => {
  const { wrapper, widget, dispatch, fetch, namespace } = await mountTargets({
    prefix: 'template/',
  })
  expect(wrapper.findAll('.dashboard-widget-filter-target')).toHaveLength(0)
  expect(wrapper.text()).toContain('textFilterWidget.noTargets')
  await button(wrapper, 'textFilterWidget.addWidgets').trigger('click')
  expect(option(wrapper, 'Other filter')).toBeUndefined()
  expect(
    option(wrapper, 'New widget')
      .element.closest('li')
      .classList.contains('disabled')
  ).toBe(true)
  await option(wrapper, 'New widget').trigger('click')
  expect(button(wrapper, 'action.add').attributes('disabled')).toBeDefined()
  await option(wrapper, 'Revenue').trigger('click')
  await option(wrapper, 'Orders').trigger('click')
  expect(dispatch).not.toHaveBeenCalled()
  await button(wrapper, 'action.cancel').trigger('click')
  expect(widget.target_filters).toHaveLength(0)
  await button(wrapper, 'textFilterWidget.addWidgets').trigger('click')
  expect(button(wrapper, 'action.add').attributes('disabled')).toBeDefined()
  await option(wrapper, 'Revenue').trigger('click')
  await option(wrapper, 'Orders').trigger('click')
  await button(wrapper, 'action.add').trigger('click')
  await flushPromises()
  expect(widget.target_filters.map((link) => link.target_widget_id)).toEqual([
    3, 5,
  ])
  expect(wrapper.findAll('.dashboard-widget-filter-target')).toHaveLength(2)
  expect(wrapper.find('.dashboard-widget-filter-target').text()).toContain(
    'textFilterWidget.setUpConditions'
  )
  expect(fetch).not.toHaveBeenCalled()
  expect(dispatch).toHaveBeenCalledOnce()
  expect(dispatch).toHaveBeenCalledWith(
    `${namespace}/updateWidget`,
    expect.objectContaining({ widgetId: 2 })
  )
  expect(testApp.store.getters[`${namespace}/getSelectedWidgetId`]).toBe(2)
})

test('opens conditions directly, locks other owners, and counts only this filter’s conditions', async () => {
  const { wrapper, widget, dispatch, fetch } = await mountTargets({
    linked: true,
  })
  expect(wrapper.find('.dashboard-widget-filter-target').text()).toContain(
    'textFilterWidget.setUpConditions'
  )
  await wrapper.find('.dashboard-widget-filter-target').trigger('click')
  await flushPromises()
  const groups = wrapper.findAllComponents({ name: 'TargetFilterGroup' })
  expect(groups.filter((g) => g.props('readOnly'))).toHaveLength(2)
  expect(dispatch).not.toHaveBeenCalled()
  expect(fetch).toHaveBeenCalledOnce()
  for (const group of groups.filter((g) => g.props('readOnly'))) {
    expect(group.find('.filters__add').exists()).toBe(false)
    expect(group.find('.filters__remove').exists()).toBe(false)
  }
  await groups
    .find((g) => !g.props('readOnly'))
    .find('.filters__add')
    .trigger('click')
  await flushPromises()
  expect(widget.target_filters[0].group.filters).toHaveLength(1)
  expect(wrapper.find('.dashboard-widget-filter-target').text()).toContain(
    'textFilterWidget.conditionCount'
  )
  expect(dispatch).toHaveBeenCalledOnce()
  expect(
    testApp.store.getters['dashboardApplication/getDataSourceById'](4)
      .filters[0].value.formula
  ).toBe('Permanent')
  expect(
    testApp.store.getters['dashboardApplication/getWidgets'].find(
      (w) => w.id === 9
    ).target_filters[0].group.filters[0].value.formula
  ).toBe('Other')
})

test('configures empty selection behavior and alternative conditions inside the modal', async () => {
  const { wrapper, widget } = await mountTargets({ linked: true })
  await wrapper.find('.dashboard-widget-filter-target').trigger('click')
  await flushPromises()
  await wrapper
    .find('.dashboard-widget-filters .dropdown__selected')
    .trigger('click')
  await option(wrapper, 'textFilterWidget.apply_alternative').trigger('click')
  await flushPromises()
  const alternative = wrapper.find(
    '.dashboard-widget-filters__group--alternative'
  )
  expect(alternative.exists()).toBe(true)
  await alternative.find('.filters__add').trigger('click')
  await flushPromises()
  expect(widget.target_filters[0].group.filters).toHaveLength(0)
  expect(widget.target_filters[0].alternative_group.filters).toHaveLength(1)
  expect(widget.target_filters[0].alternative_group.filters[0].field).toBe(99)
})

test('removes only the selected link through its context menu', async () => {
  const { wrapper, widget, dispatch } = await mountTargets({ linked: true })
  widget.target_filters.push({
    target_widget_id: 5,
    group: conditionGroup('Orders'),
    empty_behavior: 'apply_nothing',
  })
  await flushPromises()
  await wrapper.find('.dashboard-widget-filter-target button').trigger('click')
  await flushPromises()
  expect(wrapper.find('.dashboard-widget-filters').exists()).toBe(false)
  await wrapper.find('.context__menu-item-link--delete').trigger('click')
  await flushPromises()
  expect(widget.target_filters).toHaveLength(1)
  expect(widget.target_filters[0].target_widget_id).toBe(5)
  expect(widget.target_filters[0].group.filters[0].value.formula).toBe('Orders')
  expect(wrapper.find('.dashboard-widget-filter-target').text()).toContain(
    'Orders'
  )
  expect(dispatch).toHaveBeenCalledOnce()
})

test('retries loading fields without showing an empty condition editor after failure', async () => {
  const { wrapper, fetch } = await mountTargets({ linked: true })
  fetch.mockRejectedValueOnce(new Error('offline'))
  await wrapper.find('.dashboard-widget-filter-target').trigger('click')
  await flushPromises()
  expect(wrapper.text()).toContain('textFilterWidget.fieldsError')
  expect(wrapper.findComponent({ name: 'TargetFilterGroup' }).exists()).toBe(
    false
  )
  await button(wrapper, 'action.retry').trigger('click')
  await flushPromises()
  expect(wrapper.findComponent({ name: 'TargetFilterGroup' }).exists()).toBe(
    true
  )
})
