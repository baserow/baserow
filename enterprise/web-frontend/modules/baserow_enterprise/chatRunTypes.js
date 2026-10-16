import { ChatRunType } from '@baserow/modules/core/chatRuns/chatRunType'
import {
  RUN_BASELINE,
  RUN_CANCEL_REQUESTED,
  RUN_CREATED,
  RUN_FINISHED,
  RUN_STARTED,
  RUN_STATUS,
  PROGRESS,
  TEXT_DELTA,
  isTerminalStatus,
} from '@baserow/modules/core/chatRuns/constants'
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
    return { navigations: [], reasoning: true, answering: false }
  }

  shouldRetainFollower(follower) {
    return follower.runId === getStoredOnboardingRunId()
  }

  refreshChat(chatId) {
    const store = this.app.$store
    const chat = store.getters['assistant/currentChat']
    if (chat?.chatId === chatId) {
      return store.dispatch('assistant/refreshCurrentChat')
    }
  }

  getRecordMetadata(record) {
    return record._run || super.getRecordMetadata(record)
  }

  getRecordEvent(record) {
    if (record.kind) return super.getRecordEvent(record)
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
    if (metadata.cancel_requested) {
      return { kind: RUN_CANCEL_REQUESTED, data: {} }
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
        return {
          kind: NAVIGATION,
          // The send response already filters navigation to its originating tab.
          data: { location: record.location, origin_tab_id: getTabId() },
        }
      default:
        return null
    }
  }

  foldEvent(view, event) {
    switch (event.kind) {
      case TEXT_DELTA:
      case RUN_BASELINE:
        return {
          ...view,
          reasoning: event.data.variant === 'ai/reasoning',
          answering: event.data.variant !== 'ai/reasoning',
        }
      case 'text.replace':
        return {
          ...view,
          text: event.data.text,
          reasoning: event.data.reasoning,
          answering: !event.data.reasoning,
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
        if (
          live &&
          event.data.origin_tab_id === getTabId() &&
          store.getters['assistant/isPanelOpen']
        ) {
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
