import { RUN_BASELINE } from '@baserow/modules/core/chatRuns/constants'
import { Registerable } from '@baserow/modules/core/registry'
import chatRunsService from '@baserow/modules/core/services/chatRuns'

/** Product protocol and effects for the shared, panel-independent follower. */
export class ChatRunType extends Registerable {
  getInitialView() {
    return {}
  }

  /**
   * Open an authenticated, read-only HTTP follower. Never send a prompt here.
   *
   * @param {object} follower The follower, with its `runId` and `cursor`.
   * @param {Function} onRecord Called with each record, in order.
   * @param {AbortSignal} signal Aborting closes the response.
   * @returns {Promise<object>} Settles when the response ends.
   */
  openStream(follower, onRecord, signal) {
    return chatRunsService(this.app.$client).stream(
      follower.runId,
      follower.cursor,
      onRecord,
      signal
    )
  }

  /**
   * A baseline rebuilds the output before the cursor it resumes from.
   *
   * @param {object} record A record read from the run's stream.
   * @returns {object} What the store reads to order the record: its `cursor`,
   *   whether it was `replayed`, and `reset` for a baseline.
   */
  getRecordMetadata(record) {
    return record.kind === RUN_BASELINE ? { ...record, reset: true } : record
  }

  getRecordEvent(record) {
    return record
  }

  foldEvent(view, event) {
    return view
  }

  /** Refresh product history to discover work started while this tab was idle. */
  refreshChat(chatId) {}

  /** Keep a completed outcome needed for a product handoff beyond the cache limit. */
  shouldRetainFollower(follower) {
    return false
  }

  /** State is folded first; live-only product effects belong here. */
  onEvent(follower, event, live) {}
}
