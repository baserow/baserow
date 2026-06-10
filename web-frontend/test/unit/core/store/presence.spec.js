import { describe, test, expect } from 'vitest'

import {
  state as makeState,
  mutations,
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

    expect(s.spaces['table-1'].members['pid-1']).toEqual({
      user_id: 10,
    })
    expect(s.spaces['table-1'].members['pid-2']).toEqual({
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

    expect(s.spaces['table-1'].members['pid-3']).toEqual({
      user_id: 30,
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
})
