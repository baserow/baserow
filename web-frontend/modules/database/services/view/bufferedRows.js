import addPublicAuthTokenHeader from '@baserow/modules/database/utils/publicView'
import {
  LINKED_ITEMS_LOAD_ALL,
  LINKED_ITEMS_DEFAULT_LOAD_COUNT,
} from '@baserow/modules/database/constants'

export default (client, storePrefix) => {
  return {
    fetchRows({
      viewId,
      limit = 100,
      offset = null,
      includeFieldOptions = false,
      includeRowMetadata = true,
      search = '',
      searchMode = '',
      signal = null,
      publicUrl = false,
      publicAuthToken = null,
      orderBy = null,
      filters = {},
      includeFields = [],
      excludeFields = [],
      limitLinkedItems = null,
    }) {
      const params = new URLSearchParams()

      params.append('limit', limit)

      const include = []

      if (offset !== null) {
        params.append('offset', offset)
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

      Object.keys(filters).forEach((key) => {
        filters[key].forEach((value) => {
          params.append(key, value)
        })
      })

      const config = { params }

      if (publicAuthToken) {
        addPublicAuthTokenHeader(config, publicAuthToken)
      }

      if (signal !== null) {
        config.signal = signal
      }

      const url = publicUrl ? 'public/rows/' : ''

      return client.get(
        `/database/views/${storePrefix}/${viewId}/${url}`,
        config
      )
    },
    fetchCount({
      viewId,
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

      return client.get(
        `/database/views/${storePrefix}/${viewId}/${url}`,
        config
      )
    },
  }
}
