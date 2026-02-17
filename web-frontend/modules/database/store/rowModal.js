import {
  mergeRowMetadata,
  updateRowMetadataType,
} from '@baserow/modules/database/utils/row'
import { AI_FIELD_STATUS } from '@baserow/modules/database/constants'

/**
 * This store exists to always keep a copy of the row that's being edited via the
 * row edit modal. It sometimes happen that row from the original source, where it was
 * reactive with doesn't exist anymore. To make sure the modal still works in that
 * case, we always store a copy here and if it doesn't exist in the original data
 * source it accepts real time updates. This store can handle multiple row edit
 * modals being open because the rows are divided by the unique component id.
 */
export const state = () => ({
  // The key of the rows property is the unique component id indicating to which row
  // edit modal the entry is related to. The value looks like:
  // {
  //   tableId: -1,
  //   // row id
  //   id: -1,
  //   // Indicates whether the row exists in the `rows` property in the row edit modal.
  //   exists: true,
  //   // The values of the row.
  //   row: {}
  // }
  rows: {},
})

export const mutations = {
  CLEAR(state, componentId) {
    delete state.rows[componentId]
  },
  OPEN(state, { componentId, tableId, id, exists, row }) {
    state.rows = {
      ...state.rows,
      ...{
        [componentId]: {
          tableId,
          id,
          exists,
          row,
        },
      },
    }
  },
  SET_EXISTS(state, { componentId, value }) {
    state.rows[componentId] = {
      ...state.rows[componentId],
      ...{ exists: value },
    }
  },
  REPLACE_ROW(state, { componentId, row }) {
    state.rows[componentId] = {
      ...state.rows[componentId],
      ...{ row },
    }
  },
  UPDATE_ROW(state, { componentId, row }) {
    Object.assign(state.rows[componentId].row, row)
  },
  /**
   * Merges row metadata in the row modal.
   *
   * Supports two modes:
   * 1. Direct merge: pass `metadata` to merge with existing metadata
   * 2. Type-specific update: pass `rowMetadataType` and `updateFunction` to
   *    transform a specific metadata type using the function
   */
  MERGE_ROW_METADATA(
    state,
    { rowId, metadata, rowMetadataType, updateFunction }
  ) {
    Object.keys(state.rows).forEach((componentId) => {
      const data = state.rows[componentId]
      if (data.row.id === rowId) {
        if (updateFunction) {
          // Type-specific update using updateFunction
          updateRowMetadataType(data.row, rowMetadataType, updateFunction)
        } else {
          // Direct merge of metadata
          const existingMetadata = data.row._?.metadata || {}
          const mergedMetadata = mergeRowMetadata(existingMetadata, metadata)

          if (!data.row._) {
            data.row._ = { metadata: mergedMetadata }
          } else {
            data.row._ = {
              ...data.row._,
              metadata: mergedMetadata,
            }
          }
        }
      }
    })
  },
  /**
   * Replaces row metadata in the row modal with the provided metadata.
   * Used when rows_updated event provides the complete current metadata state.
   */
  REPLACE_ROW_METADATA(state, { rowId, metadata }) {
    Object.keys(state.rows).forEach((componentId) => {
      const data = state.rows[componentId]
      if (data.row.id === rowId) {
        if (!data.row._) {
          data.row._ = { metadata }
        } else {
          data.row._ = {
            ...data.row._,
            metadata,
          }
        }
      }
    })
  },
}

export const actions = {
  clear({ commit }, { componentId }) {
    commit('CLEAR', componentId)
  },
  /**
   * Is called when the row edit modal is being opened. It will register the row
   * values in this store so that it can also receive real time updates if it's
   * managed by the `rows` prop in the row edit modal.
   */
  open({ commit }, { componentId, tableId, id, exists, row }) {
    commit('OPEN', { componentId, tableId, id, exists, row })
  },
  /**
   * Marking the row as does not exist makes it managed by this store instead of the
   * provided rows. This will make sure that it accepts real time update events.
   */
  doesNotExist({ commit }, { componentId }) {
    commit('SET_EXISTS', { componentId, value: false })
  },
  doesExist({ commit }, { componentId, row }) {
    commit('SET_EXISTS', { componentId, value: true })
    commit('REPLACE_ROW', { componentId, row })
  },
  replace({ commit }, { componentId, row }) {
    commit('REPLACE_ROW', { componentId, row })
  },
  /**
   * Called when we receive a real time row update event. Only updates rows that
   * don't exist in the buffer (exists=false), since buffer rows are managed by
   * the parent component and share the same object reference with the store.
   */
  updated({ commit, getters }, { tableId, values }) {
    const rows = getters.getRows
    Object.keys(rows).forEach((key) => {
      const value = rows[key]
      if (
        value !== null &&
        value.tableId === tableId &&
        value.id === values.id &&
        !value.exists
      ) {
        commit('UPDATE_ROW', { componentId: key, row: values })
      }
    })
  },
  /**
   * If a row is open in the modal but it's not present in the buffer, we need to
   * manually update the metadata of the row. This is used for example to update the
   * notification_mode setting of a row.
   */
  updateRowMetadataType(
    { commit },
    { rowId, rowMetadataType, updateFunction }
  ) {
    commit('MERGE_ROW_METADATA', {
      rowId,
      rowMetadataType,
      updateFunction,
    })
  },
  /**
   * Updates row metadata for a specific row without changing row values.
   * Called when a rows_metadata_updated websocket event is received.
   * Deep merges new metadata with existing metadata.
   */
  updateRowMetadata({ commit }, { rowId, metadata }) {
    commit('MERGE_ROW_METADATA', { rowId, metadata })
  },
  /**
   * Replaces row metadata for a specific row with the provided metadata.
   * Called when a rows_updated websocket event is received, where metadata
   * represents the complete current state (not a delta).
   */
  replaceRowMetadata({ commit }, { rowId, metadata }) {
    commit('REPLACE_ROW_METADATA', { rowId, metadata })
  },
  /**
   * Generates AI field value for a single row with optimistic update and rollback.
   * This action handles the UI state (showing generating spinner), API call, and
   * rolling back on error.
   *
   * @param {number} fieldId - The AI field ID
   * @param {number} rowId - The row ID to generate value for
   * @param {object} row - The row object containing current metadata
   * @param {function} generateFn - Async function that calls the API (receives fieldId, rowId)
   */
  async generateAIFieldValue({ commit }, { fieldId, rowId, row, generateFn }) {
    const previousMetadata = row?._?.metadata?.ai_field?.[fieldId] || null

    // Optimistic update to show generating state
    commit('MERGE_ROW_METADATA', {
      rowId,
      metadata: {
        ai_field: {
          [fieldId]: { status: AI_FIELD_STATUS.GENERATING },
        },
      },
    })

    try {
      await generateFn(fieldId, rowId)
    } catch (error) {
      // Rollback on error
      commit('MERGE_ROW_METADATA', {
        rowId,
        metadata: {
          ai_field: {
            [fieldId]: previousMetadata,
          },
        },
      })
      throw error
    }
  },
}

export const getters = {
  getRows(state) {
    return state.rows
  },
  get: (state) => (componentId) => {
    if (!Object.prototype.hasOwnProperty.call(state.rows, componentId)) {
      return {
        id: -1,
        tableId: -1,
        exists: false,
        row: {},
      }
    }

    return state.rows[componentId]
  },
}

export default {
  namespaced: true,
  state,
  getters,
  actions,
  mutations,
}
