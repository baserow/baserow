import addPublicAuthTokenHeader from '@baserow/modules/database/utils/publicView'
import {
  LINKED_ITEMS_LOAD_ALL,
  LINKED_ITEMS_DEFAULT_LOAD_COUNT,
} from '@baserow/modules/database/constants'

export default (client) => {
  return {
    fetchRows({
      calendarId,
      limit = 100,
      offset = null,
      includeFieldOptions = false,
      includeRowMetadata = true,
      fromTimestamp = null,
      toTimestamp = null,
      userTimeZone = null,
      publicUrl = false,
      publicAuthToken = null,
      search = '',
      searchMode = '',
      filters = {},
      limitLinkedItems = null,
    }) {
      const include = []
      const params = new URLSearchParams()
      params.append('limit', limit)

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

      params.append('from_timestamp', fromTimestamp.toISOString())
      params.append('to_timestamp', toTimestamp.toISOString())

      if (limitLinkedItems !== LINKED_ITEMS_LOAD_ALL) {
        params.append(
          'limit_linked_items',
          limitLinkedItems ?? LINKED_ITEMS_DEFAULT_LOAD_COUNT
        )
      }

      if (userTimeZone) {
        params.append('user_timezone', userTimeZone)
      }
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

      if (publicAuthToken) {
        addPublicAuthTokenHeader(config, publicAuthToken)
      }

      const url = publicUrl ? 'public/rows/' : ''

      return client.get(`/database/views/calendar/${calendarId}/${url}`, config)
    },

    rotateSlug(viewId) {
      return client.post(`/database/views/calendar/${viewId}/ical_slug_rotate/`)
    },
  }
}
