import mitt from 'mitt'

/** Plugin for compat with vue2 */
export default defineNuxtPlugin({
  name: 'bus',
  setup(nuxtApp) {
    const emitter = mitt()

    const once = (event, handler) => {
      const wrapper = (...args) => {
        handler(...args)
        emitter.off(event, wrapper)
      }
      emitter.on(event, wrapper)
    }

    const bus = {
      on: emitter.on,
      off: emitter.off,
      emit: emitter.emit,

      // Vue 2 compat layer
      $on: emitter.on,
      $off: emitter.off,
      $emit: emitter.emit,
      $once: once,
    }

    nuxtApp.provide('bus', bus)
  },
})
