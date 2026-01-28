/*import Vue from 'vue'
import Datepicker from 'vuejs-datepicker'

Vue.component('DatePicker', Datepicker)
*/

//import Datepicker from 'vuejs3-datepicker'

export default defineNuxtPlugin((nuxtApp) => {
  const Datepicker = defineAsyncComponent(() => import('vuejs3-datepicker'))
  nuxtApp.vueApp.component('DatePicker', Datepicker)
})
