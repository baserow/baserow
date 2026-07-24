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

  test('SET_FOCUS mutates in place preserving object identities', () => {
    const s = makeState()
    mutations.SET_MEMBERS(s, {
      space: 'table-1',
      entries: [{ presence_id: 'pid-1', user_id: 10 }],
    })
    mutations.SET_MEMBERS(s, {
      space: 'table-2',
      entries: [{ presence_id: 'pid-9', user_id: 90 }],
    })
    const spacesBefore = s.spaces
    const spaceBefore = s.spaces['table-1']
    const membersBefore = s.spaces['table-1'].members
    const unrelatedSpaceBefore = s.spaces['table-2']

    mutations.SET_FOCUS(s, {
      space: 'table-1',
      presence_id: 'pid-1',
      focus: { type: 'cell', row_id: 1, field_id: 2, editing: false },
    })

    expect(s.spaces).toBe(spacesBefore)
    expect(s.spaces['table-1']).toBe(spaceBefore)
    expect(s.spaces['table-1'].members).toBe(membersBefore)
    expect(s.spaces['table-2']).toBe(unrelatedSpaceBefore)

    const map = applyGetter('getFocusEntriesByCell', s)('table-1')
    expect(map.get('1:2')).toHaveLength(1)
  })

  test('SET_FOCUS is a no-op for unknown space or member', () => {
    const s = makeState()
    mutations.SET_MEMBERS(s, {
      space: 'table-1',
      entries: [{ presence_id: 'pid-1', user_id: 10 }],
    })
    const focus = { type: 'cell', row_id: 1, field_id: 2, editing: false }
    mutations.SET_FOCUS(s, {
      space: 'nonexistent',
      presence_id: 'pid-1',
      focus,
    })
    mutations.SET_FOCUS(s, { space: 'table-1', presence_id: 'unknown', focus })

    expect(s.spaces['table-1'].members['pid-1'].focus).toBeNull()
  })

  test('empty focus map identity is stable across unrelated updates', () => {
    const s = makeState()
    mutations.SET_MEMBERS(s, {
      space: 'table-1',
      entries: [{ presence_id: 'pid-1', user_id: 10 }],
    })
    mutations.SET_MEMBERS(s, {
      space: 'table-2',
      entries: [{ presence_id: 'pid-2', user_id: 20 }],
    })

    const first = applyGetter('getFocusEntriesByCell', s)('table-1')
    expect(first.size).toBe(0)

    mutations.SET_FOCUS(s, {
      space: 'table-2',
      presence_id: 'pid-2',
      focus: { type: 'cell', row_id: 3, field_id: 4, editing: false },
    })

    const second = applyGetter('getFocusEntriesByCell', s)('table-1')
    expect(second).toBe(first)
    expect(applyGetter('getFocusEntriesByCell', s)('nonexistent')).toBe(first)
  })

  test('focus entries are sorted by user_id ascending', () => {
    const s = makeState()
    mutations.SET_MEMBERS(s, {
      space: 'table-1',
      entries: [
        { presence_id: 'pid-b', user_id: 30 },
        { presence_id: 'pid-a', user_id: 10 },
        { presence_id: 'pid-c', user_id: 20 },
      ],
    })
    const focus = { type: 'cell', row_id: 1, field_id: 2, editing: false }
    for (const pid of ['pid-b', 'pid-a', 'pid-c']) {
      mutations.SET_FOCUS(s, { space: 'table-1', presence_id: pid, focus })
    }

    const entries = applyGetter(
      'getFocusEntriesByCell',
      s
    )('table-1').get('1:2')
    expect(entries.map((e) => e.user_id)).toEqual([10, 20, 30])
  })

  test('same user_id ties break on presence_id string compare', () => {
    const s = makeState()
    mutations.SET_MEMBERS(s, {
      space: 'table-1',
      entries: [
        { presence_id: 'pid-z', user_id: 10 },
        { presence_id: 'pid-a', user_id: 10 },
      ],
    })
    const focus = { type: 'row', row_id: 5, editing: false }
    mutations.SET_FOCUS(s, { space: 'table-1', presence_id: 'pid-z', focus })
    mutations.SET_FOCUS(s, { space: 'table-1', presence_id: 'pid-a', focus })

    const entries = applyGetter('getFocusEntriesByRow', s)('table-1').get(5)
    expect(entries.map((e) => e.presence_id)).toEqual(['pid-a', 'pid-z'])
  })

  test('SET_EDITORS_ACTIVE tracks active editors per space', () => {
    const s = makeState()
    mutations.SET_EDITORS_ACTIVE(s, { space: 'table-1', active: true })

    expect(s.editorsActive['table-1']).toBe(true)

    mutations.SET_EDITORS_ACTIVE(s, { space: 'table-1', active: false })
    expect(s.editorsActive['table-1']).toBe(false)
  })

  test('CLEAR_SPACE also clears editorsActive for that space', () => {
    const s = makeState()
    mutations.SET_MEMBERS(s, {
      space: 'table-1',
      entries: [{ presence_id: 'pid-1', user_id: 10 }],
    })
    mutations.SET_EDITORS_ACTIVE(s, { space: 'table-1', active: true })
    mutations.SET_EDITORS_ACTIVE(s, { space: 'table-2', active: true })
    mutations.CLEAR_SPACE(s, { space: 'table-1' })

    expect(s.editorsActive['table-1']).toBeUndefined()
    expect(s.editorsActive['table-2']).toBe(true)
  })

  test('CLEAR_ALL_SPACES clears editorsActive', () => {
    const s = makeState()
    mutations.SET_EDITORS_ACTIVE(s, { space: 'table-1', active: true })
    mutations.CLEAR_ALL_SPACES(s)

    expect(Object.keys(s.editorsActive)).toHaveLength(0)
  })

  test('hasAnyActiveEditors returns true when any space has active editors', () => {
    const s = makeState()
    expect(applyGetter('hasAnyActiveEditors', s)).toBe(false)

    mutations.SET_EDITORS_ACTIVE(s, { space: 'table-1', active: false })
    expect(applyGetter('hasAnyActiveEditors', s)).toBe(false)

    mutations.SET_EDITORS_ACTIVE(s, { space: 'table-2', active: true })
    expect(applyGetter('hasAnyActiveEditors', s)).toBe(true)
  })

  test('getUniqueUsersBySpace lists anonymous entries individually', () => {
    const s = makeState()
    mutations.SET_MEMBERS(s, {
      space: 'table-1',
      entries: [
        { presence_id: 'pid-1', user_id: 10 },
        { presence_id: 'anon-1', user_id: -1 },
        { presence_id: 'anon-2', user_id: -1 },
      ],
    })

    const users = applyGetter('getUniqueUsersBySpace', s)('table-1')
    expect(users).toHaveLength(3)
    expect(users[0].user_id).toBe(10)
    expect(users[1].user_id).toBe(-1)
    expect(users[2].user_id).toBe(-1)
    expect(users[1].presence_id).not.toBe(users[2].presence_id)
  })

  test('ordering stays deterministic when members join, leave and join again', () => {
    const s = makeState()
    mutations.SET_MEMBERS(s, {
      space: 'table-1',
      entries: [
        { presence_id: 'pid-1', user_id: 10 },
        { presence_id: 'pid-2', user_id: 20 },
      ],
    })
    mutations.REMOVE_MEMBER(s, { space: 'table-1', presence_id: 'pid-1' })
    mutations.ADD_MEMBER(s, {
      space: 'table-1',
      presence_id: 'pid-3',
      user_id: 5,
    })
    const focus = { type: 'cell', row_id: 1, field_id: 2, editing: false }
    mutations.SET_FOCUS(s, { space: 'table-1', presence_id: 'pid-2', focus })
    mutations.SET_FOCUS(s, { space: 'table-1', presence_id: 'pid-3', focus })

    const entries = applyGetter(
      'getFocusEntriesByCell',
      s
    )('table-1').get('1:2')
    expect(entries.map((e) => e.user_id)).toEqual([5, 20])
  })
})
