import { TestApp } from '@baserow/test/helpers/testApp'
import GridViewFieldFooter from '@baserow/modules/database/components/view/grid/GridViewFieldFooter'
import Context from '@baserow/modules/core/components/Context'
import { clone } from '@baserow/modules/core/utils/object'
import flushPromises from 'flush-promises'

describe('Field footer component', () => {
  let testApp = null
  let mockServer = null
  let store = null

  beforeEach(() => {
    testApp = new TestApp()
    store = testApp.store
    mockServer = testApp.mockServer
  })

  afterEach(async () => {
    vi.restoreAllMocks()
    await testApp.afterEach()
  })

  const mountComponent = (props, slots = {}) => {
    return testApp.mount(GridViewFieldFooter, { propsData: props, slots })
  }

  const selectValue = async (wrapper, child) => {
    await wrapper.find(`.grid-view-aggregation`).trigger('click')
    const context = wrapper.findComponent(Context)

    await context
      .find(`.select__items > .select__item:nth-child(${child})`)
      .find('.select__item-link')
      .trigger('click')
  }

  const selectAggregationByName = async (wrapper, name) => {
    await wrapper.find(`.grid-view-aggregation`).trigger('click')
    const context = wrapper.findComponent(Context)

    const link = context
      .findAll('.select__item-link')
      .find((l) => l.find('.select__item-name-text').text() === name)
    await link.trigger('click')
  }

  test('Default component', async () => {
    await store.dispatch('page/view/grid/forceUpdateAllFieldOptions', {
      2: {
        aggregation_type: 'not_empty_percentage',
        aggregation_raw_type: 'not_empty_count',
      },
    })

    store.commit('page/view/grid/SET_COUNT', 1024)

    const view = {
      id: 1,
    }

    const database = {
      id: 1,
      workspace: { id: 1 },
    }

    // field with no aggregation
    const wrapper1 = await mountComponent({
      view,
      database,
      field: { id: 1, type: 'text' },
      storePrefix: 'page/',
    })
    expect(wrapper1.element).toMatchSnapshot()

    // Field with aggregation
    const wrapper2 = await mountComponent({
      view,
      database,
      field: { id: 2, type: 'text' },
      storePrefix: 'page/',
    })

    expect(wrapper2.element).toMatchSnapshot()

    mockServer.getAllFieldAggregationData(view.id, {
      field_2: 256,
    })

    // let's fetch the data for this field
    await store.dispatch('page/view/grid/fetchAllFieldAggregationData', {
      view,
    })

    expect(wrapper2.element).toMatchSnapshot()
  })

  test('Change type', async () => {
    await store.dispatch('page/view/grid/forceUpdateAllFieldOptions', {
      3: {
        aggregation_type: 'not_empty_count',
        aggregation_raw_type: 'not_empty_count',
      },
    })

    store.commit('page/view/grid/SET_LAST_GRID_ID', 2)

    const view = {
      id: 2,
    }

    const database = {
      id: 1,
      workspace: { id: 1 },
    }

    mockServer.getAllFieldAggregationData(view.id, {
      field_3: 256,
    })
    mockServer.updateFieldOptions(view.id, {
      3: {
        aggregation_type: '',
        aggregation_raw_type: '',
      },
    })

    // Field with aggregation
    const wrapper = await mountComponent({
      view,
      database,
      field: { id: 3, type: 'text' },
      storePrefix: 'page/',
    })

    // let's fetch the data for this field
    await store.dispatch('page/view/grid/fetchAllFieldAggregationData', {
      view,
    })

    // Open menu manually first to have the opportunity to make snapshots
    await wrapper.find(`.grid-view-aggregation`).trigger('click')
    const context = wrapper.findComponent(Context)

    expect(context.element).toMatchSnapshot()

    // Click on aggregation type empty_count
    await context
      .find('.select__items > .select__item:nth-child(1)')
      .find('.select__item-link')
      .trigger('click')

    await flushPromises()

    expect(wrapper.element).toMatchSnapshot()

    mockServer.getAllFieldAggregationData(view.id, {
      field_3: 10,
    })
    mockServer.updateFieldOptions(view.id, {
      3: {
        aggregation_type: 'empty_count',
        aggregation_raw_type: 'empty_count',
      },
    })

    await store.dispatch('page/view/grid/forceUpdateAllFieldOptions', {
      3: {
        aggregation_type: 'empty_count',
        aggregation_raw_type: 'empty_count',
      },
    })

    // Select empty count aggregation now
    await selectValue(wrapper, 2)

    await flushPromises()

    expect(
      clone(store.getters['page/view/grid/getAllFieldAggregationData'])
    ).toEqual({ 3: { loading: false, value: 10 } })

    expect(wrapper.element).toMatchSnapshot()
  })

  test('ignores an unknown stored aggregation type instead of crashing', async () => {
    // A stale/invalid aggregation_type must not crash the grid; the footer treats
    // it as unconfigured.
    await store.dispatch('page/view/grid/forceUpdateAllFieldOptions', {
      2: {
        aggregation_type: 'not_empty_count1',
        aggregation_raw_type: 'not_empty_count',
      },
    })
    store.commit('page/view/grid/SET_COUNT', 10)
    store.commit('page/view/grid/SET_FIELD_AGGREGATION_DATA', {
      fieldId: 2,
      value: 5,
    })

    const wrapper = await mountComponent({
      view: { id: 1 },
      database: { id: 1, workspace: { id: 1 } },
      field: { id: 2, type: 'text' },
      storePrefix: 'page/',
    })

    expect(wrapper.find('.grid-view-aggregation__empty').exists()).toBe(true)
  })

  const mountGroupedFooter = () => {
    store.commit('page/view/grid/SET_LAST_GRID_ID', 2)
    store.commit('page/view/grid/SET_ACTIVE_GROUP_BYS', [{ field: 1 }])
    return testApp.mount(GridViewFieldFooter, {
      propsData: {
        view: { id: 2 },
        database: { id: 1, workspace: { id: 1 } },
        field: { id: 3, type: 'text' },
        storePrefix: 'page/',
      },
    })
  }

  test('changing the aggregation refreshes the group headers in grouped mode', async () => {
    const wrapper = await mountGroupedFooter()
    const dispatch = vi.spyOn(store, 'dispatch').mockResolvedValue(undefined)

    await selectValue(wrapper, 2)
    await flushPromises()

    expect(dispatch).toHaveBeenCalledWith(
      'page/view/grid/refreshGroupByAggregations',
      expect.objectContaining({ fieldId: 3 })
    )
  })

  test('a display-only aggregation change in grouped mode persists without refetching the group tree', async () => {
    // "Empty" and "Filled" are display variants of the same raw type
    // (`empty_count`), so switching between them persists the new label but must NOT
    // spin or issue a group-by-data request — the value re-renders client-side.
    await store.dispatch('page/view/grid/forceUpdateAllFieldOptions', {
      3: {
        aggregation_type: 'empty_count',
        aggregation_raw_type: 'empty_count',
      },
    })
    mockServer.updateFieldOptions(2, {
      3: {
        aggregation_type: 'not_empty_count',
        aggregation_raw_type: 'empty_count',
      },
    })
    const wrapper = await mountGroupedFooter()
    // Run the real dispatch chain so the HTTP layer sees exactly what goes out.
    const realDispatch = store.dispatch.bind(store)
    const dispatch = vi
      .spyOn(store, 'dispatch')
      .mockImplementation((action, payload) => realDispatch(action, payload))

    await selectAggregationByName(wrapper, 'viewAggregationType.notEmptyCount')
    await flushPromises()

    // The new display type is still persisted (one PATCH to field-options)...
    expect(dispatch).toHaveBeenCalledWith(
      'page/view/grid/updateFieldOptionsOfField',
      expect.objectContaining({
        values: expect.objectContaining({
          aggregation_type: 'not_empty_count',
        }),
      })
    )
    expect(mockServer.mock.history.patch).toHaveLength(1)
    // ...but nothing spins and no group-by-data request goes out.
    expect(dispatch).not.toHaveBeenCalledWith(
      'page/view/grid/setGroupByAggregationsLoading',
      expect.anything()
    )
    expect(dispatch).not.toHaveBeenCalledWith(
      'page/view/grid/refreshGroupByAggregations',
      expect.anything()
    )
    expect(mockServer.mock.history.get).toHaveLength(0)
  })
})
