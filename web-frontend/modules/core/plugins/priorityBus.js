const listeners = {}

const priorityBus = {
  $on(event, priority, callback) {
    if (!listeners[event]) {
      listeners[event] = []
    }

    listeners[event].push({ priority, callback })
    listeners[event].sort((a, b) => b.priority - a.priority)
  },
  $off(event, callback) {
    if (listeners[event]) {
      listeners[event] = listeners[event].filter(
        (listener) => listener.callback !== callback
      )
    }
  },
  $emit(event, ...args) {
    if (listeners[event]) {
      const highestPriorityListener = listeners[event][0]
      if (highestPriorityListener) {
        highestPriorityListener.callback(...args)
      }
    }
  },
  level: {
    LOWEST: 1,
    LOW: 2,
    MEDIUM: 3,
    HIGH: 4,
    HIGHEST: 5,
  },
}

export default defineNuxtPlugin({
  name: 'priorityBus',
  setup(nuxtApp) {
    nuxtApp.provide('priorityBus', priorityBus)
  },
})
