import Vue from 'vue'

/**
 * This is a global mixin that's registered for every component. The purpose is to
 * bind to the `mounted` hook and set the related route to the `routeMounted` store.
 * This is used so that there is a reactive state of the mounted route. It can be
 * used by any other process to reactively check if a route has fully loaded and is
 * mounted, which can be needed if it depends on DOM elements to be rendered.
 */
Vue.mixin({
  mounted() {
    if (
      this.$route &&
      // Skip components that don't have a layout because those are not Nuxt pages.
      this.$options.layout !== undefined
    ) {
      this.$store.commit('routeMounted/SET_ROUTE_MOUNTED', {
        mounted: true,
        route: this.$route,
      })
    }
  },
  beforeDestroy() {
    if (this.$route && this.$options.layout !== undefined) {
      this.$store.commit('routeMounted/SET_ROUTE_MOUNTED', {
        mounted: false,
        route: null,
      })
    }
  },
})
