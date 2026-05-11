import _ from 'lodash'
import gridStore from '@baserow/modules/database/store/view/grid'
import { populateField } from '@baserow/modules/database/store/field'
import { TestApp } from '@baserow/test/helpers/testApp'

const buildTree = () => ({
  nodes: [
    { path: { field_1: 'A' }, depth: 0, count: 3 },
    { path: { field_1: 'B' }, depth: 0, count: 2 },
  ],
  truncated: false,
  total_nodes: 2,
})

const mockRegistry = {
  get() {
    return {
      isEqual: (field, a, b) => JSON.stringify(a) === JSON.stringify(b),
      getRowValueFromGroupValue: (field, value) => value,
      getGroupValueFromRowValue: (field, value) => value,
    }
  },
}

describe('grid store group tree', () => {
  let testApp = null
  let store = null

  beforeEach(() => {
    testApp = new TestApp()
    store = testApp.createStore({
      modules: {
        grid: gridStore,
        // ``syncGroupTreeForRowMove`` ultimately dispatches
        // ``fetchByScrollTop``, which reads the current view via
        // ``rootGetters['view/get']``. A minimal in-memory stand-in keeps
        // those calls inert while still letting the action complete.
        view: {
          namespaced: true,
          state: () => ({ items: {} }),
          getters: {
            get:
              (state) =>
              (id) =>
                state.items[id],
          },
          mutations: {
            SET_VIEW(state, view) {
              state.items = { ...state.items, [view.id]: view }
            },
          },
        },
        page: {
          namespaced: true,
          modules: {
            view: {
              namespaced: true,
              modules: {
                public: {
                  namespaced: true,
                  state: () => ({}),
                  getters: {
                    getIsPublic: () => false,
                    getAuthToken: () => null,
                  },
                },
              },
            },
          },
        },
      },
    })
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  test('initial groupTrees state is empty object', () => {
    expect(store.state.grid.groupTrees).toEqual({})
  })

  test('SET_GROUP_TREE stores nodes and accepts truncated payload', () => {
    store.commit('grid/SET_GROUP_TREE', {
      viewId: 42,
      tree: buildTree(),
    })

    expect(store.getters['grid/getGroupTreeForView'](42)).toEqual({
      nodes: buildTree().nodes,
      truncated: false,
      totalNodes: 2,
      // The empty key represents the depth-0 outline.
      loadedSubtrees: { '': true },
      loadingSubtrees: {},
      fullyLoaded: false,
    })
  })

  test('SET_GROUP_TREE preserves the truncated flag from the backend', () => {
    store.commit('grid/SET_GROUP_TREE', {
      viewId: 42,
      tree: { nodes: [], truncated: true, total_nodes: 999999 },
    })

    expect(store.getters['grid/getGroupTreeForView'](42)).toEqual({
      nodes: [],
      truncated: true,
      totalNodes: 999999,
      loadedSubtrees: { '': true },
      loadingSubtrees: {},
      fullyLoaded: false,
    })
  })

  test('CLEAR_GROUP_TREE drops the tree for a view', () => {
    store.commit('grid/SET_GROUP_TREE', { viewId: 42, tree: buildTree() })
    store.commit('grid/CLEAR_GROUP_TREE', { viewId: 42 })
    expect(store.getters['grid/getGroupTreeForView'](42)).toBeNull()
  })

  test('getGroupTreeForView returns null for an unknown view', () => {
    expect(store.getters['grid/getGroupTreeForView'](999)).toBeNull()
  })

  test('UPDATE_GROUP_BY_METADATA_COUNT increments the matching tree node', () => {
    store.commit('grid/SET_LAST_GRID_ID', 42)
    store.commit('grid/SET_ACTIVE_GROUP_BYS', [
      { field: 1, order: 'ASC', type: 'default' },
    ])
    store.commit('grid/SET_GROUP_TREE', { viewId: 42, tree: buildTree() })

    store.commit('grid/UPDATE_GROUP_BY_METADATA_COUNT', {
      fields: [{ id: 1, type: 'text' }],
      registry: mockRegistry,
      row: { field_1: 'A' },
      increase: true,
      decrease: false,
    })

    const tree = store.getters['grid/getGroupTreeForView'](42)
    expect(tree.nodes.find((n) => n.path.field_1 === 'A').count).toBe(4)
    expect(tree.nodes.find((n) => n.path.field_1 === 'B').count).toBe(2)
  })

  test('UPDATE_GROUP_BY_METADATA_COUNT decrements but never below zero', () => {
    store.commit('grid/SET_LAST_GRID_ID', 42)
    store.commit('grid/SET_ACTIVE_GROUP_BYS', [
      { field: 1, order: 'ASC', type: 'default' },
    ])
    store.commit('grid/SET_GROUP_TREE', {
      viewId: 42,
      tree: {
        nodes: [{ path: { field_1: 'A' }, depth: 0, count: 0 }],
        truncated: false,
        total_nodes: 1,
      },
    })

    store.commit('grid/UPDATE_GROUP_BY_METADATA_COUNT', {
      fields: [{ id: 1, type: 'text' }],
      registry: mockRegistry,
      row: { field_1: 'A' },
      increase: false,
      decrease: true,
    })

    const tree = store.getters['grid/getGroupTreeForView'](42)
    expect(tree.nodes[0].count).toBe(0)
  })

  test('UPDATE_GROUP_BY_METADATA_COUNT touches every depth whose prefix matches', () => {
    store.commit('grid/SET_LAST_GRID_ID', 42)
    store.commit('grid/SET_ACTIVE_GROUP_BYS', [
      { field: 1, order: 'ASC', type: 'default' },
      { field: 2, order: 'ASC', type: 'default' },
    ])
    store.commit('grid/SET_GROUP_TREE', {
      viewId: 42,
      tree: {
        nodes: [
          { path: { field_1: 'A' }, depth: 0, count: 5 },
          { path: { field_1: 'A', field_2: 'X' }, depth: 1, count: 3 },
          { path: { field_1: 'A', field_2: 'Y' }, depth: 1, count: 2 },
          { path: { field_1: 'B' }, depth: 0, count: 4 },
        ],
        truncated: false,
        total_nodes: 4,
      },
    })

    store.commit('grid/UPDATE_GROUP_BY_METADATA_COUNT', {
      fields: [
        { id: 1, type: 'text' },
        { id: 2, type: 'text' },
      ],
      registry: mockRegistry,
      row: { field_1: 'A', field_2: 'X' },
      increase: true,
      decrease: false,
    })

    const tree = store.getters['grid/getGroupTreeForView'](42)
    const counts = Object.fromEntries(
      tree.nodes.map((n) => [
        `${n.path.field_1}|${n.path.field_2 ?? ''}`,
        n.count,
      ])
    )
    expect(counts['A|']).toBe(6)
    expect(counts['A|X']).toBe(4)
    expect(counts['A|Y']).toBe(2)
    expect(counts['B|']).toBe(4)
  })

  test('UPDATE_GROUP_BY_METADATA_COUNT is a no-op when no tree exists', () => {
    store.commit('grid/SET_LAST_GRID_ID', 42)
    store.commit('grid/SET_ACTIVE_GROUP_BYS', [
      { field: 1, order: 'ASC', type: 'default' },
    ])

    expect(() =>
      store.commit('grid/UPDATE_GROUP_BY_METADATA_COUNT', {
        fields: [{ id: 1, type: 'text' }],
        registry: mockRegistry,
        row: { field_1: 'A' },
        increase: true,
        decrease: false,
      })
    ).not.toThrow()
    expect(store.getters['grid/getGroupTreeForView'](42)).toBeNull()
  })

  describe('collapse state is not persisted in v1', () => {
    const STORAGE_KEY = 'baserow.gridView.collapsedGroups.42'

    beforeEach(() => {
      window.localStorage.clear()
    })

    test('toggleGroupCollapsed does not write to localStorage', async () => {
      await store.dispatch('grid/toggleGroupCollapsed', {
        viewId: 42,
        groupValues: { field_1: 'A' },
      })
      expect(window.localStorage.getItem(STORAGE_KEY)).toBeNull()
    })

    test('expandAllGroups clears any leftover storage entry', async () => {
      window.localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({ groups: [{ field_1: 'A' }], mode: 'expand' })
      )
      await store.dispatch('grid/expandAllGroups', { viewId: 42 })
      expect(window.localStorage.getItem(STORAGE_KEY)).toBeNull()
    })

    test('collapseAllGroups also clears leftover storage', async () => {
      window.localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({ groups: [{ field_1: 'A' }], mode: 'expand' })
      )
      await store.dispatch('grid/collapseAllGroups', { viewId: 42 })
      expect(window.localStorage.getItem(STORAGE_KEY)).toBeNull()
    })
  })

  describe('lazy tree subtree mutations', () => {
    test('SET_GROUP_TREE_SUBTREE_LOADING marks an in-flight path', () => {
      store.commit('grid/SET_GROUP_TREE', { viewId: 42, tree: buildTree() })
      store.commit('grid/SET_GROUP_TREE_SUBTREE_LOADING', {
        viewId: 42,
        pathKey: '"A"',
        loading: true,
      })
      const tree = store.getters['grid/getGroupTreeForView'](42)
      expect(tree.loadingSubtrees).toEqual({ '"A"': true })
    })

    test('SET_GROUP_TREE_SUBTREE_LOADING with loading=false clears the flag', () => {
      store.commit('grid/SET_GROUP_TREE', { viewId: 42, tree: buildTree() })
      store.commit('grid/SET_GROUP_TREE_SUBTREE_LOADING', {
        viewId: 42,
        pathKey: '"A"',
        loading: true,
      })
      store.commit('grid/SET_GROUP_TREE_SUBTREE_LOADING', {
        viewId: 42,
        pathKey: '"A"',
        loading: false,
      })
      const tree = store.getters['grid/getGroupTreeForView'](42)
      expect(tree.loadingSubtrees).toEqual({})
    })

    test('MERGE_GROUP_TREE_SUBTREE inserts descendants after the parent and marks loaded', () => {
      store.commit('grid/SET_GROUP_TREE', {
        viewId: 42,
        tree: {
          nodes: [
            {
              path: { field_1: 'A' },
              depth: 0,
              row_count: 3,
              children_count: 2,
            },
            {
              path: { field_1: 'B' },
              depth: 0,
              row_count: 1,
              children_count: 1,
            },
          ],
          truncated: false,
          total_nodes: 2,
        },
      })

      store.commit('grid/MERGE_GROUP_TREE_SUBTREE', {
        viewId: 42,
        parentPathKey: '"A"',
        parentPath: { field_1: 'A' },
        tree: {
          nodes: [
            { path: { field_1: 'A', field_2: 'X' }, depth: 1, row_count: 2 },
            { path: { field_1: 'A', field_2: 'Y' }, depth: 1, row_count: 1 },
          ],
          truncated: false,
          total_nodes: 2,
        },
      })

      const tree = store.getters['grid/getGroupTreeForView'](42)
      expect(tree.nodes.map((n) => n.path)).toEqual([
        { field_1: 'A' },
        { field_1: 'A', field_2: 'X' },
        { field_1: 'A', field_2: 'Y' },
        { field_1: 'B' },
      ])
      expect(tree.loadedSubtrees['"A"']).toBe(true)
    })

    test('MERGE_GROUP_TREE_SUBTREE drops echoed parent from the response', () => {
      store.commit('grid/SET_GROUP_TREE', {
        viewId: 42,
        tree: {
          nodes: [
            {
              path: { field_1: 'A' },
              depth: 0,
              row_count: 1,
              children_count: 1,
            },
          ],
          truncated: false,
          total_nodes: 1,
        },
      })

      store.commit('grid/MERGE_GROUP_TREE_SUBTREE', {
        viewId: 42,
        parentPathKey: '"A"',
        parentPath: { field_1: 'A' },
        tree: {
          nodes: [
            {
              path: { field_1: 'A' },
              depth: 0,
              row_count: 1,
              children_count: 1,
            },
            { path: { field_1: 'A', field_2: 'X' }, depth: 1, row_count: 1 },
          ],
          truncated: false,
          total_nodes: 2,
        },
      })

      const tree = store.getters['grid/getGroupTreeForView'](42)
      // Parent ('A') appears exactly once.
      expect(
        tree.nodes.filter((n) => n.depth === 0 && n.path.field_1 === 'A')
      ).toHaveLength(1)
      // The descendant landed.
      expect(tree.nodes.find((n) => n.path.field_2 === 'X')).toBeTruthy()
    })
  })

  // Realtime row mutations (created / updated / deleted) must keep the buffer
  // aligned with the heightIndex so a row is never visually parked inside the
  // wrong group while the BE catches up. The expanded group's pixel range
  // would otherwise render whatever rows happen to sit at those buffer
  // indices, so we must drop / not-insert rows that don't belong there.
  describe('realtime row mutations never end up in the wrong group', () => {
    const VIEW_ID = 42
    const VIEW = {
      id: VIEW_ID,
      filters_disabled: true,
      filter_type: 'AND',
      filters: [],
      sortings: [],
      group_bys: [{ field: 1, order: 'ASC', type: 'default' }],
      ownership_type: 'collaborative',
    }
    const buildFields = () =>
      [
        { id: 1, name: 'Cat', type: 'text', primary: false },
        { id: 99, name: 'Title', type: 'text', primary: true },
      ].map((f) => populateField(f, testApp.$registry))
    let FIELDS

    const setup = ({
      treeNodes,
      bufferRows,
      bufferStartIndex = 0,
      collapsedGroups = [],
    }) => {
      // ``syncGroupTreeForRowMove`` dispatches ``fetchByScrollTop`` which
      // hits the real ``GridService.fetchRows`` HTTP endpoint. The mock
      // adapter is configured with ``onNoMatch: 'throwException'`` so any
      // unmocked URL would throw — return a benign empty page instead.
      testApp.mock.onAny().reply(200, {
        count: 0,
        results: [],
        group_by_metadata: {},
      })
      FIELDS = buildFields()
      store.commit('view/SET_VIEW', VIEW)
      store.commit('grid/SET_LAST_GRID_ID', VIEW_ID)
      store.commit('grid/SET_ACTIVE_GROUP_BYS', [
        { field: 1, order: 'ASC', type: 'default' },
      ])
      store.commit('grid/SET_GROUP_TREE', {
        viewId: VIEW_ID,
        tree: {
          nodes: treeNodes,
          truncated: false,
          total_nodes: treeNodes.length,
        },
      })
      // Mark every collapsed path so the heightIndex would render the group
      // as a header only — the equivalent of the user clicking "collapse" on
      // it before the realtime event fires.
      for (const path of collapsedGroups) {
        store.commit('grid/TOGGLE_GROUP_COLLAPSED', {
          viewId: VIEW_ID,
          groupValues: path,
        })
      }
      store.state.grid.bufferStartIndex = bufferStartIndex
      store.state.grid.bufferLimit = bufferRows.length
      store.state.grid.rows = bufferRows
      store.state.grid.count = treeNodes.reduce(
        (acc, n) => acc + (n.row_count ?? 0),
        0
      )
    }

    const makeRow = (id, order, fieldValues = {}) => ({
      id,
      order: String(id) + '.0',
      _: {
        matchFilters: true,
        matchSortings: true,
        matchSearch: true,
        fieldSearchMatches: [],
        loading: false,
        fetching: false,
        fullyLoaded: true,
        selected: false,
        selectedFieldId: -1,
        selectedBy: [],
        metadata: {},
        persistentId: 'p-' + id,
      },
      ...fieldValues,
    })

    test(
      'updatedExistingRow updates the row in place + sorts it into the new ' +
        'group when its group-by value moves to a different group',
      async () => {
        setup({
          treeNodes: [
            { path: { field_1: 'A' }, depth: 0, row_count: 3 },
            { path: { field_1: 'B' }, depth: 0, row_count: 2 },
          ],
          bufferRows: [
            makeRow(1, 1, { field_1: 'A', field_99: 'a1' }),
            makeRow(2, 2, { field_1: 'A', field_99: 'a2' }),
            makeRow(3, 3, { field_1: 'A', field_99: 'a3' }),
          ],
          collapsedGroups: [{ field_1: 'B' }],
        })

        await store.dispatch('grid/updatedExistingRow', {
          view: VIEW,
          fields: FIELDS,
          row: { id: 2, order: '2.0', field_1: 'A', field_99: 'a2' },
          values: { id: 2, order: '2.0', field_1: 'B', field_99: 'a2' },
        })

        const moved = store.state.grid.rows.find((r) => r.id === 2)
        expect(moved).toBeDefined()
        expect(moved.field_1).toBe('B')
        const tree = store.getters['grid/getGroupTreeForView'](VIEW_ID)
        expect(
          tree.nodes.find((n) => n.path.field_1 === 'A').row_count
        ).toBe(2)
        expect(
          tree.nodes.find((n) => n.path.field_1 === 'B').row_count
        ).toBe(3)
      }
    )

    test(
      'createdNewRow for a collapsed group bumps the tree count without ' +
        'inserting the row into the expanded group´s pixel range',
      async () => {
        setup({
          treeNodes: [
            { path: { field_1: 'A' }, depth: 0, row_count: 3 },
            { path: { field_1: 'B' }, depth: 0, row_count: 2 },
          ],
          bufferRows: [
            makeRow(1, 1, { field_1: 'A', field_99: 'a1' }),
            makeRow(2, 2, { field_1: 'A', field_99: 'a2' }),
            makeRow(3, 3, { field_1: 'A', field_99: 'a3' }),
          ],
          collapsedGroups: [{ field_1: 'B' }],
        })

        await store.dispatch('grid/createdNewRow', {
          view: VIEW,
          fields: FIELDS,
          values: { id: 99, order: '99.0', field_1: 'B', field_99: 'b3' },
        })

        // Collapsed group's count must reflect the new row.
        const tree = store.getters['grid/getGroupTreeForView'](VIEW_ID)
        expect(
          tree.nodes.find((n) => n.path.field_1 === 'B').row_count
        ).toBe(3)
        expect(
          tree.nodes.find((n) => n.path.field_1 === 'A').row_count
        ).toBe(3)
        // The new B-row must NOT be in the buffer — a buffer slot at the
        // sorted position would land in A's pixel range and render the row
        // visually inside A.
        expect(store.state.grid.rows.find((r) => r.id === 99)).toBeUndefined()
        expect(store.state.grid.rows.map((r) => r.id)).toEqual([1, 2, 3])
      }
    )

    test(
      'createdNewRow whose ancestor group is collapsed (deeper level) is ' +
        'kept out of the buffer',
      async () => {
        // Two-level grouping (Cat / Sub). Cat=A is expanded, but Cat=B is
        // collapsed. A new row in Cat=B,Sub=X should not enter the buffer.
        const VIEW_2D = {
          ...VIEW,
          group_bys: [
            { field: 1, order: 'ASC', type: 'default' },
            { field: 99, order: 'ASC', type: 'default' },
          ],
        }
        store.commit('view/SET_VIEW', VIEW_2D)
        store.commit('grid/SET_LAST_GRID_ID', VIEW_ID)
        store.commit('grid/SET_ACTIVE_GROUP_BYS', [
          { field: 1, order: 'ASC', type: 'default' },
          { field: 99, order: 'ASC', type: 'default' },
        ])
        store.commit('grid/SET_GROUP_TREE', {
          viewId: VIEW_ID,
          tree: {
            nodes: [
              { path: { field_1: 'A' }, depth: 0, row_count: 2 },
              { path: { field_1: 'A', field_99: 'X' }, depth: 1, row_count: 2 },
              { path: { field_1: 'B' }, depth: 0, row_count: 1 },
              { path: { field_1: 'B', field_99: 'X' }, depth: 1, row_count: 1 },
            ],
            truncated: false,
            total_nodes: 4,
          },
        })
        // Collapse Cat=B; Cat=A stays expanded.
        store.commit('grid/TOGGLE_GROUP_COLLAPSED', {
          viewId: VIEW_ID,
          groupValues: { field_1: 'B' },
        })
        FIELDS = buildFields()
        store.state.grid.bufferStartIndex = 0
        store.state.grid.bufferLimit = 2
        store.state.grid.rows = [
          makeRow(1, 1, { field_1: 'A', field_99: 'X' }),
          makeRow(2, 2, { field_1: 'A', field_99: 'X' }),
        ]
        store.state.grid.count = 3
        testApp.mock.onAny().reply(200, {
          count: 0,
          results: [],
          group_by_metadata: {},
        })

        await store.dispatch('grid/createdNewRow', {
          view: VIEW_2D,
          fields: FIELDS,
          values: { id: 77, order: '77.0', field_1: 'B', field_99: 'X' },
        })

        // Even though the leaf path (B,X) isn't itself in the collapsed
        // list, its ancestor (Cat=B) is collapsed — so the row must stay
        // out of the buffer.
        expect(store.state.grid.rows.find((r) => r.id === 77)).toBeUndefined()
        expect(store.state.grid.rows.map((r) => r.id)).toEqual([1, 2])
      }
    )

    test(
      'updatedExistingRow that creates a brand-new group inserts the new ' +
        'tree node (collapsed) and prunes the now-empty old group',
      async () => {
        // Single group-by on a boolean-style field. The tree starts with
        // only one group (false, 1 row). When the user flips the row's
        // value to true, the new "true" group did not exist yet — the FE
        // must add it locally as a collapsed node with row_count=1. The
        // old "false" group, now empty, must disappear from the tree.
        setup({
          treeNodes: [
            { path: { field_1: 'false' }, depth: 0, row_count: 1 },
          ],
          bufferRows: [
            makeRow(1, 1, { field_1: 'false', field_99: 'one' }),
          ],
        })

        await store.dispatch('grid/updatedExistingRow', {
          view: VIEW,
          fields: FIELDS,
          row: { id: 1, order: '1.0', field_1: 'false', field_99: 'one' },
          values: { id: 1, order: '1.0', field_1: 'true', field_99: 'one' },
        })

        const tree = store.getters['grid/getGroupTreeForView'](VIEW_ID)
        // The old group is now empty and must be pruned — leaving an
        // empty banner behind would clutter the grid with a dead group.
        expect(
          tree.nodes.find((n) => n.path.field_1 === 'false')
        ).toBeUndefined()
        // The new group exists locally with the moved row's count.
        const trueNode = tree.nodes.find((n) => n.path.field_1 === 'true')
        expect(trueNode).toBeDefined()
        expect(trueNode.depth).toBe(0)
        expect(trueNode.row_count).toBe(1)
        // New group is collapsed by default — auto-expanding would
        // surprise the user.
        const collapsedForView = store.getters[
          'grid/getCollapsedGroupsForView'
        ](VIEW_ID)
        expect(
          collapsedForView.some((p) => _.isEqual(p, { field_1: 'true' }))
        ).toBe(true)
        // Row stays in buffer with its new value, sort places it inside
        // the new (collapsed) group's range — heightIndex skips its
        // descendants so it isn't rendered, but it remains buffered.
        const moved = store.state.grid.rows.find((r) => r.id === 1)
        expect(moved).toBeDefined()
        expect(moved.field_1).toBe('true')
      }
    )

    test(
      'deletedExistingRow prunes the group when its last row leaves',
      async () => {
        setup({
          treeNodes: [
            { path: { field_1: 'A' }, depth: 0, row_count: 1 },
            { path: { field_1: 'B' }, depth: 0, row_count: 2 },
          ],
          bufferRows: [
            makeRow(1, 1, { field_1: 'A', field_99: 'a-only' }),
            makeRow(2, 2, { field_1: 'B', field_99: 'b1' }),
            makeRow(3, 3, { field_1: 'B', field_99: 'b2' }),
          ],
        })

        await store.dispatch('grid/deletedExistingRow', {
          view: VIEW,
          fields: FIELDS,
          row: { id: 1, order: '1.0', field_1: 'A', field_99: 'a-only' },
        })

        const tree = store.getters['grid/getGroupTreeForView'](VIEW_ID)
        // A had only one row — it must be removed entirely, not left
        // behind as a 0-row banner.
        expect(
          tree.nodes.find((n) => n.path.field_1 === 'A')
        ).toBeUndefined()
        expect(
          tree.nodes.find((n) => n.path.field_1 === 'B').row_count
        ).toBe(2)
      }
    )

    test(
      'updatedExistingRow inserts a brand-new boolean group at its sorted ' +
        'position (false before true), not at the end of the node list',
      async () => {
        // Tree starts with only ``true`` (two rows). Flipping ONE row to
        // ``false`` must place the new node *before* ``true`` so the
        // heightIndex emits headers in the same order the BE would.
        setup({
          treeNodes: [{ path: { field_1: true }, depth: 0, row_count: 2 }],
          bufferRows: [
            makeRow(1, 1, { field_1: true, field_99: 'one' }),
            makeRow(2, 2, { field_1: true, field_99: 'two' }),
          ],
        })

        await store.dispatch('grid/updatedExistingRow', {
          view: VIEW,
          fields: FIELDS,
          row: { id: 1, order: '1.0', field_1: true, field_99: 'one' },
          values: { id: 1, order: '1.0', field_1: false, field_99: 'one' },
        })

        const tree = store.getters['grid/getGroupTreeForView'](VIEW_ID)
        // ``false`` must come first (ASC order), even though it was
        // inserted after ``true`` was already in the tree.
        expect(tree.nodes.map((n) => n.path.field_1)).toEqual([false, true])
      }
    )

    test(
      'updatedExistingRow on a 2-level group-by: toggling depth-1 (e.g. ' +
        'Completed) keeps the row in the buffer and slots it into the new ' +
        'sub-group; the row must not turn into an empty placeholder',
      async () => {
        // Mirrors the user's screenshot: (Empty) is expanded, both
        // Completed=true (3 rows) and Completed=false (4 rows) are
        // expanded. Toggling row 20013 from true → false must:
        //   - keep 20013 in the buffer (no drop), so the heightIndex
        //     position 2 still maps to a real row.
        //   - patch the tree counts to true=2 / false=5.
        //   - leave the row at sorted position 2 (first false row).
        const VIEW_2D = {
          ...VIEW,
          group_bys: [
            { field: 1, order: 'ASC', type: 'default' },
            { field: 99, order: 'ASC', type: 'default' },
          ],
        }
        store.commit('view/SET_VIEW', VIEW_2D)
        store.commit('grid/SET_LAST_GRID_ID', VIEW_ID)
        store.commit('grid/SET_ACTIVE_GROUP_BYS', [
          { field: 1, order: 'ASC', type: 'default' },
          { field: 99, order: 'ASC', type: 'default' },
        ])
        store.commit('grid/SET_GROUP_TREE', {
          viewId: VIEW_ID,
          tree: {
            nodes: [
              { path: { field_1: null }, depth: 0, row_count: 7 },
              {
                path: { field_1: null, field_99: true },
                depth: 1,
                row_count: 3,
              },
              {
                path: { field_1: null, field_99: false },
                depth: 1,
                row_count: 4,
              },
            ],
            truncated: false,
            total_nodes: 3,
          },
        })
        FIELDS = buildFields()
        store.state.grid.bufferStartIndex = 0
        store.state.grid.bufferLimit = 7
        store.state.grid.rows = [
          makeRow(20011, 20011, { field_1: null, field_99: true }),
          makeRow(20012, 20012, { field_1: null, field_99: true }),
          makeRow(20013, 20013, { field_1: null, field_99: true }),
          makeRow(20021, 20021, { field_1: null, field_99: false }),
          makeRow(20022, 20022, { field_1: null, field_99: false }),
          makeRow(20023, 20023, { field_1: null, field_99: false }),
          makeRow(20030, 20030, { field_1: null, field_99: false }),
        ]
        store.state.grid.count = 7
        testApp.mock.onAny().reply(200, {
          count: 0,
          results: [],
          group_by_metadata: {},
        })

        await store.dispatch('grid/updatedExistingRow', {
          view: VIEW_2D,
          fields: FIELDS,
          row: { id: 20013, order: '20013.0', field_1: null, field_99: true },
          values: {
            id: 20013,
            order: '20013.0',
            field_1: null,
            field_99: false,
          },
        })

        // Tree counts: true = 2, false = 5.
        const tree = store.getters['grid/getGroupTreeForView'](VIEW_ID)
        expect(
          tree.nodes.find(
            (n) => n.depth === 1 && n.path.field_99 === true
          ).row_count
        ).toBe(2)
        expect(
          tree.nodes.find(
            (n) => n.depth === 1 && n.path.field_99 === false
          ).row_count
        ).toBe(5)
        // Row stays in the buffer with the new value at the same sorted
        // position (first false row → still index 2 because true rows
        // come before false rows at depth 1, ASC).
        const moved = store.state.grid.rows.find((r) => r.id === 20013)
        expect(moved).toBeDefined()
        expect(moved.field_99).toBe(false)
        // Buffer length unchanged — no empty placeholder.
        expect(store.state.grid.rows).toHaveLength(7)
        // Row 20013 is now grouped with the other false rows (20021…
        // 20030); 20011 and 20012 (still true) form the other group.
        const rows = store.state.grid.rows
        const trueIds = rows.filter((r) => r.field_99 === true).map((r) => r.id)
        const falseIds = rows.filter((r) => r.field_99 === false).map((r) => r.id)
        expect(trueIds).toEqual([20011, 20012])
        expect(falseIds).toContain(20013)
        // The two groups are not interleaved — every true row precedes
        // every false row (or vice versa) so the heightIndex's sorted
        // ranges align with the buffer slice.
        const trueIndices = rows
          .map((r, i) => (r.field_99 === true ? i : -1))
          .filter((i) => i !== -1)
        const falseIndices = rows
          .map((r, i) => (r.field_99 === false ? i : -1))
          .filter((i) => i !== -1)
        const maxTrue = Math.max(...trueIndices)
        const minFalse = Math.min(...falseIndices)
        expect(maxTrue < minFalse || minFalse < Math.min(...trueIndices)).toBe(
          true
        )
      }
    )

    test(
      'updatedExistingRow on a 2-level group-by (single-select + boolean): ' +
        'assigning a category to an Empty-group row moves the row out of ' +
        'the (Empty) section and only surfaces under the new category',
      async () => {
        // Setup mirrors the user's screenshot: Category (single-select)
        // + Completed (boolean) group-by. Tree has Development > true=1
        // and (Empty) > true=2. Buffer holds the (Empty) > true rows.
        // We flip the first (Empty) row to Category=Development and
        // assert the row is no longer found in the (Empty) section.
        const VIEW_2D = {
          ...VIEW,
          group_bys: [
            { field: 1, order: 'ASC', type: 'default' },
            { field: 99, order: 'ASC', type: 'default' },
          ],
        }
        store.commit('view/SET_VIEW', VIEW_2D)
        store.commit('grid/SET_LAST_GRID_ID', VIEW_ID)
        store.commit('grid/SET_ACTIVE_GROUP_BYS', [
          { field: 1, order: 'ASC', type: 'default' },
          { field: 99, order: 'ASC', type: 'default' },
        ])
        store.commit('grid/SET_GROUP_TREE', {
          viewId: VIEW_ID,
          tree: {
            nodes: [
              { path: { field_1: 'Development' }, depth: 0, row_count: 1 },
              {
                path: { field_1: 'Development', field_99: true },
                depth: 1,
                row_count: 1,
              },
              { path: { field_1: null }, depth: 0, row_count: 2 },
              {
                path: { field_1: null, field_99: true },
                depth: 1,
                row_count: 2,
              },
            ],
            truncated: false,
            total_nodes: 4,
          },
        })
        FIELDS = buildFields()
        // Buffer covers the (Empty) > true sub-group rows in their
        // BE-returned order: [row_20020, row_20011]. The Development
        // row is collapsed/outside the buffer for this test.
        store.state.grid.bufferStartIndex = 0
        store.state.grid.bufferLimit = 2
        store.state.grid.rows = [
          makeRow(20020, 20020, { field_1: null, field_99: true }),
          makeRow(20011, 20011, { field_1: null, field_99: true }),
        ]
        store.state.grid.count = 3
        testApp.mock.onAny().reply(200, {
          count: 0,
          results: [],
          group_by_metadata: {},
        })

        await store.dispatch('grid/updatedExistingRow', {
          view: VIEW_2D,
          fields: FIELDS,
          row: {
            id: 20020,
            order: '20020.0',
            field_1: null,
            field_99: true,
          },
          values: {
            id: 20020,
            order: '20020.0',
            field_1: 'Development',
            field_99: true,
          },
        })

        const tree = store.getters['grid/getGroupTreeForView'](VIEW_ID)
        // Tree counts patched: Development +1, (Empty) -1.
        expect(
          tree.nodes.find(
            (n) => n.depth === 0 && n.path.field_1 === 'Development'
          ).row_count
        ).toBe(2)
        expect(
          tree.nodes.find((n) => n.depth === 0 && n.path.field_1 === null)
            .row_count
        ).toBe(1)
        expect(
          tree.nodes.find(
            (n) => n.depth === 1 && n.path.field_1 === 'Development'
          ).row_count
        ).toBe(2)
        expect(
          tree.nodes.find(
            (n) =>
              n.depth === 1 &&
              n.path.field_1 === null &&
              n.path.field_99 === true
          ).row_count
        ).toBe(1)

        // Row stays in the buffer with its new Category value; sort
        // re-positions it among the Development section's rows.
        const moved = store.state.grid.rows.find((r) => r.id === 20020)
        expect(moved).toBeDefined()
        expect(moved.field_1).toBe('Development')
      }
    )

    test(
      'updatedExistingRow inserts a brand-new text group between alphabetic ' +
        'siblings, not at the end',
      async () => {
        setup({
          treeNodes: [
            { path: { field_1: 'Apple' }, depth: 0, row_count: 1 },
            { path: { field_1: 'Cherry' }, depth: 0, row_count: 1 },
          ],
          bufferRows: [
            makeRow(1, 1, { field_1: 'Apple', field_99: 'a' }),
            makeRow(2, 2, { field_1: 'Cherry', field_99: 'c' }),
          ],
        })

        await store.dispatch('grid/updatedExistingRow', {
          view: VIEW,
          fields: FIELDS,
          row: { id: 2, order: '2.0', field_1: 'Cherry', field_99: 'c' },
          values: { id: 2, order: '2.0', field_1: 'Banana', field_99: 'c' },
        })

        const tree = store.getters['grid/getGroupTreeForView'](VIEW_ID)
        // Banana must slot between Apple and Cherry; Cherry pruned.
        expect(tree.nodes.map((n) => n.path.field_1)).toEqual([
          'Apple',
          'Banana',
        ])
      }
    )

    test(
      'updatedExistingRow re-collapses a freshly recreated group only when ' +
        'the user has not previously collapsed it',
      async () => {
        // Slightly tricky: imagine the user previously collapsed group
        // ``true`` while it had rows, then those rows all moved out and
        // the group got pruned. The collapsed-list entry stays behind
        // (it's intent, not state). When a row later re-creates the
        // group, the new node must respect the lingering collapse and
        // not flip back to expanded just because we naively toggled.
        setup({
          treeNodes: [
            { path: { field_1: 'false' }, depth: 0, row_count: 1 },
          ],
          bufferRows: [
            makeRow(1, 1, { field_1: 'false', field_99: 'one' }),
          ],
        })
        // Pre-existing collapsed-list entry for the not-yet-existing
        // group, simulating "user previously collapsed it before it was
        // emptied out".
        store.commit('grid/TOGGLE_GROUP_COLLAPSED', {
          viewId: VIEW_ID,
          groupValues: { field_1: 'true' },
        })

        await store.dispatch('grid/updatedExistingRow', {
          view: VIEW,
          fields: FIELDS,
          row: { id: 1, order: '1.0', field_1: 'false', field_99: 'one' },
          values: { id: 1, order: '1.0', field_1: 'true', field_99: 'one' },
        })

        const collapsedForView = store.getters[
          'grid/getCollapsedGroupsForView'
        ](VIEW_ID)
        // Exactly one entry — the toggle must not have re-opened the
        // path because it was already in the collapsed list.
        expect(
          collapsedForView.filter((p) => _.isEqual(p, { field_1: 'true' }))
            .length
        ).toBe(1)
        const tree = store.getters['grid/getGroupTreeForView'](VIEW_ID)
        expect(
          tree.nodes.find((n) => n.path.field_1 === 'true').row_count
        ).toBe(1)
      }
    )

    test(
      'updatedExistingRow inserts both a new depth-0 and depth-1 node ' +
        'when neither path exists yet (multi-level grouping)',
      async () => {
        const VIEW_2D = {
          ...VIEW,
          group_bys: [
            { field: 1, order: 'ASC', type: 'default' },
            { field: 99, order: 'ASC', type: 'default' },
          ],
        }
        store.commit('view/SET_VIEW', VIEW_2D)
        store.commit('grid/SET_LAST_GRID_ID', VIEW_ID)
        store.commit('grid/SET_ACTIVE_GROUP_BYS', [
          { field: 1, order: 'ASC', type: 'default' },
          { field: 99, order: 'ASC', type: 'default' },
        ])
        store.commit('grid/SET_GROUP_TREE', {
          viewId: VIEW_ID,
          tree: {
            nodes: [
              { path: { field_1: 'A' }, depth: 0, row_count: 1 },
              {
                path: { field_1: 'A', field_99: 'X' },
                depth: 1,
                row_count: 1,
              },
            ],
            truncated: false,
            total_nodes: 2,
          },
        })
        FIELDS = buildFields()
        store.state.grid.bufferStartIndex = 0
        store.state.grid.bufferLimit = 1
        store.state.grid.rows = [
          makeRow(1, 1, { field_1: 'A', field_99: 'X' }),
        ]
        store.state.grid.count = 1
        testApp.mock.onAny().reply(200, {
          count: 0,
          results: [],
          group_by_metadata: {},
        })

        await store.dispatch('grid/updatedExistingRow', {
          view: VIEW_2D,
          fields: FIELDS,
          row: { id: 1, order: '1.0', field_1: 'A', field_99: 'X' },
          values: { id: 1, order: '1.0', field_1: 'B', field_99: 'Y' },
        })

        const tree = store.getters['grid/getGroupTreeForView'](VIEW_ID)
        // Old A and A.X should be pruned (each had 1 row, now 0).
        expect(
          tree.nodes.find((n) => n.depth === 0 && n.path.field_1 === 'A')
        ).toBeUndefined()
        expect(
          tree.nodes.find((n) => n.path.field_99 === 'X')
        ).toBeUndefined()
        // New B and B.Y inserted with row_count=1.
        const bNode = tree.nodes.find(
          (n) => n.depth === 0 && n.path.field_1 === 'B'
        )
        const byNode = tree.nodes.find(
          (n) => n.depth === 1 && n.path.field_99 === 'Y'
        )
        expect(bNode).toBeDefined()
        expect(bNode.row_count).toBe(1)
        expect(byNode).toBeDefined()
        expect(byNode.row_count).toBe(1)
        // Both new paths collapsed.
        const collapsed = store.getters['grid/getCollapsedGroupsForView'](
          VIEW_ID
        )
        expect(
          collapsed.some((p) => _.isEqual(p, { field_1: 'B' }))
        ).toBe(true)
        expect(
          collapsed.some((p) =>
            _.isEqual(p, { field_1: 'B', field_99: 'Y' })
          )
        ).toBe(true)
      }
    )

    test(
      'updatedExistingRow inserts only the missing depth-1 node when the ' +
        'depth-0 parent already exists (multi-level grouping)',
      async () => {
        const VIEW_2D = {
          ...VIEW,
          group_bys: [
            { field: 1, order: 'ASC', type: 'default' },
            { field: 99, order: 'ASC', type: 'default' },
          ],
        }
        store.commit('view/SET_VIEW', VIEW_2D)
        store.commit('grid/SET_LAST_GRID_ID', VIEW_ID)
        store.commit('grid/SET_ACTIVE_GROUP_BYS', [
          { field: 1, order: 'ASC', type: 'default' },
          { field: 99, order: 'ASC', type: 'default' },
        ])
        store.commit('grid/SET_GROUP_TREE', {
          viewId: VIEW_ID,
          tree: {
            nodes: [
              { path: { field_1: 'A' }, depth: 0, row_count: 2 },
              {
                path: { field_1: 'A', field_99: 'X' },
                depth: 1,
                row_count: 2,
              },
            ],
            truncated: false,
            total_nodes: 2,
          },
        })
        FIELDS = buildFields()
        store.state.grid.bufferStartIndex = 0
        store.state.grid.bufferLimit = 2
        store.state.grid.rows = [
          makeRow(1, 1, { field_1: 'A', field_99: 'X' }),
          makeRow(2, 2, { field_1: 'A', field_99: 'X' }),
        ]
        store.state.grid.count = 2
        testApp.mock.onAny().reply(200, {
          count: 0,
          results: [],
          group_by_metadata: {},
        })

        await store.dispatch('grid/updatedExistingRow', {
          view: VIEW_2D,
          fields: FIELDS,
          row: { id: 2, order: '2.0', field_1: 'A', field_99: 'X' },
          values: { id: 2, order: '2.0', field_1: 'A', field_99: 'Y' },
        })

        const tree = store.getters['grid/getGroupTreeForView'](VIEW_ID)
        // Depth-0 A keeps row_count=2 (one row left A.X, one entered A.Y).
        const aNode = tree.nodes.find(
          (n) => n.depth === 0 && n.path.field_1 === 'A'
        )
        expect(aNode.row_count).toBe(2)
        // Depth-1 A.X drops to 1 (still has one row).
        const axNode = tree.nodes.find(
          (n) => n.path.field_99 === 'X' && n.depth === 1
        )
        expect(axNode.row_count).toBe(1)
        // Depth-1 A.Y created collapsed with row_count=1.
        const ayNode = tree.nodes.find(
          (n) => n.path.field_99 === 'Y' && n.depth === 1
        )
        expect(ayNode).toBeDefined()
        expect(ayNode.row_count).toBe(1)
        const collapsed = store.getters['grid/getCollapsedGroupsForView'](
          VIEW_ID
        )
        expect(
          collapsed.some((p) =>
            _.isEqual(p, { field_1: 'A', field_99: 'Y' })
          )
        ).toBe(true)
        // Depth-0 A must NOT have been added to collapsed list — it
        // existed already, so the toggle should be skipped.
        expect(
          collapsed.some((p) => _.isEqual(p, { field_1: 'A' }))
        ).toBe(false)
      }
    )

    test(
      'deletedExistingRow prunes the leaf-only group when only the deepest ' +
        'level becomes empty (multi-level grouping)',
      async () => {
        const VIEW_2D = {
          ...VIEW,
          group_bys: [
            { field: 1, order: 'ASC', type: 'default' },
            { field: 99, order: 'ASC', type: 'default' },
          ],
        }
        store.commit('view/SET_VIEW', VIEW_2D)
        store.commit('grid/SET_LAST_GRID_ID', VIEW_ID)
        store.commit('grid/SET_ACTIVE_GROUP_BYS', [
          { field: 1, order: 'ASC', type: 'default' },
          { field: 99, order: 'ASC', type: 'default' },
        ])
        store.commit('grid/SET_GROUP_TREE', {
          viewId: VIEW_ID,
          tree: {
            nodes: [
              { path: { field_1: 'A' }, depth: 0, row_count: 2 },
              {
                path: { field_1: 'A', field_99: 'X' },
                depth: 1,
                row_count: 1,
              },
              {
                path: { field_1: 'A', field_99: 'Y' },
                depth: 1,
                row_count: 1,
              },
            ],
            truncated: false,
            total_nodes: 3,
          },
        })
        FIELDS = buildFields()
        store.state.grid.bufferStartIndex = 0
        store.state.grid.bufferLimit = 2
        store.state.grid.rows = [
          makeRow(1, 1, { field_1: 'A', field_99: 'X' }),
          makeRow(2, 2, { field_1: 'A', field_99: 'Y' }),
        ]
        store.state.grid.count = 2
        testApp.mock.onAny().reply(200, {
          count: 0,
          results: [],
          group_by_metadata: {},
        })

        await store.dispatch('grid/deletedExistingRow', {
          view: VIEW_2D,
          fields: FIELDS,
          row: { id: 1, order: '1.0', field_1: 'A', field_99: 'X' },
        })

        const tree = store.getters['grid/getGroupTreeForView'](VIEW_ID)
        // A.X had only one row — pruned.
        expect(
          tree.nodes.find((n) => n.path.field_99 === 'X')
        ).toBeUndefined()
        // A still has one row (in A.Y) — kept.
        expect(
          tree.nodes.find((n) => n.depth === 0 && n.path.field_1 === 'A')
            .row_count
        ).toBe(1)
        // A.Y untouched.
        expect(
          tree.nodes.find((n) => n.path.field_99 === 'Y').row_count
        ).toBe(1)
      }
    )

    test(
      'deletedExistingRow drops the row from the buffer and decrements the ' +
        'tree count for its group',
      async () => {
        setup({
          treeNodes: [
            { path: { field_1: 'A' }, depth: 0, row_count: 3 },
            { path: { field_1: 'B' }, depth: 0, row_count: 2 },
          ],
          bufferRows: [
            makeRow(1, 1, { field_1: 'A', field_99: 'a1' }),
            makeRow(2, 2, { field_1: 'A', field_99: 'a2' }),
            makeRow(3, 3, { field_1: 'A', field_99: 'a3' }),
          ],
          collapsedGroups: [{ field_1: 'B' }],
        })

        await store.dispatch('grid/deletedExistingRow', {
          view: VIEW,
          fields: FIELDS,
          row: { id: 2, order: '2.0', field_1: 'A', field_99: 'a2' },
        })

        expect(store.state.grid.rows.find((r) => r.id === 2)).toBeUndefined()
        const tree = store.getters['grid/getGroupTreeForView'](VIEW_ID)
        expect(
          tree.nodes.find((n) => n.path.field_1 === 'A').row_count
        ).toBe(2)
        // The other group is untouched.
        expect(
          tree.nodes.find((n) => n.path.field_1 === 'B').row_count
        ).toBe(2)
      }
    )
  })
})
