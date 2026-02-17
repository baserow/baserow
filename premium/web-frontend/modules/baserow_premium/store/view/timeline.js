import bufferedRows from '@baserow/modules/database/store/view/bufferedRows'
import TimelineService from '@baserow_premium/services/views/timeline'
import {
  getRowMetadata,
  mergeRowMetadata,
} from '@baserow/modules/database/utils/row'

export function populateRow(row, metadata = {}) {
  row._ = {
    metadata: getRowMetadata(row, metadata),
  }
  return row
}

const timelineBufferedRows = bufferedRows({
  service: TimelineService,
  customPopulateRow: populateRow,
})

export const state = () => ({
  ...timelineBufferedRows.state(),
})

export const mutations = {
  ...timelineBufferedRows.mutations,
  /**
   * Updates row metadata in the timeline buffer.
   * Deep merges new metadata with existing metadata, removing keys with null values.
   */
  UPDATE_ROW_METADATA(state, { row, metadata }) {
    const index = state.rows.findIndex((item) => item && item.id === row.id)
    if (index !== -1) {
      const existingRowState = state.rows[index]
      const existingMetadata = existingRowState._?.metadata || {}
      const mergedMetadata = mergeRowMetadata(existingMetadata, metadata)

      if (!existingRowState._) {
        populateRow(existingRowState, mergedMetadata)
      } else {
        existingRowState._ = {
          ...existingRowState._,
          metadata: mergedMetadata,
        }
      }
    }
  },
}

export const actions = {
  ...timelineBufferedRows.actions,
  async fetchInitial(
    { dispatch },
    { viewId, fields, adhocFiltering, adhocSorting }
  ) {
    const data = await dispatch('fetchInitialRows', {
      viewId,
      fields,
      initialRowArguments: {
        includeFieldOptions: true,
      },
      adhocFiltering,
      adhocSorting,
    })
    await dispatch('forceUpdateAllFieldOptions', data.field_options)
  },
  /**
   * Updates row metadata for specific rows without changing row values.
   * Called when a rows_metadata_updated websocket event is received.
   */
  updateRowMetadata({ commit, getters }, { rowIds, metadata }) {
    const allRows = getters.getRows
    rowIds.forEach((rowId) => {
      const row = allRows.find((r) => r && r.id === rowId)
      if (row) {
        const rowMetadata = metadata[rowId] || {}
        commit('UPDATE_ROW_METADATA', { row, metadata: rowMetadata })
      }
    })
  },
}

export const getters = {
  ...timelineBufferedRows.getters,
}

export default {
  namespaced: true,
  state,
  getters,
  actions,
  mutations,
}
