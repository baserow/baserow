import { ChatRunType } from '@baserow/modules/core/chatRuns/chatRunType'
import {
  RUN_FINISHED,
  RUN_STARTED,
} from '@baserow/modules/core/chatRuns/constants'

export const AGENT_RUN_TYPE = 'agent'

/** Agent replies; open conversations refresh when a reply starts, ends or may have started. */
export class AgentChatRunType extends ChatRunType {
  static getType() {
    return AGENT_RUN_TYPE
  }

  listeners = new Set()

  /**
   * @param {Function} listener Called with the id of the conversation to refresh
   *   and, when a reply just ended, the id of its run.
   * @returns {Function} Removes the listener.
   */
  onRefresh(listener) {
    this.listeners.add(listener)
    return () => this.listeners.delete(listener)
  }

  /**
   * @param {number} chatId The id of the conversation to refresh.
   * @param {string|null} finishedRunId The run whose reply just ended, if any.
   */
  refreshChat(chatId, finishedRunId = null) {
    this.listeners.forEach((listener) => listener(chatId, finishedRunId))
  }

  onEvent(follower, event) {
    if (event.kind === RUN_STARTED) this.refreshChat(follower.chatId)
    if (event.kind === RUN_FINISHED) {
      this.refreshChat(follower.chatId, follower.runId)
    }
  }
}
