import { ChatRunType } from '@baserow/modules/core/chatRuns/chatRunType'
import {
  RUN_FINISHED,
  RUN_STARTED,
} from '@baserow/modules/core/chatRuns/constants'

export const AGENT_RUN_TYPE = 'agent'

/** Refresh persisted messages as shared Core runs start and finish. */
export class AgentChatRunType extends ChatRunType {
  static getType() {
    return AGENT_RUN_TYPE
  }

  listeners = new Set()

  onRefresh(listener) {
    this.listeners.add(listener)
    return () => this.listeners.delete(listener)
  }

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
