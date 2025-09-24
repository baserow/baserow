import { TestApp } from '@baserow/test/helpers/testApp'
import { expect } from '@jest/globals'
import flushPromises from 'flush-promises'

import ViewFilterForm from '@baserow/modules/database/components/view/ViewFilterForm.vue'

// Mock the uuid functions to return a predictable value
let nextFilterUuid = 100
const mockUuid = () => nextFilterUuid++

jest.mock('@baserow/modules/core/utils/string', () => ({
  uuid: () => mockUuid(),
}))

jest.mock('uuid', () => ({
  v1: () => mockUuid(),
  v4: () => mockUuid(),
}))

const fields = [
  {
    id: 1,
    name: 'Name',
    order: 0,
    type: 'text',
    primary: true,
    text_default: '',
    _: {
      loading: false,
    },
  },
  {
    id: 2,
    table_id: 196,
    name: 'Stars',
    order: 1,
    type: 'rating',
    primary: false,
    max_value: 5,
    color: 'dark-orange',
    style: 'star',
    _: {
      loading: false,
    },
  },
  {
    id: 3,
    table_id: 196,
    name: 'Flag',
    order: 2,
    type: 'rating',
    primary: false,
    max_value: 10,
    color: 'dark-red',
    style: 'heart',
    _: {
      loading: false,
    },
  },
]

const view = {
  id: 1,
  name: 'Grid',
  type: 'grid',
  filter_type: 'AND',
  filters: [
    {
      field: 1,
      type: 'equal',
      value: 'test',
      preload_values: {},
      _: { hover: false, loading: false },
      id: 10,
    },
    {
      field: 2,
      type: 'equal',
      value: '2',
      preload_values: {},
      _: { hover: false, loading: false },
      id: 11,
    },
  ],
  filters_disabled: false,
  _: {
    selected: true,
    loading: false,
  },
  ownership_type: 'collaborative',
}

describe('ViewFilterForm match snapshots', () => {
  let testApp = null
  let mockServer = null

  beforeAll(() => {
    testApp = new TestApp()
    mockServer = testApp.mockServer
  })

  afterEach(() => {
    jest.useRealTimers()
    testApp.afterEach()
    mockServer.resetMockEndpoints()
  })

  const mountViewFilterForm = async (
    props = {
      fields: [],
      view: { filters: [], _: {}, filter_type: 'AND' },
      readOnly: false,
    },
    listeners = {}
  ) => {
    props.disableFilter = false
    const wrapper = await testApp.mount(ViewFilterForm, {
      propsData: props,
      listeners,
    })
    return wrapper
  }

  test('Default view filter component', async () => {
    const wrapper = await mountViewFilterForm()
    expect(wrapper.element).toMatchSnapshot()
  })

  test('Full view filter component', async () => {
    const wrapper = await mountViewFilterForm({
      fields,
      view,
      readOnly: false,
    })
    expect(wrapper.element).toMatchSnapshot()
  })

  test('Test rating filter', (done) => {
    const f = async function () {
      // We want to bypass some setTimeout
      jest.useFakeTimers()
      // Mock server filter update call
      mockServer.updateViewFilter(11, '5')

      // Add rating one filter
      const viewClone = JSON.parse(JSON.stringify(view))
      viewClone.filters = [
        {
          field: 2,
          type: 'equal',
          value: '2',
          preload_values: {},
          _: { hover: false, loading: false },
          id: 11,
        },
      ]

      const onChange = jest.fn(() => {
        // The test is about to finish
        expect(wrapper.emitted().changed).toBeTruthy()
        // The Five star option should be selected
        expect(wrapper.element).toMatchSnapshot()
        done()
      })

      // Mounting the component
      const wrapper = await mountViewFilterForm(
        {
          fields,
          view: viewClone,
          readOnly: false,
        },
        { changed: onChange }
      )

      // Open type dropdown
      await wrapper.find('.filters__type .dropdown__selected').trigger('click')
      expect(wrapper.element).toMatchSnapshot()

      // Select five stars
      const option = wrapper.find(
        '.filters__value  .rating > .rating__star:nth-child(5)'
      )

      await option.trigger('click')
      // Wait some timers
      await jest.runAllTimers()

      // Test finishes only when onChange callback is called
      // Wait for mockServer to respond -> see onChange callback
    }
    f()
  })
})

describe('ViewFilterForm can add/update/remove filters and filter groups', () => {
  let testApp = null
  let mockServer

  const workspace = { id: 1, users: [] }
  const database = { id: 1, workspace_id: 1 }
  const table = { id: 2, database_id: 1 }
  const fields = [
    {
      id: 10,
      name: 'Name',
      type: 'text',
      primary: true,
    },
  ]
  const viewId = 3
  const testView = { id: viewId, type: 'grid', table_id: 2, filter_type: 'AND' }
  const basePropsData = {
    database,
    table,
    fields,
    readOnly: false,
    disableFilter: false,
  }

  beforeEach(() => {
    testApp = new TestApp()
    mockServer = testApp.mockServer

    testApp.store.dispatch('workspace/forceCreate', workspace)
    testApp.store.commit('workspace/SET_SELECTED', workspace)
    testApp.store.dispatch('view/forceCreate', { data: { ...testView } })
    nextFilterUuid = 100
  })

  afterEach(() => testApp.afterEach())

  test('can add a filter', async () => {
    const app = testApp.getApp()
    const view = app.$store.getters['view/get'](viewId)
    const wrapper = await testApp.mount(ViewFilterForm, {
      propsData: { ...basePropsData, view },
    })

    expect(view.filters.length).toBe(0)

    mockServer.mock
      .onPost(`/database/views/${viewId}/filters/`)
      .reply((config) => [200, { ...config.data, view: viewId, id: 100 }])

    await wrapper
      .findAllComponents({ name: 'ButtonText' })
      .at(0)
      .trigger('click')
    await flushPromises()

    expect(view.filters.length).toBe(1)
    expect(view.filters[0].id).toBe(100)
    expect(view.filters[0].view).toBe(viewId)
    expect(view.filters[0].field).toBe(10)
    expect(view.filters[0].group).toBe(null)

    expect(wrapper.emitted('changed')).toBeTruthy()
  })

  test('can delete a filter', async () => {
    const app = testApp.getApp()
    const view = app.$store.getters['view/get'](viewId)

    await testApp.store.dispatch('view/forceCreateFilter', {
      view,
      values: {
        id: 100,
        field: 10,
        type: 'equal',
        value: '',
        group: null,
      },
    })

    const wrapper = await testApp.mount(ViewFilterForm, {
      propsData: { ...basePropsData, view },
    })

    expect(view.filters.length).toBe(1)

    mockServer.mock.onDelete('/database/views/filter/100/').reply(204, {})

    await wrapper
      .findComponent({ name: 'ViewFieldConditionItem' })
      .find('.filters__remove')
      .trigger('click')
    await flushPromises()

    expect(view.filters.length).toBe(0)

    expect(wrapper.emitted('changed')).toBeTruthy()
  })

  test('can change the filter_type from AND to OR', async () => {
    const app = testApp.getApp()
    const view = app.$store.getters['view/get'](viewId)

    // create 2 filters
    await testApp.store.dispatch('view/forceCreateFilter', {
      view,
      values: {
        id: 100,
        field: 10,
        type: 'equal',
        value: '',
        group: null,
      },
    })

    await testApp.store.dispatch('view/forceCreateFilter', {
      view,
      values: {
        id: 101,
        field: 10,
        type: 'equal',
        value: '',
        group: null,
      },
    })

    expect(view.filters.length).toBe(2)

    const wrapper = await testApp.mount(ViewFilterForm, {
      propsData: { ...basePropsData, view },
    })

    mockServer.mock
      .onPatch(`/database/views/${viewId}/`)
      .reply((config) => [200, { ...config.data, ...testView }])

    // First one is for the `WHERE` clause, the second one is the dropdown
    wrapper
      .findAllComponents({ name: 'ViewFilterFormOperator' })
      .at(1)
      .findAllComponents({ name: 'DropdownItem' })
      .at(1)
      .find('a')
      .trigger('click')

    await flushPromises()

    expect(view.filter_type).toBe('OR')
    expect(wrapper.emitted('changed')).toBeTruthy()
  })

  test('can add a filter group', async () => {
    const app = testApp.getApp()
    const view = app.$store.getters['view/get'](viewId)
    const wrapper = await testApp.mount(ViewFilterForm, {
      propsData: { ...basePropsData, view },
    })

    expect(view.filters.length).toBe(0)

    mockServer.mock
      .onPost(`/database/views/${viewId}/filter-groups/`)
      .reply((config) => [
        200,
        { ...config.data, view: viewId, id: 100, parent_group: null },
      ])

    mockServer.mock
      .onPost(`/database/views/${viewId}/filters/`)
      .reply((config) => [200, { ...config.data, view: viewId, id: 101 }])

    // button-0 creates a filter, button-1 creates a filter group
    await wrapper
      .findAllComponents({ name: 'ButtonText' })
      .at(1)
      .trigger('click')
    await flushPromises()

    expect(view.filters.length).toBe(1)
    expect(view.filters[0].id).toBe(101)
    expect(view.filters[0].view).toBe(viewId)
    expect(view.filters[0].field).toBe(10)
    expect(view.filters[0].group).toBe(100)

    expect(view.filter_groups.length).toBe(1)
    expect(view.filter_groups[0].id).toBe(100)
    expect(view.filter_groups[0].view).toBe(viewId)
    expect(view.filter_groups[0].parent_group).toBe(null)
    expect(view.filter_groups[0].filter_type).toBe('AND')

    expect(wrapper.emitted('changed')).toBeTruthy()
  })

  test('can delete a filter group', async () => {
    const app = testApp.getApp()
    const view = app.$store.getters['view/get'](viewId)

    // create a filter and a filter group in the store
    await testApp.store.dispatch('view/forceCreateFilterGroup', {
      view,
      values: {
        id: 100,
        filter_type: 'AND',
        parent_group: null,
      },
    })

    await testApp.store.dispatch('view/forceCreateFilter', {
      view,
      values: {
        id: 101,
        field: 10,
        type: 'equal',
        value: '',
        group: 100,
      },
    })

    const wrapper = await testApp.mount(ViewFilterForm, {
      propsData: { ...basePropsData, view },
    })

    expect(view.filters.length).toBe(1)
    expect(view.filter_groups.length).toBe(1)

    mockServer.mock.onDelete('/database/views/filter-group/100/').reply(204, {})

    // button-0 creates a filter, button-1 creates a filter group
    await wrapper.findAll('.filters__remove').at(0).trigger('click')
    await flushPromises()

    expect(view.filters.length).toBe(0)
    expect(view.filter_groups.length).toBe(0)

    expect(wrapper.emitted('changed')).toBeTruthy()
  })

  test('can change the filter_type from AND to OR in a group', async () => {
    const app = testApp.getApp()
    const view = app.$store.getters['view/get'](viewId)

    // create 2 filters in a group
    await testApp.store.dispatch('view/forceCreateFilterGroup', {
      view,
      values: {
        id: 100,
        filter_type: 'AND',
        parent_group: null,
      },
    })

    await testApp.store.dispatch('view/forceCreateFilter', {
      view,
      values: {
        id: 101,
        field: 10,
        type: 'equal',
        value: '',
        group: 100,
      },
    })

    await testApp.store.dispatch('view/forceCreateFilter', {
      view,
      values: {
        id: 102,
        field: 10,
        type: 'equal',
        value: '',
        group: 100,
      },
    })

    const wrapper = await testApp.mount(ViewFilterForm, {
      propsData: { ...basePropsData, view },
    })

    mockServer.mock
      .onPatch(`/database/views/filter-group/100/`)
      .reply((config) => [200, { ...config.data, ...testView }])

    // First one is for the `WHERE` clause in root filter group, the second one is the
    // `WHERE` clause for the first filter group
    wrapper
      .findAllComponents({ name: 'ViewFilterFormOperator' })
      .at(2)
      .findAllComponents({ name: 'DropdownItem' })
      .at(1)
      .find('a')
      .trigger('click')

    await flushPromises()

    expect(view.filter_groups.length).toBe(1)
    expect(view.filter_groups[0].filter_type).toBe('OR')
    expect(wrapper.emitted('changed')).toBeTruthy()
  })

  test('can add a filter group inside another group', async () => {
    const app = testApp.getApp()
    const view = app.$store.getters['view/get'](viewId)

    const wrapper = await testApp.mount(ViewFilterForm, {
      propsData: { ...basePropsData, view },
    })

    await testApp.store.dispatch('view/forceCreateFilterGroup', {
      view,
      values: {
        id: 90,
        filter_type: 'AND',
        parent_group: null,
      },
    })

    await testApp.store.dispatch('view/forceCreateFilter', {
      view,
      values: {
        id: 100,
        field: 10,
        type: 'equal',
        value: '',
        group: 90,
      },
    })

    expect(view.filters.length).toBe(1)

    mockServer.mock
      .onPost(`/database/views/${viewId}/filter-groups/`)
      .reply((config) => [200, { ...config.data, view: viewId, id: 91 }])

    mockServer.mock
      .onPost(`/database/views/${viewId}/filters/`)
      .reply((config) => [200, { ...config.data, view: viewId, id: 101 }])

    // button-0 creates a filter, button-1 creates a filter group
    wrapper
      .findComponent({ name: 'ViewFieldConditionGroup' })
      .find('.filters__group-item-action--add-filter-group')
      .trigger('click')
    await flushPromises()

    expect(view.filters.length).toBe(2)
    expect(view.filters[1].id).toBe(101)
    expect(view.filters[1].view).toBe(viewId)
    expect(view.filters[1].field).toBe(10)
    expect(view.filters[1].group).toBe(91)

    expect(view.filter_groups.length).toBe(2)
    expect(view.filter_groups[1].id).toBe(91)
    expect(view.filter_groups[1].view).toBe(viewId)
    expect(view.filter_groups[1].parent_group).toBe(90)
    expect(view.filter_groups[1].filter_type).toBe('AND')

    expect(wrapper.emitted('changed')).toBeTruthy()
  })

  test('deleting the last condition delete the outermost condition group', async () => {
    const app = testApp.getApp()
    const view = app.$store.getters['view/get'](viewId)

    await testApp.store.dispatch('view/forceCreateFilterGroup', {
      view,
      values: {
        id: 90,
        filter_type: 'AND',
        parent_group: null,
      },
    })

    await testApp.store.dispatch('view/forceCreateFilterGroup', {
      view,
      values: {
        id: 91,
        filter_type: 'AND',
        parent_group: 90,
      },
    })

    await testApp.store.dispatch('view/forceCreateFilter', {
      view,
      values: {
        id: 100,
        field: 10,
        type: 'equal',
        value: '',
        group: 91,
      },
    })

    const wrapper = await testApp.mount(ViewFilterForm, {
      propsData: { ...basePropsData, view },
    })

    expect(view.filters.length).toBe(1)

    mockServer.mock.onDelete(`/database/views/filter-group/90/`).reply(204, {})

    await wrapper.findAll('.filters__remove').at(0).trigger('click')
    await flushPromises()

    expect(view.filters.length).toBe(0)
    expect(view.filter_groups.length).toBe(0)

    expect(wrapper.emitted('changed')).toBeTruthy()
  })
})
