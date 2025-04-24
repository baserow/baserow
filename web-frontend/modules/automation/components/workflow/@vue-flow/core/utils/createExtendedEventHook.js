import { tryOnScopeDispose } from '@vueuse/core'

/**
 * Source code taken from https://github.com/vueuse/vueuse/blob/main/packages/shared/createEventHook/index.ts
 *
 * Modified to be able to check if there are any event listeners
 */
export function createExtendedEventHook(defaultHandler) {
  const fns = new Set()

  let hasDefaultHandler = false

  const hasListeners = () => fns.size > 0

  if (defaultHandler) {
    hasDefaultHandler = true
    fns.add(defaultHandler)
  }

  const off = (fn) => {
    fns.delete(fn)
  }

  const on = (fn) => {
    if (defaultHandler && hasDefaultHandler) {
      fns.delete(defaultHandler)
    }

    fns.add(fn)

    const offFn = () => {
      off(fn)

      if (defaultHandler && hasDefaultHandler) {
        fns.add(defaultHandler)
      }
    }

    tryOnScopeDispose(offFn)

    return {
      off: offFn,
    }
  }

  const trigger = (param) => {
    return Promise.all(Array.from(fns).map((fn) => fn(param)))
  }

  return {
    on,
    off,
    trigger,
    hasListeners,
    fns,
  }
}
