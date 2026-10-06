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
export function serviceFollowState() {
  return {
    formValues: {},
    formKeys: {},
    serviceSeeds: {},
  }
}

export function serviceFollowMethods({ pendingFor }) {
  return {
    serviceFormKey(item) {
      return `${item.id}-${item.service_type}-${this.formKeys[item.id] || 0}`
    },
    followService(item) {
      const service = item.service || {}
      const serialized = JSON.stringify(service)
      const previous = this.serviceSeeds[item.id]
      if (serialized === previous) {
        return
      }
      this.serviceSeeds[item.id] = serialized
      if (previous === undefined) {
        return
      }
      const held = {
        ...JSON.parse(previous),
        ...(this.formValues[item.id] || {}),
        ...pendingFor.call(this, item),
      }
      const diverged = Object.entries(service).some(
        ([key, value]) => key in held && !isEqual(held[key], value)
      )
      if (diverged) {
        this.formKeys[item.id] = (this.formKeys[item.id] || 0) + 1
        delete this.formValues[item.id]
      }
    },
  }
}
