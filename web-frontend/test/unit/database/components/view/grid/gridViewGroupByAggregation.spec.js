import { TestApp } from '@baserow/test/helpers/testApp'
import GridViewGroupByAggregation from '@baserow/modules/database/components/view/grid/GridViewGroupByAggregation'
import Context from '@baserow/modules/core/components/Context'
import flushPromises from 'flush-promises'

describe('GridViewGroupByAggregation', () => {
  let testApp = null
  let store = null

  beforeEach(() => {
    testApp = new TestApp()
    store = testApp.store
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  const field = { id: 2, name: 'Amount', type: 'number' }

  const mountCell = (props = {}, mocks = {}) =>
    testApp.mount(GridViewGroupByAggregation, {
      propsData: {
        view: { id: 1 },
        workspaceId: 1,
        field,
        storePrefix: 'page/',
        rawValue: 30,
        rowCount: 2,
        ...props,
      },
      global: { mocks },
    })

  const configureSum = () =>
    store.dispatch('page/view/grid/forceUpdateAllFieldOptions', {
      2: { aggregation_type: 'sum', aggregation_raw_type: 'sum' },
    })

  test('renders the per-group aggregation value for a configured field', async () => {
    await configureSum()

    const wrapper = await mountCell()

    expect(wrapper.find('.grid-view-aggregation').exists()).toBe(true)
    expect(wrapper.text()).toContain('30')
  })

  test('keeps the label but hides the value behind the spinner while loading', async () => {
    await configureSum()

    const wrapper = await mountCell({ loading: true })

    // Label stays; the value gets the modifier that hides it and shows the spinner.
    expect(wrapper.find('.grid-view-aggregation__generic-name').exists()).toBe(
      true
    )
    expect(
      wrapper.find('.grid-view-aggregation__generic-value--loading').exists()
    ).toBe(true)
  })

  test('shows a spinner while loading the first value (none to aggregation)', async () => {
    await configureSum()

    const wrapper = await mountCell({ rawValue: undefined, loading: true })

    expect(
      wrapper.find('.grid-view__group-by-banner-aggregation-loading').exists()
    ).toBe(true)
  })

  test('starts the spinner as the aggregation changes, before the refresh', async () => {
    await configureSum()
    const wrapper = await mountCell()
    const realDispatch = store.dispatch.bind(store)
    vi.spyOn(store, 'dispatch').mockImplementation((action, payload) => {
      if (action.endsWith('updateFieldOptionsOfField')) {
        return Promise.resolve(undefined)
      }
      return realDispatch(action, payload)
    })

    await wrapper.find('.grid-view-aggregation').trigger('click')
    const context = wrapper.findComponent(Context)
    await context
      .find('.select__items > .select__item:nth-child(2)')
      .find('.select__item-link')
      .trigger('click')
    await flushPromises()

    // Loading is set as part of the change, so the old value never flashes.
    expect(
      store.getters['page/view/grid/getGroupByAggregationsLoading'](field.id)
    ).toBe(true)
  })

  test('renders a summarize affordance when nothing is configured yet', async () => {
    const wrapper = await mountCell({ rawValue: undefined })

    // The empty state lets an editable user set an aggregation from the group.
    expect(wrapper.find('.grid-view-aggregation__empty').exists()).toBe(true)
  })

  test('renders nothing for a read-only user when nothing is configured', async () => {
    const wrapper = await mountCell(
      { rawValue: undefined },
      { $hasPermission: () => false }
    )

    expect(wrapper.find('.grid-view-aggregation').exists()).toBe(false)
  })

  test('selecting an aggregation updates the shared field option and emits change', async () => {
    await configureSum()
    const wrapper = await mountCell()
    const dispatch = vi.spyOn(store, 'dispatch').mockResolvedValue(undefined)

    await wrapper.find('.grid-view-aggregation').trigger('click')
    const context = wrapper.findComponent(Context)
    // The second item is the first aggregation function after "None".
    await context
      .find('.select__items > .select__item:nth-child(2)')
      .find('.select__item-link')
      .trigger('click')
    await flushPromises()

    expect(dispatch).toHaveBeenCalledWith(
      'page/view/grid/updateFieldOptionsOfField',
      expect.objectContaining({ field })
    )
    expect(wrapper.emitted('change')).toBeTruthy()
  })
})
