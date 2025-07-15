import AutomationHistoryService from '@baserow/modules/automation/services/history'

const state = {
  // Holds the value of which workflow history is currently selected
  workflowHistory: {},
}

const mutations = {
  SET_WORKFLOW_HISTORY(state, { data }) {
    state.workflowHistory = data
  },
}

const actions = {
  async fetchWorkflowHistory({ commit }, { workflowId }) {
    const { data } = await AutomationHistoryService(
      this.$client
    ).getWorkflowHistory(workflowId)

    commit('SET_WORKFLOW_HISTORY', { data })

    return data
  },
}

const getters = {
  getWorkflowHistory: (state) => () => {
    return state.workflowHistory
  },
}

export default {
  namespaced: true,
  state,
  getters,
  actions,
  mutations,
}
