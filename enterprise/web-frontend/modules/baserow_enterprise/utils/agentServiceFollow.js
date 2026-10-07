import { nextTick } from 'vue'
import isEqual from 'lodash/isEqual'

/**
 * A service form reads its default values once, when it mounts. These
 * helpers remount it when the saved service stops matching what the form
 * holds (an undo, another user's edit) while leaving it alone when a save
 * merely echoes the form's own values, so nobody loses focus mid-typing.
 *
 * Mix `serviceFollowState()` into `data()` and `serviceFollowMethods()` into
 * `methods`, record each `values-changed` payload in `formValues[item.id]`
 * and key the form with `serviceFormKey(item)`.
 */
// Derived by the backend, never edited by a form: the form echoes them as
// it received them, so a save that fills them in (a schema after a table
// was picked) is not a divergence worth remounting for.
const DERIVED_KEYS = new Set([
  'id',
  'type',
  'schema',
  'context_data',
  'context_data_schema',
  'sample_data',
])

export function serviceFollowState() {
  return {
    formValues: {},
    formKeys: {},
    serviceSeeds: {},
    // Item ids whose save this section is waiting on.
    ownSaves: {},
  }
}

export function serviceFollowMethods({ pendingFor }) {
  return {
    serviceFormKey(item) {
      return `${item.id}-${item.service_type}-${this.formKeys[item.id] || 0}`
    },
    /**
     * Wraps a save made by this section. The response normalizes what the
     * form sent (a formula gains its mode and version, a mapping its
     * `trashed` flag), which is this form's own work coming back, not a
     * change to follow; remounting on it would close whatever the user just
     * opened in the form.
     */
    async ownSave(item, save) {
      this.ownSaves[item.id] = (this.ownSaves[item.id] || 0) + 1
      try {
        return await save()
      } finally {
        // The store commit of the response queues the watcher that calls
        // `followService`; it runs on the next tick, so the mark must
        // outlive this promise.
        await nextTick()
        this.ownSaves[item.id] -= 1
      }
    },
    isSaving(item) {
      return (this.ownSaves[item.id] || 0) > 0
    },
    followService(item) {
      const service = item.service || {}
      const serialized = JSON.stringify(service)
      const previous = this.serviceSeeds[item.id]
      if (serialized === previous) {
        return
      }
      this.serviceSeeds[item.id] = serialized
      if (previous === undefined || this.ownSaves[item.id] > 0) {
        return
      }
      const held = {
        ...JSON.parse(previous),
        ...(this.formValues[item.id] || {}),
        ...pendingFor.call(this, item),
      }
      const diverged = Object.entries(service).some(
        ([key, value]) =>
          !DERIVED_KEYS.has(key) && key in held && !isEqual(held[key], value)
      )
      if (diverged) {
        this.formKeys[item.id] = (this.formKeys[item.id] || 0) + 1
        delete this.formValues[item.id]
      }
    },
  }
}
