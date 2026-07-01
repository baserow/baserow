export const state = () => ({
  spaces: {},
})

export const mutations = {
  SET_MEMBERS(state, { space, entries }) {
    const members = {}
    for (const entry of entries) {
      members[entry.presence_id] = {
        user_id: entry.user_id,
      }
    }
    state.spaces = { ...state.spaces, [space]: { members } }
  },
  ADD_MEMBER(state, { space, presence_id, user_id }) {
    const spaceData = state.spaces[space]
    if (!spaceData) return
    state.spaces = {
      ...state.spaces,
      [space]: {
        members: { ...spaceData.members, [presence_id]: { user_id } },
      },
    }
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
  clearSpace({ commit }, { space }) {
    commit('CLEAR_SPACE', { space })
  },
  clearAllSpaces({ commit }) {
    commit('CLEAR_ALL_SPACES')
  },
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
}

export default {
  namespaced: true,
  state,
  mutations,
  actions,
  getters,
}
