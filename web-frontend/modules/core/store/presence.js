import {
  ANONYMOUS_USER_ID,
  getPresenceColor,
} from '@baserow/modules/core/utils/presenceColors'

export const state = () => ({
  spaces: {},
  editorsActive: {},
})

export const mutations = {
  SET_MEMBERS(state, { space, entries }) {
    const members = {}
    for (const entry of entries) {
      members[entry.presence_id] = {
        user_id: entry.user_id,
        focus: entry.focus || null,
      }
    }
    state.spaces = { ...state.spaces, [space]: { members } }
  },
  ADD_MEMBER(state, { space, presence_id, user_id }) {
    const spaceData = state.spaces[space]
    if (!spaceData) return
    spaceData.members = {
      ...spaceData.members,
      [presence_id]: { user_id, focus: null },
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
    // Focus frames are the presence hot path; mutating in place keeps the
    // space and member identities stable so only consumers of this member's
    // focus re-render (state is deeply reactive in Vuex 4).
    const member = state.spaces[space]?.members[presence_id]
    if (!member) return
    member.focus = focus
  },
  CLEAR_SPACE(state, { space }) {
    const { [space]: _, ...rest } = state.spaces
    state.spaces = rest
    const { [space]: _ea, ...restEa } = state.editorsActive
    state.editorsActive = restEa
  },
  SET_EDITORS_ACTIVE(state, { space, active }) {
    state.editorsActive = { ...state.editorsActive, [space]: active }
  },
  CLEAR_ALL_SPACES(state) {
    state.spaces = {}
    state.editorsActive = {}
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
  handleEditorsActive({ commit }, { space, active }) {
    commit('SET_EDITORS_ACTIVE', { space, active })
  },
  clearAllSpaces({ commit }) {
    commit('CLEAR_ALL_SPACES')
  },
}

// Shared for every no-focus result so consumer prop identity stays stable in
// the common case where nobody focuses anything.
const EMPTY_FOCUS_MAP = new Map()

function _compareFocusEntries(a, b) {
  if (a.user_id !== b.user_id) return a.user_id - b.user_id
  if (a.presence_id < b.presence_id) return -1
  if (a.presence_id > b.presence_id) return 1
  return 0
}

function _buildFocusMap(members, focusType, keyFn) {
  let map = null
  for (const [presence_id, data] of Object.entries(members)) {
    if (!data.focus || data.focus.type !== focusType) continue
    const key = keyFn(data.focus)
    if (map === null) map = new Map()
    if (!map.has(key)) map.set(key, [])
    map.get(key).push({
      presence_id,
      user_id: data.user_id,
      editing: data.focus.editing || false,
      color: getPresenceColor(data.user_id, presence_id),
    })
  }
  if (map === null) return EMPTY_FOCUS_MAP
  for (const entries of map.values()) {
    entries.sort(_compareFocusEntries)
  }
  return map
}

export const getters = {
  getUniqueUsersBySpace: (state) => (spaceName) => {
    const spaceData = state.spaces[spaceName]
    if (!spaceData) return []
    const seen = new Set()
    const authUsers = []
    const anonUsers = []
    for (const [presenceId, data] of Object.entries(spaceData.members)) {
      if (data.user_id === ANONYMOUS_USER_ID) {
        anonUsers.push({ user_id: data.user_id, presence_id: presenceId })
      } else if (!seen.has(data.user_id)) {
        seen.add(data.user_id)
        authUsers.push({ user_id: data.user_id, presence_id: presenceId })
      }
    }
    authUsers.sort((a, b) => a.user_id - b.user_id)
    anonUsers.sort((a, b) => a.presence_id.localeCompare(b.presence_id))
    return [...authUsers, ...anonUsers]
  },
  getFocusEntriesByCell: (state) => (spaceName) => {
    const spaceData = state.spaces[spaceName]
    if (!spaceData) return EMPTY_FOCUS_MAP
    return _buildFocusMap(
      spaceData.members,
      'cell',
      (f) => `${f.row_id}:${f.field_id}`
    )
  },
  getFocusEntriesByRow: (state) => (spaceName) => {
    const spaceData = state.spaces[spaceName]
    if (!spaceData) return EMPTY_FOCUS_MAP
    return _buildFocusMap(spaceData.members, 'row', (f) => f.row_id)
  },
  // Retained for when anonymous focus emission is re-enabled (flip ANONYMOUS_FOCUS_ENABLED in modules/database/utils/presence.js).
  hasAnyActiveEditors: (state) => {
    return Object.values(state.editorsActive).some(Boolean)
  },
}

export default {
  namespaced: true,
  state,
  mutations,
  actions,
  getters,
}
