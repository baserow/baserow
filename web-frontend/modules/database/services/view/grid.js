import addPublicAuthTokenHeader from '@baserow/modules/database/utils/publicView'
import {
  LINKED_ITEMS_DEFAULT_LOAD_COUNT,
  LINKED_ITEMS_LOAD_ALL,
} from '@baserow/modules/database/constants'

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
    }) {
      const include = []
      const params = new URLSearchParams()
      params.append('limit', limit)

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
      return client.get(`/database/views/grid/${gridId}/${url}`, config)
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
