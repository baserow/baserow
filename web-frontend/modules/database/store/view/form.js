import _ from 'lodash'
import ViewService from '@baserow/modules/database/services/view'
import { clone } from '@baserow/modules/core/utils/object'

export const state = () => ({
  fieldOptions: {},
})

export const mutations = {
  REPLACE_ALL_FIELD_OPTIONS(state, fieldOptions) {
    state.fieldOptions = fieldOptions
  },
  UPDATE_ALL_FIELD_OPTIONS(state, fieldOptions) {
    state.fieldOptions = _.merge({}, state.fieldOptions, fieldOptions)
  },
  UPDATE_FIELD_OPTIONS_OF_FIELD(state, { fieldId, values }) {
    if (Object.prototype.hasOwnProperty.call(state.fieldOptions, fieldId)) {
      Object.assign(state.fieldOptions[fieldId], values)
    } else {
      state.fieldOptions = Object.assign({}, state.fieldOptions, {
        [fieldId]: values,
      })
    }
  },
  DELETE_FIELD_OPTIONS(state, fieldId) {
    if (Object.prototype.hasOwnProperty.call(state.fieldOptions, fieldId)) {
      delete state.fieldOptions[fieldId]
    }
  },
}

export const actions = {
  async fetchInitial({ dispatch, commit, getters }, { formId }) {
    const { $client } = this
    const { data } = await ViewService($client).fetchFieldOptions(formId)
    commit('REPLACE_ALL_FIELD_OPTIONS', data.field_options)
  },
  /**
   * Updates the field options of a given field in the store. So no API request to
   * the backend is made.
   */
  setFieldOptionsOfField({ commit }, { field, values }) {
    commit('UPDATE_FIELD_OPTIONS_OF_FIELD', {
      fieldId: field.id,
      values,
    })
  },
  /**
   * Replaces all field options with new values and also makes an API request to the
   * backend with the changed values. If the request fails the action is reverted.
   */
  async updateAllFieldOptions(
    { dispatch, getters },
    { form, newFieldOptions, oldFieldOptions }
  ) {
    const { $client } = this
    dispatch('forceUpdateAllFieldOptions', newFieldOptions)
    const updateValues = { field_options: newFieldOptions }

    try {
      await ViewService($client).updateFieldOptions({
        viewId: form.id,
        values: updateValues,
      })
    } catch (error) {
      dispatch('forceUpdateAllFieldOptions', oldFieldOptions)
      throw error
    }
  },
  /**
   * Forcefully updates all field options without making a call to the backend.
   */
  forceUpdateAllFieldOptions({ commit }, fieldOptions) {
    commit('UPDATE_ALL_FIELD_OPTIONS', fieldOptions)
  },
  /**
   * Updates the order of all the available field options. The provided order parameter
   * should be an array containing the field ids in the correct order.
   */
  async updateFieldOptionsOrder(
    { commit, getters, dispatch },
    { form, order }
  ) {
    const oldFieldOptions = clone(getters.getAllFieldOptions)
    const newFieldOptions = clone(getters.getAllFieldOptions)

    // Update the order of the field options that have not been provided in the order.
    // They will get a position that places them after the provided field ids.
    let i = 0
    Object.keys(newFieldOptions).forEach((fieldId) => {
      if (!order.includes(parseInt(fieldId))) {
        newFieldOptions[fieldId].order = order.length + i
        i++
      }
    })

    // Update create the field options and set the correct order value.
    order.forEach((fieldId, index) => {
      const id = fieldId.toString()
      if (Object.prototype.hasOwnProperty.call(newFieldOptions, id)) {
        newFieldOptions[fieldId.toString()].order = index
      }
    })

    return await dispatch('updateAllFieldOptions', {
      form,
      oldFieldOptions,
      newFieldOptions,
    })
  },
  /**
   * Deletes the field options of the provided field id if they exist.
   */
  forceDeleteFieldOptions({ commit }, fieldId) {
    commit('DELETE_FIELD_OPTIONS', fieldId)
  },
  /**
   * Updates the field options of a specific field.
   */
  async updateFieldOptionsOfField(
    { commit, getters },
    { form, field, values }
  ) {
    const { $client } = this
    const oldValues = clone(getters.getAllFieldOptions[field.id])
    commit('UPDATE_FIELD_OPTIONS_OF_FIELD', {
      fieldId: field.id,
      values,
    })
    const updateValues = { field_options: {} }
    updateValues.field_options[field.id] = values

    try {
      const { data } = await ViewService($client).updateFieldOptions({
        viewId: form.id,
        values: updateValues,
      })
      // Because the updated field options could contain a newly create condition,
      // we must update it our own copy to make sure we have the correct id.
      commit('UPDATE_FIELD_OPTIONS_OF_FIELD', {
        fieldId: field.id,
        values: data.field_options[field.id.toString()],
      })
    } catch (error) {
      commit('UPDATE_FIELD_OPTIONS_OF_FIELD', {
        fieldId: field.id,
        values: oldValues,
      })
      throw error
    }
  },
}

export const getters = {
  getAllFieldOptions(state) {
    return state.fieldOptions
  },
}

export default {
  namespaced: true,
  state,
  getters,
  actions,
  mutations,
}
