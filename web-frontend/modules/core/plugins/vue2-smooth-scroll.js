import VueSmoothScroll from 'vue2-smooth-scroll'

export default defineNuxtPlugin((nuxtApp) => {
  if (import.meta.client) {
    nuxtApp.vueApp.use(VueSmoothScroll)
  }
})
