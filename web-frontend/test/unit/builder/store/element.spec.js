import { vi } from 'vitest'
import elementStore from '@baserow/modules/builder/store/element'

// Applies page/forceUpdate payloads so the page object reflects handler changes.
const makeDispatch =
  (page, captured = []) =>
  (action, payload, opts) => {
    captured.push(action)
    if (action === 'page/forceUpdate') {
      Object.assign(page, payload.values)
    }
  }

// Build a minimal page compatible with ElementGraphHandler.
const makePage = (graph, elements = []) => {
  const elementMap = Object.fromEntries(elements.map((e) => [String(e.id), e]))
  return { graph: { ...graph }, elements, elementMap }
}

const el = (id) => ({ id, type: 'heading', place_in_container: '' })

describe('element store', () => {
  describe('graphInsert', () => {
    test('null+south appends element to end of chain, not at root', () => {
      // Regression: creating an element without a reference (e.g. from the
      // elements sidebar) used to call insert(null, 'south') which placed it
      // at root, pushing existing elements down. It should append to the tail.
      const el1 = el(1)
      const el2 = el(2)
      const el3 = el(3)
      const page = makePage({ 0: 1, 1: { next: { '': [2] } }, 2: {} }, [
        el1,
        el2,
      ])

      elementStore.actions.graphInsert(
        { dispatch: makeDispatch(page) },
        {
          page,
          element: el3,
          referenceElement: null,
          position: 'south',
          output: '',
        }
      )

      // el3 must be at the tail, not at root.
      expect(page.graph['0']).toBe(1)
      expect(page.graph['1'].next['']).toEqual([2])
      expect(page.graph['2'].next['']).toEqual([3])
    })

    test('non-null reference delegates to handler.insert', () => {
      // Inserting south of el1 (which has el2 as next) should splice el3 between them.
      const el1 = el(1)
      const el2 = el(2)
      const el3 = el(3)
      const page = makePage({ 0: 1, 1: { next: { '': [2] } }, 2: {} }, [
        el1,
        el2,
      ])

      elementStore.actions.graphInsert(
        { dispatch: makeDispatch(page) },
        {
          page,
          element: el3,
          referenceElement: el1,
          position: 'south',
          output: '',
        }
      )

      expect(page.graph['1'].next['']).toEqual([3])
      expect(page.graph['3'].next['']).toEqual([2])
    })
  })

  describe('graphMove', () => {
    test('null+south appends element to end of root chain', () => {
      // Chain: 1 → 2. el3 is currently first (root). Moving it to null+south
      // should place it after 2, not back at root.
      const el1 = el(1)
      const el2 = el(2)
      const el3 = el(3)
      const page = makePage(
        { 0: 3, 3: { next: { '': [1] } }, 1: { next: { '': [2] } }, 2: {} },
        [el1, el2, el3]
      )

      elementStore.actions.graphMove(
        { dispatch: makeDispatch(page) },
        {
          page,
          elementToMove: el3,
          referenceElement: null,
          position: 'south',
          output: '',
        }
      )

      // Root should now be el1, and el3 should be at the tail.
      expect(page.graph['0']).toBe(1)
      expect(page.graph['1'].next['']).toEqual([2])
      expect(page.graph['2'].next['']).toEqual([3])
      // el3 is now the tail — no successors.
      expect(page.graph['3']?.next?.[''] ?? []).toHaveLength(0)
    })
  })

  describe('graphRemove', () => {
    test('removes descendant graph entries when removing a container', () => {
      // Chain: el1 (root, has child el2), el2 has next el3. el4 follows el1.
      // Removing el1 should delete el1, el2, el3 from graph and promote el4 to root.
      const el1 = el(1)
      const el4 = el(4)
      const page = makePage(
        {
          0: 1,
          1: { next: { '': [4] }, children: { '': [2] } },
          2: { next: { '': [3] } },
          3: {},
          4: {},
        },
        [el1, el(2), el(3), el4]
      )

      elementStore.actions.graphRemove(
        { dispatch: makeDispatch(page) },
        { page, element: el1 }
      )

      expect('1' in page.graph).toBe(false)
      expect('2' in page.graph).toBe(false)
      expect('3' in page.graph).toBe(false)
      // el4 is a sibling (not a descendant) — its entry must survive.
      expect(page.graph['0']).toBe(4)
      expect('4' in page.graph).toBe(true)
    })

    test('removes only the point entry when point has no descendants', () => {
      const el1 = el(1)
      const el2 = el(2)
      const page = makePage({ 0: 1, 1: { next: { '': [2] } }, 2: {} }, [
        el1,
        el2,
      ])

      elementStore.actions.graphRemove(
        { dispatch: makeDispatch(page) },
        { page, element: el2 }
      )

      expect('2' in page.graph).toBe(false)
      expect(page.graph['0']).toBe(1)
      expect('1' in page.graph).toBe(true)
    })
  })

  describe('forceCreate', () => {
    const makeRegistry = () => ({
      get: () => ({
        afterCreate: vi.fn(),
        getPopulateStoreProperties: () => ({}),
      }),
    })

    // commit is a no-op here — we only care about which actions are dispatched.
    const commit = vi.fn()

    test('skips graphInsert when element is already in the graph', () => {
      const element = { id: 10, type: 'heading', place_in_container: '' }
      const page = makePage({ 0: 10, 10: {} }, [element])

      const dispatched = []
      const dispatch = makeDispatch(page, dispatched)

      elementStore.actions.forceCreate.call(
        { $registry: makeRegistry() },
        { dispatch, commit },
        { page, element }
      )

      expect(dispatched).not.toContain('graphInsert')
    })

    test('dispatches graphInsert when element is absent from the graph', () => {
      const existing = el(1)
      const newEl = { id: 99, type: 'heading', place_in_container: '' }
      const page = makePage({ 0: 1, 1: {} }, [existing, newEl])

      const dispatched = []
      const dispatch = makeDispatch(page, dispatched)

      elementStore.actions.forceCreate.call(
        { $registry: makeRegistry() },
        { dispatch, commit },
        { page, element: newEl }
      )

      expect(dispatched).toContain('graphInsert')
    })
  })
})
