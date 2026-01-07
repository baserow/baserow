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
})
