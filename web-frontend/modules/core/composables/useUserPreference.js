import { computed } from 'vue'
import { useStore } from 'vuex'

import { notifyIf } from '@baserow/modules/core/utils/error'

/**
 * A writable ref backed by a registered user preference, so a setting survives
 * reloads and follows the user across devices. Reading straight from the store
 * keeps the value in sync when an optimistic update is rolled back after a
 * failed request.
 *
 * @param {string} key The type of a backend registered user preference.
 * @param {*} fallback Used when the session predates the preference.
 * @returns {import('vue').WritableComputedRef} The preference value.
 */
export function useUserPreference(key, fallback = undefined) {
  const store = useStore()
  return computed({
    get: () => store.getters['auth/getUserPreference'](key) ?? fallback,
    set: (value) => {
      store
        .dispatch('auth/updateUserPreferences', { [key]: value })
        .catch((error) => {
          notifyIf(error, 'user')
        })
    },
  })
}
