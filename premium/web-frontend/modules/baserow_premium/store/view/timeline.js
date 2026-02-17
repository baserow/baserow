import bufferedRows from '@baserow/modules/database/store/view/bufferedRows'
import TimelineService from '@baserow_premium/services/views/timeline'
import {
  getRowMetadata,
  mergeRowMetadata,
  updateRowMetadataType,
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
   * Merges row metadata in the timeline buffer.
   * Supports two modes:
   * 1. Type-specific: pass rowMetadataType + updateFunction to transform one key
   * 2. Direct merge: pass metadata to deep merge with existing metadata
   */
  MERGE_ROW_METADATA(
    state,
    { row, metadata, rowMetadataType, updateFunction }
  ) {
    const index = state.rows.findIndex((item) => item && item.id === row.id)
    if (index !== -1) {
      const existingRowState = state.rows[index]

      if (updateFunction) {
        updateRowMetadataType(existingRowState, rowMetadataType, updateFunction)
      } else {
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
    }
  },
  REPLACE_ROW_METADATA(state, { row, metadata }) {
    const index = state.rows.findIndex((item) => item && item.id === row.id)
    if (index !== -1) {
      const existingRowState = state.rows[index]
      if (!existingRowState._) {
        populateRow(existingRowState, metadata)
      } else {
        existingRowState._ = {
          ...existingRowState._,
          metadata,
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
   * Updates a single row's row._.metadata based on the provided rowMetadataType and
   * updateFunction.
   */
  updateRowMetadataType(
    { commit, getters },
    { rowId, rowMetadataType, updateFunction }
  ) {
    const row = getters.getRows.find((r) => r && r.id === rowId)
    if (row) {
      commit('MERGE_ROW_METADATA', { row, rowMetadataType, updateFunction })
    }
  },
  /**
   * Replaces row metadata for specific rows without changing row values.
   * Called when a rows_metadata_updated websocket event is received.
   * Uses replace (not merge) semantics because the backend regenerates
   * complete metadata from all registry types for the affected rows.
   */
  updateRowsMetadata({ commit, getters }, { rowIds, metadata }) {
    const allRows = getters.getRows
    rowIds.forEach((rowId) => {
      const row = allRows.find((r) => r && r.id === rowId)
      if (row) {
        const rowMetadata = metadata[rowId] || {}
        commit('REPLACE_ROW_METADATA', { row, metadata: rowMetadata })
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
