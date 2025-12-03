import lowercase from '@baserow/modules/core/filters/lowercase'
import nameAbbreviation from '@baserow/modules/core/filters/nameAbbreviation'
import uppercase from '@baserow/modules/core/filters/uppercase'

export default defineNuxtPlugin(() => {
  return {
    provide: {
      filters: {
        lowercase,
        uppercase,
        nameAbbreviation,
      },
    },
  }
})
