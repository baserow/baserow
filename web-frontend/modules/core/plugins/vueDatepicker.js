/*import Vue from 'vue'
import Datepicker from 'vuejs-datepicker'

Vue.component('DatePicker', Datepicker)
*/

import Datepicker from 'vuejs3-datepicker'

export default defineNuxtPlugin((nuxtApp) => {
  nuxtApp.vueApp.component('DatePicker', Datepicker)
})
