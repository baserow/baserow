/**
 * The default realtime-tracking metadata added to a store item's `_` object.
 *
 * `realtimeVersion` is a monotonic counter that is incremented every time the
 * item is updated by a realtime event (an undo/redo, or a change from another
 * user). `viaRealtime` records whether the most recent update came from
 * realtime. Together they let an open form decide whether an external change
 * warrants resetting itself, without conflating it with the user's own local
 * edits (which never touch these fields).
 */
export const realtimeMetadata = () => ({
  viaRealtime: false,
  realtimeVersion: 0,
})

/**
 * Updates a store item's realtime metadata after it has been mutated. When
 * `viaRealtime` is true, the item is flagged and its version is bumped so that
 * watchers can react to it. When false (a local edit), the flag is cleared
 * without touching the version, so local edits never trigger a form reset.
 *
 * @param {Object} item A store item carrying an `_` metadata object.
 * @param {Boolean} viaRealtime Whether the update originated from realtime.
 */
export const markRealtimeMetadata = (item, viaRealtime = false) => {
  if (!item?._) {
    return
  }
  item._.viaRealtime = viaRealtime
  if (viaRealtime) {
    item._.realtimeVersion = (item._.realtimeVersion || 0) + 1
  }
}
