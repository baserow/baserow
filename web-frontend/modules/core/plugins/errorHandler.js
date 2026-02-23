import { showError } from '#imports'

export default defineNuxtPlugin((nuxtApp) => {
  nuxtApp.hook('vue:error', (error) => {
    showError(error)
  })
})
