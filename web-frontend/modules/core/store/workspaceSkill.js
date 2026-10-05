import WorkspaceSkillService from '@baserow/modules/core/services/workspaceSkill'

const upsert = (state, skill) => {
  const index = state.items.findIndex((item) => item.id === skill.id)
  if (index === -1) {
    state.items.push(skill)
  } else {
    state.items.splice(index, 1, skill)
  }
}

export const state = () => ({
  items: [],
  // Workspace ids whose skills were fetched, so pickers can lazily load.
  loadedWorkspaceIds: [],
})

export const mutations = {
  SET_WORKSPACE_ITEMS(state, { workspaceId, skills }) {
    state.items = state.items
      .filter((item) => item.workspace_id !== workspaceId)
      .concat(skills)
    if (!state.loadedWorkspaceIds.includes(workspaceId)) {
      state.loadedWorkspaceIds.push(workspaceId)
    }
  },
  UPSERT_ITEM(state, skill) {
    upsert(state, skill)
  },
  DELETE_ITEM(state, skillId) {
    const index = state.items.findIndex((item) => item.id === skillId)
    if (index !== -1) {
      state.items.splice(index, 1)
    }
  },
}

export const actions = {
  async fetchAll({ commit }, { workspaceId }) {
    const { data } = await WorkspaceSkillService(this.$client).list(workspaceId)
    commit('SET_WORKSPACE_ITEMS', { workspaceId, skills: data })
    return data
  },
  async create({ dispatch }, { workspaceId, values }) {
    const { data } = await WorkspaceSkillService(this.$client).create(
      workspaceId,
      values
    )
    return dispatch('forceCreate', data)
  },
  forceCreate({ commit }, skill) {
    commit('UPSERT_ITEM', skill)
    return skill
  },
  async update({ dispatch }, { skillId, values }) {
    const { data } = await WorkspaceSkillService(this.$client).update(
      skillId,
      values
    )
    return dispatch('forceUpdate', data)
  },
  forceUpdate({ commit }, skill) {
    commit('UPSERT_ITEM', skill)
    return skill
  },
  async delete({ dispatch }, skill) {
    await WorkspaceSkillService(this.$client).delete(skill.id)
    dispatch('forceDelete', skill.id)
  },
  forceDelete({ commit }, skillId) {
    commit('DELETE_ITEM', skillId)
  },
}

export const getters = {
  get: (state) => (skillId) => state.items.find((item) => item.id === skillId),
  getAllInWorkspace: (state) => (workspaceId) =>
    state.items
      .filter((item) => item.workspace_id === workspaceId)
      .sort((a, b) => a.name.localeCompare(b.name)),
  isLoaded: (state) => (workspaceId) =>
    state.loadedWorkspaceIds.includes(workspaceId),
}

export default { namespaced: true, state, mutations, actions, getters }
