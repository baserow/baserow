import AgentApplicationService from '@baserow_enterprise/services/agentApplication'
import { uuid as uuidv4 } from '@baserow/modules/core/utils/string'

export const EVENT_TYPE = {
  HUMAN: 'human',
  SYSTEM: 'system',
  MESSAGE: 'ai/message',
  THINKING: 'ai/thinking',
  REASONING: 'ai/reasoning',
  ERROR: 'ai/error',
  STARTED: 'ai/started',
  CANCELLED: 'ai/cancelled',
  CHAT_TITLE: 'chat/title',
  TOOL_CALL: 'tool_call',
  TOOL: 'tool',
  ANSWER_CHUNK: 'ai/answer_chunk',
  APPROVAL_REQUEST: 'approval_request',
  APPROVAL_DECIDED: 'approval_decided',
  // Renderable marker in the event list pointing at tool approvals that live
  // in `toolApprovals`; their status can still change after the marker was
  // placed.
  APPROVAL_SET: 'approval_set',
}

/**
 * Maps a list of persisted chat messages to the flat list of renderable chat
 * events. AI messages are expanded into their intermediate artifact events
 * (reasoning steps and tool calls) followed by the final answer.
 */
export function messagesToEvents(messages, toolApprovals = []) {
  const approvalIdsByMessageId = new Map()
  for (const approval of toolApprovals) {
    if (!approvalIdsByMessageId.has(approval.message_id)) {
      approvalIdsByMessageId.set(approval.message_id, [])
    }
    approvalIdsByMessageId.get(approval.message_id).push(approval.id)
  }

  const events = []
  const placedApprovalIds = new Set()
  for (const message of messages) {
    if (message.role === 'human' || message.role === 'system') {
      const event = {
        type: message.role,
        id: message.id,
        content: message.content,
      }
      if (message.attachments?.length > 0) {
        event.attachments = message.attachments
      }
      events.push(event)
    } else {
      const artifactEvents = message.artifacts?.events || []
      for (const event of artifactEvents) {
        if (event.type === EVENT_TYPE.TOOL_CALL) {
          events.push({
            type: EVENT_TYPE.TOOL_CALL,
            id: event.id,
            tool_name: event.tool_name,
            args: event.args,
            result: event.result || null,
          })
        } else {
          events.push({ type: event.type, content: event.content })
        }
      }
      if (message.content) {
        events.push({ type: EVENT_TYPE.MESSAGE, content: message.content })
      }
      const approvalIds = approvalIdsByMessageId.get(message.id)
      if (approvalIds) {
        events.push({ type: EVENT_TYPE.APPROVAL_SET, ids: approvalIds })
        approvalIds.forEach((id) => placedApprovalIds.add(id))
      }
    }
  }
  // Approvals whose message is not part of the transcript (e.g. older than
  // the fetched page) must still be visible; append them at the end.
  const leftoverIds = toolApprovals
    .map((approval) => approval.id)
    .filter((id) => !placedApprovalIds.has(id))
  if (leftoverIds.length > 0) {
    events.push({ type: EVENT_TYPE.APPROVAL_SET, ids: leftoverIds })
  }
  return events
}

export const state = () => ({
  currentChatUuid: null,
  chatId: null,
  events: [],
  sending: false,
  running: false,
  runningMessage: '',
  currentMessageId: null,
  source: 'manual',
  applicationId: null,
  // Realtime events that arrived before the chat id was known (the POST
  // response of a brand-new conversation may still be in flight).
  pendingEvents: [],
  // Full tool approval history of the current chat; `approval_set` events
  // reference these by id so a decision updates the rendered card in place.
  toolApprovals: [],
  awaitingApproval: false,
  hasError: false,
})

export const mutations = {
  SET_CURRENT_CHAT_UUID(state, uuid) {
    state.currentChatUuid = uuid
  },
  SET_CHAT_ID(state, id) {
    state.chatId = id
  },
  SET_EVENTS(state, events) {
    state.events = events
  },
  ADD_EVENT(state, event) {
    state.events.push(event)
  },
  UPDATE_EVENT(state, { index, values }) {
    state.events.splice(index, 1, { ...state.events[index], ...values })
  },
  REMOVE_EVENT(state, index) {
    state.events.splice(index, 1)
  },
  SET_SENDING(state, value) {
    state.sending = value
  },
  SET_RUNNING(state, value) {
    state.running = value
  },
  SET_RUNNING_MESSAGE(state, message) {
    state.runningMessage = message
  },
  SET_CURRENT_MESSAGE_ID(state, messageId) {
    state.currentMessageId = messageId
  },
  SET_SOURCE(state, source) {
    state.source = source
  },
  SET_APPLICATION_ID(state, applicationId) {
    state.applicationId = applicationId
  },
  ADD_PENDING_EVENT(state, pendingEvent) {
    state.pendingEvents.push(pendingEvent)
  },
  CLEAR_PENDING_EVENTS(state) {
    state.pendingEvents = []
  },
  SET_TOOL_APPROVALS(state, toolApprovals) {
    state.toolApprovals = toolApprovals
  },
  UPSERT_TOOL_APPROVALS(state, toolApprovals) {
    for (const approval of toolApprovals) {
      const index = state.toolApprovals.findIndex((a) => a.id === approval.id)
      if (index !== -1) {
        state.toolApprovals.splice(index, 1, {
          ...state.toolApprovals[index],
          ...approval,
        })
      } else {
        state.toolApprovals.push(approval)
      }
    }
  },
  UPDATE_TOOL_APPROVAL(state, { id, values }) {
    const index = state.toolApprovals.findIndex((a) => a.id === id)
    if (index !== -1) {
      state.toolApprovals.splice(index, 1, {
        ...state.toolApprovals[index],
        ...values,
      })
    }
  },
  SET_AWAITING_APPROVAL(state, value) {
    state.awaitingApproval = value
  },
  SET_HAS_ERROR(state, value) {
    state.hasError = value
  },
}

export const actions = {
  async openConversation({ commit }, { applicationId, chatUuid }) {
    const { data } = await AgentApplicationService(
      this.$client
    ).getChatMessages(applicationId, chatUuid)
    const toolApprovals = data.tool_approvals || []
    commit('SET_CURRENT_CHAT_UUID', chatUuid)
    commit('SET_CHAT_ID', data.chat.id)
    commit('SET_TOOL_APPROVALS', toolApprovals)
    commit('SET_EVENTS', messagesToEvents(data.messages, toolApprovals))
    commit(
      'SET_RUNNING',
      ['in_progress', 'canceling'].includes(data.chat.status)
    )
    commit('SET_AWAITING_APPROVAL', data.chat.status === 'awaiting_approval')
    commit('SET_HAS_ERROR', data.chat.status === 'error')
    commit('SET_RUNNING_MESSAGE', '')
    commit('SET_CURRENT_MESSAGE_ID', null)
    commit('SET_SOURCE', data.chat.source || 'manual')
    commit('SET_APPLICATION_ID', applicationId)
    commit('CLEAR_PENDING_EVENTS')
  },
  newConversation({ commit }) {
    commit('SET_CURRENT_CHAT_UUID', uuidv4())
    commit('SET_CHAT_ID', null)
    commit('SET_EVENTS', [])
    commit('SET_RUNNING', false)
    commit('SET_AWAITING_APPROVAL', false)
    commit('SET_HAS_ERROR', false)
    commit('SET_TOOL_APPROVALS', [])
    commit('SET_RUNNING_MESSAGE', '')
    commit('SET_CURRENT_MESSAGE_ID', null)
    commit('SET_SOURCE', 'manual')
    commit('CLEAR_PENDING_EVENTS')
  },
  async sendMessage(
    { commit, dispatch, state },
    { application, content, userFiles = [] }
  ) {
    if (!state.currentChatUuid) {
      await dispatch('newConversation')
    }

    const optimisticEvent = { type: EVENT_TYPE.HUMAN, content }
    if (userFiles.length > 0) {
      optimisticEvent.attachments = userFiles
    }
    commit('ADD_EVENT', optimisticEvent)
    commit('SET_SENDING', true)
    commit('SET_APPLICATION_ID', application.id)

    try {
      const { data } = await AgentApplicationService(this.$client).sendMessage(
        application.id,
        state.currentChatUuid,
        content,
        userFiles
      )
      commit('SET_CHAT_ID', data.id)
      commit('SET_RUNNING', true)
      dispatch('agentHistory/forceUpdateChat', { chat: data }, { root: true })

      // The sender also receives its own human message back over the
      // websocket; tagging the optimistic event with the persisted message id
      // lets that echo be recognized and skipped.
      const optimisticIndex = state.events.indexOf(optimisticEvent)
      if (optimisticIndex !== -1 && data.prompt_message_id) {
        commit('UPDATE_EVENT', {
          index: optimisticIndex,
          values: { id: data.prompt_message_id },
        })
      }
      return data
    } catch (error) {
      const index = state.events.indexOf(optimisticEvent)
      if (index !== -1) {
        commit('REMOVE_EVENT', index)
      }
      throw error
    } finally {
      commit('SET_SENDING', false)
      // Apply the realtime events that raced the POST response, now that the
      // chat id is known and the optimistic event carries its persisted id
      // (so the sender's own echo is skipped). Events of other chats are
      // discarded.
      const buffered = [...state.pendingEvents]
      commit('CLEAR_PENDING_EVENTS')
      for (const pendingEvent of buffered) {
        if (state.chatId !== null && pendingEvent.chatId === state.chatId) {
          await dispatch('handleRealtimeEvent', pendingEvent)
        }
      }
    }
  },
  async cancel({ state }, { chatUuid }) {
    await AgentApplicationService(this.$client).cancelChat(
      chatUuid || state.currentChatUuid
    )
  },
  async retryChat({ commit, state }) {
    const { data } = await AgentApplicationService(this.$client).retryChat(
      state.currentChatUuid
    )
    commit('SET_RUNNING', true)
    commit('SET_HAS_ERROR', false)
    return data
  },
  async decideApprovals({ commit, state }, { decisions }) {
    const { data } = await AgentApplicationService(
      this.$client
    ).decideApprovals(state.currentChatUuid, decisions)
    commit('UPSERT_TOOL_APPROVALS', data)
    return data
  },
  /**
   * Safety net for missed realtime chunks: when the current chat reaches a
   * terminal status while this store still thinks it is running, or paused
   * for tool approval without the approval_request event having arrived, the
   * transcript (including the approvals) is refetched once.
   */
  async handleChatUpdated({ dispatch, state }, { chat }) {
    if (chat.id !== state.chatId || state.applicationId === null) {
      return
    }
    const missedTerminal =
      ['idle', 'error'].includes(chat.status) &&
      (state.running || state.awaitingApproval)
    const missedApproval =
      chat.status === 'awaiting_approval' && !state.awaitingApproval
    if (!missedTerminal && !missedApproval) {
      return
    }
    await dispatch('openConversation', {
      applicationId: state.applicationId,
      chatUuid: state.currentChatUuid,
    })
  },
  /**
   * When the open conversation is deleted (possibly by another user), reset
   * to a fresh empty conversation.
   */
  handleChatDeleted({ dispatch, state }, { chatId }) {
    if (chatId === state.chatId) {
      dispatch('newConversation')
    }
  },
  handleRealtimeEvent(
    { commit, dispatch, state, rootGetters },
    { chatId, event }
  ) {
    // While a message POST is in flight the events racing it are buffered:
    // for a brand-new conversation the chat id is unknown until the response
    // arrives, and for an existing one the sender's own human-message echo
    // would arrive before the optimistic event is tagged with its persisted
    // id, duplicating the message.
    if (state.sending && (state.chatId === null || chatId === state.chatId)) {
      commit('ADD_PENDING_EVENT', { chatId, event })
      return
    }

    // Only apply events that belong to the currently opened conversation.
    if (state.chatId === null || chatId !== state.chatId) {
      return
    }

    switch (event.type) {
      case EVENT_TYPE.HUMAN:
      case EVENT_TYPE.SYSTEM: {
        // Skip the echo of a message this client sent itself.
        const alreadyPresent =
          event.id !== undefined &&
          state.events.some((existing) => existing.id === event.id)
        if (!alreadyPresent) {
          const newEvent = {
            type: event.type,
            id: event.id,
            content: event.content,
          }
          if (event.attachments?.length > 0) {
            newEvent.attachments = event.attachments
          }
          commit('ADD_EVENT', newEvent)
        }
        break
      }
      case EVENT_TYPE.STARTED:
        commit('SET_CURRENT_MESSAGE_ID', event.message_id)
        commit('SET_RUNNING', true)
        // A run resuming after its approvals were decided is no longer
        // paused.
        commit('SET_AWAITING_APPROVAL', false)
        commit('SET_HAS_ERROR', false)
        break
      case EVENT_TYPE.THINKING:
        commit('SET_RUNNING_MESSAGE', event.content)
        break
      case EVENT_TYPE.REASONING: {
        // The full reasoning content is sent every time, so the last reasoning
        // event must be replaced instead of appended to.
        const lastIndex = state.events.length - 1
        if (state.events[lastIndex]?.type === EVENT_TYPE.REASONING) {
          commit('UPDATE_EVENT', {
            index: lastIndex,
            values: { content: event.content },
          })
        } else {
          commit('ADD_EVENT', {
            type: EVENT_TYPE.REASONING,
            content: event.content,
          })
        }
        break
      }
      case EVENT_TYPE.ANSWER_CHUNK: {
        // The final answer streaming in; it types into a partial message
        // bubble that the final `ai/message` event replaces.
        const lastIndex = state.events.length - 1
        const lastEvent = state.events[lastIndex]
        if (lastEvent?.type === EVENT_TYPE.MESSAGE && lastEvent.partial) {
          commit('UPDATE_EVENT', {
            index: lastIndex,
            values: { content: event.content },
          })
        } else {
          commit('ADD_EVENT', {
            type: EVENT_TYPE.MESSAGE,
            content: event.content,
            partial: true,
          })
        }
        break
      }
      case EVENT_TYPE.MESSAGE: {
        const lastIndex = state.events.length - 1
        const lastEvent = state.events[lastIndex]
        if (lastEvent?.type === EVENT_TYPE.MESSAGE && lastEvent.partial) {
          // Finalize the streamed partial answer in place.
          commit('UPDATE_EVENT', {
            index: lastIndex,
            values: {
              content: event.content,
              sources: event.sources,
              partial: false,
            },
          })
        } else if (
          // A terminal-status refetch can already contain the final answer,
          // in which case a late final event must not duplicate it.
          !(
            lastEvent?.type === EVENT_TYPE.MESSAGE &&
            lastEvent.content === event.content
          )
        ) {
          commit('ADD_EVENT', {
            type: EVENT_TYPE.MESSAGE,
            content: event.content,
            sources: event.sources,
          })
        }
        commit('SET_RUNNING', false)
        commit('SET_AWAITING_APPROVAL', false)
        commit('SET_RUNNING_MESSAGE', '')
        commit('SET_CURRENT_MESSAGE_ID', null)
        break
      }
      case EVENT_TYPE.ERROR:
        commit('ADD_EVENT', { type: EVENT_TYPE.ERROR, content: event.content })
        commit('SET_HAS_ERROR', true)
        commit('SET_RUNNING', false)
        commit('SET_AWAITING_APPROVAL', false)
        commit('SET_RUNNING_MESSAGE', '')
        commit('SET_CURRENT_MESSAGE_ID', null)
        break
      case EVENT_TYPE.CANCELLED:
        commit('ADD_EVENT', { type: EVENT_TYPE.CANCELLED })
        commit('SET_RUNNING', false)
        commit('SET_AWAITING_APPROVAL', false)
        commit('SET_RUNNING_MESSAGE', '')
        commit('SET_CURRENT_MESSAGE_ID', null)
        break
      case EVENT_TYPE.CHAT_TITLE: {
        const existingChat = rootGetters['agentHistory/getChats'].find(
          (chat) => chat.id === chatId
        )
        if (existingChat) {
          dispatch(
            'agentHistory/forceUpdateChat',
            { chat: { ...existingChat, title: event.content } },
            { root: true }
          )
        }
        break
      }
      case EVENT_TYPE.TOOL_CALL:
        commit('ADD_EVENT', {
          type: EVENT_TYPE.TOOL_CALL,
          id: event.id,
          tool_name: event.tool_name,
          args: event.args,
          result: null,
        })
        break
      case EVENT_TYPE.TOOL: {
        const index = state.events.findIndex(
          (e) => e.type === EVENT_TYPE.TOOL_CALL && e.id === event.id
        )
        if (index !== -1) {
          commit('UPDATE_EVENT', {
            index,
            values: {
              result: { status: event.status, content: event.content },
            },
          })
        }
        break
      }
      case EVENT_TYPE.APPROVAL_REQUEST: {
        commit('UPSERT_TOOL_APPROVALS', event.approvals)
        // An `agent_chat_updated` refetch that raced this event may already
        // have placed a card for these approvals.
        const placedIds = new Set(
          state.events
            .filter((e) => e.type === EVENT_TYPE.APPROVAL_SET)
            .flatMap((e) => e.ids)
        )
        const newIds = event.approvals
          .map((approval) => approval.id)
          .filter((id) => !placedIds.has(id))
        if (newIds.length > 0) {
          commit('ADD_EVENT', { type: EVENT_TYPE.APPROVAL_SET, ids: newIds })
        }
        commit('SET_AWAITING_APPROVAL', true)
        commit('SET_RUNNING', false)
        commit('SET_RUNNING_MESSAGE', '')
        break
      }
      case EVENT_TYPE.APPROVAL_DECIDED:
        commit('UPDATE_TOOL_APPROVAL', {
          id: event.id,
          values: { status: event.status, reason: event.reason || '' },
        })
        break
    }
  },
}

export const getters = {
  hasError(state) {
    return state.hasError
  },
  getCurrentChatUuid: (state) => state.currentChatUuid,
  getChatId: (state) => state.chatId,
  getEvents: (state) => state.events,
  isSending: (state) => state.sending,
  isRunning: (state) => state.running,
  getRunningMessage: (state) => state.runningMessage,
  getSource: (state) => state.source,
  getToolApprovals: (state) => state.toolApprovals,
  getPendingToolApprovals: (state) =>
    state.toolApprovals.filter((approval) => approval.status === 'pending'),
  isAwaitingApproval: (state) => state.awaitingApproval,
}

export default {
  namespaced: true,
  state,
  getters,
  actions,
  mutations,
}
