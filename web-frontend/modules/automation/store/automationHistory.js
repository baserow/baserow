import { useNuxtApp } from '#app'
import AutomationHistoryService, {
  WORKFLOW_HISTORY_PAGE_SIZE,
} from '@baserow/modules/automation/services/history'
import { notifyIf } from '@baserow/modules/core/utils/error'

const state = () => ({
  // Holds the value of which workflow history is currently selected
  workflowHistory: {},
  page: 1,
  requestedPage: 1,
  refreshPending: false,
  workflowId: null,
  loading: false,
  requestId: 0,
  nodeHistoriesByWorkflowHistory: {},
  nodeResults: {},
})

const mutations = {
  START_HISTORY_REQUEST(state, { workflowId, page, refresh }) {
    state.requestId += 1
    state.workflowId = workflowId
    state.requestedPage = page
    state.refreshPending = false
    if (!refresh) state.loading = true
  },
  FINISH_HISTORY_REQUEST(state) {
    state.loading = false
    state.requestedPage = state.page
  },
  SET_REFRESH_PENDING(state, pending) {
    state.refreshPending = pending
  },
  RESET_HISTORY(state) {
    state.requestId += 1
    state.workflowId = null
    state.workflowHistory = {}
    state.page = 1
    state.requestedPage = 1
    state.refreshPending = false
    state.loading = false
  },
  SET_WORKFLOW_HISTORY(state, { data, page }) {
    state.workflowHistory = data
    state.page = page
  },
  UPDATE_WORKFLOW_HISTORY_ITEM(state, { id, values }) {
    const results = state.workflowHistory?.results
    if (!Array.isArray(results)) return
    const index = results.findIndex((item) => item.id === id)
    if (index !== -1) {
      results[index] = { ...results[index], ...values }
    }
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
  async fetchWorkflowHistory(
    { state, commit, dispatch },
    { workflowId, page = 1, refresh = false }
  ) {
    commit('START_HISTORY_REQUEST', { workflowId, page, refresh })
    const requestId = state.requestId
    try {
      const service = AutomationHistoryService(useNuxtApp().$client)
      let { data } = await service.getWorkflowHistory(workflowId, page)
      if (requestId !== state.requestId) return
      const lastPage = Math.max(
        1,
        Math.ceil(data.count / WORKFLOW_HISTORY_PAGE_SIZE)
      )
      if (page > lastPage) {
        // Retention can remove the page while the user is browsing history.
        page = lastPage
        ;({ data } = await service.getWorkflowHistory(workflowId, page))
      }
      // Navigation and closing the panel invalidate earlier responses.
      if (requestId !== state.requestId) return
      commit('SET_WORKFLOW_HISTORY', { data, page })
      return data
    } catch (error) {
      if (requestId === state.requestId) throw error
    } finally {
      if (requestId === state.requestId) {
        commit('FINISH_HISTORY_REQUEST')
        if (state.refreshPending) {
          commit('SET_REFRESH_PENDING', false)
          await dispatch('refreshWorkflowHistory', { workflowId })
        }
      }
    }
  },
  refreshWorkflowHistory({ state, commit, dispatch }, { workflowId }) {
    if (state.workflowId !== workflowId || state.requestedPage !== 1) return
    if (state.loading) {
      // A completion event can arrive after the response snapshot was taken.
      commit('SET_REFRESH_PENDING', true)
      return
    }
    if (state.page !== 1) return
    return dispatch('fetchWorkflowHistory', {
      workflowId,
      refresh: true,
    }).catch((error) => notifyIf(error, 'automationWorkflow'))
  },
  reset({ commit }) {
    commit('RESET_HISTORY')
    commit('CLEAR_HISTORY_CACHES')
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
  async cancelWorkflowRun(
    { state, commit, dispatch },
    { workflowId, workflowHistoryId }
  ) {
    try {
      const { data } = await AutomationHistoryService(
        useNuxtApp().$client
      ).cancelWorkflowHistory(workflowHistoryId)
      // The cancel endpoint returns the bare record; the plugin data attached
      // by the list endpoint is not part of it and must keep its value.
      const values = { ...data }
      delete values.plugin_data
      if (state.workflowId === workflowId) {
        commit('UPDATE_WORKFLOW_HISTORY_ITEM', { id: data.id, values })
      }
    } finally {
      // The refetch is best effort: what the caller reports is the outcome of
      // the request above, which a failed refresh must not replace. The
      // realtime event for the cancellation request refetches anyway.
      if (state.workflowId === workflowId) {
        await dispatch('fetchWorkflowHistory', {
          workflowId,
          page: state.requestedPage,
          refresh: !state.loading,
        }).catch(() => {})
      }
    }
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
