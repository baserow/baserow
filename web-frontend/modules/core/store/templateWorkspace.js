/**
 * Keeps track of the workspaces that contain the content of a template being
 * previewed. The template permission manager allows read operations in these
 * workspaces, so the preview doesn't depend on the template workspace ids in the
 * permissions payload.
 */
export const state = () => ({
  ids: [],
})

export const mutations = {
  ADD(state, workspaceId) {
    if (!state.ids.includes(workspaceId)) {
      state.ids.push(workspaceId)
    }
  },
}

export const actions = {
  register({ commit }, workspaceId) {
    commit('ADD', workspaceId)
  },
}

export const getters = {
  isTemplateWorkspace: (state) => (workspaceId) => {
    return state.ids.includes(workspaceId)
  },
}

export default {
  namespaced: true,
  state,
  getters,
  actions,
  mutations,
}
