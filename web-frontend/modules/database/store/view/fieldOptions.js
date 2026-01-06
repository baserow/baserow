import _ from 'lodash'
import { clone } from '@baserow/modules/core/utils/object'
import ViewService from '@baserow/modules/database/services/view'

/**
 * This store mixin can in combination with a view, if it needs to store options per
 * field. I noticed that we needed exactly the same code for the grid, gallery and
 * form view, so it made sense to make something reusable.
 *
 * @TODO add this mixin to the other view stores. Currently it's only used by the
 *       gallery view.
 */
export default () => {
  const state = () => ({
    fieldOptions: {},
  })

  const mutations = {
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

  const actions = {
    /**
     * Updates the field options of a given field and also makes an API request to the
     * backend with the changed values. If the request fails the action is reverted.
     */
    async updateFieldOptionsOfField(
      { commit, getters, rootGetters },
      {
        field,
        values,
        oldValues,
        readOnly = false,
        undoRedoActionGroupId = null,
      }
    ) {
      const { $client } = this
      commit('UPDATE_FIELD_OPTIONS_OF_FIELD', {
        fieldId: field.id,
        values,
      })

      const viewId = getters.getViewId
      if (!readOnly) {
        const updateValues = { field_options: {} }
        updateValues.field_options[field.id] = values

        try {
          await ViewService($client).updateFieldOptions({
            viewId,
            values: updateValues,
            undoRedoActionGroupId,
          })
        } catch (error) {
          commit('UPDATE_FIELD_OPTIONS_OF_FIELD', {
            fieldId: field.id,
            values: oldValues,
          })
          throw error
        }
      }
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
      { dispatch, getters, rootGetters },
      { newFieldOptions, oldFieldOptions, readOnly = false }
    ) {
      const { $client } = this
      dispatch('forceUpdateAllFieldOptions', newFieldOptions)

      const viewId = getters.getViewId
      if (!readOnly) {
        const updateValues = { field_options: newFieldOptions }

        try {
          await ViewService($client).updateFieldOptions({
            viewId,
            values: updateValues,
          })
        } catch (error) {
          dispatch('forceUpdateAllFieldOptions', oldFieldOptions)
          throw error
        }
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
      { order, readOnly = false }
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
        oldFieldOptions,
        newFieldOptions,
        readOnly,
      })
    },
    /**
     * Deletes the field options of the provided field id if they exist.
     */
    forceDeleteFieldOptions({ commit }, fieldId) {
      commit('DELETE_FIELD_OPTIONS', fieldId)
    },
  }

  const getters = {
    getAllFieldOptions(state) {
      return state.fieldOptions
    },
  }

  return {
    namespaced: true,
    state,
    getters,
    actions,
    mutations,
  }
}
