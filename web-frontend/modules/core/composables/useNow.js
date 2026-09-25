import { inject, onBeforeUnmount, onMounted, provide, ref } from 'vue'

export const nowKey = Symbol('now')

/**
 * A timestamp that keeps ticking while the page is open, so relative dates
 * computed from it keep ageing instead of freezing at the moment they were
 * rendered. One page provides it and every card reads the same value, so a
 * long list costs a single timer.
 *
 * @param {number} intervalMs How often the value advances.
 * @returns {import('vue').Ref<number>} The current time in milliseconds.
 */
export function provideNow(intervalMs = 60 * 1000) {
  const now = ref(Date.now())
  let timer = null
  onMounted(() => {
    timer = setInterval(() => {
      now.value = Date.now()
    }, intervalMs)
  })
  onBeforeUnmount(() => clearInterval(timer))
  provide(nowKey, now)
  return now
}

/**
 * @returns {import('vue').Ref<number>|null} The provided clock, or `null`
 *   outside of a page that provides one.
 */
export function injectNow() {
  return inject(nowKey, null)
}
