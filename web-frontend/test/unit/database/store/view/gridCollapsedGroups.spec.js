import gridStore from '@baserow/modules/database/store/view/grid'
import { TestApp } from '@baserow/test/helpers/testApp'

describe('grid store collapsed groups', () => {
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

  test('initial collapsedGroups state is empty object', () => {
    expect(store.state.grid.collapsedGroups).toEqual({})
  })

  test('SET_COLLAPSED_GROUPS sets groups for a view', () => {
    const groups = [{ field_1: 'A' }]

    store.commit('grid/SET_COLLAPSED_GROUPS', { viewId: 42, groups })

    expect(store.state.grid.collapsedGroups).toEqual({ 42: groups })
  })

  test('TOGGLE_GROUP_COLLAPSED adds a group when not present', () => {
    store.commit('grid/TOGGLE_GROUP_COLLAPSED', {
      viewId: 42,
      groupValues: { field_1: 'A' },
    })

    expect(store.state.grid.collapsedGroups[42]).toEqual([{ field_1: 'A' }])
  })

  test('TOGGLE_GROUP_COLLAPSED removes a group when already present', () => {
    store.commit('grid/SET_COLLAPSED_GROUPS', {
      viewId: 42,
      groups: [{ field_1: 'A' }, { field_1: 'B' }],
    })

    store.commit('grid/TOGGLE_GROUP_COLLAPSED', {
      viewId: 42,
      groupValues: { field_1: 'A' },
    })

    expect(store.state.grid.collapsedGroups[42]).toEqual([{ field_1: 'B' }])
  })

  test('CLEAR_COLLAPSED_GROUPS clears all groups for a view', () => {
    store.commit('grid/SET_COLLAPSED_GROUPS', {
      viewId: 42,
      groups: [{ field_1: 'A' }],
    })

    store.commit('grid/CLEAR_COLLAPSED_GROUPS', { viewId: 42 })

    expect(store.state.grid.collapsedGroups[42]).toEqual([])
  })

  test('getCollapsedGroupsForView returns groups for a view', () => {
    store.commit('grid/SET_COLLAPSED_GROUPS', {
      viewId: 42,
      groups: [{ field_1: 'A' }],
    })

    expect(store.getters['grid/getCollapsedGroupsForView'](42)).toEqual([
      { field_1: 'A' },
    ])
  })

  test('getCollapsedGroupsForView returns empty array for unknown view', () => {
    expect(store.getters['grid/getCollapsedGroupsForView'](999)).toEqual([])
  })
})
