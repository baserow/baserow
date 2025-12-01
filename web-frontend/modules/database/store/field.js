import FieldService from '@baserow/modules/database/services/field'
import { clone } from '@baserow/modules/core/utils/object'

export function populateField(field, registry) {
  const type = registry.get('field', field.type)

  field._ = {
    type: type.serialize(),
    loading: false,
  }
  return type.populate(field)
}

export const state = () => ({
  types: {},
  loading: false,
  loaded: false,
  items: [],
})

export const mutations = {
  SET_ITEMS(state, fields) {
    state.items = fields
  },
  SET_LOADING(state, value) {
    state.loading = value
  },
  SET_ITEM_LOADING(state, { field, value }) {
    if (!Object.prototype.hasOwnProperty.call(field, '_')) {
      return
    }
    field._.loading = value
  },
  SET_LOADED(state, value) {
    state.loaded = value
  },
  ADD_ITEM(state, item) {
    state.items.push(item)
  },
  UPDATE_ITEM(state, { id, values }) {
    const index = state.items.findIndex((item) => item.id === id)
    state.items.splice(index, 1, values)
  },
  DELETE_ITEM(state, id) {
    const index = state.items.findIndex((item) => item.id === id)
    state.items.splice(index, 1)
  },
  SET_SELECTED(state, field) {
    Object.values(state.items).forEach((item) => {
      item._.selected = false
    })
    field._.selected = true
    state.selected = field
  },
  UNSELECT(state) {
    Object.values(state.items).forEach((item) => {
      item._.selected = false
    })
    state.selected = {}
  },
}

export const actions = {
  /**
   * Changes the loading state of a specific field.
   */
  setItemLoading({ commit }, { field, value }) {
    commit('SET_ITEM_LOADING', { field, value })
  },
  /**
   * Fetches all the fields of a given table. The is mostly called when the user
   * selects a different table.
   */
  async fetchAll({ commit, getters, dispatch }, table) {
    commit('SET_LOADING', true)
    commit('SET_LOADED', false)
    commit('UNSELECT', {})

    try {
      const { data } = await FieldService(this.$client).fetchAll(table.id)
      await dispatch('forceSetFields', { fields: data })
    } catch (error) {
      commit('SET_ITEMS', [])
      commit('SET_LOADING', false)

      throw error
    }
    return getters.getAll
  },
  forceSetFields({ commit, rootGetters }, { fields }) {
    fields.forEach((part, index) => {
      populateField(fields[index], this.$registry)
    })

    commit('SET_ITEMS', fields)
    commit('SET_LOADING', false)
    commit('SET_LOADED', true)

    return { fields }
  },
  /**
   * Creates a new field with the provided type for the given table.
   */
  async create(
    context,
    { type, table, values, forceCreate = true, undoRedoActionGroupId = null }
  ) {
    const { dispatch } = context

    if (Object.prototype.hasOwnProperty.call(values, 'type')) {
      throw new Error(
        'The key "type" is a reserved, but is already set on the ' +
          'values when creating a new field.'
      )
    }

    if (!this.$registry.exists('field', type)) {
      throw new Error(`A field with type "${type}" doesn't exist.`)
    }

    const postData = clone(values)
    postData.type = type
    const { data } = await FieldService(this.$client).create(
      table.id,
      postData,
      undoRedoActionGroupId
    )
    const forceCreateCallback = async () => {
      return await dispatch('forceCreate', {
        table,
        values: data,
        relatedFields: data.related_fields,
      })
    }
    const fieldType = this.$registry.get('field', type)

    const fetchNeeded =
      fieldType.shouldFetchDataWhenAdded() ||
      anyFieldsNeedFetch(data.related_fields, this.$registry)
    const callback = forceCreate
      ? await forceCreateCallback()
      : forceCreateCallback
    return {
      forceCreateCallback: callback,
      fetchNeeded,
      newField: data,
      undoRedoActionGroupId,
    }
  },
  /**
   * Restores a field into the field store and notifies the selected view that the
   * field has been restored so it can update it's own state if the view type contains
   * any field specific state.
   */
  async fieldRestored(context, { table, selectedView, values }) {
    const { commit } = context
    const fieldType = this.$registry.get('field', values.type)
    const populatedField = populateField(values, this.$registry)
    commit('ADD_ITEM', populatedField)

    if (selectedView) {
      const selectedViewType = this.$registry.get('view', selectedView.type)
      await selectedViewType.fieldRestored(
        context,
        table,
        selectedView,
        populatedField,
        fieldType,
        'page/'
      )
    }
  },
  /**
   * Forcefully create a new field without making a call to the backend.
   */
  async forceCreate(context, { table, values, relatedFields = [] }) {
    const { commit, dispatch } = context
    const fieldType = this.$registry.get('field', values.type)
    const data = populateField(values, this.$registry)
    commit('ADD_ITEM', data)

    // Call the field created event on all the registered views because they might
    // need to change things in loaded data. For example the grid field will add the
    // field to all of the rows that are in memory.
    for (const viewType of Object.values(this.$registry.getAll('view'))) {
      await viewType.afterFieldCreated(context, table, data, fieldType, 'page/')
    }

    await dispatch('forceUpdateFields', {
      fields: relatedFields,
    })
  },
  /**
   * Updates the values of the provided field.
   */
  async update(context, { field, type, values, forceUpdate = true }) {
    const { dispatch } = context

    if (Object.prototype.hasOwnProperty.call(values, 'type')) {
      throw new Error(
        'The key "type" is a reserved, but is already set on the values when ' +
          'creating a new field.'
      )
    }

    if (!this.$registry.exists('field', type)) {
      throw new Error(`A field with type "${type}" doesn't exist.`)
    }

    const oldField = clone(field)
    const postData = clone(values)
    postData.type = type

    const { data } = await FieldService(this.$client).update(field.id, postData)
    const forceUpdateCallback = async () => {
      return await dispatch('forceUpdate', {
        field,
        oldField,
        data,
        relatedFields: data.related_fields,
      })
    }

    return forceUpdate ? await forceUpdateCallback() : forceUpdateCallback
  },
  /**
   * Promote the provided field to primary field.
   */
  async changePrimary(context, { field, forceUpdate = true }) {
    const { dispatch } = context

    const newField = clone(field)
    const oldField = clone(field)
    newField.primary = true

    const { data } = await FieldService(this.$client).changePrimary(
      field.table_id,
      field.id
    )
    const forceUpdateCallback = async () => {
      return await dispatch('forceUpdate', {
        field,
        oldField,
        data,
        relatedFields: data.related_fields,
      })
    }

    return forceUpdate ? await forceUpdateCallback() : forceUpdateCallback
  },
  /**
   * Forcefully update an existing field without making a request to the backend.
   */
  async forceUpdate(context, { field, oldField, data, relatedFields = [] }) {
    const { commit, dispatch } = context
    const fieldType = this.$registry.get('field', data.type)
    data = populateField(data, this.$registry)

    commit('UPDATE_ITEM', { id: field.id, values: data })
    commit('UPDATE_ITEM', { id: field.id, values: data })

    // The view might need to do some cleanup regarding the filters and sortings if the
    // type has changed.
    await dispatch(
      'view/fieldUpdated',
      { field: data, fieldType },
      { root: true }
    )

    // Call the field updated event on all the registered views because they might
    // need to change things in loaded data. For example the changed rows.
    for (const viewType of Object.values(this.$registry.getAll('view'))) {
      await viewType.afterFieldUpdated(
        context,
        data,
        oldField,
        fieldType,
        'page/'
      )
    }

    await dispatch('forceUpdateFields', {
      fields: relatedFields,
    })
  },
  /**
   * Forcefully updates a list of fields.
   */
  async forceUpdateFields({ getters, dispatch }, { fields }) {
    for (const f of fields) {
      const field = getters.get(f.id)
      if (field !== undefined) {
        const oldField = clone(field)
        await dispatch('forceUpdate', {
          field,
          oldField,
          data: f,
        })
      }
    }
  },
  /**
   * Deletes an existing field with the provided id.
   */
  async delete({ commit, dispatch }, field) {
    try {
      const { data } = await dispatch('deleteCall', field)
      await dispatch('forceDelete', field)
      await dispatch('forceUpdateFields', {
        fields: data.related_fields,
      })
    } catch (error) {
      // If the field to delete wasn't found we can just delete it from the
      // state.
      if (error.response && error.response.status === 404) {
        dispatch('forceDelete', field)
      } else {
        throw error
      }
    }
  },
  /**
   * Only makes the delete call to the server.
   */
  async deleteCall({ commit, dispatch }, field) {
    return await FieldService(this.$client).delete(field.id)
  },
  /**
   * Remove the field from the items without calling the server.
   */
  async forceDelete(context, field) {
    const { commit, dispatch } = context

    // Also delete the related filters if there are any.
    dispatch('view/fieldDeleted', { field }, { root: true })
    commit('DELETE_ITEM', field.id)

    // Call the field delete event on all the registered views because they might
    // need to change things in loaded data. For example the grid field will remove the
    // field options of that field.
    const fieldType = this.$registry.get('field', field.type)
    for (const viewType of Object.values(this.$registry.getAll('view'))) {
      await viewType.afterFieldDeleted(context, field, fieldType, 'page/')
    }
  },
}

export const getters = {
  isLoaded(state) {
    return state.loaded
  },
  get: (state) => (id) => {
    return state.items.find((item) => item.id === id)
  },
  getAll(state) {
    return state.items
  },
}

export default {
  namespaced: true,
  state,
  getters,
  actions,
  mutations,
}

export function anyFieldsNeedFetch(fields, registry) {
  return fields.some((f) => {
    const relatedFieldType = registry.get('field', f.type)
    return relatedFieldType.shouldFetchDataWhenAdded()
  })
}
