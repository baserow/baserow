import { defineNuxtPlugin } from '#app'

export default defineNuxtPlugin({
  name: 'theme',
  setup(nuxtApp) {
    const store = nuxtApp.$store
    if (store) {
      store.dispatch('uiTheme/init')
    }
  },
})
