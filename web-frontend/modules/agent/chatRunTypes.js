import { ChatRunType } from '@baserow/modules/core/chatRuns/chatRunType'
import { RUN_FINISHED } from '@baserow/modules/core/chatRuns/constants'

export const AGENT_RUN_TYPE = 'agent'

/** Tell the open Agent page when a reply ends or its chat needs a re-read. */
export class AgentChatRunType extends ChatRunType {
  static getType() {
    return AGENT_RUN_TYPE
  }

  listeners = new Set()

  listen(listener) {
    this.listeners.add(listener)
    return () => this.listeners.delete(listener)
  }

  refreshChat(chatId) {
    this.listeners.forEach((listener) => listener.chatReconnected(chatId))
  }

  onEvent(follower, event) {
    if (event.kind === RUN_FINISHED) {
      this.listeners.forEach((listener) => listener.replyFinished(follower))
    }
  }
}
