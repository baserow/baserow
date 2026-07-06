import { TestApp } from '@baserow/test/helpers/testApp'
import GridViewGroupByAggregation from '@baserow/modules/database/components/view/grid/GridViewGroupByAggregation'
import DistributionAggregation from '@baserow/modules/database/components/aggregation/DistributionAggregation'
import Context from '@baserow/modules/core/components/Context'
import flushPromises from 'flush-promises'

describe('GridViewGroupByAggregation', () => {
  let testApp = null
  let store = null
  let mockServer = null

  beforeEach(() => {
    testApp = new TestApp()
    store = testApp.store
    mockServer = testApp.mockServer
  })

  afterEach(async () => {
    // Restore spies so a mocked `store.dispatch` from one test can't leak into the
    // next and turn its setup dispatches into no-ops.
    vi.restoreAllMocks()
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

  const configureNotEmptyCount = () =>
    store.dispatch('page/view/grid/forceUpdateAllFieldOptions', {
      2: {
        aggregation_type: 'not_empty_count',
        aggregation_raw_type: 'empty_count',
      },
    })

  const configureDistribution = () =>
    store.dispatch('page/view/grid/forceUpdateAllFieldOptions', {
      2: {
        aggregation_type: 'distribution',
        aggregation_raw_type: 'distribution',
      },
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

  test('formats derived counts with the server-confirmed aggregation row count', async () => {
    await configureNotEmptyCount()

    const wrapper = await mountCell({
      rawValue: 1,
      rowCount: 3,
      aggregationRowCount: 2,
    })

    expect(wrapper.find('.grid-view-aggregation__generic-value').text()).toBe(
      '1'
    )
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

  test('never shows the summarize affordance for a configured field without a per-group value', async () => {
    // A non-scalar aggregation (e.g. distribution) is configured but the backend
    // returns no per-group value, so the field must not look unconfigured.
    await configureSum()

    const wrapper = await mountCell({ rawValue: undefined })

    expect(wrapper.find('.grid-view-aggregation__empty').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('30')
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

  test('switching to a display type that shares the raw type re-renders without a refetch or spinner', async () => {
    // not_empty_count and empty_count share the raw type, so switching between them
    // only re-renders the existing value — the choice is persisted but no group-by-data
    // request goes out and the cell never spins (like the footer). The cell emits
    // `change` to trigger the refetch, so "no change emitted" is the no-request proof.
    store.commit('page/view/grid/SET_LAST_GRID_ID', 1)
    await configureNotEmptyCount()
    mockServer.updateFieldOptions(1, {
      2: {
        aggregation_type: 'empty_count',
        aggregation_raw_type: 'empty_count',
      },
    })
    const wrapper = await mountCell()
    // Run the real dispatch chain so the HTTP layer sees exactly what goes out.
    const realDispatch = store.dispatch.bind(store)
    const dispatch = vi
      .spyOn(store, 'dispatch')
      .mockImplementation((action, payload) => realDispatch(action, payload))

    await wrapper.find('.grid-view-aggregation').trigger('click')
    const context = wrapper.findComponent(Context)
    const emptyCountItem = context.findAll('.select__item').find((item) => {
      const name = item.find('.select__item-name-text')
      return name.exists() && name.text() === 'viewAggregationType.emptyCount'
    })
    await emptyCountItem.find('.select__item-link').trigger('click')
    await flushPromises()

    // The new display type is still persisted (one PATCH to field-options)...
    expect(dispatch).toHaveBeenCalledWith(
      'page/view/grid/updateFieldOptionsOfField',
      expect.objectContaining({
        values: expect.objectContaining({
          aggregation_type: 'empty_count',
          aggregation_raw_type: 'empty_count',
        }),
      })
    )
    expect(mockServer.mock.history.patch).toHaveLength(1)
    // ...but it neither triggers the refetch, spins the cell, nor issues a GET.
    expect(wrapper.emitted('change')).toBeFalsy()
    expect(dispatch).not.toHaveBeenCalledWith(
      'page/view/grid/setGroupByAggregationsLoading',
      expect.objectContaining({ fieldId: field.id })
    )
    expect(mockServer.mock.history.get).toHaveLength(0)
  })

  test('renders nothing instead of crashing on a table-only aggregation', async () => {
    // Distribution is footer-only; the field's stale scalar value must not be fed to
    // its array-shaped getValue (which would throw and break the group render).
    await configureDistribution()

    const wrapper = await mountCell({ rawValue: 25 })

    expect(wrapper.findComponent(DistributionAggregation).exists()).toBe(false)
    expect(wrapper.find('.grid-view-aggregation__empty').exists()).toBe(true)
  })

  test('omits table-only aggregations from the group context menu', async () => {
    await configureSum()
    const wrapper = await mountCell()

    await wrapper.find('.grid-view-aggregation').trigger('click')
    const names = wrapper
      .findComponent(Context)
      .findAll('.select__item-name-text')
      .map((node) => node.text())

    expect(names).toContain('viewAggregationType.sum')
    expect(names).not.toContain('viewAggregationType.distribution')
  })
})
