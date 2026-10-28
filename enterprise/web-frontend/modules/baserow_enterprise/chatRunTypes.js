import { ChatRunType } from '@baserow/modules/core/chatRuns/chatRunType'
import {
  RUN_CREATED,
  RUN_FINISHED,
  RUN_STARTED,
  RUN_STATUS,
  PROGRESS,
  isTerminalStatus,
} from '@baserow/modules/core/chatRuns/constants'
import assistantService from '@baserow_enterprise/services/assistant'
import {
  getStoredOnboardingRunId,
  getTabId,
  storeOnboardingRunId,
} from '@baserow_enterprise/utils/assistantTabStorage'

export const ASSISTANT_RUN_TYPE = 'assistant'
const NAVIGATION = 'navigation'
const CHAT_TITLE = 'chat.title'
const DATABASE_TABLE = 'database-table'

/** Turns Kuma's JSON records into run events and applies their effects. */
export class AssistantChatRunType extends ChatRunType {
  static getType() {
    return ASSISTANT_RUN_TYPE
  }

  getInitialView() {
    return { navigations: [], reasoning: true }
  }

  shouldRetainFollower(follower) {
    return follower.runId === getStoredOnboardingRunId()
  }

  openStream(follower, onRecord, signal) {
    const chat = this.app.$store.state.assistant.chats.find(
      (chat) => chat.chatId === follower.chatId
    )
    const uuid = follower.context.chatUuid || chat?.id
    if (!uuid) throw new Error('The conversation is unavailable.')
    return assistantService(this.app.$client).resumeMessage(
      uuid,
      follower.runId,
      follower.cursor,
      onRecord,
      { tabId: getTabId(), signal }
    )
  }

  refreshChat(chatId) {
    const store = this.app.$store
    const chat = store.getters['assistant/currentChat']
    if (chat?.chatId === chatId) {
      return store.dispatch('assistant/refreshCurrentChat')
    }
  }

  getRecordMetadata(record) {
    return record._run
  }

  getRecordEvent(record) {
    const metadata = record._run || {}
    // Only a saved answer is an outcome; the follower re-checks bare statuses.
    if (
      isTerminalStatus(metadata.status) &&
      record.type === 'ai/message' &&
      record.id
    ) {
      return {
        kind: RUN_FINISHED,
        data: {
          status: metadata.status,
          error_code: metadata.error_code,
          message: record,
        },
      }
    }
    switch (record.type) {
      case 'human':
        return { kind: RUN_CREATED, data: { human_message: record } }
      case 'chat-run-state':
        return metadata.status === RUN_STATUS.RUNNING
          ? { kind: RUN_STARTED, data: {} }
          : null
      case 'ai/message':
      case 'ai/reasoning':
        return {
          kind: 'text.replace',
          data: {
            text: record.content,
            reasoning: record.type === 'ai/reasoning',
          },
        }
      case 'ai/thinking':
        return { kind: PROGRESS, data: { text: record.content } }
      case 'chat/title':
        return { kind: CHAT_TITLE, data: { title: record.content } }
      case 'ai/navigation':
        return { kind: NAVIGATION, data: { location: record.location } }
      default:
        return null
    }
  }

  foldEvent(view, event) {
    switch (event.kind) {
      case 'text.replace':
        return {
          ...view,
          text: event.data.text,
          reasoning: event.data.reasoning,
        }
      case NAVIGATION:
        return {
          ...view,
          navigations: [...view.navigations, event.data.location],
        }
      default:
        return view
    }
  }

  onEvent(follower, event, live) {
    const store = this.app.$store
    const { chatId } = follower
    switch (event.kind) {
      case RUN_CREATED:
        store.dispatch('assistant/forceAddRunMessage', {
          chatId,
          message: event.data.human_message,
        })
        break
      case CHAT_TITLE:
        store.dispatch('assistant/forceUpdateChatTitle', {
          chatId,
          title: event.data.title,
        })
        break
      case NAVIGATION:
        if (live && store.getters['assistant/isPanelOpen']) {
          store.dispatch('assistant/forceNavigate', event.data.location)
        }
        break
      case RUN_FINISHED: {
        const message = event.data.message || this.unsavedAnswer(follower)
        if (message) {
          store.dispatch('assistant/forceAddRunMessage', { chatId, message })
          if (typeof message.chat_title === 'string') {
            store.dispatch('assistant/forceUpdateChatTitle', {
              chatId,
              title: message.chat_title,
            })
          }
        }
        // Unlike live navigation, the onboarding table also opens on replay.
        if (follower.runId === getStoredOnboardingRunId()) {
          this.openOnboardingTable(follower)
        }
        break
      }
    }
  }

  unsavedAnswer(follower) {
    const { text, status, errorCode } = follower.view
    // A run that saved no answer still shows how it ended, even without text.
    return {
      id: `run-${follower.runId}`,
      type: 'ai/message',
      content: text,
      run_status: status,
      error_code: errorCode,
      can_submit_feedback: false,
    }
  }

  openOnboardingTable(follower) {
    const message = follower.view.message
    const table =
      message?.onboarding_target ||
      follower.view.navigations.find(
        (location) => location.type === DATABASE_TABLE
      )
    if (table && this.app.$store.getters['assistant/isPanelOpen']) {
      storeOnboardingRunId(null)
      this.app.$store.dispatch('assistant/forceNavigate', table)
    }
  }
}
