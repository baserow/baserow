import { showError } from '#imports'

export default defineNuxtPlugin((nuxtApp) => {
  const defaultHandler = nuxtApp.vueApp.config.errorHandler

  nuxtApp.vueApp.config.errorHandler = (error, instance, info) => {
    if (error.fatal === false) {
      showError(error)
      return false
    } else {
      return defaultHandler(error, instance, info)
    }
  }
})
