import gridStore from '@baserow/modules/database/store/view/grid'
import { TestApp } from '@baserow/test/helpers/testApp'
import { createStore } from 'vuex'

const initialState = {
  bufferStartIndex: 9,
  bufferLimit: 10,

  multiSelectActive: false,
  multiSelectHolding: false,
  multiSelectHeadRowIndex: -1,
  multiSelectHeadFieldIndex: -1,
  multiSelectTailRowIndex: -1,
  multiSelectTailFieldIndex: -1,
  multiSelectStartRowIndex: -1,
  multiSelectStartFieldIndex: -1,

  fieldOptions: {
    1: {
      order: 0,
      hidden: false,
    },
    2: {
      order: 1,
      hidden: true,
    },
    3: {
      order: 3,
      hidden: false,
    },
    4: {
      order: 2,
      hidden: false,
    },
  },

  rows: [
    {
      id: 10,
      field_1: '10',
      field_2: 10,
      field_3: true,
      field_4: 'abc',
      order: '10.00',
      _: {},
    },
    {
      id: 11,
      field_1: '11',
      field_2: 11,
      field_3: true,
      field_4: 'def',
      order: '11.00',
      _: {},
    },
    {
      id: 12,
      field_1: '12',
      field_2: 12,
      field_3: false,
      field_4: 'ghi',
      order: '12.00',
      _: {},
    },
    {
      id: 13,
      field_1: '13',
      field_2: 13,
      field_3: false,
      field_4: 'jkl',
      order: '13.00',
      _: {},
    },
    {
      id: 14,
      field_1: '14',
      field_2: 14,
      field_3: true,
      field_4: 'mno',
      order: '14.00',
      _: {},
    },
    {
      id: 15,
      field_1: '15',
      field_2: 15,
      field_3: false,
      field_4: 'pq',
      order: '15.00',
      _: {},
    },
    {
      id: 16,
      field_1: '16',
      field_2: 16,
      field_3: true,
      field_4: 'st',
      order: '16.00',
      _: {},
    },
    {
      id: 17,
      field_1: '17',
      field_2: 17,
      field_3: false,
      field_4: 'uv',
      order: '17.00',
      _: {},
    },
    {
      id: 18,
      field_1: '18',
      field_2: 18,
      field_3: true,
      field_4: 'wxz',
      order: '18.00',
      _: {},
    },
  ],

  count: 100,
}

describe('Grid view multiple select', () => {
  let testApp = null
  let store = null

  beforeEach(() => {
    testApp = new TestApp()
    store = testApp.createStore({
      modules: {
        grid: gridStore,
      },
    })
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  test('multiSelectStart', async () => {
    const state = Object.assign(gridStore.state(), initialState)

    store.replaceState({ ...store.state, grid: state })

    await store.dispatch('grid/multiSelectStart', { rowId: 15, fieldIndex: 1 })

    expect(store.getters['grid/getMultiSelectHeadRowIndex']).toBe(14)
    expect(store.getters['grid/getMultiSelectTailRowIndex']).toBe(14)
    expect(store.getters['grid/getMultiSelectHeadFieldIndex']).toBe(1)
    expect(store.getters['grid/getMultiSelectTailFieldIndex']).toBe(1)
    expect(store.getters['grid/getMultiSelectStartRowIndex']).toBe(14)
    expect(store.getters['grid/getMultiSelectStartFieldIndex']).toBe(1)
    expect(store.getters['grid/isMultiSelectHolding']).toBe(true)
    expect(store.getters['grid/isMultiSelectActive']).toBe(false)
  })

  test('setMultipleSelect', async () => {
    const state = Object.assign(gridStore.state(), initialState)
    state.rows[0]._.selected = true

    store.replaceState({ ...store.state, grid: state })

    await store.dispatch('grid/setMultipleSelect', {
      rowHeadIndex: 14,
      fieldHeadIndex: 1,
      rowTailIndex: 15,
      fieldTailIndex: 2,
    })

    expect(store.getters['grid/getMultiSelectHeadRowIndex']).toBe(14)
    expect(store.getters['grid/getMultiSelectTailRowIndex']).toBe(15)
    expect(store.getters['grid/getMultiSelectHeadFieldIndex']).toBe(1)
    expect(store.getters['grid/getMultiSelectTailFieldIndex']).toBe(2)
    expect(store.getters['grid/getMultiSelectStartRowIndex']).toBe(-1)
    expect(store.getters['grid/getMultiSelectStartFieldIndex']).toBe(-1)
    expect(store.getters['grid/isMultiSelectHolding']).toBe(false)
    expect(store.getters['grid/isMultiSelectActive']).toBe(true)
    expect(state.rows[0]._.selected).toBe(false)
  })

  test('multiSelectHold', async () => {
    const state = Object.assign(gridStore.state(), initialState)

    store.replaceState({ ...store.state, grid: state })

    await store.dispatch('grid/multiSelectHold', { rowId: 15, fieldIndex: 1 })

    // no change as multiSelectHolding is false
    expect(store.getters['grid/getMultiSelectHeadRowIndex']).toBe(-1)
    expect(store.getters['grid/getMultiSelectTailRowIndex']).toBe(-1)
    expect(store.getters['grid/getMultiSelectHeadFieldIndex']).toBe(-1)
    expect(store.getters['grid/getMultiSelectTailFieldIndex']).toBe(-1)
    expect(store.getters['grid/getMultiSelectStartRowIndex']).toBe(-1)
    expect(store.getters['grid/getMultiSelectStartFieldIndex']).toBe(-1)
    expect(store.getters['grid/isMultiSelectHolding']).toBe(false)
    expect(store.getters['grid/isMultiSelectActive']).toBe(false)

    // when holding is true, indexes will be set according to
    // multiSelectStartRowIndex and multiSelectStartFieldIndex
    state.multiSelectHolding = true
    state.multiSelectStartRowIndex = 0
    state.multiSelectStartFieldIndex = 0

    store.replaceState({ ...store.state, grid: state })

    await store.dispatch('grid/multiSelectHold', { rowId: 15, fieldIndex: 1 })

    expect(store.getters['grid/getMultiSelectHeadRowIndex']).toBe(0)
    expect(store.getters['grid/getMultiSelectTailRowIndex']).toBe(14)
    expect(store.getters['grid/getMultiSelectHeadFieldIndex']).toBe(0)
    expect(store.getters['grid/getMultiSelectTailFieldIndex']).toBe(1)
    expect(store.getters['grid/getMultiSelectStartRowIndex']).toBe(0)
    expect(store.getters['grid/getMultiSelectStartFieldIndex']).toBe(0)
    expect(store.getters['grid/isMultiSelectHolding']).toBe(true)
    expect(store.getters['grid/isMultiSelectActive']).toBe(true)
  })

  test('updateMultipleSelectIndexes', async () => {
    const state = Object.assign(gridStore.state(), initialState)

    store.replaceState({ ...store.state, grid: state })

    // invalid values
    await store.dispatch('grid/updateMultipleSelectIndexes', {
      position: 'head',
      rowIndex: -1,
      fieldIndex: 1,
    })
    await store.dispatch('grid/updateMultipleSelectIndexes', {
      position: 'head',
      rowIndex: 14,
      fieldIndex: -1,
    })
    await store.dispatch('grid/updateMultipleSelectIndexes', {
      position: 'head',
      rowIndex: 18,
      fieldIndex: 1,
    })
    await store.dispatch('grid/updateMultipleSelectIndexes', {
      position: 'head',
      rowIndex: 14,
      fieldIndex: 3,
    })

    expect(store.getters['grid/getMultiSelectHeadRowIndex']).toBe(-1)
    expect(store.getters['grid/getMultiSelectTailRowIndex']).toBe(-1)
    expect(store.getters['grid/getMultiSelectHeadFieldIndex']).toBe(-1)
    expect(store.getters['grid/getMultiSelectTailFieldIndex']).toBe(-1)

    await store.dispatch('grid/updateMultipleSelectIndexes', {
      position: 'head',
      rowIndex: 14,
      fieldIndex: 1,
    })

    expect(store.getters['grid/getMultiSelectHeadRowIndex']).toBe(14)
    expect(store.getters['grid/getMultiSelectTailRowIndex']).toBe(-1)
    expect(store.getters['grid/getMultiSelectHeadFieldIndex']).toBe(1)
    expect(store.getters['grid/getMultiSelectTailFieldIndex']).toBe(-1)

    await store.dispatch('grid/updateMultipleSelectIndexes', {
      position: 'tail',
      rowIndex: 15,
      fieldIndex: 2,
    })

    expect(store.getters['grid/getMultiSelectHeadRowIndex']).toBe(14)
    expect(store.getters['grid/getMultiSelectTailRowIndex']).toBe(15)
    expect(store.getters['grid/getMultiSelectHeadFieldIndex']).toBe(1)
    expect(store.getters['grid/getMultiSelectTailFieldIndex']).toBe(2)
  })

  describe('multiSelectShiftChange', () => {
    let state = null

    beforeEach(() => {
      state = Object.assign(gridStore.state(), initialState)
      store.replaceState({ ...store.state, grid: state })
      state.multiSelectActive = true
      state.multiSelectHeadRowIndex = 14
      state.multiSelectHeadFieldIndex = 1
      state.multiSelectTailRowIndex = 15
      state.multiSelectTailFieldIndex = 2
      state.multiSelectStartRowIndex = 14
      state.multiSelectStartFieldIndex = 1
    })

    test('do nothing when starting indexes are not set', async () => {
      state.multiSelectActive = false
      state.multiSelectStartRowIndex = -1
      state.multiSelectStartFieldIndex = 1

      await store.dispatch('grid/multiSelectShiftChange', {
        direction: 'previous',
      })

      state.multiSelectStartRowIndex = 14
      state.multiSelectStartFieldIndex = -1

      await store.dispatch('grid/multiSelectShiftChange', {
        direction: 'previous',
      })

      // no change
      expect(store.getters['grid/getMultiSelectHeadRowIndex']).toBe(14)
      expect(store.getters['grid/getMultiSelectTailRowIndex']).toBe(15)
      expect(store.getters['grid/getMultiSelectHeadFieldIndex']).toBe(1)
      expect(store.getters['grid/getMultiSelectTailFieldIndex']).toBe(2)
      expect(store.getters['grid/isMultiSelectActive']).toBe(false)
    })

    test('activate multiselect if not active', async () => {
      state.multiSelectActive = false
      state.rows[0]._.selected = true
      state.multiSelectHeadRowIndex = -1
      state.multiSelectHeadFieldIndex = -1
      state.multiSelectTailRowIndex = -1
      state.multiSelectTailFieldIndex = -1

      await store.dispatch('grid/multiSelectShiftChange', {
        direction: 'previous',
      })

      expect(store.getters['grid/getMultiSelectHeadRowIndex']).toBe(14)
      expect(store.getters['grid/getMultiSelectTailRowIndex']).toBe(14)
      expect(store.getters['grid/getMultiSelectHeadFieldIndex']).toBe(0)
      expect(store.getters['grid/getMultiSelectTailFieldIndex']).toBe(1)
      expect(store.getters['grid/getMultiSelectStartRowIndex']).toBe(14)
      expect(store.getters['grid/getMultiSelectStartFieldIndex']).toBe(1)
      expect(store.getters['grid/isMultiSelectActive']).toBe(true)
      expect(state.rows[0]._.selected).toBe(false)
    })

    test('update head when moving below', async () => {
      state.multiSelectHeadRowIndex = 14
      state.multiSelectTailRowIndex = 15
      state.multiSelectStartRowIndex = 15

      await store.dispatch('grid/multiSelectShiftChange', {
        direction: 'below',
      })

      expect(store.getters['grid/getMultiSelectHeadRowIndex']).toBe(15)
      expect(store.getters['grid/getMultiSelectTailRowIndex']).toBe(15)
      expect(store.getters['grid/getMultiSelectHeadFieldIndex']).toBe(1)
      expect(store.getters['grid/getMultiSelectTailFieldIndex']).toBe(2)
      expect(store.getters['grid/getMultiSelectStartRowIndex']).toBe(15)
      expect(store.getters['grid/getMultiSelectStartFieldIndex']).toBe(1)
    })

    test('update tail when moving below', async () => {
      state.multiSelectHeadRowIndex = 14
      state.multiSelectTailRowIndex = 15
      state.multiSelectStartRowIndex = 14

      await store.dispatch('grid/multiSelectShiftChange', {
        direction: 'below',
      })

      expect(store.getters['grid/getMultiSelectHeadRowIndex']).toBe(14)
      expect(store.getters['grid/getMultiSelectTailRowIndex']).toBe(16)
      expect(store.getters['grid/getMultiSelectHeadFieldIndex']).toBe(1)
      expect(store.getters['grid/getMultiSelectTailFieldIndex']).toBe(2)
      expect(store.getters['grid/getMultiSelectStartRowIndex']).toBe(14)
      expect(store.getters['grid/getMultiSelectStartFieldIndex']).toBe(1)
    })

    test('update head when moving above', async () => {
      state.multiSelectHeadRowIndex = 14
      state.multiSelectTailRowIndex = 15
      state.multiSelectStartRowIndex = 15

      await store.dispatch('grid/multiSelectShiftChange', {
        direction: 'above',
      })

      expect(store.getters['grid/getMultiSelectHeadRowIndex']).toBe(13)
      expect(store.getters['grid/getMultiSelectTailRowIndex']).toBe(15)
      expect(store.getters['grid/getMultiSelectHeadFieldIndex']).toBe(1)
      expect(store.getters['grid/getMultiSelectTailFieldIndex']).toBe(2)
      expect(store.getters['grid/getMultiSelectStartRowIndex']).toBe(15)
      expect(store.getters['grid/getMultiSelectStartFieldIndex']).toBe(1)
    })

    test('update tail when moving above', async () => {
      state.multiSelectHeadRowIndex = 14
      state.multiSelectTailRowIndex = 15
      state.multiSelectStartRowIndex = 14

      await store.dispatch('grid/multiSelectShiftChange', {
        direction: 'above',
      })

      expect(store.getters['grid/getMultiSelectHeadRowIndex']).toBe(14)
      expect(store.getters['grid/getMultiSelectTailRowIndex']).toBe(14)
      expect(store.getters['grid/getMultiSelectHeadFieldIndex']).toBe(1)
      expect(store.getters['grid/getMultiSelectTailFieldIndex']).toBe(2)
      expect(store.getters['grid/getMultiSelectStartRowIndex']).toBe(14)
      expect(store.getters['grid/getMultiSelectStartFieldIndex']).toBe(1)
    })

    test('update head when moving previous', async () => {
      state.multiSelectHeadFieldIndex = 1
      state.multiSelectTailFieldIndex = 2
      state.multiSelectStartFieldIndex = 2

      await store.dispatch('grid/multiSelectShiftChange', {
        direction: 'previous',
      })

      expect(store.getters['grid/getMultiSelectHeadRowIndex']).toBe(14)
      expect(store.getters['grid/getMultiSelectTailRowIndex']).toBe(15)
      expect(store.getters['grid/getMultiSelectHeadFieldIndex']).toBe(0)
      expect(store.getters['grid/getMultiSelectTailFieldIndex']).toBe(2)
      expect(store.getters['grid/getMultiSelectStartRowIndex']).toBe(14)
      expect(store.getters['grid/getMultiSelectStartFieldIndex']).toBe(2)
    })

    test('update tail when moving previous', async () => {
      state.multiSelectHeadFieldIndex = 0
      state.multiSelectTailFieldIndex = 2
      state.multiSelectStartFieldIndex = 0

      await store.dispatch('grid/multiSelectShiftChange', {
        direction: 'previous',
      })

      expect(store.getters['grid/getMultiSelectHeadRowIndex']).toBe(14)
      expect(store.getters['grid/getMultiSelectTailRowIndex']).toBe(15)
      expect(store.getters['grid/getMultiSelectHeadFieldIndex']).toBe(0)
      expect(store.getters['grid/getMultiSelectTailFieldIndex']).toBe(1)
      expect(store.getters['grid/getMultiSelectStartRowIndex']).toBe(14)
      expect(store.getters['grid/getMultiSelectStartFieldIndex']).toBe(0)
    })

    test('update head when moving next', async () => {
      state.multiSelectHeadFieldIndex = 0
      state.multiSelectTailFieldIndex = 2
      state.multiSelectStartFieldIndex = 2

      await store.dispatch('grid/multiSelectShiftChange', {
        direction: 'next',
      })

      expect(store.getters['grid/getMultiSelectHeadRowIndex']).toBe(14)
      expect(store.getters['grid/getMultiSelectTailRowIndex']).toBe(15)
      expect(store.getters['grid/getMultiSelectHeadFieldIndex']).toBe(1)
      expect(store.getters['grid/getMultiSelectTailFieldIndex']).toBe(2)
      expect(store.getters['grid/getMultiSelectStartRowIndex']).toBe(14)
      expect(store.getters['grid/getMultiSelectStartFieldIndex']).toBe(2)
    })

    test('update tail when moving next', async () => {
      state.multiSelectHeadFieldIndex = 0
      state.multiSelectTailFieldIndex = 1
      state.multiSelectStartFieldIndex = 0

      await store.dispatch('grid/multiSelectShiftChange', {
        direction: 'next',
      })

      expect(store.getters['grid/getMultiSelectHeadRowIndex']).toBe(14)
      expect(store.getters['grid/getMultiSelectTailRowIndex']).toBe(15)
      expect(store.getters['grid/getMultiSelectHeadFieldIndex']).toBe(0)
      expect(store.getters['grid/getMultiSelectTailFieldIndex']).toBe(2)
      expect(store.getters['grid/getMultiSelectStartRowIndex']).toBe(14)
      expect(store.getters['grid/getMultiSelectStartFieldIndex']).toBe(0)
    })
  })

  describe('setMultiSelectHeadOrTail', () => {
    let state = null

    beforeEach(() => {
      state = Object.assign(gridStore.state(), initialState)
      store.replaceState({ ...store.state, grid: state })
      state.multiSelectActive = false
      state.multiSelectHeadRowIndex = 14
      state.multiSelectHeadFieldIndex = 1
      state.multiSelectTailRowIndex = 15
      state.multiSelectTailFieldIndex = 2
      state.multiSelectStartRowIndex = 14
      state.multiSelectStartFieldIndex = 1
    })

    test('top left from start indexes', async () => {
      await store.dispatch('grid/setMultiSelectHeadOrTail', {
        rowId: 12,
        fieldIndex: 0,
      })

      expect(store.getters['grid/getMultiSelectHeadRowIndex']).toBe(11)
      expect(store.getters['grid/getMultiSelectTailRowIndex']).toBe(14)
      expect(store.getters['grid/getMultiSelectHeadFieldIndex']).toBe(0)
      expect(store.getters['grid/getMultiSelectTailFieldIndex']).toBe(1)
      expect(store.getters['grid/getMultiSelectStartRowIndex']).toBe(14)
      expect(store.getters['grid/getMultiSelectStartFieldIndex']).toBe(1)
      expect(store.getters['grid/isMultiSelectHolding']).toBe(false)
      expect(store.getters['grid/isMultiSelectActive']).toBe(true)
    })

    test('top right from start indexes', async () => {
      await store.dispatch('grid/setMultiSelectHeadOrTail', {
        rowId: 12,
        fieldIndex: 2,
      })

      expect(store.getters['grid/getMultiSelectHeadRowIndex']).toBe(11)
      expect(store.getters['grid/getMultiSelectTailRowIndex']).toBe(14)
      expect(store.getters['grid/getMultiSelectHeadFieldIndex']).toBe(1)
      expect(store.getters['grid/getMultiSelectTailFieldIndex']).toBe(2)
      expect(store.getters['grid/getMultiSelectStartRowIndex']).toBe(14)
      expect(store.getters['grid/getMultiSelectStartFieldIndex']).toBe(1)
      expect(store.getters['grid/isMultiSelectHolding']).toBe(false)
      expect(store.getters['grid/isMultiSelectActive']).toBe(true)
    })

    test('bottom left from start indexes', async () => {
      await store.dispatch('grid/setMultiSelectHeadOrTail', {
        rowId: 16,
        fieldIndex: 0,
      })

      expect(store.getters['grid/getMultiSelectHeadRowIndex']).toBe(14)
      expect(store.getters['grid/getMultiSelectTailRowIndex']).toBe(15)
      expect(store.getters['grid/getMultiSelectHeadFieldIndex']).toBe(0)
      expect(store.getters['grid/getMultiSelectTailFieldIndex']).toBe(1)
      expect(store.getters['grid/getMultiSelectStartRowIndex']).toBe(14)
      expect(store.getters['grid/getMultiSelectStartFieldIndex']).toBe(1)
      expect(store.getters['grid/isMultiSelectHolding']).toBe(false)
      expect(store.getters['grid/isMultiSelectActive']).toBe(true)
    })

    test('bottom right from start indexes', async () => {
      await store.dispatch('grid/setMultiSelectHeadOrTail', {
        rowId: 16,
        fieldIndex: 2,
      })

      expect(store.getters['grid/getMultiSelectHeadRowIndex']).toBe(14)
      expect(store.getters['grid/getMultiSelectTailRowIndex']).toBe(15)
      expect(store.getters['grid/getMultiSelectHeadFieldIndex']).toBe(1)
      expect(store.getters['grid/getMultiSelectTailFieldIndex']).toBe(2)
      expect(store.getters['grid/getMultiSelectStartRowIndex']).toBe(14)
      expect(store.getters['grid/getMultiSelectStartFieldIndex']).toBe(1)
      expect(store.getters['grid/isMultiSelectHolding']).toBe(false)
      expect(store.getters['grid/isMultiSelectActive']).toBe(true)
    })
  })

  describe('setSelectedCellCancelledMultiSelect', () => {
    let state = null

    beforeEach(() => {
      state = Object.assign(gridStore.state(), initialState)
      store.replaceState({ ...store.state, grid: state })
    })

    test('previous direction', async () => {
      const fields = []
      state.multiSelectActive = false
      state.multiSelectHeadRowIndex = 14
      state.multiSelectHeadFieldIndex = 1
      state.multiSelectTailRowIndex = 15
      state.multiSelectTailFieldIndex = 2
      state.multiSelectStartRowIndex = 14
      state.multiSelectStartFieldIndex = 1

      await store.dispatch('grid/setSelectedCellCancelledMultiSelect', {
        direction: 'previous',
        fields,
      })

      expect(store.getters['grid/getMultiSelectHeadRowIndex']).toBe(-1)
      expect(store.getters['grid/getMultiSelectTailRowIndex']).toBe(-1)
      expect(store.getters['grid/getMultiSelectHeadFieldIndex']).toBe(-1)
      expect(store.getters['grid/getMultiSelectTailFieldIndex']).toBe(-1)
      expect(store.getters['grid/getMultiSelectStartRowIndex']).toBe(14)
      expect(store.getters['grid/getMultiSelectStartFieldIndex']).toBe(0)
      expect(store.getters['grid/isMultiSelectHolding']).toBe(false)
      expect(store.getters['grid/isMultiSelectActive']).toBe(false)
      expect(state.rows[5]._.selected).toBe(true)
      expect(state.rows[5]._.selectedFieldId).toBe(1)
    })

    test('next direction', async () => {
      const fields = []
      state.multiSelectActive = false
      state.multiSelectHeadRowIndex = 14
      state.multiSelectHeadFieldIndex = 1
      state.multiSelectTailRowIndex = 15
      state.multiSelectTailFieldIndex = 2
      state.multiSelectStartRowIndex = 14
      state.multiSelectStartFieldIndex = 1

      await store.dispatch('grid/setSelectedCellCancelledMultiSelect', {
        direction: 'next',
        fields,
      })

      expect(store.getters['grid/getMultiSelectHeadRowIndex']).toBe(-1)
      expect(store.getters['grid/getMultiSelectTailRowIndex']).toBe(-1)
      expect(store.getters['grid/getMultiSelectHeadFieldIndex']).toBe(-1)
      expect(store.getters['grid/getMultiSelectTailFieldIndex']).toBe(-1)
      expect(store.getters['grid/getMultiSelectStartRowIndex']).toBe(14)
      expect(store.getters['grid/getMultiSelectStartFieldIndex']).toBe(2)
      expect(store.getters['grid/isMultiSelectHolding']).toBe(false)
      expect(store.getters['grid/isMultiSelectActive']).toBe(false)
      expect(state.rows[5]._.selected).toBe(true)
      expect(state.rows[5]._.selectedFieldId).toBe(3)
    })

    test('above direction', async () => {
      const fields = []
      state.multiSelectActive = false
      state.multiSelectHeadRowIndex = 14
      state.multiSelectHeadFieldIndex = 1
      state.multiSelectTailRowIndex = 15
      state.multiSelectTailFieldIndex = 2
      state.multiSelectStartRowIndex = 14
      state.multiSelectStartFieldIndex = 1

      await store.dispatch('grid/setSelectedCellCancelledMultiSelect', {
        direction: 'above',
        fields,
      })

      expect(store.getters['grid/getMultiSelectHeadRowIndex']).toBe(-1)
      expect(store.getters['grid/getMultiSelectTailRowIndex']).toBe(-1)
      expect(store.getters['grid/getMultiSelectHeadFieldIndex']).toBe(-1)
      expect(store.getters['grid/getMultiSelectTailFieldIndex']).toBe(-1)
      expect(store.getters['grid/getMultiSelectStartRowIndex']).toBe(13)
      expect(store.getters['grid/getMultiSelectStartFieldIndex']).toBe(1)
      expect(store.getters['grid/isMultiSelectHolding']).toBe(false)
      expect(store.getters['grid/isMultiSelectActive']).toBe(false)
      expect(state.rows[4]._.selected).toBe(true)
      expect(state.rows[4]._.selectedFieldId).toBe(4)
    })

    test('below direction', async () => {
      const fields = []
      state.multiSelectActive = false
      state.multiSelectHeadRowIndex = 14
      state.multiSelectHeadFieldIndex = 1
      state.multiSelectTailRowIndex = 15
      state.multiSelectTailFieldIndex = 2
      state.multiSelectStartRowIndex = 14
      state.multiSelectStartFieldIndex = 1

      await store.dispatch('grid/setSelectedCellCancelledMultiSelect', {
        direction: 'below',
        fields,
      })

      expect(store.getters['grid/getMultiSelectHeadRowIndex']).toBe(-1)
      expect(store.getters['grid/getMultiSelectTailRowIndex']).toBe(-1)
      expect(store.getters['grid/getMultiSelectHeadFieldIndex']).toBe(-1)
      expect(store.getters['grid/getMultiSelectTailFieldIndex']).toBe(-1)
      expect(store.getters['grid/getMultiSelectStartRowIndex']).toBe(15)
      expect(store.getters['grid/getMultiSelectStartFieldIndex']).toBe(1)
      expect(store.getters['grid/isMultiSelectHolding']).toBe(false)
      expect(store.getters['grid/isMultiSelectActive']).toBe(false)
      expect(state.rows[6]._.selected).toBe(true)
      expect(state.rows[6]._.selectedFieldId).toBe(4)
    })

    test('previous direction at the edge', async () => {
      const fields = []
      state.multiSelectActive = false
      state.multiSelectHeadRowIndex = 14
      state.multiSelectHeadFieldIndex = 0
      state.multiSelectTailRowIndex = 15
      state.multiSelectTailFieldIndex = 2
      state.multiSelectStartRowIndex = 14
      state.multiSelectStartFieldIndex = 0

      await store.dispatch('grid/setSelectedCellCancelledMultiSelect', {
        direction: 'previous',
        fields,
      })

      expect(store.getters['grid/getMultiSelectHeadRowIndex']).toBe(-1)
      expect(store.getters['grid/getMultiSelectTailRowIndex']).toBe(-1)
      expect(store.getters['grid/getMultiSelectHeadFieldIndex']).toBe(-1)
      expect(store.getters['grid/getMultiSelectTailFieldIndex']).toBe(-1)
      expect(store.getters['grid/getMultiSelectStartRowIndex']).toBe(14)
      expect(store.getters['grid/getMultiSelectStartFieldIndex']).toBe(0)
      expect(store.getters['grid/isMultiSelectHolding']).toBe(false)
      expect(store.getters['grid/isMultiSelectActive']).toBe(false)
      expect(state.rows[5]._.selected).toBe(true)
      expect(state.rows[5]._.selectedFieldId).toBe(1)
    })

    test('next direction at the edge', async () => {
      const fields = []
      state.multiSelectActive = false
      state.multiSelectHeadRowIndex = 14
      state.multiSelectHeadFieldIndex = 2
      state.multiSelectTailRowIndex = 15
      state.multiSelectTailFieldIndex = 2
      state.multiSelectStartRowIndex = 14
      state.multiSelectStartFieldIndex = 2

      await store.dispatch('grid/setSelectedCellCancelledMultiSelect', {
        direction: 'next',
        fields,
      })

      expect(store.getters['grid/getMultiSelectHeadRowIndex']).toBe(-1)
      expect(store.getters['grid/getMultiSelectTailRowIndex']).toBe(-1)
      expect(store.getters['grid/getMultiSelectHeadFieldIndex']).toBe(-1)
      expect(store.getters['grid/getMultiSelectTailFieldIndex']).toBe(-1)
      expect(store.getters['grid/getMultiSelectStartRowIndex']).toBe(14)
      expect(store.getters['grid/getMultiSelectStartFieldIndex']).toBe(2)
      expect(store.getters['grid/isMultiSelectHolding']).toBe(false)
      expect(store.getters['grid/isMultiSelectActive']).toBe(false)
      expect(state.rows[5]._.selected).toBe(true)
      expect(state.rows[5]._.selectedFieldId).toBe(3)
    })

    test('above direction at the edge', async () => {
      const fields = []
      state.multiSelectActive = false
      state.multiSelectHeadRowIndex = 9
      state.multiSelectHeadFieldIndex = 1
      state.multiSelectTailRowIndex = 15
      state.multiSelectTailFieldIndex = 2
      state.multiSelectStartRowIndex = 9
      state.multiSelectStartFieldIndex = 1

      await store.dispatch('grid/setSelectedCellCancelledMultiSelect', {
        direction: 'above',
        fields,
      })

      expect(store.getters['grid/getMultiSelectHeadRowIndex']).toBe(-1)
      expect(store.getters['grid/getMultiSelectTailRowIndex']).toBe(-1)
      expect(store.getters['grid/getMultiSelectHeadFieldIndex']).toBe(-1)
      expect(store.getters['grid/getMultiSelectTailFieldIndex']).toBe(-1)
      expect(store.getters['grid/getMultiSelectStartRowIndex']).toBe(9)
      expect(store.getters['grid/getMultiSelectStartFieldIndex']).toBe(1)
      expect(store.getters['grid/isMultiSelectHolding']).toBe(false)
      expect(store.getters['grid/isMultiSelectActive']).toBe(false)
      expect(state.rows[0]._.selected).toBe(true)
      expect(state.rows[0]._.selectedFieldId).toBe(4)
    })

    test('below direction at the edge', async () => {
      const fields = []
      state.multiSelectActive = false
      state.multiSelectHeadRowIndex = 17
      state.multiSelectHeadFieldIndex = 1
      state.multiSelectTailRowIndex = 17
      state.multiSelectTailFieldIndex = 2
      state.multiSelectStartRowIndex = 17
      state.multiSelectStartFieldIndex = 1

      await store.dispatch('grid/setSelectedCellCancelledMultiSelect', {
        direction: 'below',
        fields,
      })

      expect(store.getters['grid/getMultiSelectHeadRowIndex']).toBe(-1)
      expect(store.getters['grid/getMultiSelectTailRowIndex']).toBe(-1)
      expect(store.getters['grid/getMultiSelectHeadFieldIndex']).toBe(-1)
      expect(store.getters['grid/getMultiSelectTailFieldIndex']).toBe(-1)
      expect(store.getters['grid/getMultiSelectStartRowIndex']).toBe(17)
      expect(store.getters['grid/getMultiSelectStartFieldIndex']).toBe(1)
      expect(store.getters['grid/isMultiSelectHolding']).toBe(false)
      expect(store.getters['grid/isMultiSelectActive']).toBe(false)
      expect(state.rows[8]._.selected).toBe(true)
      expect(state.rows[8]._.selectedFieldId).toBe(4)
    })
  })

  describe('correctMultiSelect', () => {
    let state = null

    beforeEach(() => {
      state = Object.assign(gridStore.state(), initialState)
      store.replaceState({ ...store.state, grid: state })
    })

    test('reset when head is out of grid', async () => {
      state.multiSelectActive = true
      state.multiSelectHeadRowIndex = 100
      state.multiSelectHeadFieldIndex = 100
      state.multiSelectTailRowIndex = 101
      state.multiSelectTailFieldIndex = 101
      state.multiSelectStartRowIndex = 100
      state.multiSelectStartFieldIndex = 100

      await store.dispatch('grid/correctMultiSelect')

      expect(store.getters['grid/getMultiSelectHeadRowIndex']).toBe(-1)
      expect(store.getters['grid/getMultiSelectTailRowIndex']).toBe(-1)
      expect(store.getters['grid/getMultiSelectHeadFieldIndex']).toBe(-1)
      expect(store.getters['grid/getMultiSelectTailFieldIndex']).toBe(-1)
      expect(store.getters['grid/getMultiSelectStartRowIndex']).toBe(-1)
      expect(store.getters['grid/getMultiSelectStartFieldIndex']).toBe(-1)
    })

    test('correct tail and start when they are out of grid', async () => {
      state.multiSelectActive = true
      state.multiSelectHeadRowIndex = 1
      state.multiSelectHeadFieldIndex = 1
      state.multiSelectTailRowIndex = 101
      state.multiSelectTailFieldIndex = 101
      state.multiSelectStartRowIndex = 101
      state.multiSelectStartFieldIndex = 101

      await store.dispatch('grid/correctMultiSelect')

      expect(store.getters['grid/getMultiSelectHeadRowIndex']).toBe(1)
      expect(store.getters['grid/getMultiSelectTailRowIndex']).toBe(17)
      expect(store.getters['grid/getMultiSelectHeadFieldIndex']).toBe(1)
      expect(store.getters['grid/getMultiSelectTailFieldIndex']).toBe(2)
      expect(store.getters['grid/getMultiSelectStartRowIndex']).toBe(17)
      expect(store.getters['grid/getMultiSelectStartFieldIndex']).toBe(2)
    })
  })
})
