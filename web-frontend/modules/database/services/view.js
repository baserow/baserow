import { getUndoRedoActionRequestConfig } from '@baserow/modules/database/utils/action'
import addPublicAuthTokenHeader from '@baserow/modules/database/utils/publicView'
import RowService from '@baserow/modules/database/services/row'

export default (client) => {
  return {
    fetchAll(
      tableId,
      includeFilters = false,
      includeSortings = false,
      includeGroupBys = false,
      includeDecorations = false,
      limit = null,
      type = null
    ) {
      const config = {
        params: {},
      }
      const include = []

      if (includeFilters) {
        include.push('filters')
      }

      if (includeSortings) {
        include.push('sortings')
      }

      if (includeGroupBys) {
        include.push('group_bys')
      }

      if (includeDecorations) {
        include.push('decorations')
      }

      if (include.length > 0) {
        config.params.include = include.join(',')
      }

      if (limit !== null) {
        config.params.limit = limit
      }

      if (type !== null) {
        config.params.type = type
      }

      return client.get(`/database/views/table/${tableId}/`, config)
    },
    create(tableId, values) {
      return client.post(`/database/views/table/${tableId}/`, {
        name: values.name,
        ownership_type: values.ownershipType,
        type: values.type,
      })
    },
    get(
      viewId,
      includeFilters = false,
      includeSortings = false,
      includeDecorations = false,
      includeGroupBys = false
    ) {
      const config = {
        params: {},
      }
      const include = []
      if (includeFilters) {
        include.push('filters')
      }

      if (includeSortings) {
        include.push('sortings')
      }

      if (includeDecorations) {
        include.push('decorations')
      }

      if (includeGroupBys) {
        include.push('group_bys')
      }

      if (include.length > 0) {
        config.params.include = include.join(',')
      }
      return client.get(`/database/views/${viewId}/`, config)
    },
    update(viewId, values) {
      return client.patch(`/database/views/${viewId}/`, values)
    },
    duplicate(viewId) {
      return client.post(`/database/views/${viewId}/duplicate/`)
    },
    order(tableId, ownershipType, order) {
      return client.post(`/database/views/table/${tableId}/order/`, {
        view_ids: order,
        ownership_type: ownershipType,
      })
    },
    delete(viewId) {
      return client.delete(`/database/views/${viewId}/`)
    },
    fetchFieldOptions(viewId) {
      return client.get(`/database/views/${viewId}/field-options/`)
    },
    updateFieldOptions({ viewId, values, undoRedoActionGroupId = null }) {
      const config = getUndoRedoActionRequestConfig({ undoRedoActionGroupId })
      return client.patch(
        `/database/views/${viewId}/field-options/`,
        values,
        config
      )
    },
    rotateSlug(viewId) {
      return client.post(`/database/views/${viewId}/rotate-slug/`)
    },
    linkRowFieldLookup(
      slug,
      fieldId,
      page,
      search = null,
      size = 100,
      publicAuthToken = null
    ) {
      const config = {
        params: {
          page,
          size,
        },
      }

      if (search !== null) {
        config.params.search = search
      }

      if (publicAuthToken) {
        addPublicAuthTokenHeader(config, publicAuthToken)
      }

      return client.get(
        `/database/views/${slug}/link-row-field-lookup/${fieldId}/`,
        config
      )
    },
    fetchPublicViewInfo(viewSlug, publicAuthToken = null) {
      const config = {}
      if (publicAuthToken) {
        addPublicAuthTokenHeader(config, publicAuthToken)
      }
      return client.get(`/database/views/${viewSlug}/public/info/`, config)
    },
    fetchRow(
      tableId,
      rowId,
      viewSlug = null,
      publicUrl = false,
      publicAuthToken = null
    ) {
      if (!publicUrl) {
        return RowService(client).get(tableId, rowId)
      }

      const config = {}
      if (publicAuthToken) {
        addPublicAuthTokenHeader(config, publicAuthToken)
      }
      return client.get(`/database/views/${viewSlug}/row/${rowId}/`, config)
    },
  }
}
