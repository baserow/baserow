/**
 * Structural integration test for the GridGrouped container. Verifies
 * that the container, the store, and the pure render core wire up
 * correctly: given a populated store, the right number of banners /
 * rows / placeholders appear in the DOM with the right keys.
 */
import { TestApp } from '@baserow/test/helpers/testApp'
import GridGrouped from '@baserow/modules/database/components/view/grid/GridGrouped'
import gridGroupedStore from '@baserow/modules/database/store/view/gridGrouped'
import { pathKey } from '@baserow/modules/database/utils/gridGroupedRender'

describe('GridGrouped container', () => {
  let testApp = null
  let store = null

  beforeEach(() => {
    testApp = new TestApp()
    store = testApp.store
    if (!store.hasModule('page/view/gridGrouped')) {
      store.registerModule('page/view/gridGrouped', gridGroupedStore)
    }
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  const groupByFields = [
    { id: 1, name: 'Category', type: 'text' },
    { id: 2, name: 'Completed', type: 'boolean' },
  ]

  // Compute a row's leaf section key the same way the store would.
  const sectionKeyForRow = (row, fields) => {
    const path = {}
    for (const f of fields) {
      path[`field_${f.id}`] = row[`field_${f.id}`]
    }
    return pathKey(path, fields)
  }

  // Group rows by section, write each group into its bucket starting
  // at position 0. Doesn't try to preserve any pre-existing order
  // beyond the array given.
  const seedSectionRows = (fields, rows) => {
    const bySection = new Map()
    for (const row of rows) {
      const key = sectionKeyForRow(row, fields)
      if (!bySection.has(key)) bySection.set(key, [])
      bySection.get(key).push(row)
    }
    for (const [sectionKey, sectionRows] of bySection) {
      store.commit('page/view/gridGrouped/MERGE_SECTION_ROWS', {
        sectionKey,
        startPosition: 0,
        rows: sectionRows,
      })
    }
  }

  const seedStore = (overrides = {}) => {
    const fields = overrides.groupByFields ?? groupByFields
    store.commit('page/view/gridGrouped/INIT', {
      gridId: 1,
      groupByFields: fields,
      sortings: [],
      collapseMode: 'expand',
      registry: testApp.$registry,
    })
    store.commit('page/view/gridGrouped/SET_TREE', {
      nodes: overrides.nodes ?? [
        { path: { field_1: 'Development' }, depth: 0, rowCount: 2 },
        {
          path: { field_1: 'Development', field_2: true },
          depth: 1,
          rowCount: 1,
        },
        {
          path: { field_1: 'Development', field_2: false },
          depth: 1,
          rowCount: 1,
        },
      ],
      fullyLoaded: true,
    })
    seedSectionRows(
      fields,
      overrides.rows ?? [
        { id: 10, field_1: 'Development', field_2: true },
        { id: 11, field_1: 'Development', field_2: false },
      ]
    )
  }

  const mountGrouped = async (overrides = {}) => {
    seedStore(overrides)
    const wrapper = await testApp.mount(GridGrouped, {
      props: {
        view: { id: 1, group_bys: [{ field: 1 }, { field: 2 }] },
        visibleFields: overrides.visibleFields ?? [
          { id: 1, name: 'Category', type: 'text' },
          { id: 2, name: 'Completed', type: 'boolean' },
        ],
        allFieldsInTable: overrides.visibleFields ?? [
          { id: 1, name: 'Category', type: 'text' },
          { id: 2, name: 'Completed', type: 'boolean' },
        ],
        fieldOptions: {},
        workspaceId: 1,
        readOnly: true,
        ...overrides.props,
      },
      global: {
        stubs: {
          GridViewCell: {
            name: 'GridViewCell',
            template: '<div class="grid-view__column" />',
          },
          GridViewHead: {
            name: 'GridViewHead',
            template: '<div class="grid-view__head" />',
          },
          GridViewFieldFooter: {
            name: 'GridViewFieldFooter',
            template: '<div class="grid-view-aggregation" />',
          },
        },
      },
    })
    store.commit('page/view/gridGrouped/SET_VIEWPORT', {
      scrollTop: 0,
      clientHeight: overrides.clientHeight ?? 5000,
    })
    await wrapper.vm.$nextTick()
    return wrapper
  }

  test('renders one banner per visible header item', async () => {
    const wrapper = await mountGrouped()
    expect(wrapper.findAll('.grid-grouped-banner')).toHaveLength(3)
  })

  test('renders one row per cached row whose section is visible', async () => {
    const wrapper = await mountGrouped()
    expect(wrapper.findAll('.grid-grouped-row')).toHaveLength(2)
  })

  test('renders placeholders for missing rows in a partial-cache section', async () => {
    const wrapper = await mountGrouped({
      nodes: [
        { path: { field_1: 'Development' }, depth: 0, rowCount: 2 },
        {
          path: { field_1: 'Development', field_2: true },
          depth: 1,
          rowCount: 2,
        },
      ],
      rows: [{ id: 10, field_1: 'Development', field_2: true }],
      groupByFields,
    })
    expect(wrapper.findAll('.grid-grouped-placeholder')).toHaveLength(1)
  })

  test('collapsed section emits a header but no body rows / placeholders', async () => {
    const wrapper = await mountGrouped({
      nodes: [{ path: { field_1: 'Development' }, depth: 0, rowCount: 2 }],
      rows: [
        { id: 10, field_1: 'Development' },
        { id: 11, field_1: 'Development' },
      ],
      groupByFields: [{ id: 1, name: 'Category', type: 'text' }],
    })
    store.commit('page/view/gridGrouped/TOGGLE_COLLAPSE', {
      field_1: 'Development',
    })
    await wrapper.vm.$nextTick()
    expect(wrapper.findAll('.grid-grouped-banner')).toHaveLength(1)
    expect(
      wrapper.find('.grid-grouped-banner').attributes('data-collapsed')
    ).toBe('true')
    expect(wrapper.findAll('.grid-grouped-row')).toHaveLength(0)
    expect(wrapper.findAll('.grid-grouped-placeholder')).toHaveLength(0)
  })

  test('regression: collapse toggle leaves other sections` buckets untouched (no placeholder flicker)', async () => {
    // Direct reproducer for the 4-placeholders-after-collapse bug.
    // Before the per-section refactor, collapse cleared all fetched
    // bookkeeping + stripped _globalOffset, which made row positions
    // drift. Now collapse is a structural no-op for buckets.
    const wrapper = await mountGrouped({
      groupByFields,
      nodes: [
        { path: { field_1: 'A' }, depth: 0, rowCount: 1 },
        { path: { field_1: 'A', field_2: true }, depth: 1, rowCount: 1 },
        { path: { field_1: 'B' }, depth: 0, rowCount: 1 },
        { path: { field_1: 'B', field_2: false }, depth: 1, rowCount: 1 },
      ],
      rows: [
        { id: 1, field_1: 'A', field_2: true },
        { id: 2, field_1: 'B', field_2: false },
      ],
    })
    // Toggle A → still see row 2 below B (no flicker).
    store.commit('page/view/gridGrouped/TOGGLE_COLLAPSE', { field_1: 'A' })
    await wrapper.vm.$nextTick()
    const rowsAfter = wrapper.findAll('.grid-grouped-row')
    expect(rowsAfter).toHaveLength(1)
    expect(rowsAfter[0].attributes('data-row-id')).toBe('2')
    // Toggle back open → row 1 reappears in A immediately, still no
    // placeholders elsewhere.
    store.commit('page/view/gridGrouped/TOGGLE_COLLAPSE', { field_1: 'A' })
    await wrapper.vm.$nextTick()
    expect(wrapper.findAll('.grid-grouped-row')).toHaveLength(2)
    expect(wrapper.findAll('.grid-grouped-placeholder')).toHaveLength(0)
  })

  test('regression: an optimistic group-by edit moves the row to its new banner; no neighbour displacement', async () => {
    // Reproducer for the original visual bug, using the
    // `optimisticEditRow` action (which is what an inline edit would
    // dispatch). The action now structurally moves the row; render
    // result must place it under the new banner.
    const wrapper = await mountGrouped({
      groupByFields,
      nodes: [
        { path: { field_1: 'Development' }, depth: 0, rowCount: 1 },
        {
          path: { field_1: 'Development', field_2: true },
          depth: 1,
          rowCount: 1,
        },
        { path: { field_1: null }, depth: 0, rowCount: 2 },
        { path: { field_1: null, field_2: true }, depth: 1, rowCount: 1 },
        { path: { field_1: null, field_2: false }, depth: 1, rowCount: 1 },
      ],
      rows: [
        { id: 1, field_1: null, field_2: false }, // pre-edit BE state
        { id: 2, field_1: null, field_2: true },
        { id: 10, field_1: 'Development', field_2: true },
      ],
    })
    // Dispatch the optimistic action — what an inline edit would do.
    await store.dispatch('page/view/gridGrouped/optimisticEditRow', {
      rowId: 1,
      values: { field_1: 'Development' },
    })
    await wrapper.vm.$nextTick()
    const row1 = wrapper
      .findAll('.grid-grouped-row')
      .find((w) => w.attributes('data-row-id') === '1')
    expect(row1).toBeDefined()
    const banners = wrapper.findAll('.grid-grouped-banner')
    // The absolute-positioned shell is the row's parent wrapper —
    // the inner `.grid-grouped-row` is static inside it so wrapper
    // decorations (row coloring) can wrap the row cleanly.
    const row1Wrapper = row1.element.closest('.grid-grouped-row__wrapper')
    const row1Y = parseInt(row1Wrapper.style.top, 10)
    const bannersAbove = banners.filter(
      (b) => parseInt(b.element.style.top, 10) < row1Y
    )
    const last = bannersAbove[bannersAbove.length - 1]
    // Closest banner above row 1 must be a depth-1 banner (a leaf
    // group's header, since 2-level group-by).
    expect(last.attributes('data-depth')).toBe('1')
  })
})
