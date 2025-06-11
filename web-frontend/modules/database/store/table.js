import axios from 'axios'

import { StoreItemLookupError } from '@baserow/modules/core/errors'
import TableService from '@baserow/modules/database/services/table'
import { DatabaseApplicationType } from '@baserow/modules/database/applicationTypes'
import { DATABASE_ACTION_SCOPES } from '@baserow/modules/database/utils/undoRedoConstants'
import { generateHash } from '@baserow/modules/core/utils/hashing'

export function populateTable(table) {
  return {
    ...table,
    _: {
      disabled: false,
      selected: false,
    },
  }
}

export const state = () => ({
  // Indicates whether the table is loading. This is used to show a loading
  // animation when switching between views.
  loading: false,
  selected: {},
})

export const mutations = {
  ADD_ITEM(state, { database, table }) {
    database.tables.push(populateTable(table))
  },
  UPDATE_ITEM(state, { table, values }) {
    Object.assign(table, table, values)
  },
  ORDER_TABLES(state, { database, order, isHashed = false }) {
    database.tables.forEach((table) => {
      const tableId = isHashed ? generateHash(table.id) : table.id
      const index = order.findIndex((value) => value === tableId)
      table.order = index === -1 ? 0 : index + 1
    })
  },
  SET_SELECTED(state, { database, table }) {
    Object.values(database.tables).forEach((item) => {
      item._.selected = false
    })
    table._.selected = true
    state.selected = table
  },
  UNSELECT(state) {
    if (!Object.prototype.hasOwnProperty.call(state.selected, '_')) {
      return
    }
    state.selected._.selected = false
    state.selected = {}
  },
  DELETE_ITEM(state, { database, id }) {
    const index = database.tables.findIndex((item) => item.id === id)
    database.tables.splice(index, 1)
  },
  SET_LOADING(state, value) {
    state.loading = value
  },
}

export const actions = {
  setLoading({ commit }, value) {
    commit('SET_LOADING', value)
  },
  /**
   * Trigger a new table creation based on the provided values. The job id corresponding
   * to the table creation task is returned. Once this job is finished a create_table
   * signal will be received and the table will be added in the store for the related
   * database.
   */
  async create(
    { commit, dispatch },
    {
      database,
      values,
      initialData = null,
      firstRowHeader = true,
      onUploadProgress = null,
    }
  ) {
    const type = DatabaseApplicationType.getType()

    // Check if the provided database (application) has the correct type.
    if (database.type !== type) {
      throw new Error(
        `The provided database application doesn't have the required type
        "${type}".`
      )
    }

    const { data } = await TableService(this.$client).create(
      database.id,
      values,
      initialData,
      firstRowHeader,
      {
        onUploadProgress,
      }
    )
    // The returned data is a table creation job
    return data
  },
  /**
   * Fetches one table for the authenticated user.
   */
  async fetch({ commit, dispatch }, { database, tableId }) {
    commit('SET_LOADING', true)

    try {
      const { data } = await TableService(this.$client).get(tableId)
      dispatch('forceCreate', { database, data })
      commit('SET_LOADING', false)
      return data
    } catch (error) {
      commit('SET_LOADING', false)
      throw error
    }
  },
  /**
   * Forcefully create or update an item in the store without making a call to
   * the server.
   */
  forceUpsert({ commit }, { database, data }) {
    const table = database.tables.find((item) => item.id === data.id)
    if (table === undefined) {
      commit('ADD_ITEM', { database, table: data })
    } else {
      commit('UPDATE_ITEM', { database, table, values: data })
    }
    return database.tables.find((item) => item.id === data.id)
  },
  /**
   * Update an existing table of the provided database with the provided tables.
   */
  async update({ commit, dispatch }, { database, table, values }) {
    const { data } = await TableService(this.$client).update(table.id, values)
    // Create a dict with only the values we want to update.
    const update = Object.keys(values).reduce((result, key) => {
      result[key] = data[key]
      return result
    }, {})

    dispatch('forceUpdate', { database, table, values: update })
  },
  /**
   * Forcefully update an item in the store without making a call to the server.
   */
  forceUpdate({ commit }, { database, table, values }) {
    commit('UPDATE_ITEM', { database, table, values })
  },
  /**
   * Updates the order of all the tables in a database.
   */
  async order(
    { commit, getters },
    { database, order, oldOrder, isHashed = false }
  ) {
    commit('ORDER_TABLES', { database, order, isHashed })

    try {
      await TableService(this.$client).order(database.id, order)
    } catch (error) {
      commit('ORDER_TABLES', { database, order: oldOrder, isHashed })
      throw error
    }
  },
  /**
   * Deletes an existing application.
   */
  async delete({ commit, dispatch }, { database, table }) {
    try {
      await TableService(this.$client).delete(table.id)
      return dispatch('forceDelete', { database, table })
    } catch (error) {
      if (error.response && error.response.status === 404) {
        return dispatch('forceDelete', { database, table })
      } else {
        throw error
      }
    }
  },
  /**
   * Delete the table from the store only. It will not send a request for deleting
   * to the server.
   */
  forceDelete(context, { database, table }) {
    const { commit, rootGetters } = context

    // Call the table deleted event on all fields.
    rootGetters['field/getAll'].forEach((field) => {
      const fieldType = this.$registry.get('field', field.type)
      fieldType.tableDeleted(context, field, table, database)
    })

    if (table._.selected) {
      // Redirect back to the dashboard because the table doesn't exist anymore.
      this.$router.push({ name: 'dashboard' })
    }

    commit('DELETE_ITEM', { database, id: table.id })
  },
  /**
   * When selecting the table we will have to fetch all the views and fields that
   * belong to the table we want to select. While the user is waiting they will see a
   * loading icon in the related database and after that the table is selected.
   */
  async select({ commit, dispatch, getters }, { database, table }) {
    // If the table is already selected we don't have to fetch the views and fields.
    if (getters.getSelectedId === table.id) {
      return { database, table }
    }
    let error = null
    await axios
      .all([
        dispatch('view/fetchAll', table, { root: true }),
        dispatch('field/fetchAll', table, { root: true }),
      ])
      .catch((err) => {
        error = err
      })
    await dispatch('application/clearChildrenSelected', null, { root: true })
    await dispatch('forceSelect', { database, table })
    return { database, table, error }
  },
  forceSelect({ commit, dispatch }, { database, table }) {
    dispatch(
      'undoRedo/updateCurrentScopeSet',
      DATABASE_ACTION_SCOPES.table(table.id),
      { root: true }
    )
    commit('SET_SELECTED', { database, table })
  },
  /**
   * Selects a table based on the provided database (application) and table id. The
   * application will also be selected if it has not already been selected. Because the
   * table object is stored inside the database (application) object we have to check if
   * it exists in there, if so it will be selected.
   */
  async selectById(
    { dispatch, getters, rootGetters },
    { databaseId, tableId }
  ) {
    const database = await dispatch('application/selectById', databaseId, {
      root: true,
    })
    const type = DatabaseApplicationType.getType()

    // Check if the just selected application is a database
    if (database.type !== type) {
      throw new StoreItemLookupError(
        `The application doesn't have the required ${type} type.`
      )
    }

    // Check if the provided table id is found in the just selected database.
    const index = database.tables.findIndex((item) => item.id === tableId)
    if (index === -1) {
      throw new StoreItemLookupError(
        'The table is not found in the selected application.'
      )
    }
    const table = database.tables[index]

    return await dispatch('select', { database, table })
  },
  /**
   * Unselect the selected table.
   */
  unselect({ commit, dispatch, getters }) {
    dispatch(
      'undoRedo/updateCurrentScopeSet',
      DATABASE_ACTION_SCOPES.table(null),
      { root: true }
    )
    commit('UNSELECT')
  },
}

export const getters = {
  getSelected: (state) => {
    return state.selected
  },
  getSelectedId(state) {
    return state.selected.id || 0
  },
}

export default {
  namespaced: true,
  state,
  getters,
  actions,
  mutations,
}
