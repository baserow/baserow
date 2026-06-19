import addPublicAuthTokenHeader from '@baserow/modules/database/utils/publicView'
import {
  LINKED_ITEMS_DEFAULT_LOAD_COUNT,
  LINKED_ITEMS_LOAD_ALL,
} from '@baserow/modules/database/constants'

/**
 * Normalizes a grid rows response requested with `compact_notation`. Such a
 * response is positional: `data.fields` holds the ordered column names once and
 * `data.results` is an array of value arrays. This reconstructs the row objects
 * so the rest of the app sees the regular shape. The compact select cell values
 * (option ids) are resolved separately by the store. No-op for a regular
 * response.
 */
export function reconstructCompactGridRows(data) {
  if (data && Array.isArray(data.fields)) {
    const header = data.fields
    data.results = data.results.map((values) => {
      const row = {}
      for (let index = 0; index < header.length; index++) {
        row[header[index]] = values[index]
      }
      return row
    })
    delete data.fields
  }
  return data
}

export default (client) => {
  return {
    fetchRows({
      gridId,
      limit = 100,
      offset = null,
      signal = null,
      includeFieldOptions = false,
      includeRowMetadata = true,
      search = '',
      searchMode = '',
      publicUrl = false,
      publicAuthToken = null,
      groupBy = '',
      orderBy = null,
      filters = {},
      includeFields = [],
      excludeFields = [],
      excludeCount = false,
      limitLinkedItems = null,
      rowIds = [],
      compactNotation = false,
    }) {
      const include = []
      const params = new URLSearchParams()
      params.append('limit', limit)

      if (compactNotation) {
        params.append('compact_notation', true)
      }

      if (offset !== null) {
        params.append('offset', offset)
      }

      if (excludeCount) {
        params.append('exclude_count', true)
      }

      if (includeFieldOptions) {
        include.push('field_options')
      }

      if (includeRowMetadata) {
        include.push('row_metadata')
      }

      if (include.length > 0) {
        params.append('include', include.join(','))
      }

      if (search) {
        params.append('search', search)
        if (searchMode) {
          params.append('search_mode', searchMode)
        }
      }

      if (groupBy) {
        params.append('group_by', groupBy)
      }

      if (orderBy || orderBy === '') {
        params.append('order_by', orderBy)
      }

      if (includeFields.length > 0) {
        params.append('include_fields', includeFields.join(','))
      }

      if (excludeFields.length > 0) {
        params.append('exclude_fields', excludeFields.join(','))
      }

      if (limitLinkedItems !== LINKED_ITEMS_LOAD_ALL) {
        params.append(
          'limit_linked_items',
          limitLinkedItems ?? LINKED_ITEMS_DEFAULT_LOAD_COUNT
        )
      }

      if (rowIds.length > 0) {
        params.append('filter__field_id__in', rowIds.join(','))
      }

      Object.keys(filters).forEach((key) => {
        filters[key].forEach((value) => {
          params.append(key, value)
        })
      })

      const config = { params }

      if (signal !== null) {
        config.signal = signal
      }

      if (publicAuthToken) {
        addPublicAuthTokenHeader(config, publicAuthToken)
      }

      const url = publicUrl ? 'public/rows/' : ''
      return client
        .get(`/database/views/grid/${gridId}/${url}`, config)
        .then((response) => {
          reconstructCompactGridRows(response.data)
          return response
        })
    },
    fetchCount({
      gridId,
      search = '',
      searchMode = '',
      signal = null,
      publicUrl = false,
      publicAuthToken = null,
      filters = {},
    }) {
      const params = new URLSearchParams()
      params.append('count', true)

      if (search) {
        params.append('search', search)
        if (searchMode) {
          params.append('search_mode', searchMode)
        }
      }

      Object.keys(filters).forEach((key) => {
        filters[key].forEach((value) => {
          params.append(key, value)
        })
      })

      const config = { params }

      if (signal !== null) {
        config.signal = signal
      }

      if (publicAuthToken) {
        addPublicAuthTokenHeader(config, publicAuthToken)
      }

      const url = publicUrl ? 'public/rows/' : ''
      return client.get(`/database/views/grid/${gridId}/${url}`, config)
    },
    filterRows({ gridId, rowIds, fieldIds = null }) {
      const data = { row_ids: rowIds }

      if (fieldIds !== null) {
        data.field_ids = fieldIds
      }

      return client.post(`/database/views/grid/${gridId}/`, data)
    },
    fetchFieldAggregations({
      gridId,
      filters = {},
      search = '',
      searchMode = '',
      signal = null,
    }) {
      const params = new URLSearchParams()

      Object.keys(filters).forEach((key) => {
        filters[key].forEach((value) => {
          params.append(key, value)
        })
      })

      if (search) {
        params.append('search', search)
        if (searchMode) {
          params.append('search_mode', searchMode)
        }
      }

      const config = { params }

      if (signal !== null) {
        config.signal = signal
      }

      return client.get(`/database/views/grid/${gridId}/aggregations/`, config)
    },
    fetchPublicFieldAggregations({
      slug,
      publicAuthToken = null,
      filters = {},
      search = '',
      searchMode = '',
      signal = null,
    }) {
      const params = new URLSearchParams()

      Object.keys(filters).forEach((key) => {
        filters[key].forEach((value) => {
          params.append(key, value)
        })
      })

      if (search) {
        params.append('search', search)
        if (searchMode) {
          params.append('search_mode', searchMode)
        }
      }

      const config = { params }
      if (publicAuthToken) {
        addPublicAuthTokenHeader(config, publicAuthToken)
      }

      if (signal !== null) {
        config.signal = signal
      }

      return client.get(
        `/database/views/grid/${slug}/public/aggregations/`,
        config
      )
    },
  }
}
