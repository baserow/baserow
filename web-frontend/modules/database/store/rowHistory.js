import _ from 'lodash'

import moment from '@baserow/modules/core/moment'

import RowHistoryService from '@baserow/modules/database/services/rowHistory'

export const state = () => ({
  entries: [],
  loading: false,
  loaded: false,
  totalCount: 0,
  loadedRowId: false,
  loadedTableId: false,
})

export const mutations = {
  ADD_ENTRIES(state, { entries }) {
    entries.forEach((newEntry) => {
      const existingIndex = state.entries.findIndex((e) => e.id === newEntry.id)
      if (existingIndex >= 0) {
        // Prevent duplicates by just replacing them inline
        state.entries.splice(existingIndex, 0, newEntry)
      } else {
        state.entries.push(newEntry)
      }
    })
  },
  RESET_ENTRIES(state) {
    state.entries = []
    state.totalCount = 0
  },
  SET_LOADING(state, loading) {
    state.loading = loading
  },
  SET_LOADED(state, loaded) {
    state.loaded = loaded
  },
  SET_LOADED_TABLE_AND_ROW(state, { tableId, rowId }) {
    state.loadedRowId = rowId
    state.loadedTableId = tableId
  },
  SET_TOTAL_COUNT(state, totalCount) {
    state.totalCount = totalCount
  },
}

export const actions = {
  async fetchInitial({ commit }, { tableId, rowId }) {
    const { $client } = this
    commit('RESET_ENTRIES')
    commit('SET_LOADING', true)
    commit('SET_LOADED', false)
    try {
      const { data } = await RowHistoryService($client).fetchAll({
        tableId,
        rowId,
        limit: 30,
      })
      commit('ADD_ENTRIES', { entries: data.results })
      commit('SET_TOTAL_COUNT', data.count)
      commit('SET_LOADED_TABLE_AND_ROW', { tableId, rowId })
      commit('SET_LOADED', true)
    } finally {
      commit('SET_LOADING', false)
    }
  },
  async fetchNextPage({ commit, getters }, { tableId, rowId }) {
    const { $client } = this
    commit('SET_LOADING', true)
    try {
      const { data } = await RowHistoryService($client).fetchAll({
        tableId,
        rowId,
        offset: getters.getCurrentCount,
        limit: 30,
      })
      commit('ADD_ENTRIES', { entries: data.results })
      commit('SET_TOTAL_COUNT', data.count)
    } finally {
      commit('SET_LOADING', false)
    }
  },
  forceCreate({ commit, state }, { rowHistoryEntry, rowId, tableId }) {
    if (state.loadedTableId === tableId && state.loadedRowId === rowId) {
      commit('ADD_ENTRIES', { entries: [rowHistoryEntry] })
      commit('SET_TOTAL_COUNT', state.totalCount + 1)
    }
  },
}

export const getters = {
  getSortedEntries(state) {
    return _.sortBy(state.entries, (e) => -moment.utc(e.timestamp))
  },
  getCurrentCount(state) {
    return state.entries.length
  },
  getTotalCount(state) {
    return state.totalCount
  },
  getLoading(state) {
    return state.loading
  },
  getLoaded(state) {
    return state.loaded
  },
}

export default {
  namespaced: true,
  state,
  getters,
  actions,
  mutations,
}
