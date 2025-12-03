/*import Vue from 'vue'
import VueSmoothScroll from 'vue2-smooth-scroll'

Vue.use(VueSmoothScroll)
*/

import VueSmoothScroll from 'vue2-smooth-scroll'

export default defineNuxtPlugin((nuxtApp) => {
  if (process.client) {
    nuxtApp.vueApp.use(VueSmoothScroll)
  }
})
