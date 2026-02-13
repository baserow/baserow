import pkg from '../../../package.json'

export default defineNuxtPlugin((nuxtApp) => {
  nuxtApp.provide('baserowVersion', pkg.version)
})
