import { Registerable } from '@baserow/modules/core/registry'

/** Product protocol and effects for the shared, panel-independent follower. */
export class ChatRunType extends Registerable {
  getInitialView() {
    return {}
  }

  /** Open an authenticated, read-only HTTP follower. Never send a prompt here. */
  openStream(follower, onRecord, signal) {
    throw new Error('A chat run type must implement its HTTP follower.')
  }

  getRecordMetadata(record) {
    return record
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
