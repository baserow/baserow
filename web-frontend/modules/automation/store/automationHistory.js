import { useNuxtApp } from '#app'
import {
  STATUS_ERROR,
  STATUS_LOADED,
  STATUS_LOADING,
} from '@baserow/modules/automation/constants'
import AutomationHistoryService from '@baserow/modules/automation/services/history'

const nodeHistoriesKey = (workflowHistoryId, parentNodeId, iterationPath) =>
  `${workflowHistoryId}:${parentNodeId ?? 'root'}:${iterationPath ?? ''}`

const state = {
  // Holds the value of which workflow history is currently selected
  workflowHistory: {},
  // Cached children of a parent in a workflow history run.
  // Keyed by `${workflowHistoryId}:${parentNodeId ?? 'root'}:${iterationPath ?? ''}`.
  // Each value: { status, items }.
  nodeHistoriesByParent: {},
  // Cached node history result blobs, fetched on demand.
  // Keyed by node_history_id.
  // Each value: { status, result }.
  nodeResults: {},
}

const mutations = {
  SET_WORKFLOW_HISTORY(state, { data }) {
    state.workflowHistory = data
  },
  SET_NODE_HISTORIES(state, { key, data }) {
    state.nodeHistoriesByParent[key] = data
  },
  SET_NODE_RESULT(state, { nodeHistoryId, data }) {
    state.nodeResults[nodeHistoryId] = data
  },
  CLEAR_HISTORY_CACHES(state) {
    state.nodeHistoriesByParent = {}
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
  async fetchNodeHistories(
    { state, commit },
    { workflowHistoryId, parentNodeId = null, iterationPath = '' }
  ) {
    const key = nodeHistoriesKey(workflowHistoryId, parentNodeId, iterationPath)
    const entry = state.nodeHistoriesByParent[key]
    if (
      entry &&
      (entry.status === STATUS_LOADING || entry.status === STATUS_LOADED)
    ) {
      return
    }

    commit('SET_NODE_HISTORIES', {
      key,
      data: { status: STATUS_LOADING, items: [] },
    })
    try {
      const { data } = await AutomationHistoryService(
        useNuxtApp().$client
      ).getNodeHistories(workflowHistoryId, parentNodeId, iterationPath)
      commit('SET_NODE_HISTORIES', {
        key,
        data: { status: STATUS_LOADED, items: data },
      })
    } catch (e) {
      commit('SET_NODE_HISTORIES', {
        key,
        data: { status: STATUS_ERROR, items: [] },
      })
      throw e
    }
  },
  async fetchNodeResult({ state, commit }, { nodeHistoryId }) {
    const entry = state.nodeResults[nodeHistoryId]
    if (
      entry &&
      (entry.status === STATUS_LOADING || entry.status === STATUS_LOADED)
    ) {
      return
    }

    commit('SET_NODE_RESULT', {
      nodeHistoryId,
      data: { status: STATUS_LOADING, result: null },
    })
    try {
      const { data } = await AutomationHistoryService(
        useNuxtApp().$client
      ).getNodeResult(nodeHistoryId)
      commit('SET_NODE_RESULT', {
        nodeHistoryId,
        data: { status: STATUS_LOADED, result: data.result },
      })
    } catch (e) {
      commit('SET_NODE_RESULT', {
        nodeHistoryId,
        data: { status: STATUS_ERROR, result: null },
      })
      throw e
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
  getNodeHistoriesByParent:
    (state) =>
    (workflowHistoryId, parentNodeId = null, iterationPath = '') => {
      const key = nodeHistoriesKey(
        workflowHistoryId,
        parentNodeId,
        iterationPath
      )
      return (
        state.nodeHistoriesByParent[key] || {
          status: STATUS_LOADING,
          items: [],
        }
      )
    },
  getNodeResult: (state) => (nodeHistoryId) => {
    return (
      state.nodeResults[nodeHistoryId] || {
        status: STATUS_LOADING,
        result: null,
      }
    )
  },
}

export default {
  namespaced: true,
  state,
  getters,
  actions,
  mutations,
}
