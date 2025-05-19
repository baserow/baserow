import addPublicAuthTokenHeader from '@baserow/modules/database/utils/publicView'
import {
  LINKED_ITEMS_LOAD_ALL,
  LINKED_ITEMS_DEFAULT_LOAD_COUNT,
} from '@baserow/modules/database/constants'

export default (client) => {
  return {
    fetchRows({
      kanbanId,
      limit = 100,
      offset = null,
      signal = null,
      includeFieldOptions = false,
      includeRowMetadata = true,
      selectOptions = [],
      publicUrl = false,
      publicAuthToken = null,
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

      Object.keys(filters).forEach((key) => {
        filters[key].forEach((value) => {
          params.append(key, value)
        })
      })

      selectOptions.forEach((selectOption) => {
        let value = selectOption.id.toString()
        if (Object.prototype.hasOwnProperty.call(selectOption, 'limit')) {
          value += `,${selectOption.limit}`
          if (Object.prototype.hasOwnProperty.call(selectOption, 'offset')) {
            value += `,${selectOption.offset}`
          }
        }
        params.append('select_option', value)
      })

      if (limitLinkedItems !== LINKED_ITEMS_LOAD_ALL) {
        params.append(
          'limit_linked_items',
          limitLinkedItems ?? LINKED_ITEMS_DEFAULT_LOAD_COUNT
        )
      }

      const config = { params }

      if (publicAuthToken) {
        addPublicAuthTokenHeader(config, publicAuthToken)
      }

      if (signal !== null) {
        config.signal = signal
      }

      const url = publicUrl ? 'public/rows/' : ''
      return client.get(`/database/views/kanban/${kanbanId}/${url}`, config)
    },
  }
}
