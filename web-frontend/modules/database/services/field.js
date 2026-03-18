import { getUndoRedoActionRequestConfig } from '@baserow/modules/database/utils/action'

export default (client) => {
  return {
    fetchAll(tableId, viewId) {
      const config = { params: {} }

      if (viewId) {
        config.params.view = viewId
      }

      return client.get(`/database/fields/table/${tableId}/`, config)
    },
    create(tableId, values, undoRedoActionGroupId = null) {
      const config = getUndoRedoActionRequestConfig({ undoRedoActionGroupId })
      return client.post(`/database/fields/table/${tableId}/`, values, config)
    },
    get(fieldId) {
      return client.get(`/database/fields/${fieldId}/`)
    },
    getUniqueRowValues(fieldId, limit = 10, splitCommaSeparated = false) {
      const config = {
        params: {
          limit,
        },
      }

      if (splitCommaSeparated) {
        config.params.split_comma_separated = 'true'
      }

      return client.get(
        `/database/fields/${fieldId}/unique_row_values/`,
        config
      )
    },
    update(fieldId, values) {
      return client.patch(`/database/fields/${fieldId}/`, values)
    },
    delete(fieldId) {
      return client.delete(`/database/fields/${fieldId}/`)
    },
    asyncDuplicate(
      fieldId,
      duplicateData = false,
      undoRedoActionGroupId = null
    ) {
      const config = getUndoRedoActionRequestConfig({ undoRedoActionGroupId })
      return client.post(
        `/database/fields/${fieldId}/duplicate/async/`,
        { duplicate_data: duplicateData },
        config
      )
    },
    changePrimary(tableId, newPrimaryFieldId) {
      return client.post(
        `/database/fields/table/${tableId}/change-primary-field/`,
        {
          new_primary_field_id: newPrimaryFieldId,
        }
      )
    },
  }
}
