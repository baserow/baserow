/**
 * Inside a pending `<Suspense>` click listeners already work while template refs
 * and the `mounted` hook wait for it to resolve. `whenMounted` runs a call that
 * needs refs now if `mounted` has run, else queues it until then. Pass values
 * that only exist during the event, like `$event.currentTarget`, as arguments.
 */
export function createWhenMounted() {
  let mountedHookRan = false
  const callsBeforeMounted = []
  return {
    whenMounted(callback, ...args) {
      if (mountedHookRan) {
        callback(...args)
      } else {
        callsBeforeMounted.push(() => callback(...args))
      }
    },
    mounted() {
      mountedHookRan = true
      callsBeforeMounted.splice(0).forEach((call) => call())
    },
  }
}
