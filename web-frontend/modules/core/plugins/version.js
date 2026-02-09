/*const pkg = require('../package.json')

export default (context, inject) => {
  inject('baserowVersion', pkg.version)
}
*/

import pkg from '../../../package.json'

export default defineNuxtPlugin((nuxtApp) => {
  nuxtApp.provide('baserowVersion', pkg.version)
})
