import KanbanViewStack from '@baserow_premium/components/views/kanban/KanbanViewStack.vue'

describe('KanbanViewStack drag behaviour', () => {
  test('dragRestrictedBySort returns true when the view has sortings', () => {
    const view = { sortings: [{ id: 1, field: 1, order: 'ASC' }] }
    expect(KanbanViewStack.computed.dragRestrictedBySort.call({ view })).toBe(
      true
    )
  })

  test('dragRestrictedBySort returns false when the view has no sortings', () => {
    const view = { sortings: [] }
    expect(KanbanViewStack.computed.dragRestrictedBySort.call({ view })).toBe(
      false
    )
  })

  test('cardMoveOver does not reorder vertically within a stack when sortings are active', async () => {
    const dispatched = []
    const draggingRow = { id: 1 }
    const targetRow = { id: 2 }
    // The dragging row and the target row both belong to stack `stack-a`.
    const findStackIdAndIndex = (id) => {
      if (id === draggingRow.id) return ['stack-a', 0]
      if (id === targetRow.id) return ['stack-a', 1]
      return undefined
    }

    const context = {
      draggingRow,
      draggingOriginalStackId: 'stack-a',
      dragRestrictedBySort: true,
      storePrefix: 'page/',
      view: { sortings: [{ field: 1, order: 'ASC' }] },
      fields: [],
      $registry: { get: () => ({ canWriteFieldValues: () => true }) },
      singleSelectField: { type: 'single_select' },
      $store: {
        getters: {
          'page/view/kanban/findStackIdAndIndex': findStackIdAndIndex,
        },
        dispatch: (action, payload) => {
          dispatched.push({ action, payload })
          return Promise.resolve(true)
        },
      },
    }
    const event = {
      target: { transitioning: false, getBoundingClientRect: () => ({}) },
    }

    await KanbanViewStack.methods.cardMoveOver.call(context, event, targetRow)

    expect(dispatched).toEqual([])
  })

  test('cardMoveOver moves a row to a different stack at the sort-determined index when sortings are active', async () => {
    const dispatched = []
    const draggingRow = { id: 1 }
    const targetRow = { id: 2 }
    const findStackIdAndIndex = (id) => {
      if (id === draggingRow.id) return ['stack-a', 0]
      if (id === targetRow.id) return ['stack-b', 0]
      return undefined
    }

    const context = {
      draggingRow,
      draggingOriginalStackId: 'stack-a',
      dragRestrictedBySort: true,
      storePrefix: 'page/',
      view: { sortings: [{ field: 99, order: 'ASC', type: 'default' }] },
      fields: [],
      $registry: { get: () => ({ canWriteFieldValues: () => true }) },
      singleSelectField: { type: 'single_select' },
      $store: {
        getters: {
          'page/view/kanban/findStackIdAndIndex': findStackIdAndIndex,
        },
        dispatch: (action, payload) => {
          dispatched.push({ action, payload })
          return Promise.resolve(true)
        },
      },
      moved: vi.fn(),
      // The component delegates the sort lookup to this helper; we stub it
      // here so the test focuses on the cross-stack dispatching logic.
      sortedIndexInStack: vi.fn(() => 1),
    }
    const event = {
      target: { transitioning: false, getBoundingClientRect: () => ({}) },
    }

    await KanbanViewStack.methods.cardMoveOver.call(context, event, targetRow)

    expect(context.sortedIndexInStack).toHaveBeenCalledWith('stack-b')
    expect(dispatched).toHaveLength(1)
    expect(dispatched[0].action).toBe('page/view/kanban/forceMoveRowTo')
    expect(dispatched[0].payload).toEqual({
      row: draggingRow,
      targetStackId: 'stack-b',
      targetIndex: 1,
    })
  })

  test('sortedIndexInStack returns the sort-determined index for the dragging row', () => {
    const draggingRow = { id: 1, field_99: 'M' }
    const stackResults = [
      { id: 2, field_99: 'A' },
      { id: 3, field_99: 'Z' },
    ]
    const sortField = { id: 99, type: 'text' }

    const context = {
      draggingRow,
      storePrefix: 'page/',
      view: { sortings: [{ field: 99, order: 'ASC', type: 'default' }] },
      fields: [sortField],
      $registry: {
        get: (registry, type) => {
          if (registry === 'field' && type === 'text') {
            return {
              getSortTypes: () => ({
                default: {
                  function: (fieldName, order) => (a, b) => {
                    const valueA = a[fieldName] ?? ''
                    const valueB = b[fieldName] ?? ''
                    const cmp = valueA.localeCompare(valueB)
                    return order === 'ASC' ? cmp : -cmp
                  },
                },
              }),
            }
          }
          return {}
        },
      },
      $store: {
        getters: {
          'page/view/kanban/getStack': () => ({ results: stackResults }),
        },
      },
    }

    // 'M' sorts between 'A' and 'Z', so the dragging row should land at index 1.
    expect(
      KanbanViewStack.methods.sortedIndexInStack.call(context, 'stack-b')
    ).toBe(1)
  })

  test('cardMoveOver falls back to default before/after behaviour when no sortings are configured', async () => {
    const dispatched = []
    const draggingRow = { id: 1 }
    const targetRow = { id: 2 }
    const findStackIdAndIndex = (id) => {
      if (id === draggingRow.id) return ['stack-a', 0]
      if (id === targetRow.id) return ['stack-a', 1]
      return undefined
    }
    const context = {
      draggingRow,
      draggingOriginalStackId: 'stack-a',
      dragRestrictedBySort: false,
      storePrefix: 'page/',
      view: { sortings: [] },
      fields: [],
      $registry: { get: () => ({ canWriteFieldValues: () => true }) },
      singleSelectField: { type: 'single_select' },
      $store: {
        getters: {
          'page/view/kanban/findStackIdAndIndex': findStackIdAndIndex,
        },
        dispatch: (action, payload) => {
          dispatched.push({ action, payload })
          return Promise.resolve(true)
        },
      },
      moved: vi.fn(),
    }
    const event = {
      clientY: 5,
      target: {
        transitioning: false,
        getBoundingClientRect: () => ({ top: 0, height: 20 }),
      },
    }

    await KanbanViewStack.methods.cardMoveOver.call(context, event, targetRow)

    expect(dispatched).toHaveLength(1)
    expect(dispatched[0].action).toBe('page/view/kanban/forceMoveRowBefore')
    expect(dispatched[0].payload.targetBefore).toBe(true)
  })
})
