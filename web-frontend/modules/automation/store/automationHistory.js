import { useNuxtApp } from '#app'
import AutomationHistoryService from '@baserow/modules/automation/services/history'

const state = {
  // Holds the value of which workflow history is currently selected
  workflowHistory: {},
  nodeHistoriesByWorkflowHistory: {},
  nodeResults: {},
}

const mutations = {
  SET_WORKFLOW_HISTORY(state, { data }) {
    state.workflowHistory = data
  },
  SET_NODE_HISTORIES(state, { workflowHistoryId, data }) {
    state.nodeHistoriesByWorkflowHistory[workflowHistoryId] = data
  },
  SET_NODE_RESULT(state, { nodeHistoryId, data }) {
    state.nodeResults[nodeHistoryId] = data
  },
  CLEAR_HISTORY_CACHES(state) {
    state.nodeHistoriesByWorkflowHistory = {}
    state.nodeResults = {}
  },
}

const actions = {
  async fetchWorkflowHistory({ commit }, { workflowId }) {
    const { data } = await AutomationHistoryService(
      useNuxtApp().$client
    ).getWorkflowHistory(workflowId)

    commit('SET_WORKFLOW_HISTORY', { data })

    return data
  },
  async fetchNodeHistories({ state, commit }, { workflowHistoryId }) {
    if (workflowHistoryId in state.nodeHistoriesByWorkflowHistory) return

    const { data } = await AutomationHistoryService(
      useNuxtApp().$client
    ).getNodeHistories(workflowHistoryId)
    commit('SET_NODE_HISTORIES', {
      workflowHistoryId,
      data: Object.freeze(data),
    })
  },
  async fetchNodeResult({ state, commit }, { nodeHistoryId }) {
    if (nodeHistoryId in state.nodeResults) return

    const { data } = await AutomationHistoryService(
      useNuxtApp().$client
    ).getNodeResult(nodeHistoryId)
    commit('SET_NODE_RESULT', { nodeHistoryId, data: data.result })
  },
  invalidate({ commit }) {
    commit('CLEAR_HISTORY_CACHES')
  },
}

const getters = {
  getWorkflowHistory: (state) => () => {
    return state.workflowHistory
  },
  // Returns null if the data hasn't been fetched yet.
  getNodeHistories: (state) => (workflowHistoryId) => {
    return state.nodeHistoriesByWorkflowHistory[workflowHistoryId] ?? null
  },

  getNodeResult: (state) => (nodeHistoryId) => {
    return state.nodeResults[nodeHistoryId]
  },
}

export default {
  namespaced: true,
  state,
  getters,
  actions,
  mutations,
}
