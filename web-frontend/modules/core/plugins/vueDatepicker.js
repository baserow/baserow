export default defineNuxtPlugin((nuxtApp) => {
  const Datepicker = defineAsyncComponent(() => import('vuejs3-datepicker'))
  nuxtApp.vueApp.component('DatePicker', Datepicker)
})
