import flushPromises from 'flush-promises'
import { nextTick } from 'vue'

export default defineNuxtPlugin((nuxtApp) => {
  const ensureRender = async () => {
    await nextTick()
    await new Promise((resolve) => requestAnimationFrame(resolve))
    await flushPromises()
  }

  nuxtApp.provide('ensureRender', ensureRender)
})
