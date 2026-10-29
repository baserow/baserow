import { flushPromises } from '@vue/test-utils'
import { TestApp } from '@baserow/test/helpers/testApp'
import TextFilterWidgetSettings from '@baserow/modules/dashboard/components/widget/TextFilterWidgetSettings'

let testApp
beforeEach(() => {
  testApp = new TestApp()
})
afterEach(() => testApp.afterEach())

describe('TextFilterWidgetSettings', () => {
  test('renders literal settings and saves clearing through the widget store', async () => {
    const dispatch = vi.spyOn(testApp.store, 'dispatch').mockResolvedValue()
    const wrapper = await testApp.mount(TextFilterWidgetSettings, {
      props: {
        dashboard: { id: 1 },
        widget: { id: 2, placeholder: 'Type here', default_value: 'Initial' },
      },
    })
    expect(wrapper.html()).toMatchSnapshot()
    const inputs = wrapper.findAll('input')
    expect(inputs).toHaveLength(2)
    await inputs[0].setValue('')
    await inputs[0].trigger('blur')
    await flushPromises()
    expect(dispatch).toHaveBeenCalledWith('dashboardApplication/updateWidget', {
      widgetId: 2,
      values: { placeholder: '', default_value: 'Initial', target_filters: [] },
      originalValues: {
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
        placeholder: 'Type here',
        default_value: "get('literal')",
        target_filters: [],
      },
      originalValues: {
        placeholder: 'Type here',
        default_value: 'Initial',
        target_filters: [],
      },
    })
    dispatch.mockRestore()
  })
})

test('configures a target inside the input sidebar and keeps template saves isolated', async () => {
  const group = { filters: [], filter_groups: [], filter_type: 'AND' }
  const input = {
    id: 2,
    type: 'text_filter',
    title: 'Search',
    placeholder: '',
    default_value: '',
    target_filters: [],
  }
  const target = {
    id: 3,
    type: 'summary',
    title: 'Revenue',
    data_source_id: 4,
  }
  const namespace = 'template/dashboardApplication'
  testApp.store.commit(`${namespace}/SET_DASHBOARD_ID`, 1)
  testApp.store.commit(`${namespace}/SET_WIDGETS`, [
    input,
    target,
    { ...target, id: 5, title: 'Costs', data_source_id: 6 },
    { ...target, id: 7, title: 'New widget', data_source_id: 8 },
    { ...target, id: 9, type: 'chart', title: 'Chart', data_source_id: 4 },
  ])
  testApp.store.commit(`${namespace}/SET_DATA_SOURCES`, [
    {
      id: 4,
      table_id: 5,
      ...group,
      filters: [
        {
          id: 1,
          field: 99,
          type: 'equal',
          value: { formula: 'Permanent', mode: 'raw' },
        },
      ],
    },
    { id: 6, table_id: 5, ...group },
    { id: 8, table_id: null, ...group },
  ])
  testApp.store.commit(`${namespace}/SELECT_WIDGET`, 2)
  const dispatch = vi.spyOn(testApp.store, 'dispatch').mockResolvedValue()
  vi.spyOn(testApp.store.$client, 'get').mockResolvedValue({ data: [] })
  const wrapper = await testApp.mount(TextFilterWidgetSettings, {
    props: { widget: input, dashboard: { id: 1 }, storePrefix: 'template/' },
    global: {
      stubs: {
        TargetFilterGroup: {
          props: { group: Object, owner: Object, readOnly: Boolean },
          emits: ['update'],
          template: `<div v-if="readOnly" class="readonly-group">{{ owner ? owner.title : 'permanent' }}</div><button v-else class="edit-group" @click="$emit('update', { ...group, filter_type: 'OR' })">{{ owner ? 'dynamic' : 'permanent' }}</button>`,
        },
      },
    },
  })
  await wrapper
    .findAll('.dashboard-widget-filter-target__name')
    .find((node) => node.text().includes('Revenue'))
    .trigger('click')
  await flushPromises()
  expect(wrapper.html()).toMatchSnapshot()
  expect(wrapper.findAll('[role="switch"]')).toHaveLength(4)
  expect(wrapper.findAll('.header__filter-link')).toHaveLength(0)
  expect(
    wrapper.findAll('[role="switch"]')[2].attributes('aria-disabled')
  ).toBe('true')
  expect(wrapper.text()).toContain('New widget')
  expect(
    wrapper.findAll('[role="switch"]')[3].attributes('aria-disabled')
  ).toBe('false')
  expect(wrapper.text()).toContain('Chart')
  expect(dispatch).not.toHaveBeenCalled()
  await wrapper.findAll('[role="switch"]')[2].trigger('click')
  expect(dispatch).not.toHaveBeenCalled()
  await wrapper.findAll('[role="switch"]')[0].trigger('click')
  expect(dispatch).toHaveBeenLastCalledWith(
    `${namespace}/updateWidget`,
    expect.objectContaining({
      widgetId: 2,
      values: expect.objectContaining({
        target_filters: [
          { target_widget_id: 3, group, empty_behavior: 'apply_nothing' },
        ],
      }),
    })
  )
  await wrapper.setProps({
    widget: {
      ...input,
      target_filters: [
        { target_widget_id: 3, group, empty_behavior: 'apply_nothing' },
      ],
    },
  })
  await flushPromises()
  expect(
    wrapper.findAll('.select__item-name-text').map((item) => item.text())
  ).toEqual([
    'textFilterWidget.apply_nothing',
    'textFilterWidget.apply_alternative',
  ])
  expect(testApp.store.getters[`${namespace}/getSelectedWidgetId`]).toBe(2)
  const callsBeforeNameClick = dispatch.mock.calls.length
  const name = wrapper
    .findAll('.dashboard-widget-filter-target__name')
    .find((node) => node.text() === 'Revenue')
  await name.trigger('click')
  expect(wrapper.findAll('.expandable--expanded')).toHaveLength(0)
  expect(wrapper.find('[role="switch"]').attributes('aria-checked')).toBe(
    'true'
  )
  await name.trigger('click')
  expect(wrapper.findAll('.expandable--expanded')).toHaveLength(1)
  expect(dispatch).toHaveBeenCalledTimes(callsBeforeNameClick)

  const clickButton = async (label) => {
    await wrapper
      .findAll('button')
      .find((button) => button.text() === label)
      .trigger('click')
  }
  expect(wrapper.findAll('.edit-group')).toHaveLength(0)
  await wrapper.find('.header__filter-link').trigger('click')
  expect(wrapper.html()).toMatchSnapshot('normal group modal')
  expect(wrapper.findAll('.edit-group')).toHaveLength(1)
  await wrapper.find('.edit-group').trigger('click')
  expect(dispatch).toHaveBeenCalledWith(
    `${namespace}/updateWidget`,
    expect.objectContaining({
      widgetId: 2,
      values: expect.objectContaining({
        target_filters: [
          {
            target_widget_id: 3,
            empty_behavior: 'apply_nothing',
            group: { ...group, filter_type: 'OR' },
          },
        ],
      }),
    })
  )
  expect(wrapper.find('.readonly-group').text()).toBe('permanent')
  expect(dispatch).not.toHaveBeenCalledWith(
    `${namespace}/updateDataSource`,
    expect.anything()
  )
  await clickButton('action.close')
  await vi.waitFor(() =>
    expect(wrapper.findComponent({ name: 'Modal' }).vm.open).toBe(false)
  )
  await flushPromises()
  expect(wrapper.findAll('.edit-group')).toHaveLength(0)
  await wrapper.setProps({
    widget: {
      ...input,
      target_filters: [
        {
          target_widget_id: 3,
          group,
          alternative_group: group,
          empty_behavior: 'apply_alternative',
        },
      ],
    },
  })
  expect(wrapper.findAll('.edit-group')).toHaveLength(0)
  expect(wrapper.findAll('.header__filter-link')).toHaveLength(1)
  expect(wrapper.find('.header__filter-link').text()).toBe(
    'serviceRefinementForms.filterTabTitle - 1'
  )
  expect(wrapper.find('.header__filter-link').classes()).toContain(
    'active--success'
  )
  await wrapper.find('.header__filter-link').trigger('click')
  await flushPromises()
  const alternativeEditor = wrapper.find(
    '.dashboard-widget-filters__group--alternative .edit-group'
  )
  expect(alternativeEditor.text()).toBe('dynamic')
  await alternativeEditor.trigger('click')
  expect(dispatch).toHaveBeenLastCalledWith(
    `${namespace}/updateWidget`,
    expect.objectContaining({
      widgetId: 2,
      values: expect.objectContaining({
        target_filters: [
          expect.objectContaining({
            alternative_group: { ...group, filter_type: 'OR' },
          }),
        ],
      }),
    })
  )
  await clickButton('action.close')
  await wrapper.findAll('[role="switch"]')[0].trigger('click')
  expect(dispatch).toHaveBeenLastCalledWith(
    `${namespace}/updateWidget`,
    expect.objectContaining({
      values: expect.objectContaining({ target_filters: [] }),
    })
  )
  await wrapper
    .findAll('.sidebar-expandable__header')
    .find((header) => header.text().includes('Costs'))
    .trigger('click')
  await flushPromises()
  expect(wrapper.findAll('.sidebar-expandable__header')).toHaveLength(4)
  expect(wrapper.findAll('.expandable--expanded')).toHaveLength(1)
  expect(wrapper.findAll('.header__filter-link')).toHaveLength(0)
  expect(wrapper.text()).toContain('textFilterWidget.enableTargetHelp')
  await wrapper
    .findAll('.sidebar-expandable__header')
    .find((header) => header.text().includes('Costs'))
    .trigger('click')
  expect(wrapper.findAll('.expandable--expanded')).toHaveLength(0)
  expect(wrapper.findAll('.header__filter-link')).toHaveLength(0)
  expect(testApp.store.getters[`${namespace}/getSelectedWidgetId`]).toBe(2)
})

test('one modal locks permanent and other-input groups while saving only the owning input', async () => {
  const conditions = (value) => ({
    filter_type: 'OR',
    filter_groups: [],
    filters: [
      {
        id: value,
        field: 99,
        type: 'equal',
        group: null,
        value: { formula: value, mode: 'raw' },
      },
    ],
  })
  const widget = {
    id: 2,
    type: 'text_filter',
    title: 'Search',
    target_filters: [
      {
        target_widget_id: 3,
        group: { filters: [], filter_groups: [], filter_type: 'AND' },
        empty_behavior: 'apply_nothing',
      },
    ],
  }
  const other = {
    id: 4,
    type: 'text_filter',
    title: 'Other input',
    target_filters: [
      {
        target_widget_id: 3,
        group: conditions('Other'),
        empty_behavior: 'apply_nothing',
      },
    ],
  }
  const store = testApp.store
  store.commit('dashboardApplication/SET_WIDGETS', [
    widget,
    other,
    { id: 3, type: 'summary', title: 'Total', data_source_id: 5 },
  ])
  store.commit('dashboardApplication/SET_DATA_SOURCES', [
    { id: 5, table_id: 1, ...conditions('Permanent') },
  ])
  vi.spyOn(store.$client, 'get').mockResolvedValue({
    data: [{ id: 99, name: 'Name', type: 'text' }],
  })
  const dispatch = vi.spyOn(store, 'dispatch').mockResolvedValue()
  const wrapper = await testApp.mount(TextFilterWidgetSettings, {
    props: { widget, dashboard: { id: 1 } },
  })
  await wrapper
    .findAll('.sidebar-expandable__header')
    .find((header) => header.text().includes('Total'))
    .trigger('click')
  await flushPromises()
  expect(wrapper.findAll('.header__filter-link')).toHaveLength(1)
  expect(wrapper.find('.header__filter-link').text()).toBe(
    'serviceRefinementForms.filterTabTitle - 2'
  )
  await wrapper.find('.header__filter-link').trigger('click')
  await flushPromises()
  const groups = wrapper.findAllComponents({ name: 'TargetFilterGroup' })
  expect(groups.filter((group) => group.props('readOnly'))).toHaveLength(2)
  expect(wrapper.text()).toContain('Other input')
  expect(wrapper.text()).toContain('textFilterWidget.permanentGroup')
  dispatch.mockClear()
  for (const group of groups.filter((group) => group.props('readOnly'))) {
    expect(group.find('.filters__add').exists()).toBe(false)
    expect(group.find('.filters__remove').exists()).toBe(false)
  }
  expect(dispatch).not.toHaveBeenCalled()
  const editable = groups.find((group) => !group.props('readOnly'))
  await editable.find('.filters__add').trigger('click')
  await flushPromises()
  expect(dispatch).toHaveBeenCalledOnce()
  expect(dispatch).toHaveBeenLastCalledWith(
    'dashboardApplication/updateWidget',
    expect.objectContaining({
      widgetId: widget.id,
      values: expect.objectContaining({
        target_filters: [
          expect.objectContaining({
            target_widget_id: 3,
            group: expect.objectContaining({
              filters: [expect.objectContaining({ field: 99 })],
            }),
          }),
        ],
      }),
    })
  )
  expect(
    store.getters['dashboardApplication/getDataSourceById'](5).filters[0].value
      .formula
  ).toBe('Permanent')
})

test('selecting the alternative policy opens its editor and saves alternative conditions', async () => {
  const group = { filters: [], filter_groups: [], filter_type: 'AND' }
  const store = testApp.store
  store.commit('dashboardApplication/SET_WIDGETS', [
    {
      id: 2,
      type: 'text_filter',
      title: 'Search',
      placeholder: '',
      default_value: '',
      target_filters: [
        { target_widget_id: 3, group, empty_behavior: 'apply_nothing' },
      ],
    },
    { id: 3, type: 'summary', title: 'Total', data_source_id: 5 },
  ])
  store.commit('dashboardApplication/SET_DATA_SOURCES', [
    { id: 5, table_id: 1, ...group },
  ])
  vi.spyOn(store.$client, 'get').mockResolvedValue({
    data: [{ id: 99, name: 'Name', type: 'text' }],
  })
  const dispatch = vi
    .spyOn(store, 'dispatch')
    .mockImplementation(async (action, payload) => {
      if (action === 'dashboardApplication/updateWidget')
        store.commit('dashboardApplication/UPDATE_WIDGET', payload)
    })
  dispatch.mockClear()
  const widget = store.getters['dashboardApplication/getWidgets'].find(
    (item) => item.id === 2
  )
  const wrapper = await testApp.mount(TextFilterWidgetSettings, {
    props: { widget, dashboard: { id: 1 } },
  })
  await wrapper
    .findAll('.sidebar-expandable__header')
    .find((header) => header.text().includes('Total'))
    .trigger('click')
  await flushPromises()
  await wrapper.find('.dropdown__selected').trigger('click')
  await wrapper
    .findAll('.select__item-link')
    .find((option) => option.text() === 'textFilterWidget.apply_alternative')
    .trigger('click')
  await flushPromises()
  expect(
    wrapper.find('.dashboard-widget-filters__group--alternative').exists()
  ).toBe(true)
  expect(wrapper.text()).toContain('textFilterWidget.alternativeSeparator')
  await wrapper
    .find('.dashboard-widget-filters__group--alternative .filters__add')
    .trigger('click')
  await flushPromises()
  expect(widget.target_filters[0].group.filters).toHaveLength(0)
  expect(widget.target_filters[0].alternative_group.filters).toHaveLength(1)
  expect(widget.target_filters[0].alternative_group.filters[0].field).toBe(99)
})
