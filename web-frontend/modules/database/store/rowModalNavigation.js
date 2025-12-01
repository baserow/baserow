import RowService from '@baserow/modules/database/services/row'
import { notifyIf } from '@baserow/modules/core/utils/error'
import { getDefaultSearchModeFromEnv } from '@baserow/modules/database/utils/search'

/**
 * This store exists to deal with the row edit modal navigation.
 * It handles the state of the navigation which can be in a loading
 * state or in a ready state. It also handles the state of the row
 * which can either be taken from the buffer or fetched if outside
 * of the buffer.
 */
export const state = () => ({
  loading: false,
  /**
   * The row refers to the row that the view is
   * trying to display. It has a slightly different
   * purpose to the rows stored in the `rowModal` store
   * since those rows are accessed by the row edit modal
   * directly while this row is accessed by the view and
   * given to the row edit modal via `show()`.
   *
   * The row can be outside of the buffer and could therefore
   * also not be part of the `rows` in the `rowModal` store.
   */
  row: null,
  failedToFetchTableRowId: null,
})

export const mutations = {
  CLEAR_ROW(state) {
    state.row = null
  },
  SET_LOADING(state, value) {
    state.loading = value
  },
  SET_ROW(state, row) {
    state.row = row
  },
  SET_FAILED_TO_FETCH_TABLE_ROW_ID(state, tableAndRowId) {
    state.row = null
    state.failedToFetchTableRowId = tableAndRowId
  },
}
export const actions = {
  clearRow({ commit }) {
    commit('SET_FAILED_TO_FETCH_TABLE_ROW_ID', null)
    commit('CLEAR_ROW')
  },
  setRow({ commit }, row) {
    commit('SET_FAILED_TO_FETCH_TABLE_ROW_ID', null)
    commit('SET_ROW', row)
  },
  async fetchRow({ commit }, { tableId, rowId, viewId = null }) {
    try {
      const { data: row } = await RowService(this.$client).get(
        tableId,
        rowId,
        true,
        viewId
      )
      commit('SET_ROW', row)
      return row
    } catch (error) {
      commit('SET_FAILED_TO_FETCH_TABLE_ROW_ID', { tableId, rowId })
      notifyIf(error, 'row')
    }
  },
  async fetchAdjacentRow(
    { commit, dispatch, state },
    { tableId, viewId, previous, activeSearchTerm }
  ) {
    commit('SET_LOADING', true)
    try {
      const { data: row, status } = await RowService(this.$client).getAdjacent({
        previous,
        tableId,
        viewId,
        rowId: state.row.id,
        search: activeSearchTerm,
        searchMode: getDefaultSearchModeFromEnv(this.$config),
      })
      if (row) {
        commit('SET_ROW', row)
      }
      commit('SET_LOADING', false)
      return { row, status }
    } catch (error) {
      commit('SET_LOADING', false)
      const status = error.response?.status ?? null

      // This is the backend not responding at all
      if (status === null) {
        notifyIf(error, 'row')
      }

      return { row: null, status }
    }
  },
}
export const getters = {
  getLoading(state) {
    return state.loading
  },
  getRow(state) {
    return state.row
  },
  getFailedToFetchTableRowId(state) {
    return state.failedToFetchTableRowId
  },
}

export default {
  namespaced: true,
  state,
  getters,
  actions,
  mutations,
}
