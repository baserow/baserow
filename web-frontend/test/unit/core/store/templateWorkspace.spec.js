import { describe, test, expect, vi } from 'vitest'

import {
  state as makeState,
  mutations,
  actions,
  getters,
} from '@baserow/modules/core/store/templateWorkspace'

describe('templateWorkspace store', () => {
  test('ADD registers a workspace id once', () => {
    const s = makeState()
    mutations.ADD(s, 1)
    mutations.ADD(s, 2)
    mutations.ADD(s, 1)
    expect(s.ids).toEqual([1, 2])
  })

  test('register commits ADD', () => {
    const commit = vi.fn()
    actions.register({ commit }, 3)
    expect(commit).toHaveBeenCalledWith('ADD', 3)
  })

  test('isTemplateWorkspace only matches registered ids', () => {
    const s = makeState()
    mutations.ADD(s, 5)
    expect(getters.isTemplateWorkspace(s)(5)).toBe(true)
    expect(getters.isTemplateWorkspace(s)(6)).toBe(false)
  })
})
