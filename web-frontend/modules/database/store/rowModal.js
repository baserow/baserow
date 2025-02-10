import { updateRowMetadataType } from '@baserow/modules/database/utils/row'

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
  UPDATE_ROW_METADATA(state, { rowId, rowMetadataType, updateFunction }) {
    Object.values(state.rows)
      .filter((data) => data.row.id === rowId)
      .forEach((data) =>
        updateRowMetadataType(data.row, rowMetadataType, updateFunction)
      )
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
   * Called when we receive a real time row update event. It loops over all the rows
   * we have in memory here and checks if the updated row exists and if it's not
   * managed by the `rows` prop in the row edit modal. If so, it will make the
   * update. If the row is managed by the `rows` prop we don't have to do the update
   * because it will be done via `rows` property.
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
  updateRowMetadata({ commit }, { rowId, rowMetadataType, updateFunction }) {
    commit('UPDATE_ROW_METADATA', { rowId, rowMetadataType, updateFunction })
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
