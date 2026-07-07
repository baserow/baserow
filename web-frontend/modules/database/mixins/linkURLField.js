import { isValidURL } from '@baserow/modules/core/utils/string'
import { ensureUrlProtocol } from '@baserow/modules/core/utils/url'

export default {
  methods: {
    isValid(value) {
      return isValidURL(value?.url)
    },
    getLabelOrURL(value) {
      if (!value) {
        return ''
      } else {
        return value.label ? value.label : value.url
      }
    },
    getHref(value) {
      const url = typeof value === 'string' ? value : value?.url
      return url ? ensureUrlProtocol(url) : undefined
    },
  },
}
