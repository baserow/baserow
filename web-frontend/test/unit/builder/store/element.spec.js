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

    test('moving an element absent from the graph makes it join the graph', () => {
      // Regression: moving an orphan (present on the page but missing from the
      // graph) used to throw "Cannot read properties of undefined (reading
      // 'children')". It must instead join the graph at the requested position.
      const el1 = el(1)
      const el2 = el(2)
      const orphan = el(99)
      const page = makePage({ 0: 1, 1: { next: { '': [2] } }, 2: {} }, [
        el1,
        el2,
        orphan,
      ])

      expect(() =>
        elementStore.actions.graphMove(
          { dispatch: makeDispatch(page) },
          {
            page,
            elementToMove: orphan,
            referenceElement: el1,
            position: 'south',
            output: '',
          }
        )
      ).not.toThrow()

      // The orphan is now spliced into the graph between el1 and el2.
      expect(page.graph['1'].next['']).toEqual([99])
      expect(page.graph['99'].next['']).toEqual([2])
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

  describe('create', () => {
    // Element type stub with the methods create() touches.
    const makeRegistry = () => ({
      get: () => ({
        getDefaultValues: () => ({}),
        getPopulateStoreProperties: () => ({}),
      }),
    })

    const makeContext = (commit) => ({
      commit,
      dispatch: vi.fn(() => Promise.resolve()),
      getters: {
        getElementById: () => null,
        getParent: () => null,
      },
    })

    const makeThis = (element) => ({
      $registry: makeRegistry(),
      $client: { post: vi.fn(() => Promise.resolve({ data: element })) },
    })

    test('does not add the element directly when forceCreate is true', async () => {
      // Regression: with forceCreate the element is added via the forceCreate
      // action; adding it here too pushes a duplicate into page.elements that
      // DELETE_ITEM (single occurrence) leaves behind as a "phantom".
      const element = { id: 5, type: 'heading' }
      const page = makePage({ 0: 1, 1: {} }, [])
      const commit = vi.fn()

      await elementStore.actions.create.call(
        makeThis(element),
        makeContext(commit),
        {
          builder: {},
          page,
          elementType: 'heading',
          forceCreate: true,
        }
      )

      expect(commit).not.toHaveBeenCalledWith('ADD_ITEM', expect.anything())
    })

    test('adds the element directly when forceCreate is false', async () => {
      const element = { id: 5, type: 'heading' }
      const page = makePage({ 0: 1, 1: {} }, [])
      const commit = vi.fn()
      const context = makeContext(commit)

      await elementStore.actions.create.call(makeThis(element), context, {
        builder: {},
        page,
        elementType: 'heading',
        forceCreate: false,
      })

      expect(commit).toHaveBeenCalledWith('ADD_ITEM', { page, element })
      // forceCreate (which would also add it) must not run in this path.
      const dispatchedActions = context.dispatch.mock.calls.map(
        ([name]) => name
      )
      expect(dispatchedActions).not.toContain('forceCreate')
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

  describe('move', () => {
    beforeEach(() => {
      vi.useFakeTimers()
    })

    afterEach(() => {
      vi.clearAllTimers()
      vi.useRealTimers()
    })

    test('cross-page move relocates the element workflow actions', async () => {
      // Regression: moving an element to another page (e.g. to the shared page)
      // must move its workflow actions along too, otherwise they are stranded on
      // the source page and appear disassociated from the element.
      const button = { id: 5, type: 'button', place_in_container: '' }
      const sourcePage = { ...makePage({ 0: 5, 5: {} }, [button]), id: 1 }
      const targetPage = { ...makePage({}, []), id: 2 }

      const workflowAction = { id: 9, element_id: 5, page_id: sourcePage.id }

      const dispatched = []
      const dispatch = vi.fn((action, payload, opts) => {
        dispatched.push({ action, payload })
      })

      const context = {
        commit: vi.fn(),
        dispatch,
        getters: {
          getElementById: () => button,
          getParent: () => null,
        },
        rootGetters: {
          'builderWorkflowAction/getElementWorkflowActions': (page, id) =>
            id === button.id ? [workflowAction] : [],
        },
      }

      // wrapMove just runs its callback; the backend call is debounced and kept
      // pending by fake timers because this test only covers optimistic behavior.
      const thisCtx = {
        $client: {},
        $registry: { get: () => ({ wrapMove: (ctxArg, cb) => cb() }) },
      }

      await elementStore.actions.move.call(thisCtx, context, {
        builder: {},
        page: sourcePage,
        elementId: button.id,
        referenceElementId: null,
        position: 'south',
        placeInContainer: '',
        targetPage,
      })

      const wa = (action) =>
        dispatched.filter((d) => d.action === action).map((d) => d.payload)

      expect(wa('builderWorkflowAction/forceDelete')).toEqual([
        { page: sourcePage, workflowActionId: 9 },
      ])
      expect(wa('builderWorkflowAction/forceCreate')).toEqual([
        {
          page: targetPage,
          workflowAction: { id: 9, element_id: 5, page_id: targetPage.id },
        },
      ])
    })

    test('same-page move does not touch workflow actions', async () => {
      const button = { id: 5, type: 'button', place_in_container: '' }
      const first = el(1)
      const page = makePage({ 0: 1, 1: { next: { '': [5] } }, 5: {} }, [
        first,
        button,
      ])

      const dispatched = []
      const dispatch = vi.fn((action, payload) => {
        dispatched.push({ action, payload })
      })

      const context = {
        commit: vi.fn(),
        dispatch,
        getters: { getElementById: () => button, getParent: () => null },
        rootGetters: {
          'builderWorkflowAction/getElementWorkflowActions': () => [],
        },
      }
      const thisCtx = {
        $client: {},
        $registry: { get: () => ({ wrapMove: (ctxArg, cb) => cb() }) },
      }

      await elementStore.actions.move.call(thisCtx, context, {
        builder: {},
        page,
        elementId: button.id,
        referenceElementId: first.id,
        position: 'north',
        placeInContainer: '',
        targetPage: null,
      })

      expect(
        dispatched.some((d) => d.action.startsWith('builderWorkflowAction/'))
      ).toBe(false)
    })

    test('flushes a pending move when a different element is moved', async () => {
      // Regression: `moveTimeout` is shared across all elements. Moving a second
      // element within the debounce window used to cancel the first element's
      // timer and drop its backend move (and its undo action).
      const elementA = { id: 5, type: 'heading', place_in_container: '' }
      const elementB = { id: 6, type: 'heading', place_in_container: '' }
      const page = makePage({ 0: 5, 5: { next: { '': [6] } }, 6: {} }, [
        elementA,
        elementB,
      ])

      const patch = vi.fn((url) =>
        Promise.resolve({
          data: { id: Number(url.match(/element\/(\d+)/)[1]), page_id: page.id },
        })
      )
      const thisCtx = {
        $client: { patch },
        $registry: { get: () => ({ wrapMove: (ctxArg, cb) => cb() }) },
      }
      const context = {
        commit: vi.fn(),
        dispatch: vi.fn(() => Promise.resolve()),
        getters: {
          getElementById: (p, id) =>
            [elementA, elementB].find((e) => e.id === id) ?? null,
          getParent: () => null,
        },
        rootGetters: {
          'builderWorkflowAction/getElementWorkflowActions': () => [],
        },
      }

      const move = (elementId) =>
        elementStore.actions.move.call(thisCtx, context, {
          builder: {},
          page,
          elementId,
          referenceElementId: null,
          position: 'south',
          placeInContainer: '',
          targetPage: null,
        })

      await move(5)
      // Still within A's debounce window: nothing persisted yet.
      expect(patch).not.toHaveBeenCalled()

      // Moving B flushes A's pending move instead of discarding it.
      await move(6)
      expect(patch).toHaveBeenCalledWith(
        'builder/element/5/move/',
        expect.anything()
      )

      // B is still debounced; let its timer fire.
      await vi.advanceTimersByTimeAsync(1000)
      expect(patch).toHaveBeenCalledWith(
        'builder/element/6/move/',
        expect.anything()
      )
      expect(patch).toHaveBeenCalledTimes(2)
    })
  })

  describe('debouncedUpdate', () => {
    beforeEach(() => {
      vi.useFakeTimers()
    })

    afterEach(() => {
      vi.clearAllTimers()
      vi.useRealTimers()
    })

    const makeContext = () => ({
      dispatch: vi.fn(() => Promise.resolve()),
      getters: {},
    })

    test('flushes the pending update when a different element is edited', async () => {
      // Regression: the debounce context is shared across all elements. Editing a
      // second element before the first's debounce fired used to clear the first
      // element's timer and drop its save entirely, leaving the local state ahead
      // of the backend and its undo action missing.
      const patch = vi.fn(() => Promise.resolve({ data: {} }))
      const thisCtx = { $client: { patch } }
      const page = makePage({}, [])
      const elementA = { id: 1, type: 'heading', value: 'a' }
      const elementB = { id: 2, type: 'heading', value: 'b' }

      const p1 = elementStore.actions.debouncedUpdate.call(
        thisCtx,
        makeContext(),
        { builder: {}, page, element: elementA, values: { value: 'AAA' } }
      )
      await vi.advanceTimersByTimeAsync(0)
      // Still within A's debounce window: nothing persisted yet.
      expect(patch).not.toHaveBeenCalled()

      const p2 = elementStore.actions.debouncedUpdate.call(
        thisCtx,
        makeContext(),
        { builder: {}, page, element: elementB, values: { value: 'BBB' } }
      )
      await vi.advanceTimersByTimeAsync(0)
      // Editing B flushed A's pending update instead of discarding it.
      expect(patch).toHaveBeenCalledWith('builder/element/1/', { value: 'AAA' })

      // B is still debounced; let its timer fire.
      await vi.advanceTimersByTimeAsync(500)
      expect(patch).toHaveBeenCalledWith('builder/element/2/', { value: 'BBB' })
      expect(patch).toHaveBeenCalledTimes(2)

      await Promise.all([p1, p2])
    })

    test('coalesces rapid edits to the same element into a single save', async () => {
      const patch = vi.fn(() => Promise.resolve({ data: {} }))
      const thisCtx = { $client: { patch } }
      const page = makePage({}, [])
      const element = { id: 1, type: 'heading', value: 'a' }

      const p1 = elementStore.actions.debouncedUpdate.call(
        thisCtx,
        makeContext(),
        { builder: {}, page, element, values: { value: 'X' } }
      )
      await vi.advanceTimersByTimeAsync(200)
      const p2 = elementStore.actions.debouncedUpdate.call(
        thisCtx,
        makeContext(),
        { builder: {}, page, element, values: { value: 'XY' } }
      )
      await vi.advanceTimersByTimeAsync(500)

      // Same element: the edits coalesce into one PATCH with the latest value,
      // never prematurely flushed.
      expect(patch).toHaveBeenCalledTimes(1)
      expect(patch).toHaveBeenCalledWith('builder/element/1/', { value: 'XY' })

      await Promise.all([p1, p2])
    })
  })

  describe('getRootElements', () => {
    test('appends elements absent from the graph as bottom root elements', () => {
      // Regression: an Element that exists on the page but is missing from the
      // graph (e.g. created during a not-yet-zero-downtime deployment) must still
      // be shown, at the bottom of the root list, rather than silently hidden.
      const orphan = el(99)
      const page = makePage({ 0: 1, 1: { next: { '': [2] } }, 2: {} }, [
        el(1),
        el(2),
        orphan,
      ])

      const result = elementStore.getters.getRootElements(null, null)(page)

      expect(result.map((e) => e.id)).toEqual([1, 2, 99])
    })

    test('does not promote container children to root', () => {
      // Child 2 lives inside container 1's slot "0". It is present in the graph,
      // so it is not an orphan and must not appear as a root element.
      const page = makePage({ 0: 1, 1: { children: { 0: [2] } }, 2: {} }, [
        el(1),
        el(2),
        el(99),
      ])

      const result = elementStore.getters.getRootElements(null, null)(page)

      expect(result.map((e) => e.id)).toEqual([1, 99])
    })
  })
})
