/**
 * Tests for the grouped grid Vuex module (per-section caching).
 *
 * The module's job is to keep the per-section row buckets consistent
 * with BE truth + the user's optimistic edits in flight. Each mutation
 * is a tiny, deterministic state transition; each action composes
 * those mutations + the pure render utilities + the network layer.
 *
 * Architecture invariant under test: a row at section S position P
 * lives at `state.sectionRows.get(S).get(P)`. The reverse index
 * `state.rowIndex.get(rowId)` returns `{sectionKey, position}` and
 * stays in lockstep with every structural mutation.
 *
 * What is NOT tested here:
 *   - Pixel layout / DOM emission — covered in
 *     `test/unit/database/utils/gridGroupedRender.spec.js`.
 *   - Component-level scroll handling — covered in component tests +
 *     e2e.
 */
import { vi } from 'vitest'
import gridGroupedModule from '@baserow/modules/database/store/view/gridGrouped'
import { pathKey } from '@baserow/modules/database/utils/gridGroupedRender'
import RowService from '@baserow/modules/database/services/row'

vi.mock('@baserow/modules/database/services/row', () => ({
  default: vi.fn(),
}))

const identityRegistry = {
  get() {
    return {
      isEqual: (_field, a, b) => JSON.stringify(a) === JSON.stringify(b),
      getGroupValueFromRowValue: (_field, value) => value,
      getRowValueFromGroupValue: (_field, value) => value,
      onRowChange: (_row, _field, value) => value,
      prepareValueForUpdate: (_field, value) => value,
      getSortTypes: (_field) => ({
        default: {
          function: (fieldName, order) => (a, b) => {
            const av = a[fieldName]
            const bv = b[fieldName]
            const cmp = av < bv ? -1 : av > bv ? 1 : 0
            return order === 'DESC' ? -cmp : cmp
          },
        },
      }),
    }
  },
}

const textField = (id) => ({ id, name: `f${id}`, type: 'text' })

const makeContext = (overrides = {}) => {
  const state = gridGroupedModule.state()
  state.registry = identityRegistry
  const commit = (name, payload) => {
    const m = gridGroupedModule.mutations[name]
    if (!m) throw new Error(`Unknown mutation: ${name}`)
    m(state, payload)
  }
  const dispatched = []
  const stubs = {}
  const fakeThis = {
    $client: {},
    $registry: identityRegistry,
  }
  const dispatch = async (name, payload) => {
    dispatched.push({ name, payload })
    if (Object.prototype.hasOwnProperty.call(stubs, name)) {
      return stubs[name](payload)
    }
    const a = gridGroupedModule.actions[name]
    if (!a) return
    return a.call(fakeThis, { commit, state, dispatch, getters: {} }, payload)
  }
  const stubAction = (name, impl) => {
    stubs[name] = impl
  }
  return { state, commit, dispatch, dispatched, stubAction, ...overrides }
}

// Initialise + seed a tree + one row in section A at position 0.
// Returns helpers for the section keys used in the test.
const seedSingleLevel = (commit, opts = {}) => {
  const fields = [textField(1)]
  commit('INIT', {
    gridId: 1,
    groupByFields: fields,
    collapseMode: 'expand',
  })
  commit('SET_TREE', {
    nodes: opts.nodes ?? [
      { path: { field_1: 'A' }, depth: 0, rowCount: 1 },
      { path: { field_1: 'B' }, depth: 0, rowCount: 0 },
    ],
    fullyLoaded: true,
  })
  const aKey = pathKey({ field_1: 'A' }, fields)
  const bKey = pathKey({ field_1: 'B' }, fields)
  if (opts.seedRow !== false) {
    commit('MERGE_SECTION_ROWS', {
      sectionKey: aKey,
      startPosition: 0,
      rows: [{ id: 1, field_1: 'A' }],
    })
  }
  return { fields, aKey, bKey }
}

describe('gridGrouped store / state shape', () => {
  test('initial state has empty tree, empty sectionRows, empty pending, expand mode', () => {
    const s = gridGroupedModule.state()
    expect(s.tree).toEqual({ nodes: [], fullyLoaded: false })
    expect(s.collapse).toEqual({ mode: 'expand', paths: [] })
    expect(s.sectionRows).toBeInstanceOf(Map)
    expect(s.sectionRows.size).toBe(0)
    expect(s.rowIndex).toBeInstanceOf(Map)
    expect(s.rowIndex.size).toBe(0)
    expect(s.pendingMutations).toBeInstanceOf(Map)
    expect(s.pendingMutations.size).toBe(0)
    expect(s.viewport).toEqual({ scrollTop: 0, clientHeight: 0 })
    expect(s.groupByFields).toEqual([])
    expect(s.sortings).toEqual([])
    expect(s.sectionFetched).toBeInstanceOf(Map)
    expect(s.sectionInflight).toBeInstanceOf(Map)
  })
})

describe('gridGrouped store / mutations', () => {
  test('INIT wipes per-section state', () => {
    const { state, commit } = makeContext()
    const fields = [textField(1)]
    commit('INIT', { gridId: 1, groupByFields: fields })
    commit('SET_TREE', {
      nodes: [{ path: { field_1: 'A' }, depth: 0, rowCount: 1 }],
      fullyLoaded: true,
    })
    commit('MERGE_SECTION_ROWS', {
      sectionKey: pathKey({ field_1: 'A' }, fields),
      startPosition: 0,
      rows: [{ id: 1, field_1: 'A' }],
    })
    commit('INIT', { gridId: 2, groupByFields: [textField(2)] })
    expect(state.sectionRows.size).toBe(0)
    expect(state.rowIndex.size).toBe(0)
    expect(state.tree.nodes).toEqual([])
    expect(state.pendingMutations.size).toBe(0)
  })

  test('MERGE_SECTION_ROWS writes rows into a section bucket at the given start position', () => {
    const { state, commit } = makeContext()
    const { aKey } = seedSingleLevel(commit, { seedRow: false })
    commit('MERGE_SECTION_ROWS', {
      sectionKey: aKey,
      startPosition: 5,
      rows: [
        { id: 10, field_1: 'A' },
        { id: 11, field_1: 'A' },
      ],
    })
    const bucket = state.sectionRows.get(aKey)
    expect(bucket.get(5).id).toBe(10)
    expect(bucket.get(6).id).toBe(11)
    expect(state.rowIndex.get(10)).toEqual({ sectionKey: aKey, position: 5 })
    expect(state.rowIndex.get(11)).toEqual({ sectionKey: aKey, position: 6 })
  })

  test('MERGE_SECTION_ROWS attaches `_` metadata block to each row', () => {
    const { state, commit } = makeContext()
    const { aKey } = seedSingleLevel(commit, { seedRow: false })
    commit('MERGE_SECTION_ROWS', {
      sectionKey: aKey,
      startPosition: 0,
      rows: [{ id: 7, field_1: 'A' }],
    })
    const row = state.sectionRows.get(aKey).get(0)
    expect(row._).toMatchObject({
      loading: false,
      persistentId: 'r7',
    })
  })

  test('MERGE_SECTION_ROWS dropping stale rowIndex entry when row appears at a new section/position', () => {
    // Section change between fetches (e.g., a remote rename): the new
    // merge should evict the row from its old bucket so we don't have
    // two copies floating around.
    const { state, commit } = makeContext()
    const { aKey, bKey } = seedSingleLevel(commit, { seedRow: false })
    commit('MERGE_SECTION_ROWS', {
      sectionKey: aKey,
      startPosition: 0,
      rows: [{ id: 1, field_1: 'A' }],
    })
    commit('MERGE_SECTION_ROWS', {
      sectionKey: bKey,
      startPosition: 0,
      rows: [{ id: 1, field_1: 'B' }],
    })
    expect(state.sectionRows.get(aKey)?.size ?? 0).toBe(0)
    expect(state.sectionRows.get(bKey).get(0).id).toBe(1)
    expect(state.rowIndex.get(1)).toEqual({ sectionKey: bKey, position: 0 })
  })

  test('INSERT_ROW_INTO_SECTION shifts existing positions ≥ position up by 1', () => {
    const { state, commit } = makeContext()
    const { aKey } = seedSingleLevel(commit, {
      nodes: [{ path: { field_1: 'A' }, depth: 0, rowCount: 3 }],
      seedRow: false,
    })
    commit('MERGE_SECTION_ROWS', {
      sectionKey: aKey,
      startPosition: 0,
      rows: [
        { id: 10, field_1: 'A' },
        { id: 11, field_1: 'A' },
        { id: 12, field_1: 'A' },
      ],
    })
    commit('INSERT_ROW_INTO_SECTION', {
      sectionKey: aKey,
      position: 1,
      row: { id: 99, field_1: 'A' },
    })
    const bucket = state.sectionRows.get(aKey)
    expect(bucket.get(0).id).toBe(10)
    expect(bucket.get(1).id).toBe(99)
    expect(bucket.get(2).id).toBe(11)
    expect(bucket.get(3).id).toBe(12)
    expect(state.rowIndex.get(11)).toEqual({ sectionKey: aKey, position: 2 })
    expect(state.rowIndex.get(12)).toEqual({ sectionKey: aKey, position: 3 })
    expect(state.rowIndex.get(99)).toEqual({ sectionKey: aKey, position: 1 })
  })

  test('REMOVE_ROW_FROM_SECTION shifts positions > position down by 1', () => {
    const { state, commit } = makeContext()
    const { aKey } = seedSingleLevel(commit, {
      nodes: [{ path: { field_1: 'A' }, depth: 0, rowCount: 3 }],
      seedRow: false,
    })
    commit('MERGE_SECTION_ROWS', {
      sectionKey: aKey,
      startPosition: 0,
      rows: [
        { id: 10, field_1: 'A' },
        { id: 11, field_1: 'A' },
        { id: 12, field_1: 'A' },
      ],
    })
    commit('REMOVE_ROW_FROM_SECTION', { sectionKey: aKey, position: 1 })
    const bucket = state.sectionRows.get(aKey)
    expect(bucket.get(0).id).toBe(10)
    expect(bucket.get(1).id).toBe(12)
    expect(bucket.get(2)).toBeUndefined()
    expect(state.rowIndex.get(11)).toBeUndefined()
    expect(state.rowIndex.get(12)).toEqual({ sectionKey: aKey, position: 1 })
  })

  test('INSERT/REMOVE preserves fetched-range coverage by shifting ranges', () => {
    const { state, commit } = makeContext()
    const { aKey } = seedSingleLevel(commit, {
      nodes: [{ path: { field_1: 'A' }, depth: 0, rowCount: 10 }],
      seedRow: false,
    })
    state.sectionFetched.set(aKey, new Set(['0:5', '7:10']))
    commit('INSERT_ROW_INTO_SECTION', {
      sectionKey: aKey,
      position: 3,
      row: { id: 99, field_1: 'A' },
    })
    // "0:5" spans position 3 → "0:6"; "7:10" entirely after → "8:11"
    expect([...state.sectionFetched.get(aKey)]).toEqual(['0:6', '8:11'])
    commit('REMOVE_ROW_FROM_SECTION', { sectionKey: aKey, position: 3 })
    // Insert+remove at same position should net-zero.
    expect([...state.sectionFetched.get(aKey)]).toEqual(['0:5', '7:10'])
  })

  test('MOVE_ROW_BETWEEN_SECTIONS atomically removes from source and inserts into target', () => {
    const { state, commit } = makeContext()
    const { aKey, bKey } = seedSingleLevel(commit, {
      nodes: [
        { path: { field_1: 'A' }, depth: 0, rowCount: 3 },
        { path: { field_1: 'B' }, depth: 0, rowCount: 1 },
      ],
      seedRow: false,
    })
    commit('MERGE_SECTION_ROWS', {
      sectionKey: aKey,
      startPosition: 0,
      rows: [
        { id: 10, field_1: 'A' },
        { id: 11, field_1: 'A' },
        { id: 12, field_1: 'A' },
      ],
    })
    commit('MERGE_SECTION_ROWS', {
      sectionKey: bKey,
      startPosition: 0,
      rows: [{ id: 20, field_1: 'B' }],
    })
    commit('MOVE_ROW_BETWEEN_SECTIONS', {
      rowId: 11,
      fromSectionKey: aKey,
      fromPosition: 1,
      toSectionKey: bKey,
      toPosition: 1,
    })
    // Source: row 11 gone, row 12 shifted to position 1
    const aBucket = state.sectionRows.get(aKey)
    expect(aBucket.get(0).id).toBe(10)
    expect(aBucket.get(1).id).toBe(12)
    expect(state.rowIndex.get(11).sectionKey).toBe(bKey)
    // Target: row 20 still at 0, row 11 at 1
    const bBucket = state.sectionRows.get(bKey)
    expect(bBucket.get(0).id).toBe(20)
    expect(bBucket.get(1).id).toBe(11)
    expect(state.rowIndex.get(11)).toEqual({ sectionKey: bKey, position: 1 })
  })

  test('UPDATE_ROW_DATA modifies field data in place without moving the row', () => {
    const { state, commit } = makeContext()
    const { aKey } = seedSingleLevel(commit)
    commit('UPDATE_ROW_DATA', {
      rowId: 1,
      patch: { id: 1, field_2: 'new' },
    })
    const bucket = state.sectionRows.get(aKey)
    expect(bucket.get(0).field_2).toBe('new')
    expect(state.rowIndex.get(1)).toEqual({ sectionKey: aKey, position: 0 })
  })

  test('RECONCILE_SECTIONS drops buckets whose section keys are no longer in the tree', () => {
    const { state, commit } = makeContext()
    const { aKey, bKey } = seedSingleLevel(commit, {
      nodes: [
        { path: { field_1: 'A' }, depth: 0, rowCount: 1 },
        { path: { field_1: 'B' }, depth: 0, rowCount: 1 },
      ],
    })
    commit('MERGE_SECTION_ROWS', {
      sectionKey: bKey,
      startPosition: 0,
      rows: [{ id: 2, field_1: 'B' }],
    })
    state.sectionFetched.set(bKey, new Set(['0:1']))
    commit('RECONCILE_SECTIONS', { validSectionKeys: [aKey] })
    expect(state.sectionRows.has(bKey)).toBe(false)
    expect(state.sectionFetched.has(bKey)).toBe(false)
    expect(state.rowIndex.get(2)).toBeUndefined()
    // A bucket survives
    expect(state.sectionRows.has(aKey)).toBe(true)
  })

  test('UPDATE_TREE_NODE_COUNT clamps to 0 and never goes negative', () => {
    const { state, commit } = makeContext()
    commit('INIT', { gridId: 1, groupByFields: [textField(1)] })
    commit('SET_TREE', {
      nodes: [{ path: { field_1: 'A' }, depth: 0, rowCount: 1 }],
      fullyLoaded: true,
    })
    commit('UPDATE_TREE_NODE_COUNT', { path: { field_1: 'A' }, delta: -5 })
    expect(state.tree.nodes[0].rowCount).toBe(0)
  })

  test('TOGGLE_COLLAPSE does NOT touch sectionRows or sectionFetched', () => {
    // Regression: the original global-offset architecture had to wipe
    // fetched bookkeeping + strip _globalOffset on every collapse
    // toggle. Per-section caches are invariant of other groups'
    // collapse state, so this state must survive.
    const { state, commit } = makeContext()
    const { aKey } = seedSingleLevel(commit)
    state.sectionFetched.set(aKey, new Set(['0:1']))
    commit('TOGGLE_COLLAPSE', { field_1: 'A' })
    expect(state.sectionRows.get(aKey).size).toBe(1)
    expect(state.sectionFetched.get(aKey).size).toBe(1)
  })

  test('SET_PENDING_ROW merges patch field values onto any existing entry', () => {
    const { state, commit } = makeContext()
    commit('SET_PENDING_ROW', { rowId: 1, mutation: { patch: { f1: 'A' } } })
    commit('SET_PENDING_ROW', { rowId: 1, mutation: { patch: { f2: 'B' } } })
    expect(state.pendingMutations.get(1).patch).toEqual({ f1: 'A', f2: 'B' })
  })

  test('SET_VIEWPORT updates scroll position + height', () => {
    const { state, commit } = makeContext()
    commit('SET_VIEWPORT', { scrollTop: 100, clientHeight: 800 })
    expect(state.viewport).toEqual({ scrollTop: 100, clientHeight: 800 })
  })
})

describe('gridGrouped store / actions', () => {
  describe('optimisticEditRow', () => {
    test('non-group-by edit only writes a pending patch — tree + buckets unchanged', async () => {
      const ctx = makeContext()
      const { aKey } = seedSingleLevel(ctx.commit)
      await ctx.dispatch('optimisticEditRow', {
        rowId: 1,
        values: { field_2: 'new' },
      })
      expect(ctx.state.pendingMutations.get(1).patch).toEqual({
        field_2: 'new',
      })
      expect(ctx.state.tree.nodes[0].rowCount).toBe(1)
      expect(ctx.state.sectionRows.get(aKey).get(0).id).toBe(1)
    })

    test('group-by edit structurally moves the row + adjusts tree counts', async () => {
      const ctx = makeContext()
      const { aKey, bKey } = seedSingleLevel(ctx.commit, {
        nodes: [
          { path: { field_1: 'A' }, depth: 0, rowCount: 1 },
          { path: { field_1: 'B' }, depth: 0, rowCount: 0 },
        ],
      })
      await ctx.dispatch('optimisticEditRow', {
        rowId: 1,
        values: { field_1: 'B' },
      })
      // Tree counts shifted.
      const a = ctx.state.tree.nodes.find((n) => n.path.field_1 === 'A')
      const b = ctx.state.tree.nodes.find((n) => n.path.field_1 === 'B')
      expect(a.rowCount).toBe(0)
      expect(b.rowCount).toBe(1)
      // Row 1 structurally moved.
      expect(ctx.state.sectionRows.get(aKey)?.has(0)).toBe(false)
      expect(ctx.state.sectionRows.get(bKey).get(0).id).toBe(1)
      // Pending entry retains from/to bookkeeping for rollback.
      const pending = ctx.state.pendingMutations.get(1)
      expect(pending.patch).toEqual({ field_1: 'B' })
      expect(pending.fromSectionKey).toBe(aKey)
      expect(pending.toSectionKey).toBe(bKey)
    })

    test('group-by edit creating a brand-new group inserts a tree node', async () => {
      const ctx = makeContext()
      const fields = [textField(1)]
      seedSingleLevel(ctx.commit, {
        nodes: [{ path: { field_1: 'A' }, depth: 0, rowCount: 1 }],
      })
      await ctx.dispatch('optimisticEditRow', {
        rowId: 1,
        values: { field_1: 'BRAND_NEW' },
      })
      const brand = ctx.state.tree.nodes.find(
        (n) => n.path.field_1 === 'BRAND_NEW'
      )
      expect(brand).toBeDefined()
      expect(brand.rowCount).toBe(1)
      const newKey = pathKey({ field_1: 'BRAND_NEW' }, fields)
      expect(ctx.state.sectionRows.get(newKey).get(0).id).toBe(1)
    })

    test('cross-section move uses sort function to pick insertion position, not append-at-end', async () => {
      // Section B already has 3 loaded rows ordered by `field_2`
      // ASC: ["apple", "mango", "peach"]. Moving in row 1 with
      // field_2="banana" should slot in at position 1 (between apple
      // and mango), shifting mango/peach up by 1.
      const ctx = makeContext()
      const fields = [textField(1), textField(2)]
      ctx.commit('INIT', {
        gridId: 1,
        groupByFields: [textField(1)],
        sortings: [{ field: 2, order: 'ASC', type: 'default' }],
        collapseMode: 'expand',
      })
      ctx.commit('SET_TREE', {
        nodes: [
          { path: { field_1: 'A' }, depth: 0, rowCount: 1 },
          { path: { field_1: 'B' }, depth: 0, rowCount: 3 },
        ],
        fullyLoaded: true,
      })
      const aKey = pathKey({ field_1: 'A' }, [textField(1)])
      const bKey = pathKey({ field_1: 'B' }, [textField(1)])
      ctx.commit('MERGE_SECTION_ROWS', {
        sectionKey: aKey,
        startPosition: 0,
        rows: [{ id: 1, field_1: 'A', field_2: 'banana' }],
      })
      ctx.commit('MERGE_SECTION_ROWS', {
        sectionKey: bKey,
        startPosition: 0,
        rows: [
          { id: 10, field_1: 'B', field_2: 'apple' },
          { id: 11, field_1: 'B', field_2: 'mango' },
          { id: 12, field_1: 'B', field_2: 'peach' },
        ],
      })
      await ctx.dispatch('optimisticEditRow', {
        rowId: 1,
        values: { field_1: 'B' },
        fields,
      })
      const bBucket = ctx.state.sectionRows.get(bKey)
      expect(bBucket.get(0).id).toBe(10) // apple
      expect(bBucket.get(1).id).toBe(1) // banana ← inserted here
      expect(bBucket.get(2).id).toBe(11) // mango (shifted)
      expect(bBucket.get(3).id).toBe(12) // peach (shifted)
    })

    test('cross-section move with empty target bucket does NOT insert (refetch reconciles)', async () => {
      // Empty target → sort can't pick a confident position. The
      // optimistic action only removes from source; the next
      // viewport-driven refetch brings the row into the target
      // bucket at its true position.
      const ctx = makeContext()
      const fields = [textField(1), textField(2)]
      ctx.commit('INIT', {
        gridId: 1,
        groupByFields: [textField(1)],
        sortings: [{ field: 2, order: 'ASC', type: 'default' }],
        collapseMode: 'expand',
      })
      ctx.commit('SET_TREE', {
        nodes: [
          { path: { field_1: 'A' }, depth: 0, rowCount: 1 },
          { path: { field_1: 'B' }, depth: 0, rowCount: 0 },
        ],
        fullyLoaded: true,
      })
      const aKey = pathKey({ field_1: 'A' }, [textField(1)])
      const bKey = pathKey({ field_1: 'B' }, [textField(1)])
      ctx.commit('MERGE_SECTION_ROWS', {
        sectionKey: aKey,
        startPosition: 0,
        rows: [{ id: 1, field_1: 'A', field_2: 'x' }],
      })
      await ctx.dispatch('optimisticEditRow', {
        rowId: 1,
        values: { field_1: 'B' },
        fields,
      })
      expect(ctx.state.sectionRows.get(aKey)?.size ?? 0).toBe(0)
      expect(ctx.state.sectionRows.get(bKey)?.size ?? 0).toBe(0)
      // Tree counts shifted, pending records the move for rollback.
      expect(
        ctx.state.tree.nodes.find((n) => n.path.field_1 === 'A').rowCount
      ).toBe(0)
      expect(
        ctx.state.tree.nodes.find((n) => n.path.field_1 === 'B').rowCount
      ).toBe(1)
      const pending = ctx.state.pendingMutations.get(1)
      expect(pending.toPosition).toBeNull()
      expect(pending.fromRowSnapshot).toMatchObject({ id: 1, field_1: 'A' })
    })

    test('sort-before-all + bucket starts at position 0 → insert at 0 (safe edge)', async () => {
      // We've loaded the first page, so we know nothing else is
      // before it — placing at position 0 is safe.
      const ctx = makeContext()
      const fields = [textField(1), textField(2)]
      ctx.commit('INIT', {
        gridId: 1,
        groupByFields: [textField(1)],
        sortings: [{ field: 2, order: 'ASC', type: 'default' }],
        collapseMode: 'expand',
      })
      ctx.commit('SET_TREE', {
        nodes: [
          { path: { field_1: 'A' }, depth: 0, rowCount: 1 },
          { path: { field_1: 'B' }, depth: 0, rowCount: 10 },
        ],
        fullyLoaded: true,
      })
      const aKey = pathKey({ field_1: 'A' }, [textField(1)])
      const bKey = pathKey({ field_1: 'B' }, [textField(1)])
      ctx.commit('MERGE_SECTION_ROWS', {
        sectionKey: aKey,
        startPosition: 0,
        rows: [{ id: 1, field_1: 'A', field_2: 'apple' }],
      })
      // B's loaded rows all sort AFTER "apple". Loaded from
      // position 0 (so before-first is safe).
      ctx.commit('MERGE_SECTION_ROWS', {
        sectionKey: bKey,
        startPosition: 0,
        rows: [
          { id: 10, field_1: 'B', field_2: 'mango' },
          { id: 11, field_1: 'B', field_2: 'orange' },
          { id: 12, field_1: 'B', field_2: 'peach' },
        ],
      })
      await ctx.dispatch('optimisticEditRow', {
        rowId: 1,
        values: { field_1: 'B' },
        fields,
      })
      const bBucket = ctx.state.sectionRows.get(bKey)
      // Row 1 at position 0; existing rows shifted up by 1.
      expect(bBucket.get(0).id).toBe(1)
      expect(bBucket.get(1).id).toBe(10)
      expect(bBucket.get(3).id).toBe(12)
    })

    test('sort-before-all but bucket does NOT start at 0 → no insert (unloaded territory before)', async () => {
      const ctx = makeContext()
      const fields = [textField(1), textField(2)]
      ctx.commit('INIT', {
        gridId: 1,
        groupByFields: [textField(1)],
        sortings: [{ field: 2, order: 'ASC', type: 'default' }],
        collapseMode: 'expand',
      })
      ctx.commit('SET_TREE', {
        nodes: [
          { path: { field_1: 'A' }, depth: 0, rowCount: 1 },
          { path: { field_1: 'B' }, depth: 0, rowCount: 10 },
        ],
        fullyLoaded: true,
      })
      const aKey = pathKey({ field_1: 'A' }, [textField(1)])
      const bKey = pathKey({ field_1: 'B' }, [textField(1)])
      ctx.commit('MERGE_SECTION_ROWS', {
        sectionKey: aKey,
        startPosition: 0,
        rows: [{ id: 1, field_1: 'A', field_2: 'apple' }],
      })
      // B's loaded window starts at position 5, NOT 0.
      ctx.commit('MERGE_SECTION_ROWS', {
        sectionKey: bKey,
        startPosition: 5,
        rows: [
          { id: 10, field_1: 'B', field_2: 'mango' },
          { id: 11, field_1: 'B', field_2: 'orange' },
        ],
      })
      await ctx.dispatch('optimisticEditRow', {
        rowId: 1,
        values: { field_1: 'B' },
        fields,
      })
      // Removed from A, B unchanged — refetch handles placement.
      expect(ctx.state.sectionRows.get(aKey)?.size ?? 0).toBe(0)
      expect(ctx.state.sectionRows.get(bKey).get(5).id).toBe(10)
      expect(ctx.state.sectionRows.get(bKey).get(6).id).toBe(11)
    })

    test('sort-after-all + bucket reaches old last position → insert at new last (safe edge)', async () => {
      const ctx = makeContext()
      const fields = [textField(1), textField(2)]
      ctx.commit('INIT', {
        gridId: 1,
        groupByFields: [textField(1)],
        sortings: [{ field: 2, order: 'ASC', type: 'default' }],
        collapseMode: 'expand',
      })
      ctx.commit('SET_TREE', {
        nodes: [
          { path: { field_1: 'A' }, depth: 0, rowCount: 1 },
          { path: { field_1: 'B' }, depth: 0, rowCount: 3 },
        ],
        fullyLoaded: true,
      })
      const aKey = pathKey({ field_1: 'A' }, [textField(1)])
      const bKey = pathKey({ field_1: 'B' }, [textField(1)])
      ctx.commit('MERGE_SECTION_ROWS', {
        sectionKey: aKey,
        startPosition: 0,
        rows: [{ id: 1, field_1: 'A', field_2: 'zebra' }],
      })
      // B loaded positions 0..2 (the entire pre-edit section). After
      // tree count +1, newRowCount=4; loaded max=2=newRowCount-2.
      ctx.commit('MERGE_SECTION_ROWS', {
        sectionKey: bKey,
        startPosition: 0,
        rows: [
          { id: 10, field_1: 'B', field_2: 'apple' },
          { id: 11, field_1: 'B', field_2: 'mango' },
          { id: 12, field_1: 'B', field_2: 'peach' },
        ],
      })
      await ctx.dispatch('optimisticEditRow', {
        rowId: 1,
        values: { field_1: 'B' },
        fields,
      })
      const bBucket = ctx.state.sectionRows.get(bKey)
      // Insert at new last position (3); existing rows untouched.
      expect(bBucket.get(0).id).toBe(10)
      expect(bBucket.get(3).id).toBe(1)
    })

    test('sort-after-all but bucket does NOT reach old last → no insert (unloaded territory after)', async () => {
      const ctx = makeContext()
      const fields = [textField(1), textField(2)]
      ctx.commit('INIT', {
        gridId: 1,
        groupByFields: [textField(1)],
        sortings: [{ field: 2, order: 'ASC', type: 'default' }],
        collapseMode: 'expand',
      })
      ctx.commit('SET_TREE', {
        nodes: [
          { path: { field_1: 'A' }, depth: 0, rowCount: 1 },
          { path: { field_1: 'B' }, depth: 0, rowCount: 10 },
        ],
        fullyLoaded: true,
      })
      const aKey = pathKey({ field_1: 'A' }, [textField(1)])
      const bKey = pathKey({ field_1: 'B' }, [textField(1)])
      ctx.commit('MERGE_SECTION_ROWS', {
        sectionKey: aKey,
        startPosition: 0,
        rows: [{ id: 1, field_1: 'A', field_2: 'zebra' }],
      })
      ctx.commit('MERGE_SECTION_ROWS', {
        sectionKey: bKey,
        startPosition: 0,
        rows: [
          { id: 10, field_1: 'B', field_2: 'apple' },
          { id: 11, field_1: 'B', field_2: 'mango' },
        ],
      })
      await ctx.dispatch('optimisticEditRow', {
        rowId: 1,
        values: { field_1: 'B' },
        fields,
      })
      expect(ctx.state.sectionRows.get(aKey)?.size ?? 0).toBe(0)
      expect(ctx.state.sectionRows.get(bKey).size).toBe(2)
    })

    test('2-level group-by: depth-1 edit shifts sub-group counts; depth-0 unchanged', async () => {
      const ctx = makeContext()
      const fields = [textField(1), textField(2)]
      ctx.commit('INIT', {
        gridId: 1,
        groupByFields: fields,
        collapseMode: 'expand',
      })
      ctx.commit('SET_TREE', {
        nodes: [
          { path: { field_1: 'A' }, depth: 0, rowCount: 2 },
          { path: { field_1: 'A', field_2: true }, depth: 1, rowCount: 1 },
          { path: { field_1: 'A', field_2: false }, depth: 1, rowCount: 1 },
        ],
        fullyLoaded: true,
      })
      const trueLeafKey = pathKey({ field_1: 'A', field_2: true }, fields)
      const falseLeafKey = pathKey({ field_1: 'A', field_2: false }, fields)
      ctx.commit('MERGE_SECTION_ROWS', {
        sectionKey: trueLeafKey,
        startPosition: 0,
        rows: [{ id: 1, field_1: 'A', field_2: true }],
      })
      await ctx.dispatch('optimisticEditRow', {
        rowId: 1,
        values: { field_2: false },
      })
      const a = ctx.state.tree.nodes.find(
        (n) => n.depth === 0 && n.path.field_1 === 'A'
      )
      const aTrue = ctx.state.tree.nodes.find(
        (n) =>
          n.depth === 1 && n.path.field_1 === 'A' && n.path.field_2 === true
      )
      const aFalse = ctx.state.tree.nodes.find(
        (n) =>
          n.depth === 1 && n.path.field_1 === 'A' && n.path.field_2 === false
      )
      expect(a.rowCount).toBe(2) // depth-0 unchanged
      expect(aTrue.rowCount).toBe(0)
      expect(aFalse.rowCount).toBe(2)
      // Row structurally moved.
      expect(ctx.state.sectionRows.get(trueLeafKey)?.has(0)).toBe(false)
      expect(ctx.state.sectionRows.get(falseLeafKey).get(1).id).toBe(1)
    })
  })

  describe('commitPendingEdit', () => {
    test('writes BE response to row + clears pending; tree counts unchanged (already adjusted on optimistic)', async () => {
      const ctx = makeContext()
      const { aKey, bKey } = seedSingleLevel(ctx.commit, {
        nodes: [
          { path: { field_1: 'A' }, depth: 0, rowCount: 1 },
          { path: { field_1: 'B' }, depth: 0, rowCount: 0 },
        ],
      })
      await ctx.dispatch('optimisticEditRow', {
        rowId: 1,
        values: { field_1: 'B' },
      })
      await ctx.dispatch('commitPendingEdit', {
        rowId: 1,
        beRow: { id: 1, field_1: 'B', formula_99: 'computed' },
      })
      expect(ctx.state.pendingMutations.has(1)).toBe(false)
      // Row in B with merged data
      const row = ctx.state.sectionRows.get(bKey).get(0)
      expect(row).toMatchObject({
        id: 1,
        field_1: 'B',
        formula_99: 'computed',
      })
      // Tree counts where optimistic put them
      expect(
        ctx.state.tree.nodes.find((n) => n.path.field_1 === 'A').rowCount
      ).toBe(0)
      expect(
        ctx.state.tree.nodes.find((n) => n.path.field_1 === 'B').rowCount
      ).toBe(1)
    })

    test('BE response in a different group than optimistic move → re-moves to BE`s group', async () => {
      // Edge case: user typed value got normalised differently by BE.
      const ctx = makeContext()
      const fields = [textField(1)]
      const { aKey, bKey } = seedSingleLevel(ctx.commit, {
        nodes: [
          { path: { field_1: 'A' }, depth: 0, rowCount: 1 },
          { path: { field_1: 'B' }, depth: 0, rowCount: 0 },
          { path: { field_1: 'C' }, depth: 0, rowCount: 0 },
        ],
      })
      await ctx.dispatch('optimisticEditRow', {
        rowId: 1,
        values: { field_1: 'B' },
      })
      const cKey = pathKey({ field_1: 'C' }, fields)
      await ctx.dispatch('commitPendingEdit', {
        rowId: 1,
        beRow: { id: 1, field_1: 'C' },
      })
      expect(ctx.state.sectionRows.get(bKey)?.size ?? 0).toBe(0)
      expect(ctx.state.sectionRows.get(cKey).get(0).id).toBe(1)
      expect(
        ctx.state.tree.nodes.find((n) => n.path.field_1 === 'B').rowCount
      ).toBe(0)
      expect(
        ctx.state.tree.nodes.find((n) => n.path.field_1 === 'C').rowCount
      ).toBe(1)
    })
  })

  describe('refreshRowAfterChange', () => {
    test('matchFilters=false on unselect: row removed and tree counts decremented', async () => {
      const ctx = makeContext()
      const { aKey } = seedSingleLevel(ctx.commit, {
        nodes: [{ path: { field_1: 'A' }, depth: 0, rowCount: 1 }],
      })
      // Mark the row's filter-match flag as failed.
      ctx.commit('SET_ROW_MATCH_FLAGS', {
        rowId: 1,
        matchFilters: false,
        matchSortings: true,
      })
      await ctx.dispatch('refreshRowAfterChange', { rowId: 1 })
      expect(ctx.state.sectionRows.get(aKey)?.size ?? 0).toBe(0)
      expect(
        ctx.state.tree.nodes.find((n) => n.path.field_1 === 'A').rowCount
      ).toBe(0)
      expect(ctx.state.rowIndex.has(1)).toBe(false)
    })

    test('matchSortings=false on unselect: section tracking is cleared so next viewport tick refetches', async () => {
      const ctx = makeContext()
      const { aKey } = seedSingleLevel(ctx.commit, {
        nodes: [{ path: { field_1: 'A' }, depth: 0, rowCount: 1 }],
      })
      ctx.state.sectionFetched.set(aKey, new Set(['0:1']))
      ctx.commit('SET_ROW_MATCH_FLAGS', {
        rowId: 1,
        matchFilters: true,
        matchSortings: false,
      })
      ctx.stubAction('ensureRowsForViewport', () => {})
      await ctx.dispatch('refreshRowAfterChange', { rowId: 1 })
      // Tracking gone; row still in the bucket awaiting refetch.
      expect(ctx.state.sectionFetched.has(aKey)).toBe(false)
      expect(ctx.state.sectionRows.has(aKey)).toBe(false)
    })

    test('all match flags true: no-op', async () => {
      const ctx = makeContext()
      const { aKey } = seedSingleLevel(ctx.commit, {
        nodes: [{ path: { field_1: 'A' }, depth: 0, rowCount: 1 }],
      })
      ctx.commit('SET_ROW_MATCH_FLAGS', {
        rowId: 1,
        matchFilters: true,
        matchSortings: true,
      })
      await ctx.dispatch('refreshRowAfterChange', { rowId: 1 })
      expect(ctx.state.sectionRows.get(aKey).get(0).id).toBe(1)
      expect(
        ctx.state.tree.nodes.find((n) => n.path.field_1 === 'A').rowCount
      ).toBe(1)
    })
  })

  describe('selectCell / clearCellSelection', () => {
    test('selectCell on a different row refreshes the previously-selected row', async () => {
      const ctx = makeContext()
      const { aKey } = seedSingleLevel(ctx.commit, {
        nodes: [{ path: { field_1: 'A' }, depth: 0, rowCount: 2 }],
        seedRow: false,
      })
      ctx.commit('MERGE_SECTION_ROWS', {
        sectionKey: aKey,
        startPosition: 0,
        rows: [
          { id: 1, field_1: 'A' },
          { id: 2, field_1: 'A' },
        ],
      })
      // Row 1 has a non-matching filter; row 2 is the new selection.
      ctx.commit('SELECT_CELL', { rowId: 1, fieldId: 1 })
      ctx.commit('SET_ROW_MATCH_FLAGS', {
        rowId: 1,
        matchFilters: false,
        matchSortings: true,
      })
      await ctx.dispatch('selectCell', { rowId: 2, fieldId: 1 })
      // Row 1 dropped; row 2 remains. Tree count decremented.
      expect(ctx.state.sectionRows.get(aKey).size).toBe(1)
      expect(
        ctx.state.tree.nodes.find((n) => n.path.field_1 === 'A').rowCount
      ).toBe(1)
      expect(ctx.state.selectedCell).toEqual({ rowId: 2, fieldId: 1 })
    })

    test('clearCellSelection refreshes the previously-selected row', async () => {
      const ctx = makeContext()
      const { aKey } = seedSingleLevel(ctx.commit, {
        nodes: [{ path: { field_1: 'A' }, depth: 0, rowCount: 1 }],
      })
      ctx.commit('SELECT_CELL', { rowId: 1, fieldId: 1 })
      ctx.commit('SET_ROW_MATCH_FLAGS', {
        rowId: 1,
        matchFilters: false,
        matchSortings: true,
      })
      await ctx.dispatch('clearCellSelection')
      expect(ctx.state.selectedCell).toBeNull()
      expect(ctx.state.sectionRows.get(aKey)?.size ?? 0).toBe(0)
    })
  })

  describe('rollbackPendingEdit', () => {
    test('reverses structural move + tree-count changes and clears pending', async () => {
      const ctx = makeContext()
      const { aKey, bKey } = seedSingleLevel(ctx.commit, {
        nodes: [
          { path: { field_1: 'A' }, depth: 0, rowCount: 1 },
          { path: { field_1: 'B' }, depth: 0, rowCount: 0 },
        ],
      })
      await ctx.dispatch('optimisticEditRow', {
        rowId: 1,
        values: { field_1: 'B' },
      })
      await ctx.dispatch('rollbackPendingEdit', { rowId: 1 })
      expect(ctx.state.pendingMutations.has(1)).toBe(false)
      // Row back in A.
      expect(ctx.state.sectionRows.get(bKey)?.size ?? 0).toBe(0)
      expect(ctx.state.sectionRows.get(aKey).get(0).id).toBe(1)
      // Tree counts restored.
      expect(
        ctx.state.tree.nodes.find((n) => n.path.field_1 === 'A').rowCount
      ).toBe(1)
      expect(
        ctx.state.tree.nodes.find((n) => n.path.field_1 === 'B').rowCount
      ).toBe(0)
    })
  })

  describe('handleRealtimeRowUpdated', () => {
    test('same-section update merges data; no structural move', async () => {
      const ctx = makeContext()
      const { aKey } = seedSingleLevel(ctx.commit)
      await ctx.dispatch('handleRealtimeRowUpdated', {
        row: { id: 1, field_1: 'A', field_2: 'new' },
      })
      const row = ctx.state.sectionRows.get(aKey).get(0)
      expect(row.field_2).toBe('new')
      expect(ctx.state.tree.nodes[0].rowCount).toBe(1)
    })

    test('cross-section realtime update structurally moves the row', async () => {
      const ctx = makeContext()
      const { aKey, bKey } = seedSingleLevel(ctx.commit, {
        nodes: [
          { path: { field_1: 'A' }, depth: 0, rowCount: 1 },
          { path: { field_1: 'B' }, depth: 0, rowCount: 0 },
        ],
      })
      await ctx.dispatch('handleRealtimeRowUpdated', {
        row: { id: 1, field_1: 'B' },
      })
      expect(ctx.state.sectionRows.get(aKey)?.size ?? 0).toBe(0)
      expect(ctx.state.sectionRows.get(bKey).get(0).id).toBe(1)
      expect(
        ctx.state.tree.nodes.find((n) => n.path.field_1 === 'A').rowCount
      ).toBe(0)
      expect(
        ctx.state.tree.nodes.find((n) => n.path.field_1 === 'B').rowCount
      ).toBe(1)
    })

    test('realtime for a row not in any bucket is a no-op (lazy refetch will catch it)', async () => {
      const ctx = makeContext()
      seedSingleLevel(ctx.commit)
      await ctx.dispatch('handleRealtimeRowUpdated', {
        row: { id: 99, field_1: 'A' },
      })
      // Row 99 was never in our cache; nothing to update.
      expect(ctx.state.rowIndex.get(99)).toBeUndefined()
    })
  })

  describe('handleRealtimeRowCreated', () => {
    test('bumps tree count for the row`s section', async () => {
      const ctx = makeContext()
      seedSingleLevel(ctx.commit)
      await ctx.dispatch('handleRealtimeRowCreated', {
        row: { id: 99, field_1: 'A' },
      })
      expect(
        ctx.state.tree.nodes.find((n) => n.path.field_1 === 'A').rowCount
      ).toBe(2)
    })

    test('inserts row at section position when supplied + section already loaded', async () => {
      const ctx = makeContext()
      const { aKey } = seedSingleLevel(ctx.commit, {
        nodes: [{ path: { field_1: 'A' }, depth: 0, rowCount: 3 }],
        seedRow: false,
      })
      ctx.commit('MERGE_SECTION_ROWS', {
        sectionKey: aKey,
        startPosition: 0,
        rows: [
          { id: 10, field_1: 'A' },
          { id: 11, field_1: 'A' },
          { id: 12, field_1: 'A' },
        ],
      })
      await ctx.dispatch('handleRealtimeRowCreated', {
        row: { id: 99, field_1: 'A' },
        sectionPosition: 1,
      })
      const bucket = ctx.state.sectionRows.get(aKey)
      expect(bucket.get(0).id).toBe(10)
      expect(bucket.get(1).id).toBe(99)
      expect(bucket.get(2).id).toBe(11)
      expect(bucket.get(3).id).toBe(12)
    })
  })

  describe('handleRealtimeRowDeleted', () => {
    test('structurally removes the row + decrements tree count', async () => {
      const ctx = makeContext()
      const { aKey } = seedSingleLevel(ctx.commit, {
        nodes: [{ path: { field_1: 'A' }, depth: 0, rowCount: 2 }],
        seedRow: false,
      })
      ctx.commit('MERGE_SECTION_ROWS', {
        sectionKey: aKey,
        startPosition: 0,
        rows: [
          { id: 10, field_1: 'A' },
          { id: 11, field_1: 'A' },
        ],
      })
      await ctx.dispatch('handleRealtimeRowDeleted', { rowId: 10 })
      const bucket = ctx.state.sectionRows.get(aKey)
      expect(bucket.get(0).id).toBe(11) // shifted down
      expect(bucket.size).toBe(1)
      expect(
        ctx.state.tree.nodes.find((n) => n.path.field_1 === 'A').rowCount
      ).toBe(1)
    })
  })

  describe('ensureRowsForViewport', () => {
    // Stub `fetchSectionRows` so we can assert what the coordinator
    // requests without touching the network.
    const makeCoordinatorContext = () => {
      const ctx = makeContext()
      const fields = [textField(1)]
      ctx.commit('INIT', {
        gridId: 1,
        groupByFields: fields,
        collapseMode: 'expand',
      })
      ctx.commit('SET_TREE', {
        nodes: [
          { path: { field_1: 'A' }, depth: 0, rowCount: 500 },
          { path: { field_1: 'B' }, depth: 0, rowCount: 200 },
        ],
        fullyLoaded: true,
      })
      const aKey = pathKey({ field_1: 'A' }, fields)
      const bKey = pathKey({ field_1: 'B' }, fields)
      const calls = []
      ctx.stubAction('fetchSectionRows', (payload) => {
        calls.push(payload)
      })
      return { ctx, calls, aKey, bKey }
    }

    test('requests one block-aligned chunk per visible section', async () => {
      const { ctx, calls, aKey } = makeCoordinatorContext()
      // Viewport covers just the top of A.
      ctx.commit('SET_VIEWPORT', { scrollTop: 0, clientHeight: 600 })
      await ctx.dispatch('ensureRowsForViewport', { padding: 0 })
      // Block size 120, viewport up to row ~17 of A → block [0:120].
      expect(calls).toEqual([
        { sectionKey: aKey, startPosition: 0, count: 120 },
      ])
    })

    test('viewport spanning two sections dispatches per section', async () => {
      const { ctx, calls, aKey, bKey } = makeCoordinatorContext()
      // A's section ends at y = HEADER_HEIGHT + 500*ROW_HEIGHT = 16548.
      // GROUP_GAP (8) + B's header (48) = 16604 is B's first row.
      // Pick a viewport spanning A's last ~5 rows + B's first ~10
      // rows.
      ctx.commit('SET_VIEWPORT', {
        scrollTop: 16400,
        clientHeight: 400,
      })
      await ctx.dispatch('ensureRowsForViewport', { padding: 0 })
      const keys = calls.map((c) => c.sectionKey)
      expect(keys).toContain(aKey)
      expect(keys).toContain(bKey)
    })

    test('does not re-fetch a block already in sectionFetched', async () => {
      const { ctx, calls, aKey } = makeCoordinatorContext()
      ctx.state.sectionFetched.set(aKey, new Set(['0:120']))
      ctx.commit('SET_VIEWPORT', { scrollTop: 0, clientHeight: 600 })
      await ctx.dispatch('ensureRowsForViewport', { padding: 0 })
      expect(calls).toEqual([])
    })

    test('does not double-fire while a block is in flight', async () => {
      const { ctx, calls, aKey } = makeCoordinatorContext()
      ctx.state.sectionInflight.set(aKey, new Set(['0:120']))
      ctx.commit('SET_VIEWPORT', { scrollTop: 0, clientHeight: 600 })
      await ctx.dispatch('ensureRowsForViewport', { padding: 0 })
      expect(calls).toEqual([])
    })

    test('block size caps to section row count so the fetch never bleeds into the next section', async () => {
      // Make A small so the 120-row block lands entirely inside it.
      const ctx = makeContext()
      const fields = [textField(1)]
      ctx.commit('INIT', {
        gridId: 1,
        groupByFields: fields,
        collapseMode: 'expand',
      })
      ctx.commit('SET_TREE', {
        nodes: [
          { path: { field_1: 'A' }, depth: 0, rowCount: 50 },
          { path: { field_1: 'B' }, depth: 0, rowCount: 50 },
        ],
        fullyLoaded: true,
      })
      const aKey = pathKey({ field_1: 'A' }, fields)
      const calls = []
      ctx.stubAction('fetchSectionRows', (payload) => calls.push(payload))
      ctx.commit('SET_VIEWPORT', { scrollTop: 0, clientHeight: 400 })
      await ctx.dispatch('ensureRowsForViewport', { padding: 0 })
      // The A block request asks for 120 rows; the action's job is to
      // cap it to A's 50 — verified separately in fetchSectionRows
      // tests. Here we just confirm the dispatch went out for A.
      expect(calls.some((c) => c.sectionKey === aKey)).toBe(true)
    })
  })

  describe('updateRowValue', () => {
    test('happy path: dispatches optimisticEditRow, calls BE, then commitPendingEdit with the response', async () => {
      // Pre-populate B with rows that bracket the moved row in sort
      // order so the optimistic insert is confident (mid-bucket
      // placement, not before-first / after-last).
      const ctx = makeContext()
      const fields = [textField(1), textField(2)]
      ctx.commit('INIT', {
        gridId: 1,
        groupByFields: [textField(1)],
        sortings: [{ field: 2, order: 'ASC', type: 'default' }],
        collapseMode: 'expand',
      })
      ctx.commit('SET_TREE', {
        nodes: [
          { path: { field_1: 'A' }, depth: 0, rowCount: 1 },
          { path: { field_1: 'B' }, depth: 0, rowCount: 2 },
        ],
        fullyLoaded: true,
      })
      const aKey = pathKey({ field_1: 'A' }, [textField(1)])
      const bKey = pathKey({ field_1: 'B' }, [textField(1)])
      ctx.commit('MERGE_SECTION_ROWS', {
        sectionKey: aKey,
        startPosition: 0,
        rows: [{ id: 1, field_1: 'A', field_2: 'm' }],
      })
      ctx.commit('MERGE_SECTION_ROWS', {
        sectionKey: bKey,
        startPosition: 0,
        rows: [
          { id: 10, field_1: 'B', field_2: 'a' },
          { id: 11, field_1: 'B', field_2: 'z' },
        ],
      })
      const batchUpdate = vi.fn().mockResolvedValue({
        data: { items: [{ id: 1, field_1: 'B', field_2: 'm', formula_99: 'be' }] },
      })
      RowService.mockReturnValue({ batchUpdate })

      await ctx.dispatch('updateRowValue', {
        table: { id: 99 },
        view: { id: 7 },
        fields,
        row: ctx.state.sectionRows.get(aKey).get(0),
        field: textField(1),
        value: 'B',
        oldValue: 'A',
      })

      expect(batchUpdate).toHaveBeenCalledTimes(1)
      expect(batchUpdate.mock.calls[0][0]).toBe(99) // table id
      expect(batchUpdate.mock.calls[0][1][0]).toMatchObject({
        id: 1,
        field_1: 'B',
      })
      const actionNames = ctx.dispatched.map((d) => d.name)
      expect(actionNames).toEqual([
        'updateRowValue',
        'optimisticEditRow',
        'commitPendingEdit',
      ])
      // Row landed between 'a' and 'z' (position 1), BE response
      // merged in.
      expect(ctx.state.sectionRows.get(bKey).get(1)).toMatchObject({
        id: 1,
        field_1: 'B',
        field_2: 'm',
        formula_99: 'be',
      })
      expect(ctx.state.pendingMutations.has(1)).toBe(false)
    })

    test('BE failure rolls back: row returns to source section, no pending entry', async () => {
      const ctx = makeContext()
      const { aKey, bKey } = seedSingleLevel(ctx.commit, {
        nodes: [
          { path: { field_1: 'A' }, depth: 0, rowCount: 1 },
          { path: { field_1: 'B' }, depth: 0, rowCount: 0 },
        ],
      })
      const batchUpdate = vi.fn().mockRejectedValue(new Error('BE down'))
      RowService.mockReturnValue({ batchUpdate })

      await expect(
        ctx.dispatch('updateRowValue', {
          table: { id: 99 },
          view: { id: 7 },
          fields: [textField(1)],
          row: ctx.state.sectionRows.get(aKey).get(0),
          field: textField(1),
          value: 'B',
          oldValue: 'A',
        })
      ).rejects.toThrow('BE down')

      // Row back in A; B's bucket empty; no pending entry.
      expect(ctx.state.sectionRows.get(aKey).get(0).id).toBe(1)
      expect(ctx.state.sectionRows.get(bKey)?.size ?? 0).toBe(0)
      expect(ctx.state.pendingMutations.has(1)).toBe(false)
      expect(
        ctx.state.tree.nodes.find((n) => n.path.field_1 === 'A').rowCount
      ).toBe(1)
      expect(
        ctx.state.tree.nodes.find((n) => n.path.field_1 === 'B').rowCount
      ).toBe(0)
    })
  })

  describe('TOGGLE_COLLAPSE stability', () => {
    test('toggling collapse on one section does NOT clear another section`s buckets', async () => {
      // Regression for the 4-placeholders-after-collapse bug. With
      // per-section caching, collapse changes don't touch any
      // bucket — section contents are invariant of which other groups
      // are expanded.
      const ctx = makeContext()
      const { aKey, bKey } = seedSingleLevel(ctx.commit, {
        nodes: [
          { path: { field_1: 'A' }, depth: 0, rowCount: 1 },
          { path: { field_1: 'B' }, depth: 0, rowCount: 1 },
        ],
      })
      ctx.commit('MERGE_SECTION_ROWS', {
        sectionKey: bKey,
        startPosition: 0,
        rows: [{ id: 2, field_1: 'B' }],
      })
      ctx.state.sectionFetched.set(aKey, new Set(['0:1']))
      ctx.state.sectionFetched.set(bKey, new Set(['0:1']))
      ctx.commit('TOGGLE_COLLAPSE', { field_1: 'A' })
      // Both buckets + both fetched ranges survive.
      expect(ctx.state.sectionRows.get(aKey).get(0).id).toBe(1)
      expect(ctx.state.sectionRows.get(bKey).get(0).id).toBe(2)
      expect(ctx.state.sectionFetched.get(aKey).size).toBe(1)
      expect(ctx.state.sectionFetched.get(bKey).size).toBe(1)
    })
  })

  // ─── Drag-reorder within a section ──────────────────────────────
  //
  // `moveRow` is the user-facing drop handler for the drag handle.
  // Same-section reorder only — cross-section drops go through
  // `moveRowToSection` (which patches the group-by field value).
  describe('moveRow', () => {
    const seedThreeRowsInA = (ctx) => {
      const { fields, aKey } = seedSingleLevel(ctx.commit, {
        nodes: [{ path: { field_1: 'A' }, depth: 0, rowCount: 3 }],
        seedRow: false,
      })
      ctx.commit('MERGE_SECTION_ROWS', {
        sectionKey: aKey,
        startPosition: 0,
        rows: [
          { id: 10, field_1: 'A' },
          { id: 11, field_1: 'A' },
          { id: 12, field_1: 'A' },
        ],
      })
      return { fields, aKey }
    }

    test('moves the row before the target row and shifts neighbours', async () => {
      // Arrange: section A has rows [10, 11, 12] at positions 0..2.
      const ctx = makeContext()
      const { aKey } = seedThreeRowsInA(ctx)
      RowService.mockReturnValue({
        move: vi.fn().mockResolvedValue({ data: { id: 12, order: '1.5' } }),
      })

      // Act: drag row 12 (position 2) to *before* row 11 (position 1).
      await ctx.dispatch('moveRow', {
        table: { id: 99 },
        rowId: 12,
        beforeRowId: 11,
      })

      // Assert: bucket order is now [10, 12, 11]; rowIndex is in sync.
      const bucket = ctx.state.sectionRows.get(aKey)
      expect(bucket.get(0).id).toBe(10)
      expect(bucket.get(1).id).toBe(12)
      expect(bucket.get(2).id).toBe(11)
      expect(ctx.state.rowIndex.get(12)).toEqual({ sectionKey: aKey, position: 1 })
      expect(ctx.state.rowIndex.get(11)).toEqual({ sectionKey: aKey, position: 2 })
    })

    test('beforeRowId=null moves the row to the end of the section', async () => {
      const ctx = makeContext()
      const { aKey } = seedThreeRowsInA(ctx)
      RowService.mockReturnValue({
        move: vi.fn().mockResolvedValue({ data: { id: 10, order: '3.5' } }),
      })

      // Act: drag row 10 (currently first) to the end.
      await ctx.dispatch('moveRow', {
        table: { id: 99 },
        rowId: 10,
        beforeRowId: null,
      })

      const bucket = ctx.state.sectionRows.get(aKey)
      expect(bucket.get(0).id).toBe(11)
      expect(bucket.get(1).id).toBe(12)
      expect(bucket.get(2).id).toBe(10)
    })

    test('dropping a row right before itself is a no-op', async () => {
      const ctx = makeContext()
      const { aKey } = seedThreeRowsInA(ctx)
      const move = vi.fn().mockResolvedValue({ data: {} })
      RowService.mockReturnValue({ move })

      await ctx.dispatch('moveRow', {
        table: { id: 99 },
        rowId: 11,
        beforeRowId: 11,
      })

      expect(move).not.toHaveBeenCalled()
      expect(ctx.state.sectionRows.get(aKey).get(1).id).toBe(11)
    })

    test('cross-section drop is rejected (only same-section reorder supported)', async () => {
      // Arrange: row 1 in section A, row 99 in section B.
      const ctx = makeContext()
      const { aKey, bKey } = seedSingleLevel(ctx.commit)
      ctx.commit('MERGE_SECTION_ROWS', {
        sectionKey: bKey,
        startPosition: 0,
        rows: [{ id: 99, field_1: 'B' }],
      })
      const move = vi.fn()
      RowService.mockReturnValue({ move })

      // Act: try to move row 1 (in A) before row 99 (in B).
      await ctx.dispatch('moveRow', {
        table: { id: 99 },
        rowId: 1,
        beforeRowId: 99,
      })

      // Assert: nothing happened. The cross-section path is
      // `moveRowToSection`, not `moveRow`.
      expect(move).not.toHaveBeenCalled()
      expect(ctx.state.sectionRows.get(aKey).get(0).id).toBe(1)
      expect(ctx.state.sectionRows.get(bKey).get(0).id).toBe(99)
    })

    test('BE failure rolls back the optimistic move', async () => {
      const ctx = makeContext()
      const { aKey } = seedThreeRowsInA(ctx)
      RowService.mockReturnValue({
        move: vi.fn().mockRejectedValue(new Error('BE down')),
      })

      await expect(
        ctx.dispatch('moveRow', {
          table: { id: 99 },
          rowId: 10,
          beforeRowId: null,
        })
      ).rejects.toThrow('BE down')

      const bucket = ctx.state.sectionRows.get(aKey)
      expect(bucket.get(0).id).toBe(10)
      expect(bucket.get(1).id).toBe(11)
      expect(bucket.get(2).id).toBe(12)
    })
  })

  // ─── Drag-reorder across sections (group-by change) ─────────────
  //
  // `moveRowToSection` is what fires when the user drops a row in a
  // different section's pixel range. It just patches the row's
  // group-by field values; the regular updateRowValue/optimisticEdit
  // pipeline does the structural move.
  describe('moveRowToSection', () => {
    test('sends a single batchUpdate patching the group-by field to the target value', async () => {
      // Arrange: row 1 in section A; section B exists in the tree but
      // has nothing loaded yet (the common case when the user drops
      // into an off-screen section).
      const ctx = makeContext()
      const { fields, aKey } = seedSingleLevel(ctx.commit)
      const batchUpdate = vi.fn().mockResolvedValue({
        data: { items: [{ id: 1, field_1: 'B' }] },
      })
      RowService.mockReturnValue({ batchUpdate })

      // Act: drop row 1 (section A) into section B's pixel range.
      await ctx.dispatch('moveRowToSection', {
        table: { id: 99 },
        view: { id: 7 },
        fields,
        row: ctx.state.sectionRows.get(aKey).get(0),
        targetPath: { field_1: 'B' },
      })

      // Assert: one batch PATCH carrying the new group-by value.
      // The optimistic+commit pipeline removes the row from A's
      // bucket; B's bucket is repopulated by the next refetch, since
      // we don't have enough loaded rows there to confidently pick
      // an insertion position locally.
      expect(batchUpdate).toHaveBeenCalledTimes(1)
      expect(batchUpdate.mock.calls[0][1]).toEqual([{ id: 1, field_1: 'B' }])
      expect(ctx.state.sectionRows.get(aKey)?.size ?? 0).toBe(0)
    })

    test('skips when the target path values already match the row', async () => {
      const ctx = makeContext()
      const { fields, aKey } = seedSingleLevel(ctx.commit)
      const batchUpdate = vi.fn()
      RowService.mockReturnValue({ batchUpdate })

      await ctx.dispatch('moveRowToSection', {
        table: { id: 99 },
        view: { id: 7 },
        fields,
        row: ctx.state.sectionRows.get(aKey).get(0),
        targetPath: { field_1: 'A' },
      })

      expect(batchUpdate).not.toHaveBeenCalled()
    })
  })

  // ─── Multi-cell paste: one batch call for the whole rectangle ───
  //
  // Verifies that `pasteRectangleScoped` (component-level) → the
  // store action sends ONE batch PATCH for every selected cell, not
  // one PATCH per row.
  describe('batchUpdateRowValues', () => {
    test('combines per-row patches into a single batchUpdate request', async () => {
      // Arrange: two rows in section A.
      const ctx = makeContext()
      const fields = [textField(1), textField(2)]
      const { aKey } = seedSingleLevel(ctx.commit, {
        nodes: [{ path: { field_1: 'A' }, depth: 0, rowCount: 2 }],
        seedRow: false,
      })
      ctx.commit('MERGE_SECTION_ROWS', {
        sectionKey: aKey,
        startPosition: 0,
        rows: [
          { id: 10, field_1: 'A', field_2: 'old10' },
          { id: 11, field_1: 'A', field_2: 'old11' },
        ],
      })
      const batchUpdate = vi.fn().mockResolvedValue({
        data: {
          items: [
            { id: 10, field_1: 'A', field_2: 'new10' },
            { id: 11, field_1: 'A', field_2: 'new11' },
          ],
        },
      })
      RowService.mockReturnValue({ batchUpdate })

      // Act: paste two cell-updates, one per row.
      const f2 = textField(2)
      await ctx.dispatch('batchUpdateRowValues', {
        table: { id: 99 },
        view: { id: 7 },
        fields,
        updates: [
          {
            row: ctx.state.sectionRows.get(aKey).get(0),
            fieldValuePairs: [
              { field: f2, value: 'new10', oldValue: 'old10' },
            ],
          },
          {
            row: ctx.state.sectionRows.get(aKey).get(1),
            fieldValuePairs: [
              { field: f2, value: 'new11', oldValue: 'old11' },
            ],
          },
        ],
      })

      // Assert: exactly one request to the BE, carrying both rows.
      expect(batchUpdate).toHaveBeenCalledTimes(1)
      expect(batchUpdate.mock.calls[0][1]).toEqual([
        { id: 10, field_2: 'new10' },
        { id: 11, field_2: 'new11' },
      ])
      // Both rows now reflect the BE response.
      expect(ctx.state.sectionRows.get(aKey).get(0).field_2).toBe('new10')
      expect(ctx.state.sectionRows.get(aKey).get(1).field_2).toBe('new11')
    })

    test('BE failure rolls back every optimistic edit', async () => {
      const ctx = makeContext()
      const fields = [textField(1), textField(2)]
      const { aKey } = seedSingleLevel(ctx.commit, {
        nodes: [{ path: { field_1: 'A' }, depth: 0, rowCount: 1 }],
        seedRow: false,
      })
      ctx.commit('MERGE_SECTION_ROWS', {
        sectionKey: aKey,
        startPosition: 0,
        rows: [{ id: 10, field_1: 'A', field_2: 'old' }],
      })
      RowService.mockReturnValue({
        batchUpdate: vi.fn().mockRejectedValue(new Error('BE down')),
      })

      await expect(
        ctx.dispatch('batchUpdateRowValues', {
          table: { id: 99 },
          view: { id: 7 },
          fields,
          updates: [
            {
              row: ctx.state.sectionRows.get(aKey).get(0),
              fieldValuePairs: [
                { field: textField(2), value: 'new', oldValue: 'old' },
              ],
            },
          ],
        })
      ).rejects.toThrow('BE down')

      expect(ctx.state.sectionRows.get(aKey).get(0).field_2).toBe('old')
      expect(ctx.state.pendingMutations.has(10)).toBe(false)
    })
  })

  // ─── Realtime: row.order change → in-memory re-sort, no refetch ─
  //
  // When the BE emits `rows_updated` after a move (manual reorder or
  // undo), we should reposition the row inside its bucket using the
  // payload — NOT by clearing + refetching the section.
  describe('handleRealtimeRowUpdated — order change', () => {
    const seedContiguousBucket = (ctx) => {
      const { fields, aKey } = seedSingleLevel(ctx.commit, {
        nodes: [{ path: { field_1: 'A' }, depth: 0, rowCount: 3 }],
        seedRow: false,
      })
      ctx.commit('MERGE_SECTION_ROWS', {
        sectionKey: aKey,
        startPosition: 0,
        rows: [
          { id: 10, field_1: 'A', order: '1.0' },
          { id: 11, field_1: 'A', order: '2.0' },
          { id: 12, field_1: 'A', order: '3.0' },
        ],
      })
      return { fields, aKey }
    }

    test('contiguous bucket re-sorts in place — no fetchSectionRows dispatch', async () => {
      const ctx = makeContext()
      const { aKey } = seedContiguousBucket(ctx)

      // Act: row 12 moves to first by gaining a smaller order value.
      await ctx.dispatch('handleRealtimeRowUpdated', {
        row: { id: 12, field_1: 'A', order: '0.5' },
        fields: [textField(1)],
      })

      // Assert: new order is [12, 10, 11], no refetch dispatched.
      const bucket = ctx.state.sectionRows.get(aKey)
      expect(bucket.get(0).id).toBe(12)
      expect(bucket.get(1).id).toBe(10)
      expect(bucket.get(2).id).toBe(11)
      const fetched = ctx.dispatched.find((d) => d.name === 'ensureRowsForViewport')
      expect(fetched).toBeUndefined()
    })

    test('non-contiguous bucket clears tracking and refetches', async () => {
      // A bucket with positions {0, 5} (a gap) can't be safely
      // re-sorted in place — collapsing the gap would corrupt
      // BE-truthful indices. Fall back to refetch.
      const ctx = makeContext()
      const { fields, aKey } = seedSingleLevel(ctx.commit, {
        nodes: [{ path: { field_1: 'A' }, depth: 0, rowCount: 10 }],
        seedRow: false,
      })
      ctx.commit('MERGE_SECTION_ROWS', {
        sectionKey: aKey,
        startPosition: 0,
        rows: [{ id: 10, field_1: 'A', order: '1.0' }],
      })
      ctx.commit('MERGE_SECTION_ROWS', {
        sectionKey: aKey,
        startPosition: 5,
        rows: [{ id: 15, field_1: 'A', order: '6.0' }],
      })

      await ctx.dispatch('handleRealtimeRowUpdated', {
        row: { id: 15, field_1: 'A', order: '0.5' },
        fields,
      })

      const fetched = ctx.dispatched.find((d) => d.name === 'ensureRowsForViewport')
      expect(fetched).toBeDefined()
    })

    test('order unchanged → no resort, no refetch', async () => {
      const ctx = makeContext()
      seedContiguousBucket(ctx)

      await ctx.dispatch('handleRealtimeRowUpdated', {
        row: { id: 11, field_1: 'A', order: '2.0', extra: 'new-field-value' },
        fields: [textField(1)],
      })

      expect(
        ctx.dispatched.find((d) => d.name === 'ensureRowsForViewport')
      ).toBeUndefined()
    })
  })

  // ─── Search: highlight-only vs hide-mode ────────────────────────
  //
  // The grouped store mirrors the flat store's activeSearchTerm and
  // hideRowsNotMatchingSearch. Hide-mode propagates the search to BE
  // fetches; highlight-only doesn't — it just sets the local flags.
  describe('setActiveSearch', () => {
    test('highlight-only mode does not refetch', async () => {
      const ctx = makeContext()
      seedSingleLevel(ctx.commit)

      await ctx.dispatch('setActiveSearch', {
        activeSearchTerm: 'foo',
        hideRowsNotMatchingSearch: false,
      })

      expect(ctx.state.activeSearchTerm).toBe('foo')
      expect(ctx.state.hideRowsNotMatchingSearch).toBe(false)
      expect(ctx.dispatched.find((d) => d.name === 'fetchTree')).toBeUndefined()
    })

    test('entering hide-mode with a search refetches tree + viewport', async () => {
      const ctx = makeContext()
      seedSingleLevel(ctx.commit)
      ctx.stubAction('fetchTree', async () => {})
      ctx.stubAction('ensureRowsForViewport', async () => {})

      await ctx.dispatch('setActiveSearch', {
        activeSearchTerm: 'foo',
        hideRowsNotMatchingSearch: true,
      })

      const names = ctx.dispatched.map((d) => d.name)
      expect(names).toContain('fetchTree')
      expect(names).toContain('ensureRowsForViewport')
    })

    test('clearing the search while in hide-mode triggers a refetch', async () => {
      const ctx = makeContext()
      seedSingleLevel(ctx.commit)
      ctx.state.activeSearchTerm = 'foo'
      ctx.state.hideRowsNotMatchingSearch = true
      ctx.stubAction('fetchTree', async () => {})
      ctx.stubAction('ensureRowsForViewport', async () => {})

      await ctx.dispatch('setActiveSearch', {
        activeSearchTerm: '',
        hideRowsNotMatchingSearch: true,
      })

      expect(ctx.dispatched.map((d) => d.name)).toContain('fetchTree')
    })

    test('toggling highlight ↔ highlight (no hide) does not refetch', async () => {
      const ctx = makeContext()
      seedSingleLevel(ctx.commit)
      ctx.state.activeSearchTerm = 'foo'

      await ctx.dispatch('setActiveSearch', {
        activeSearchTerm: 'bar',
        hideRowsNotMatchingSearch: false,
      })

      expect(ctx.dispatched.find((d) => d.name === 'fetchTree')).toBeUndefined()
    })
  })

  // ─── Collapse all / expand all ──────────────────────────────────
  describe('setCollapsedAll', () => {
    test('collapsed=true switches into collapse-mode and clears exceptions', async () => {
      const ctx = makeContext()
      seedSingleLevel(ctx.commit)
      ctx.commit('TOGGLE_COLLAPSE', { field_1: 'A' })
      ctx.stubAction('fetchTree', async () => {})
      ctx.stubAction('ensureRowsForViewport', async () => {})

      await ctx.dispatch('setCollapsedAll', { collapsed: true })

      expect(ctx.state.collapse.mode).toBe('collapse')
      expect(ctx.state.collapse.paths).toEqual([])
    })

    test('collapsed=false switches into expand-mode and clears exceptions', async () => {
      const ctx = makeContext()
      seedSingleLevel(ctx.commit)
      ctx.state.collapse.mode = 'collapse'
      ctx.state.collapse.paths = [{ field_1: 'A' }]
      ctx.stubAction('fetchTree', async () => {})
      ctx.stubAction('ensureRowsForViewport', async () => {})

      await ctx.dispatch('setCollapsedAll', { collapsed: false })

      expect(ctx.state.collapse.mode).toBe('expand')
      expect(ctx.state.collapse.paths).toEqual([])
    })
  })

  // ─── Row height: layout + cell pixel size ───────────────────────
  describe('row height', () => {
    test('SET_ROW_HEIGHT updates state; ignores non-positive values', () => {
      const ctx = makeContext()
      expect(ctx.state.rowHeight).toBe(33)
      ctx.commit('SET_ROW_HEIGHT', 55)
      expect(ctx.state.rowHeight).toBe(55)
      ctx.commit('SET_ROW_HEIGHT', 0)
      expect(ctx.state.rowHeight).toBe(55)
      ctx.commit('SET_ROW_HEIGHT', -1)
      expect(ctx.state.rowHeight).toBe(55)
    })

    test('layout getter emits row sections sized by state.rowHeight', () => {
      const ctx = makeContext()
      seedSingleLevel(ctx.commit, {
        nodes: [{ path: { field_1: 'A' }, depth: 0, rowCount: 2 }],
      })
      ctx.commit('SET_ROW_HEIGHT', 99)

      const layout = gridGroupedModule.getters.layout(ctx.state)
      const section = layout.items.find((it) => it.type === 'rowSection')

      expect(section.height).toBe(99 * 2)
    })
  })
})
