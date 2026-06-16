import { describe, test, expect } from 'vitest'

import {
  state as makeState,
  mutations,
  actions,
  getters,
} from '@baserow/modules/core/store/presence'

function applyGetter(getter, currentState) {
  const boundGetters = {}
  for (const [key, fn] of Object.entries(getters)) {
    Object.defineProperty(boundGetters, key, {
      get: () => fn(currentState, boundGetters),
    })
  }
  return boundGetters[getter]
}

describe('presence store', () => {
  test('SET_MEMBERS populates members from snapshot data', () => {
    const s = makeState()
    mutations.SET_MEMBERS(s, {
      space: 'table-1',
      entries: [
        { presence_id: 'pid-1', user_id: 10 },
        { presence_id: 'pid-2', user_id: 20 },
      ],
    })

    expect(s.spaces['table-1'].members['pid-1']).toMatchObject({
      user_id: 10,
      focus: null,
    })
    expect(s.spaces['table-1'].members['pid-2']).toMatchObject({
      user_id: 20,
    })
    expect(Object.keys(s.spaces)).toContain('table-1')
  })

  test('ADD_MEMBER adds a new connection', () => {
    const s = makeState()
    mutations.SET_MEMBERS(s, { space: 'table-1', entries: [] })
    mutations.ADD_MEMBER(s, {
      space: 'table-1',
      presence_id: 'pid-3',
      user_id: 30,
    })

    expect(s.spaces['table-1'].members['pid-3']).toMatchObject({
      user_id: 30,
      focus: null,
    })
  })

  test('REMOVE_MEMBER removes a connection', () => {
    const s = makeState()
    mutations.SET_MEMBERS(s, {
      space: 'table-1',
      entries: [{ presence_id: 'pid-1', user_id: 10 }],
    })
    mutations.REMOVE_MEMBER(s, { space: 'table-1', presence_id: 'pid-1' })

    expect(s.spaces['table-1'].members['pid-1']).toBeUndefined()
  })

  test('CLEAR_SPACE removes all data for a space', () => {
    const s = makeState()
    mutations.SET_MEMBERS(s, {
      space: 'table-1',
      entries: [{ presence_id: 'pid-1', user_id: 10 }],
    })
    mutations.CLEAR_SPACE(s, { space: 'table-1' })

    expect(s.spaces['table-1']).toBeUndefined()
    expect(Object.keys(s.spaces)).not.toContain('table-1')
  })

  test('CLEAR_ALL_SPACES removes all spaces', () => {
    const s = makeState()
    mutations.SET_MEMBERS(s, {
      space: 'table-1',
      entries: [{ presence_id: 'pid-1', user_id: 10 }],
    })
    mutations.SET_MEMBERS(s, {
      space: 'table-2',
      entries: [{ presence_id: 'pid-2', user_id: 20 }],
    })
    mutations.CLEAR_ALL_SPACES(s)

    expect(Object.keys(s.spaces)).toHaveLength(0)
  })

  test('getUniqueUsersBySpace deduplicates by user_id', () => {
    const s = makeState()
    mutations.SET_MEMBERS(s, {
      space: 'table-1',
      entries: [
        { presence_id: 'pid-1', user_id: 10 },
        { presence_id: 'pid-2', user_id: 10 },
        { presence_id: 'pid-3', user_id: 20 },
      ],
    })

    const users = applyGetter('getUniqueUsersBySpace', s)('table-1')
    expect(users).toHaveLength(2)
    expect(users.map((u) => u.user_id)).toEqual([10, 20])
  })

  test('unknown space name returns empty array', () => {
    const s = makeState()
    const users = applyGetter('getUniqueUsersBySpace', s)('nonexistent')

    expect(users).toEqual([])
  })

  // -- Focus tests --

  test('SET_FOCUS updates focus for a member', () => {
    const s = makeState()
    mutations.SET_MEMBERS(s, {
      space: 'table-1',
      entries: [{ presence_id: 'pid-1', user_id: 10 }],
    })
    const focus = { type: 'cell', row_id: 1, field_id: 2, editing: false }
    mutations.SET_FOCUS(s, { space: 'table-1', presence_id: 'pid-1', focus })

    expect(s.spaces['table-1'].members['pid-1'].focus).toEqual(focus)
  })

  test('SET_MEMBERS populates focus from payload', () => {
    const s = makeState()
    const focus = { type: 'cell', row_id: 5, field_id: 3, editing: true }
    mutations.SET_MEMBERS(s, {
      space: 'table-1',
      entries: [
        { presence_id: 'pid-1', user_id: 10, focus },
        { presence_id: 'pid-2', user_id: 20 },
      ],
    })

    expect(s.spaces['table-1'].members['pid-1'].focus).toEqual(focus)
    expect(s.spaces['table-1'].members['pid-2'].focus).toBeNull()
  })

  test('handleFocus action commits SET_FOCUS', () => {
    const s = makeState()
    const committed = []
    const commit = (type, payload) => committed.push({ type, payload })
    const focus = { type: 'cell', row_id: 1, field_id: 2, editing: false }
    actions.handleFocus(
      { commit, state: s },
      { space: 'table-1', presence_id: 'pid-1', focus }
    )

    expect(committed[0]).toEqual({
      type: 'SET_FOCUS',
      payload: { space: 'table-1', presence_id: 'pid-1', focus },
    })
  })

  test('getFocusEntriesByCell groups focus by row:field', () => {
    const s = makeState()
    mutations.SET_MEMBERS(s, {
      space: 'table-1',
      entries: [
        { presence_id: 'pid-1', user_id: 10 },
        { presence_id: 'pid-2', user_id: 20 },
      ],
    })
    mutations.SET_FOCUS(s, {
      space: 'table-1',
      presence_id: 'pid-1',
      focus: { type: 'cell', row_id: 1, field_id: 2, editing: false },
    })
    mutations.SET_FOCUS(s, {
      space: 'table-1',
      presence_id: 'pid-2',
      focus: { type: 'cell', row_id: 3, field_id: 4, editing: true },
    })

    const map = applyGetter('getFocusEntriesByCell', s)('table-1')
    expect(map.get('1:2')).toHaveLength(1)
    expect(map.get('1:2')[0].user_id).toBe(10)
    expect(map.get('3:4')).toHaveLength(1)
    expect(map.get('3:4')[0].editing).toBe(true)
  })

  test('getFocusEntriesByRow groups row focus by row_id', () => {
    const s = makeState()
    mutations.SET_MEMBERS(s, {
      space: 'table-1',
      entries: [{ presence_id: 'pid-1', user_id: 10 }],
    })
    mutations.SET_FOCUS(s, {
      space: 'table-1',
      presence_id: 'pid-1',
      focus: { type: 'row', row_id: 5, editing: false },
    })

    const map = applyGetter('getFocusEntriesByRow', s)('table-1')
    expect(map.get(5)).toHaveLength(1)
    expect(map.get(5)[0].user_id).toBe(10)
  })

  test('getFocusEntriesByCell excludes null focus entries', () => {
    const s = makeState()
    mutations.SET_MEMBERS(s, {
      space: 'table-1',
      entries: [
        { presence_id: 'pid-1', user_id: 10 },
        { presence_id: 'pid-2', user_id: 20 },
      ],
    })
    mutations.SET_FOCUS(s, {
      space: 'table-1',
      presence_id: 'pid-1',
      focus: { type: 'cell', row_id: 1, field_id: 2, editing: false },
    })

    const map = applyGetter('getFocusEntriesByCell', s)('table-1')
    expect(map.size).toBe(1)
  })

  test('same-target collapse: multiple users on same cell grouped', () => {
    const s = makeState()
    mutations.SET_MEMBERS(s, {
      space: 'table-1',
      entries: [
        { presence_id: 'pid-1', user_id: 10 },
        { presence_id: 'pid-2', user_id: 20 },
        { presence_id: 'pid-3', user_id: 30 },
      ],
    })
    const focus = { type: 'cell', row_id: 1, field_id: 2, editing: false }
    mutations.SET_FOCUS(s, { space: 'table-1', presence_id: 'pid-1', focus })
    mutations.SET_FOCUS(s, { space: 'table-1', presence_id: 'pid-2', focus })
    mutations.SET_FOCUS(s, { space: 'table-1', presence_id: 'pid-3', focus })

    const map = applyGetter('getFocusEntriesByCell', s)('table-1')
    expect(map.get('1:2')).toHaveLength(3)
  })

  test('getFocusEntriesByCell returns cached result on repeated access', () => {
    const s = makeState()
    mutations.SET_MEMBERS(s, {
      space: 'table-1',
      entries: [{ presence_id: 'pid-1', user_id: 10 }],
    })
    mutations.SET_FOCUS(s, {
      space: 'table-1',
      presence_id: 'pid-1',
      focus: { type: 'cell', row_id: 1, field_id: 2, editing: false },
    })

    const getter = applyGetter('getFocusEntriesByCell', s)
    const first = getter('table-1')
    const second = getter('table-1')
    expect(second).toBe(first)
  })

  test('getFocusEntriesByCell cache invalidates on mutation', () => {
    const s = makeState()
    mutations.SET_MEMBERS(s, {
      space: 'table-1',
      entries: [
        { presence_id: 'pid-1', user_id: 10 },
        { presence_id: 'pid-2', user_id: 20 },
      ],
    })
    mutations.SET_FOCUS(s, {
      space: 'table-1',
      presence_id: 'pid-1',
      focus: { type: 'cell', row_id: 1, field_id: 2, editing: false },
    })

    const first = applyGetter('getFocusEntriesByCell', s)('table-1')

    mutations.SET_FOCUS(s, {
      space: 'table-1',
      presence_id: 'pid-2',
      focus: { type: 'cell', row_id: 3, field_id: 4, editing: false },
    })

    const second = applyGetter('getFocusEntriesByCell', s)('table-1')
    expect(second).not.toBe(first)
    expect(second.size).toBe(2)
  })
})
