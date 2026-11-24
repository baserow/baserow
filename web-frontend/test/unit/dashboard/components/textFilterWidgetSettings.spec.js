import { flushPromises } from '@vue/test-utils'
import { TestApp } from '@baserow/test/helpers/testApp'

import TextFilterWidgetSettings from '@baserow/modules/dashboard/components/widget/TextFilterWidgetSettings'

let testApp
beforeEach(() => {
  testApp = new TestApp()
})
afterEach(async () => {
  await testApp.afterEach()
  vi.restoreAllMocks()
})

describe('TextFilterWidgetSettings', () => {
  test('keeps only the retained default when switching back to multiple values', async () => {
    const widget = {
      id: 2,
      type: 'text_filter',
      mode: 'dropdown',
      multiple: true,
      options: { formula: 'France, Belgium', mode: 'raw' },
      default_value: ['France', 'Belgium'],
    }
    const dispatch = vi.spyOn(testApp.store, 'dispatch').mockResolvedValue()
    const wrapper = await testApp.mount(TextFilterWidgetSettings, {
      props: { dashboard: { id: 1 }, widget },
    })
    dispatch.mockClear()
    const selection = wrapper.findAll('.segment-control')[1]
    await selection.findAll('button')[0].trigger('click')
    const singleSave = dispatch.mock.calls[0][1]
    expect(singleSave.values).toMatchObject({
      multiple: false,
      default_value: 'France',
    })
    expect(singleSave.originalValues.default_value).toEqual([
      'France',
      'Belgium',
    ])
    await wrapper.setProps({ widget: { ...widget, ...singleSave.values } })
    dispatch.mockClear()
    await selection.findAll('button')[1].trigger('click')
    expect(dispatch).toHaveBeenCalledWith(
      'dashboardApplication/updateWidget',
      expect.objectContaining({
        values: expect.objectContaining({
          multiple: true,
          default_value: ['France'],
        }),
        originalValues: expect.objectContaining({ default_value: 'France' }),
      })
    )
    dispatch.mockRestore()
  })
  test.each([false, true])(
    'resets defaults together with changed options (multiple: %s)',
    async (multiple) => {
      const widget = {
        id: 2,
        type: 'text_filter',
        mode: 'dropdown',
        multiple,
        options: { formula: 'France, Belgium', mode: 'raw' },
        default_value: multiple ? ['France', 'Belgium'] : 'France',
      }
      const dispatch = vi.spyOn(testApp.store, 'dispatch').mockResolvedValue()
      const wrapper = await testApp.mount(TextFilterWidgetSettings, {
        props: { dashboard: { id: 1 }, widget },
      })
      const input = wrapper.get('.formula-input-field__raw-input input')
      dispatch.mockClear()
      await input.setValue('France, Belgium')
      await flushPromises()
      expect(dispatch).not.toHaveBeenCalled()
      await input.setValue('Germany, Spain')
      await flushPromises()
      expect(dispatch).toHaveBeenCalledOnce()
      expect(dispatch).toHaveBeenCalledWith(
        'dashboardApplication/updateWidget',
        expect.objectContaining({
          values: expect.objectContaining({
            options: { formula: 'Germany, Spain', mode: 'raw' },
            default_value: multiple ? [] : '',
          }),
          originalValues: expect.objectContaining({
            options: widget.options,
            default_value: widget.default_value,
          }),
        })
      )
      dispatch.mockRestore()
    }
  )
  test('selects and clears a default from source context', async () => {
    const widget = {
      id: 2,
      type: 'text_filter',
      mode: 'dropdown',
      multiple: false,
      default_value: '',
      options: {
        formula: "get('table_context.1.field_10.*.value')",
        mode: 'advanced',
      },
    }
    const store = testApp.store
    store.commit('dashboardApplication/SET_WIDGETS', [widget])
    store.commit('dashboardApplication/SET_DATA_SOURCES', [
      {
        id: 1,
        table_id: 1,
        context_data: { field_10: [{ value: 'France' }, { value: 'Belgium' }] },
      },
    ])
    const get = vi.spyOn(store.$client, 'get')
    const dispatch = vi.spyOn(store, 'dispatch')
    const wrapper = await testApp.mount(TextFilterWidgetSettings, {
      props: { dashboard: { id: 1 }, widget },
    })
    await flushPromises()
    expect(get).not.toHaveBeenCalled()
    dispatch.mockResolvedValue()
    const dropdown = wrapper
      .findAll('.control')
      .find((control) =>
        control.text().includes('textFilterWidget.defaultValue')
      )
    await dropdown.get('.dropdown__selected').trigger('click')
    expect(
      dropdown.findAll('.select__item-name-text').map((item) => item.text())
    ).toEqual(['France', 'Belgium'])
    await dropdown.findAll('.select__item-link')[1].trigger('click')
    expect(dispatch).toHaveBeenCalledWith(
      'dashboardApplication/updateWidget',
      expect.objectContaining({
        values: expect.objectContaining({ default_value: 'Belgium' }),
      })
    )
    await wrapper.setProps({ widget: { ...widget, default_value: 'Belgium' } })
    expect(dropdown.get('.dropdown__selected-text').text()).toBe('Belgium')
    await dropdown.get('.select__footer button').trigger('click')
    expect(dispatch).toHaveBeenCalledWith(
      'dashboardApplication/updateWidget',
      expect.objectContaining({
        values: expect.objectContaining({ default_value: '' }),
      })
    )
    await wrapper.setProps({
      widget: { ...widget, default_value: 'Archived country' },
    })
    expect(dropdown.get('.dropdown__selected-text').text()).toBe(
      'Archived country'
    )
    await wrapper.setProps({
      widget: { ...widget, multiple: true, default_value: ['France'] },
    })
    await dropdown.get('.dropdown__selected').trigger('click')
    await dropdown.findAll('.select__item-link')[1].trigger('click')
    expect(dispatch).toHaveBeenCalledWith(
      'dashboardApplication/updateWidget',
      expect.objectContaining({
        values: expect.objectContaining({
          default_value: ['France', 'Belgium'],
        }),
      })
    )
    await wrapper.setProps({
      widget: {
        ...widget,
        multiple: true,
        default_value: ['France', 'Belgium'],
      },
    })
    expect(dropdown.get('.dropdown__selected-text').text()).toBe(
      'France, Belgium'
    )
    await dropdown.get('.select__footer button').trigger('click')
    expect(dispatch).toHaveBeenCalledWith(
      'dashboardApplication/updateWidget',
      expect.objectContaining({
        values: expect.objectContaining({ default_value: [] }),
      })
    )
    await wrapper.setProps({ widget: { ...widget, mode: 'input' } })
    expect(dropdown.find('.dropdown').exists()).toBe(false)
    expect(dropdown.find('input').exists()).toBe(true)
    dispatch.mockRestore()
    get.mockRestore()
  })
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
        values: { multiple: true, default_value: [] },
      })
    )
    dispatch.mockRestore()
  })
  test('renders literal settings and saves clearing through the widget store', async () => {
    const dispatch = vi.spyOn(testApp.store, 'dispatch').mockResolvedValue()
    const wrapper = await testApp.mount(TextFilterWidgetSettings, {
      global: { provide: { createDashboardWidget: vi.fn() } },
      props: {
        dashboard: { id: 1 },
        widget: {
          id: 2,
          placeholder: 'Type here',
          default_value: 'Initial',
        },
      },
    })
    expect(wrapper.html()).toMatchSnapshot()
    const inputs = wrapper
      .findAll('.control input')
      .filter(
        (input) =>
          input.attributes('type') !== 'checkbox' &&
          !input.classes().includes('select__search-input')
      )
    expect(inputs).toHaveLength(2)
    await inputs[0].setValue('')
    await inputs[0].trigger('blur')
    await flushPromises()
    expect(dispatch).toHaveBeenCalledWith('dashboardApplication/updateWidget', {
      widgetId: 2,
      values: { placeholder: '' },
      originalValues: { placeholder: 'Type here' },
    })
    await inputs[1].setValue("get('literal')")
    await inputs[1].trigger('blur')
    await flushPromises()
    expect(dispatch).toHaveBeenCalledWith('dashboardApplication/updateWidget', {
      widgetId: 2,
      values: { default_value: "get('literal')" },
      originalValues: { default_value: 'Initial' },
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

test('toggles a target without opening its conditions or losing either group', async () => {
  const { wrapper, widget, dispatch, fetch } = await mountTargets({
    linked: true,
  })
  widget.target_filters[0].group = conditionGroup('Country')
  widget.target_filters[0].empty_behavior = 'apply_alternative'
  widget.target_filters[0].alternative_group = conditionGroup('Fallback')
  widget.target_filters.push({
    target_widget_id: 5,
    group: conditionGroup('Orders'),
    empty_behavior: 'apply_nothing',
  })
  await flushPromises()
  const original = JSON.parse(JSON.stringify(widget.target_filters))
  const toggle = wrapper.find('[role="switch"]')
  expect(toggle.attributes('aria-checked')).toBe('true')
  await toggle.trigger('click')
  await flushPromises()
  expect(widget.target_filters).toEqual([
    { ...original[0], enabled: false },
    original[1],
  ])
  expect(toggle.attributes('aria-checked')).toBe('false')
  expect(wrapper.find('.dashboard-widget-filter-target').text()).toContain(
    'textFilterWidget.targetDisabled'
  )
  expect(
    wrapper.findComponent({ name: 'WidgetFilterConfigurationModal' }).exists()
  ).toBe(false)
  expect(fetch).not.toHaveBeenCalled()
  expect(dispatch).toHaveBeenCalledOnce()
  await toggle.trigger('click')
  await flushPromises()
  expect(widget.target_filters).toEqual([
    { ...original[0], enabled: true },
    original[1],
  ])
  expect(toggle.attributes('aria-checked')).toBe('true')
})

test('associates one existing widget and opens its conditions', async () => {
  const { wrapper, widget, dispatch, fetch, namespace } = await mountTargets({
    prefix: 'template/',
  })
  await button(wrapper, 'textFilterWidget.addWidgets').trigger('click')
  expect(option(wrapper, 'Other filter')).toBeUndefined()
  expect(
    option(wrapper, 'New widget')
      .element.closest('li')
      .classList.contains('disabled')
  ).toBe(true)
  await option(wrapper, 'New widget').trigger('click')
  expect(dispatch).not.toHaveBeenCalled()
  await button(wrapper, 'action.cancel').trigger('click')
  expect(widget.target_filters).toHaveLength(0)
  await button(wrapper, 'textFilterWidget.addWidgets').trigger('click')
  await option(wrapper, 'Orders').trigger('click')
  await flushPromises()
  expect(widget.target_filters.map((link) => link.target_widget_id)).toEqual([
    5,
  ])
  expect(wrapper.findAll('.dashboard-widget-filter-target')).toHaveLength(1)
  expect(
    wrapper
      .findComponent({ name: 'WidgetFilterConfigurationModal' })
      .props('target').id
  ).toBe(5)
  expect(fetch).toHaveBeenCalled()
  expect(dispatch).toHaveBeenCalledOnce()
  expect(dispatch).toHaveBeenCalledWith(
    `${namespace}/updateWidget`,
    expect.objectContaining({ widgetId: 2 })
  )
  expect(testApp.store.getters[`${namespace}/getSelectedWidgetId`]).toBe(2)
})

test('does not present disabled filter links as other applied conditions', async () => {
  const { wrapper } = await mountTargets({ linked: true })
  const other = testApp.store.getters['dashboardApplication/getWidgets'].find(
    (widget) => widget.id === 9
  )
  other.target_filters[0].enabled = false
  await wrapper.find('.dashboard-widget-filter-target').trigger('click')
  await flushPromises()
  const modal = wrapper.findComponent({
    name: 'WidgetFilterConfigurationModal',
  })
  expect(modal.find('.dashboard-widget-filters__other').text()).not.toContain(
    'Other filter'
  )
  expect(
    modal.find('.dashboard-widget-filters__other-header .badge').text()
  ).toBe('1')
})

test('separates editable conditions from other owners without changing their rules', async () => {
  const { wrapper, widget, dispatch, fetch } = await mountTargets({
    linked: true,
  })
  expect(wrapper.find('.dashboard-widget-filter-target').text()).toContain(
    'textFilterWidget.setUpConditions'
  )
  await wrapper.find('.dashboard-widget-filter-target').trigger('click')
  await flushPromises()
  const modal = wrapper.findComponent({
    name: 'WidgetFilterConfigurationModal',
  })
  const otherConditions = modal.find('.dashboard-widget-filters__other')
  const heading = otherConditions.find(
    '.dashboard-widget-filters__other-header'
  )
  expect(heading.text()).toContain('textFilterWidget.otherConditions')
  expect(heading.find('.badge').text()).toBe('2')
  expect(modal.findAllComponents({ name: 'TargetFilterGroup' })).toHaveLength(1)

  for (const summary of otherConditions.findAll(
    '.dashboard-widget-filters__source-toggle'
  )) {
    expect(summary.attributes('aria-expanded')).toBe('false')
    await summary.trigger('click')
  }
  const groups = otherConditions.findAllComponents({
    name: 'TargetFilterGroup',
  })
  expect(groups).toHaveLength(2)
  for (const group of groups) {
    expect(group.find('.filters__add').exists()).toBe(false)
    expect(group.find('.filters__remove').exists()).toBe(false)
  }
  const sources = otherConditions.findAll('.dashboard-widget-filters__source')
  for (const [index, tooltip] of [
    'textFilterWidget.editWidgetConditions',
    'textFilterWidget.editFilterConditions',
  ].entries()) {
    const lock = sources[index].find('.dashboard-widget-filters__source-lock')
    expect(lock.classes()).toContain('iconoir-lock')
    await lock.trigger('mouseenter')
    expect(document.querySelector('.tooltip__content').textContent).toBe(
      tooltip
    )
    await lock.trigger('mouseleave')
  }
  const operators = modal.findAll('.dashboard-widget-filters__operator')
  expect(operators.map((operator) => operator.find('.badge').text())).toEqual([
    'AND',
    'AND',
  ])
  expect(operators[0].element.nextElementSibling).toBe(otherConditions.element)
  expect(operators[1].element.previousElementSibling).toBe(sources[0].element)
  expect(operators[1].element.nextElementSibling).toBe(sources[1].element)
  expect(dispatch).not.toHaveBeenCalled()
  expect(fetch).toHaveBeenCalledOnce()

  await modal.find('.filters__add').trigger('click')
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

test('shows both cases together and keeps alternative conditions apart', async () => {
  const { wrapper, widget, dispatch } = await mountTargets({ linked: true })
  await wrapper.find('.dashboard-widget-filter-target').trigger('click')
  await flushPromises()
  const modal = wrapper.findComponent({
    name: 'WidgetFilterConfigurationModal',
  })
  const titles = modal
    .findAll('.dashboard-widget-filters__case-title')
    .map((title) => title.text())
  expect(titles).toEqual([
    'textFilterWidget.withValueTitle',
    'textFilterWidget.whenEmptyTitle',
  ])
  expect(modal.find('.filters__none').exists()).toBe(false)
  // The empty behavior is visible without switching to another tab.
  expect(modal.find('.dashboard-widget-filters__empty-behavior').exists()).toBe(
    true
  )
  expect(modal.findAllComponents({ name: 'TargetFilterGroup' })).toHaveLength(1)

  await modal
    .find('.dashboard-widget-filters__empty-behavior .dropdown__selected')
    .trigger('click')
  await option(wrapper, 'textFilterWidget.apply_alternative').trigger('click')
  await flushPromises()
  expect(modal.findAllComponents({ name: 'TargetFilterGroup' })).toHaveLength(2)
  const emptyCase = modal.findAll('.dashboard-widget-filters__case')[1]
  expect(emptyCase.text()).toContain(
    'textFilterWidget.whenEmptyAlternativeHelp'
  )
  await emptyCase.find('.filters__add').trigger('click')
  await flushPromises()
  expect(widget.target_filters[0].group.filters).toHaveLength(0)
  expect(widget.target_filters[0].alternative_group.filters).toHaveLength(1)
  expect(widget.target_filters[0].alternative_group.filters[0].field).toBe(99)
  // Each case keeps its own conditions.
  expect(
    modal
      .findAll('.dashboard-widget-filters__case')[0]
      .find('.filters__item')
      .exists()
  ).toBe(false)
  expect(dispatch).toHaveBeenCalled()
})

test('keeps other owners’ alternative conditions read-only while editing the current filter', async () => {
  const { wrapper, dispatch } = await mountTargets({ linked: true })
  const source =
    testApp.store.getters['dashboardApplication/getDataSourceById'](4)
  source.filter_type = 'OR'
  const other = testApp.store.getters['dashboardApplication/getWidgets'].find(
    (w) => w.id === 9
  )
  const alternative = conditionGroup('Fallback')
  alternative.filter_groups = [
    { id: 10, filter_type: 'OR', parent_group: null },
  ]
  alternative.filters[0].group = 10
  alternative.filters.push({ ...alternative.filters[0], id: 2 })
  other.target_filters[0].empty_behavior = 'apply_alternative'
  other.target_filters[0].alternative_group = alternative

  await wrapper.find('.dashboard-widget-filter-target').trigger('click')
  await flushPromises()
  const modal = wrapper.findComponent({
    name: 'WidgetFilterConfigurationModal',
  })
  expect(
    modal.find('.dashboard-widget-filters__other-header .badge').text()
  ).toBe('4')
  const section = modal.find('.dashboard-widget-filters__other')
  const sources = section.findAll('.dashboard-widget-filters__source')
  expect(sources).toHaveLength(2)
  await sources[1]
    .find('.dashboard-widget-filters__source-toggle')
    .trigger('click')
  expect(sources[1].text()).toContain('textFilterWidget.withValue')
  expect(sources[1].text()).toContain('textFilterWidget.whenEmpty')
  const groups = sources[1].findAllComponents({ name: 'TargetFilterGroup' })
  expect(groups).toHaveLength(2)
  for (const group of groups) {
    expect(group.find('.filters__add').exists()).toBe(false)
    expect(group.find('.filters__remove').exists()).toBe(false)
  }
  expect(sources[1].findAll('input:disabled')).toHaveLength(3)
  expect(
    modal
      .findAll('.dashboard-widget-filters__operator')
      .map((operator) => operator.find('.badge').text())
  ).toEqual(['OR', 'OR'])
  expect(dispatch).not.toHaveBeenCalled()

  await modal.find('.dashboard-widget-filters__footer button').trigger('click')
  await vi.waitFor(() =>
    expect(wrapper.find('.modal__wrapper').exists()).toBe(false)
  )
  await wrapper.find('.dashboard-widget-filter-target').trigger('click')
  await flushPromises()
  const reopened = wrapper.findComponent({
    name: 'WidgetFilterConfigurationModal',
  })
  expect(reopened.find('.dashboard-widget-filters__other').exists()).toBe(true)
  expect(dispatch).not.toHaveBeenCalled()
})

test('shows the only other source directly without adding another expansion step', async () => {
  const { wrapper, dispatch } = await mountTargets({ linked: true })
  testApp.store.getters['dashboardApplication/getDataSourceById'](4).filters =
    []
  await wrapper.find('.dashboard-widget-filter-target').trigger('click')
  await flushPromises()
  const modal = wrapper.findComponent({
    name: 'WidgetFilterConfigurationModal',
  })
  const section = modal.find('.dashboard-widget-filters__other')
  expect(section.findAll('.dashboard-widget-filters__source')).toHaveLength(1)
  expect(
    section
      .find('.dashboard-widget-filters__source-toggle')
      .attributes('aria-expanded')
  ).toBe('true')
  expect(section.findAll('input:disabled')).toHaveLength(1)
  expect(section.find('input:disabled').element.value).toBe('Other')
  expect(dispatch).not.toHaveBeenCalled()
})

test('saves a new condition group of the value case once', async () => {
  const { wrapper, widget, dispatch } = await mountTargets({ linked: true })
  await wrapper.find('.dashboard-widget-filter-target').trigger('click')
  await flushPromises()
  const modal = wrapper.findComponent({
    name: 'WidgetFilterConfigurationModal',
  })
  await modal
    .findAll('.dashboard-widget-filters__case')[0]
    .findAll('.filters__add')[1]
    .trigger('click')
  await flushPromises()
  expect(dispatch).toHaveBeenCalledOnce()
  expect(widget.target_filters[0].group.filter_groups).toHaveLength(1)
  expect(widget.target_filters[0].group.filters).toHaveLength(1)
  expect(widget.target_filters[0].group.filters[0].group).toBe(
    widget.target_filters[0].group.filter_groups[0].id
  )
  expect(modal.findAll('.filters__item--level-2')).toHaveLength(1)
})

test('omits other conditions when the widget and other filters have none', async () => {
  const { wrapper } = await mountTargets({ linked: true })
  testApp.store.getters['dashboardApplication/getDataSourceById'](4).filters =
    []
  testApp.store.getters['dashboardApplication/getWidgets'].find(
    (w) => w.id === 9
  ).target_filters = []
  await wrapper.find('.dashboard-widget-filter-target').trigger('click')
  await flushPromises()
  const modal = wrapper.findComponent({
    name: 'WidgetFilterConfigurationModal',
  })
  expect(modal.find('.dashboard-widget-filters__operator').exists()).toBe(false)
  expect(modal.find('.dashboard-widget-filters__other').exists()).toBe(false)
  expect(modal.find('.filters__add').exists()).toBe(true)
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

test('a new filter can target widgets without choosing a table', async () => {
  const wrapper = await testApp.mount(TextFilterWidgetSettings, {
    props: {
      dashboard: { id: 1 },
      widget: {
        id: 2,
        type: 'text_filter',
        mode: 'input',
        multiple: false,
        default_value: '',
        target_filters: [],
      },
    },
  })
  expect(wrapper.text()).toContain('textFilterWidget.howItLooks')
  expect(wrapper.text()).toContain('textFilterWidget.targets')
  expect(wrapper.text()).not.toContain('filterTableSetup.question')
  await button(wrapper, 'textFilterWidget.addWidgets').trigger('click')
  expect(
    wrapper.find('.dashboard-widget-filter-targets__create').exists()
  ).toBe(true)
})

test.each([
  ['input', true],
  ['dropdown', false],
])('a %s filter shows the placeholder setting: %s', async (mode, shown) => {
  const wrapper = await testApp.mount(TextFilterWidgetSettings, {
    props: {
      dashboard: { id: 1 },
      widget: {
        id: 2,
        type: 'text_filter',
        mode,
        multiple: false,
        default_value: '',
        options: { formula: '', mode: 'raw' },
        target_filters: [],
      },
    },
  })

  expect(wrapper.text().includes('textFilterWidget.placeholder')).toBe(shown)
})

describe('creating widgets from a filter', () => {
  const fields = [
    { id: 21, name: 'Name', type: 'text', primary: true, order: 0 },
  ]
  const filterWidget = (values = {}) => ({
    id: 2,
    type: 'text_filter',
    title: 'Filter',
    mode: 'input',
    multiple: false,
    default_value: '',
    target_filters: [],
    apply_to_new_widgets: false,
    ...values,
  })
  const configurationStub = {
    name: 'ConfigureFilterTargetModal',
    props: ['widgetId', 'linkFilterWidgetId'],
    emits: ['configured', 'hidden'],
    template: '<div />',
    methods: {
      show() {},
      hide() {
        this.$emit('hidden')
      },
    },
  }

  async function mountFilters(widgets) {
    const store = testApp.store
    store.commit('dashboardApplication/SET_DASHBOARD_ID', 1)
    store.commit('dashboardApplication/SET_WIDGETS', widgets)
    store.commit('dashboardApplication/SET_DATA_SOURCES', [])
    vi.spyOn(store.$client, 'get').mockResolvedValue({ data: fields })
    const dispatch = vi
      .spyOn(store, 'dispatch')
      .mockImplementation(async (action, payload) => {
        if (action.endsWith('/updateWidget'))
          store.commit('dashboardApplication/UPDATE_WIDGET', payload)
      })
    const createDashboardWidget = vi.fn(async () => {
      const created = {
        id: 30,
        type: 'summary',
        title: 'Summary',
        data_source_id: 31,
      }
      store.commit('dashboardApplication/SET_WIDGETS', [...widgets, created])
      store.commit('dashboardApplication/SET_DATA_SOURCES', [
        { id: 31, table_id: null, filters: [] },
      ])
      return created
    })
    const wrapper = await testApp.mount(TextFilterWidgetSettings, {
      props: { dashboard: { id: 1, workspace: { id: 1 } }, widget: widgets[0] },
      global: {
        provide: { createDashboardWidget },
        stubs: { ConfigureFilterTargetModal: configurationStub },
      },
    })
    dispatch.mockClear()
    return { wrapper, createDashboardWidget, dispatch, store }
  }

  async function createSummary(wrapper) {
    await button(wrapper, 'textFilterWidget.addWidgets').trigger('click')
    await wrapper
      .findAll('.dashboard-widget-filter-targets__create')
      .at(-1)
      .trigger('click')
    const modal = wrapper.findComponent({ name: 'CreateWidgetModal' })
    expect(modal.props('hideFilters')).toBe(true)
    modal.vm.$emit(
      'widget-variation-selected',
      testApp.$registry.get('dashboardWidget', 'summary').variations[0]
    )
    await flushPromises()
  }

  test('opens the setup of the new widget for this filter, then just closes it', async () => {
    const { wrapper, createDashboardWidget, dispatch, store } =
      await mountFilters([filterWidget()])
    await createSummary(wrapper)
    expect(createDashboardWidget).toHaveBeenCalledExactlyOnceWith(
      expect.objectContaining({ type: 'summary', select: false })
    )
    const configuration = wrapper.findComponent({
      name: 'ConfigureFilterTargetModal',
    })
    expect(configuration.props('widgetId')).toBe(30)
    expect(configuration.props('linkFilterWidgetId')).toBe(2)

    // The modal saved the widget and its conditions as they were set.
    configuration.vm.$emit(
      'configured',
      store.getters['dashboardApplication/getWidgets'].find(
        (widget) => widget.id === 30
      )
    )
    await flushPromises()
    expect(dispatch).not.toHaveBeenCalled()
    expect(
      wrapper.findComponent({ name: 'ConfigureFilterTargetModal' }).exists()
    ).toBe(false)
    expect(
      wrapper.findComponent({ name: 'WidgetFilterConfigurationModal' }).exists()
    ).toBe(false)
  })

  test('closing configuration leaves the filter unlinked', async () => {
    const { wrapper, dispatch } = await mountFilters([filterWidget()])
    await createSummary(wrapper)
    wrapper
      .findComponent({ name: 'ConfigureFilterTargetModal' })
      .vm.$emit('hidden')
    await flushPromises()
    expect(dispatch).not.toHaveBeenCalled()
    expect(
      wrapper.findComponent({ name: 'WidgetFilterConfigurationModal' }).exists()
    ).toBe(false)
  })

  test('changing filters dismisses the guided configuration', async () => {
    const second = filterWidget({ id: 5 })
    const { wrapper } = await mountFilters([filterWidget(), second])
    await createSummary(wrapper)
    expect(
      wrapper.findComponent({ name: 'ConfigureFilterTargetModal' }).exists()
    ).toBe(true)
    await wrapper.setProps({ widget: second })
    expect(
      wrapper.findComponent({ name: 'ConfigureFilterTargetModal' }).exists()
    ).toBe(false)
  })
})
