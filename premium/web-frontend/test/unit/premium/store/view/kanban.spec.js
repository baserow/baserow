import kanbanStore from '@baserow_premium/store/view/kanban'
import { TestApp } from '@baserow/test/helpers/testApp'

describe('Kanban view store', () => {
  let testApp = null
  let store = null
  const view = {
    filters: [],
    filters_disabled: false,
  }

  beforeEach(() => {
    testApp = new TestApp()
    store = testApp.createStore({
      modules: {
        kanban: kanbanStore,
      },
    })
  })

  afterEach(() => {
    testApp.afterEach()
  })

  test('createdNewRow', async () => {
    const stacks = {}
    stacks.null = {
      count: 1,
      results: [{ id: 2, order: '2.00', field_1: null }],
    }
    stacks['1'] = {
      count: 100,
      results: [
        { id: 10, order: '10.00', field_1: { id: 1 } },
        { id: 11, order: '11.00', field_1: { id: 1 } },
      ],
    }

    const state = Object.assign(kanbanStore.state(), {
      singleSelectFieldId: 1,
      stacks,
    })
    store.replaceState({ ...store.state, kanban: state })

    const fields = []
    await store.dispatch('kanban/createdNewRow', {
      view,
      values: {
        id: 1,
        order: '1.00',
        field_1: null,
      },
      fields,
    })
    await store.dispatch('kanban/createdNewRow', {
      view,
      values: {
        id: 3,
        order: '3.00',
        field_1: null,
      },
      fields,
    })

    expect(store.state.kanban.stacks.null.count).toBe(3)
    expect(store.state.kanban.stacks.null.results.length).toBe(3)
    expect(store.state.kanban.stacks.null.results[0].id).toBe(1)
    expect(store.state.kanban.stacks.null.results[1].id).toBe(2)
    expect(store.state.kanban.stacks.null.results[2].id).toBe(3)

    await store.dispatch('kanban/createdNewRow', {
      view,
      values: {
        id: 9,
        order: '9.00',
        field_1: { id: 1 },
      },
      fields,
    })
    await store.dispatch('kanban/createdNewRow', {
      view,
      values: {
        id: 12,
        order: '12.00',
        field_1: { id: 1 },
      },
      fields,
    })

    expect(store.state.kanban.stacks['1'].count).toBe(102)
    expect(store.state.kanban.stacks['1'].results.length).toBe(3)
    expect(store.state.kanban.stacks['1'].results[0].id).toBe(9)
    expect(store.state.kanban.stacks['1'].results[1].id).toBe(10)
    expect(store.state.kanban.stacks['1'].results[2].id).toBe(11)
  })

  test('deletedExistingRow', async () => {
    const stacks = {}
    stacks.null = {
      count: 1,
      results: [{ id: 2, order: '2.00', field_1: null }],
    }
    stacks['1'] = {
      count: 100,
      results: [
        { id: 10, order: '10.00', field_1: { id: 1 } },
        { id: 11, order: '11.00', field_1: { id: 1 } },
      ],
    }

    const state = Object.assign(kanbanStore.state(), {
      singleSelectFieldId: 1,
      stacks,
    })
    store.replaceState({ ...store.state, kanban: state })

    const fields = []

    await store.dispatch('kanban/deletedExistingRow', {
      view,
      row: {
        id: 2,
        order: '2.00',
        field_1: null,
      },
      fields,
    })

    expect(store.state.kanban.stacks.null.count).toBe(0)
    expect(store.state.kanban.stacks.null.results.length).toBe(0)

    await store.dispatch('kanban/deletedExistingRow', {
      view,
      row: {
        id: 50,
        order: '50.00',
        field_1: { id: 1 },
      },
      fields,
    })
    await store.dispatch('kanban/deletedExistingRow', {
      view,
      row: {
        id: 10,
        order: '10.00',
        field_1: { id: 1 },
      },
      fields,
    })

    expect(store.state.kanban.stacks['1'].count).toBe(98)
    expect(store.state.kanban.stacks['1'].results.length).toBe(1)
    expect(store.state.kanban.stacks['1'].results[0].id).toBe(11)
  })

  test('updatedExistingRow', async () => {
    const stacks = {}
    stacks.null = {
      count: 1,
      results: [{ id: 2, order: '2.00', field_1: null }],
    }
    stacks['1'] = {
      count: 100,
      results: [
        { id: 10, order: '10.00', field_1: { id: 1 } },
        {
          id: 11,
          order: '11.00',
          field_1: { id: 1 },
          _: { mustPersist: true },
        },
      ],
    }

    const state = Object.assign(kanbanStore.state(), {
      singleSelectFieldId: 1,
      stacks,
    })
    store.replaceState({ ...store.state, kanban: state })

    const fields = []

    // Should be moved to the first in the buffer
    await store.dispatch('kanban/updatedExistingRow', {
      view,
      row: { id: 11, order: '11.00', field_1: { id: 1 } },
      values: {
        order: '9.00',
      },
      fields,
    })
    // Should be completely ignored because it's outside of the buffer
    await store.dispatch('kanban/updatedExistingRow', {
      view,
      row: { id: 12, order: '12.00', field_1: { id: 1 } },
      values: {
        order: '13.00',
      },
      fields,
    })
    // Did not exist before, but has moved within the buffer.
    await store.dispatch('kanban/updatedExistingRow', {
      view,
      row: { id: 8, order: '13.00', field_1: { id: 1 } },
      values: {
        order: '8.00',
      },
      fields,
    })

    expect(store.state.kanban.stacks['1'].count).toBe(101)
    expect(store.state.kanban.stacks['1'].results.length).toBe(3)
    expect(store.state.kanban.stacks['1'].results[0].id).toBe(8)
    expect(store.state.kanban.stacks['1'].results[1].id).toBe(11)
    expect(store.state.kanban.stacks['1'].results[1]._.mustPersist).toBe(true)
    expect(store.state.kanban.stacks['1'].results[2].id).toBe(10)

    // Moved to stack `null`, because the position is within the buffer, we expect
    // it to be added to it.
    await store.dispatch('kanban/updatedExistingRow', {
      view,
      row: { id: 8, order: '8.00', field_1: { id: 1 } },
      values: {
        field_1: null,
      },
      fields,
    })
    // Moved to stack `null`, because the position is within the buffer, we expect
    // it to be added to it.
    await store.dispatch('kanban/updatedExistingRow', {
      view,
      row: { id: 11, order: '9.00', field_1: { id: 1 } },
      values: {
        field_1: null,
        order: '1.00',
      },
      fields,
    })

    expect(store.state.kanban.stacks.null.count).toBe(3)
    expect(store.state.kanban.stacks.null.results.length).toBe(3)
    expect(store.state.kanban.stacks.null.results[0].id).toBe(11)
    expect(store.state.kanban.stacks.null.results[0]._.mustPersist).toBe(true)
    expect(store.state.kanban.stacks.null.results[1].id).toBe(2)
    expect(store.state.kanban.stacks.null.results[2].id).toBe(8)

    expect(store.state.kanban.stacks['1'].count).toBe(99)
    expect(store.state.kanban.stacks['1'].results.length).toBe(1)
    expect(store.state.kanban.stacks['1'].results[0].id).toBe(10)

    // Moved to stack `1`, because the position is within the buffer, we expect
    // it to be added to it.
    await store.dispatch('kanban/updatedExistingRow', {
      view,
      row: { id: 2, order: '1.00', field_1: null },
      values: {
        field_1: { id: 1 },
      },
      fields,
    })
    // Moved to stack `1`, because the position is outside the buffer, we expect it
    // not to be in there.
    await store.dispatch('kanban/updatedExistingRow', {
      view,
      row: { id: 11, order: '99.00', field_1: null },
      values: {
        field_1: { id: 1 },
      },
      fields,
    })

    expect(store.state.kanban.stacks.null.count).toBe(1)
    expect(store.state.kanban.stacks.null.results.length).toBe(1)
    expect(store.state.kanban.stacks.null.results[0].id).toBe(8)

    expect(store.state.kanban.stacks['1'].count).toBe(100)
    expect(store.state.kanban.stacks['1'].results.length).toBe(2)
    expect(store.state.kanban.stacks['1'].results[0].id).toBe(2)
    expect(store.state.kanban.stacks['1'].results[1].id).toBe(10)
  })
})
