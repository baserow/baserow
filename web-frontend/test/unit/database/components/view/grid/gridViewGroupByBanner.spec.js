import { TestApp } from '@baserow/test/helpers/testApp'
import GridViewGroupByBanner from '@baserow/modules/database/components/view/grid/GridViewGroupByBanner'
import GridViewGroupByAggregation from '@baserow/modules/database/components/view/grid/GridViewGroupByAggregation'

describe('GridViewGroupByBanner component', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  const mountBanner = (field, { path, display }) =>
    testApp.mount(GridViewGroupByBanner, {
      props: {
        groupByFields: [field],
        item: {
          type: 'header',
          depth: 0,
          path,
          display,
          rowCount: 1,
          collapsed: false,
          y: 0,
          height: 48,
        },
        includeRowDetails: true,
        visibleFields: [field],
        fieldWidths: { [field.id]: 200 },
        width: 300,
        workspaceId: null,
      },
    })

  test('renders the collaborator name from the backend display value', async () => {
    const field = { id: 1, type: 'multiple_collaborators', name: 'People' }
    const wrapper = await mountBanner(field, {
      path: { field_1: [10] },
      display: { field_1: [{ id: 10, name: 'Davide' }] },
    })

    expect(wrapper.text()).toContain('Davide')
    // The raw collaborator id must no longer leak into the header.
    expect(wrapper.text()).not.toContain('10')
  })

  test('renders the linked row primary value from the backend display value', async () => {
    const field = { id: 2, type: 'link_row', name: 'Links' }
    const wrapper = await mountBanner(field, {
      path: { field_2: [5] },
      display: { field_2: [{ id: 5, value: 'Row A' }] },
    })

    expect(wrapper.text()).toContain('Row A')
  })

  test('renders the single select value from the backend display value', async () => {
    const field = {
      id: 3,
      type: 'single_select',
      name: 'Status',
      select_options: [],
    }
    const wrapper = await mountBanner(field, {
      path: { field_3: 7 },
      display: { field_3: { id: 7, value: 'Open', color: 'blue' } },
    })

    expect(wrapper.text()).toContain('Open')
  })

  test('renders the multiple select values from the backend display value', async () => {
    const field = {
      id: 5,
      type: 'multiple_select',
      name: 'Tags',
      select_options: [],
    }
    const wrapper = await mountBanner(field, {
      path: { field_5: [7, 8] },
      display: {
        field_5: [
          { id: 7, value: 'Red', color: 'red' },
          { id: 8, value: 'Blue', color: 'blue' },
        ],
      },
    })

    expect(wrapper.text()).toContain('Red')
    expect(wrapper.text()).toContain('Blue')
  })

  test('renders a scalar field from the path value when no display is present', async () => {
    const field = { id: 4, type: 'text', name: 'Title' }
    const wrapper = await mountBanner(field, {
      path: { field_4: 'hello world' },
      display: undefined,
    })

    expect(wrapper.text()).toContain('hello world')
  })

  test('shows the empty label for an empty array-valued group', async () => {
    const field = {
      id: 6,
      type: 'multiple_select',
      name: 'Tags',
      select_options: [],
    }
    const wrapper = await mountBanner(field, {
      path: { field_6: [] },
      display: { field_6: [] },
    })

    // An empty array (multiple select / link row / collaborators) must render the
    // empty-value label, not a blank group-value component.
    expect(
      wrapper.find('.grid-view__group-by-banner-value-empty').exists()
    ).toBe(true)
  })

  const separatorLefts = (wrapper) =>
    wrapper
      .findAll('.grid-view__group-by-banner-separator')
      .map((separator) => separator.element.style.left)

  test('renders separators after the row details lane and internal left fields', async () => {
    const fields = [
      { id: 1, type: 'text', name: 'Name' },
      { id: 2, type: 'text', name: 'Team' },
      { id: 3, type: 'text', name: 'Notes' },
    ]
    const wrapper = await testApp.mount(GridViewGroupByBanner, {
      props: {
        groupByFields: [fields[0]],
        item: {
          depth: 0,
          path: { field_1: 'A' },
          display: undefined,
          rowCount: 1,
          collapsed: false,
          y: 0,
          height: 48,
        },
        includeRowDetails: true,
        rowDetailsWidth: 72,
        visibleFields: fields,
        fieldWidths: { 1: 200, 2: 150, 3: 100 },
        width: 522,
        workspaceId: null,
      },
    })

    expect(separatorLefts(wrapper)).toEqual(['71px', '271px', '421px'])
  })

  test('renders separators on internal right-section field boundaries', async () => {
    const fields = [
      { id: 1, type: 'text', name: 'Team' },
      { id: 2, type: 'text', name: 'Notes' },
      { id: 3, type: 'text', name: 'Score' },
    ]
    const wrapper = await testApp.mount(GridViewGroupByBanner, {
      props: {
        groupByFields: [fields[0]],
        item: {
          depth: 0,
          path: { field_1: 'A' },
          display: undefined,
          rowCount: 1,
          collapsed: false,
          y: 0,
          height: 48,
        },
        includeRowDetails: false,
        visibleFields: fields,
        fieldWidths: { 1: 200, 2: 150, 3: 100 },
        width: 450,
        workspaceId: null,
      },
    })

    expect(separatorLefts(wrapper)).toEqual(['199px', '349px'])
  })

  const mountAtDepth = (fieldCount, depth, rowDetailsWidth = 72) =>
    testApp.mount(GridViewGroupByBanner, {
      props: {
        groupByFields: Array.from({ length: fieldCount }, (_, i) => ({
          id: i + 1,
          type: 'text',
          name: `Field ${i + 1}`,
        })),
        item: {
          depth,
          path: { [`field_${depth + 1}`]: 'x' },
          display: undefined,
          rowCount: 1,
          collapsed: false,
          y: 0,
          height: 48,
        },
        includeRowDetails: true,
        visibleFields: [{ id: 1, type: 'text', name: 'Field 1' }],
        fieldWidths: { 1: 200 },
        rowDetailsWidth,
        width: 300,
        workspaceId: null,
      },
    })

  const chevronPadding = (wrapper) =>
    parseFloat(
      wrapper.find('.grid-view__group-by-banner-chevron-lane').element.style
        .paddingLeft
    )

  test('caps the chevron indent so deep nesting stops shifting right', async () => {
    // 14 levels: the deepest chevron must still fit inside the 72px row-details lane
    // (base 12 + at most 36 = 48, leaving room for the 24px chevron) so it never
    // marches the field name + count off to the right.
    const deepest = await mountAtDepth(14, 13)
    const pad = chevronPadding(deepest)
    expect(pad).toBeGreaterThan(12)
    expect(pad).toBeLessThanOrEqual(48)
  })

  test('shrinks the per-level step as the number of group-bys grows', async () => {
    const fewStep = chevronPadding(await mountAtDepth(3, 1)) - 12
    const manyStep = chevronPadding(await mountAtDepth(13, 1)) - 12
    expect(manyStep).toBeLessThan(fewStep)
    expect(manyStep).toBeGreaterThan(0)
  })

  test('indents the field-name block in lockstep with its chevron', async () => {
    const subGroup = await mountAtDepth(2, 1)
    const labelPadding = parseFloat(
      subGroup.find('.grid-view__group-by-banner-field--primary').element.style
        .paddingLeft
    )
    expect(labelPadding).toBe(chevronPadding(subGroup))
    expect(labelPadding).toBeGreaterThan(12)
  })
})

describe('GridViewGroupByBanner aggregations', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  const colorField = { id: 1, name: 'Color', type: 'text' }
  const amountField = { id: 2, name: 'Amount', type: 'number' }
  const sizeField = { id: 3, name: 'Size', type: 'number' }

  const header = (aggregations) => ({
    type: 'header',
    depth: 0,
    path: { field_1: 'Green' },
    rowCount: 2,
    y: 0,
    height: 48,
    collapsed: false,
    aggregations,
  })

  const mountBanner = (item, featureEnabled = true) =>
    testApp.mount(GridViewGroupByBanner, {
      propsData: {
        item,
        groupByFields: [colorField],
        includeRowDetails: false,
        width: 200,
        workspaceId: 1,
        visibleFields: [amountField],
        fieldWidths: { [amountField.id]: 200 },
        view: { id: 1 },
        storePrefix: 'page/',
      },
      global: {
        mocks: { $featureFlagIsEnabled: () => featureEnabled },
        stubs: { GridViewGroupByAggregation: true },
      },
    })

  test('renders an aggregation cell per visible field with the group value when enabled', async () => {
    const wrapper = await mountBanner(header({ field_2: 30 }))

    const cell = wrapper.findComponent(GridViewGroupByAggregation)
    expect(cell.exists()).toBe(true)
    expect(cell.props('rawValue')).toBe(30)
    expect(cell.props('rowCount')).toBe(2)
    expect(cell.props('field')).toEqual(amountField)
  })

  test('renders no aggregation cell when the feature flag is disabled', async () => {
    const wrapper = await mountBanner(header({ field_2: 30 }), false)

    expect(wrapper.findComponent(GridViewGroupByAggregation).exists()).toBe(
      false
    )
  })

  test('passes an undefined raw value when the group has no value for the field', async () => {
    const wrapper = await mountBanner(header({}))

    const cell = wrapper.findComponent(GridViewGroupByAggregation)
    expect(cell.exists()).toBe(true)
    expect(cell.props('rawValue')).toBeUndefined()
  })

  const mountTwoFieldBanner = (aggregations) =>
    testApp.mount(GridViewGroupByBanner, {
      propsData: {
        item: header(aggregations),
        groupByFields: [colorField],
        includeRowDetails: false,
        width: 400,
        workspaceId: 1,
        visibleFields: [amountField, sizeField],
        fieldWidths: { [amountField.id]: 200, [sizeField.id]: 200 },
        view: { id: 1 },
        storePrefix: 'page/',
      },
      global: {
        mocks: { $featureFlagIsEnabled: () => true },
        stubs: { GridViewGroupByAggregation: true },
      },
    })

  test('spins only the changed field when a single aggregation is refreshing', async () => {
    testApp.store.commit('page/view/grid/SET_GROUP_BY_AGGREGATIONS_LOADING', [
      amountField.id,
    ])
    const wrapper = await mountTwoFieldBanner({ field_2: 30, field_3: 5 })

    const cells = wrapper.findAllComponents(GridViewGroupByAggregation)
    expect(cells[0].props('field')).toEqual(amountField)
    expect(cells[0].props('loading')).toBe(true)
    expect(cells[1].props('field')).toEqual(sizeField)
    expect(cells[1].props('loading')).toBe(false)
  })

  test('spins every field when all aggregations are refreshing after a row edit', async () => {
    testApp.store.commit(
      'page/view/grid/SET_GROUP_BY_AGGREGATIONS_LOADING',
      true
    )
    const wrapper = await mountTwoFieldBanner({ field_2: 30, field_3: 5 })

    const cells = wrapper.findAllComponents(GridViewGroupByAggregation)
    expect(cells[0].props('loading')).toBe(true)
    expect(cells[1].props('loading')).toBe(true)
  })

  test('forwards the changed field id with the aggregation-changed event', async () => {
    const wrapper = await mountBanner(header({ field_2: 30 }))

    wrapper.findComponent(GridViewGroupByAggregation).vm.$emit('change')

    expect(wrapper.emitted('aggregation-changed')[0]).toEqual([amountField.id])
  })
})
