import { getPresenceUserColor } from '@baserow/modules/core/utils/presenceColors'

export const state = () => ({
  spaces: {},
})

export const mutations = {
  SET_MEMBERS(state, { space, entries }) {
    const members = {}
    for (let i = 0; i < entries.length; i++) {
      const entry = entries[i]
      members[entry.presence_id] = {
        user_id: entry.user_id,
        focus: entry.focus || null,
        order: i,
      }
    }
    state.spaces = { ...state.spaces, [space]: { members } }
  },
  ADD_MEMBER(state, { space, presence_id, user_id }) {
    const spaceData = state.spaces[space]
    if (!spaceData) return
    const order = Object.keys(spaceData.members).length
    spaceData.members = {
      ...spaceData.members,
      [presence_id]: { user_id, focus: null, order },
    }
    state.spaces = { ...state.spaces }
  },
  REMOVE_MEMBER(state, { space, presence_id }) {
    const spaceData = state.spaces[space]
    if (!spaceData) return
    const { [presence_id]: _, ...rest } = spaceData.members
    state.spaces = {
      ...state.spaces,
      [space]: { members: rest },
    }
  },
  SET_FOCUS(state, { space, presence_id, focus }) {
    const spaceData = state.spaces[space]
    if (!spaceData) return
    const member = spaceData.members[presence_id]
    if (!member) return
    spaceData.members = {
      ...spaceData.members,
      [presence_id]: { ...member, focus },
    }
    state.spaces = { ...state.spaces }
  },
  CLEAR_SPACE(state, { space }) {
    const { [space]: _, ...rest } = state.spaces
    state.spaces = rest
  },
  CLEAR_ALL_SPACES(state) {
    state.spaces = {}
  },
}

export const actions = {
  handleMembers({ commit }, { space, entries }) {
    commit('SET_MEMBERS', { space, entries })
  },
  handleJoin({ commit }, { space, presence_id, user_id }) {
    commit('ADD_MEMBER', { space, presence_id, user_id })
  },
  handleLeave({ commit }, { space, presence_id }) {
    commit('REMOVE_MEMBER', { space, presence_id })
  },
  handleFocus({ commit }, { space, presence_id, focus }) {
    commit('SET_FOCUS', { space, presence_id, focus })
  },
  clearSpace({ commit }, { space }) {
    commit('CLEAR_SPACE', { space })
  },
  clearAllSpaces({ commit }) {
    commit('CLEAR_ALL_SPACES')
  },
}

const _cellFocusCache = new WeakMap()
const _rowFocusCache = new WeakMap()

function _buildFocusMap(members, focusType, keyFn, cache) {
  const cached = cache.get(members)
  if (cached) return cached
  const map = new Map()
  for (const [presence_id, data] of Object.entries(members)) {
    if (!data.focus || data.focus.type !== focusType) continue
    const key = keyFn(data.focus)
    if (!map.has(key)) map.set(key, [])
    map.get(key).push({
      presence_id,
      user_id: data.user_id,
      editing: data.focus.editing || false,
      color: getPresenceUserColor(data.user_id),
      order: data.order,
    })
  }
  for (const entries of map.values()) {
    entries.sort((a, b) => a.order - b.order)
  }
  cache.set(members, map)
  return map
}

export const getters = {
  getUniqueUsersBySpace: (state) => (spaceName) => {
    const spaceData = state.spaces[spaceName]
    if (!spaceData) return []
    const seen = new Set()
    const users = []
    for (const [, data] of Object.entries(spaceData.members)) {
      if (!seen.has(data.user_id)) {
        seen.add(data.user_id)
        users.push({ user_id: data.user_id })
      }
    }
    return users.sort((a, b) => a.user_id - b.user_id)
  },
  getFocusEntriesByCell: (state) => (spaceName) => {
    const spaceData = state.spaces[spaceName]
    if (!spaceData) return new Map()
    return _buildFocusMap(
      spaceData.members,
      'cell',
      (f) => `${f.row_id}:${f.field_id}`,
      _cellFocusCache
    )
  },
  getFocusEntriesByRow: (state) => (spaceName) => {
    const spaceData = state.spaces[spaceName]
    if (!spaceData) return new Map()
    return _buildFocusMap(
      spaceData.members,
      'row',
      (f) => f.row_id,
      _rowFocusCache
    )
  },
}

export default {
  namespaced: true,
  state,
  mutations,
  actions,
  getters,
}
