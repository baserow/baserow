import assistant from '@baserow_enterprise/services/assistant'
import { ASSISTANT_RUN_TYPE } from '@baserow_enterprise/chatRunTypes'
import { usesBackgroundRuns } from '@baserow_enterprise/utils/assistant'
import {
  getStoredChatUuid,
  getTabId,
  storeChatUuid,
  getStoredOnboardingRunId,
} from '@baserow_enterprise/utils/assistantTabStorage'
import { uuid as uuidv4 } from '@baserow/modules/core/utils/string'
import { isTerminalStatus } from '@baserow/modules/core/chatRuns/constants'

const MESSAGE_TYPE = {
  MESSAGE: 'ai/message', // The main AI message content, both for partial and final answers
  THINKING: 'ai/thinking', // Update the status bar in the UI
  REASONING: 'ai/reasoning', // Show reasoning steps before the final answer
  NAVIGATION: 'ai/navigation', // Navigate the user to a specific location in the UI
  ERROR: 'ai/error', // Show an error message
  CHAT_TITLE: 'chat/title', // Update the chat title
  AI_STARTED: 'ai/started', // Indicates the AI started generating a response
  AI_CANCELLED: 'ai/cancelled', // Indicates the AI generation was cancelled
}

function parseMessage(message) {
  return {
    role: message.type === 'human' ? 'human' : 'ai',
    loading: false,
    ...message,
  }
}

/**
 * The answer a run is still writing, shown after the chat's saved messages.
 * Its text reads as reasoning until the saved answer replaces it.
 */
function inFlightMessage(follower) {
  const { text, reasoning } = follower.view
  return {
    id: `run-${follower.runId}`,
    role: 'ai',
    content: text,
    loading: !text,
    reasoning: Boolean(text) && reasoning,
    can_submit_feedback: false,
  }
}

const CHAT_RUN_IN_PROGRESS = 'ERROR_CHAT_RUN_IN_PROGRESS'
// The backend has its flag off, or predates the send endpoint.
const RUNS_UNAVAILABLE_CODES = ['ERROR_FEATURE_DISABLED', 'URL_NOT_FOUND']

/**
 * How Kuma took a message: a run answers it, the chat still answers another
 * one, or it was refused, which the chat explains.
 */
export const SEND_OUTCOME = {
  ACCEPTED: 'accepted',
  BUSY: 'busy',
  FAILED: 'failed',
}

/**
 * @returns {string} Why Kuma refused to start answering, for the chat.
 */
function refusalMessage(error, i18n) {
  const handler = error.handler
  if (handler?.isTooManyRequests()) {
    return i18n.t('assistant.runLimitReached')
  }
  // The UI builds the rest of the body, so only the message's length can fail.
  if (handler?.hasRequestBodyValidationError()) {
    return i18n.t('assistant.runMessageTooLong')
  }
  if (RUNS_UNAVAILABLE_CODES.includes(handler?.code)) {
    return i18n.t('assistant.runFailedToStart')
  }
  const detail = handler?.detail
  return typeof detail === 'string' && detail
    ? detail
    : i18n.t('assistant.runFailedToStart')
}

export const state = () => ({
  currentChatId: null,
  messages: [],
  chats: [],
  isLoadingChats: false,
  uiLocation: null,
  uiLocationHistory: [],
  // A message asked for from outside the panel, like the prompt on the workspace
  // homepage. The panel picks it up when it mounts, which is the only moment it
  // can send it, and it survives `reset` for that reason.
  pendingPrompt: null,
  // Kuma only navigates a tab whose panel is open.
  panelOpen: false,
})

export const mutations = {
  SET_CURRENT_CHAT_ID(state, id) {
    state.currentChatId = id
  },

  SET_PENDING_PROMPT(state, prompt) {
    state.pendingPrompt = prompt
  },

  SET_CHAT_LOADING(state, { chat, value }) {
    chat.loading = value
  },

  SET_ASSISTANT_RUNNING(state, { chat, value }) {
    chat.running = value
  },

  SET_ASSISTANT_RUNNING_MESSAGE(state, { chat, message = '' }) {
    chat.runningMessage = message
  },

  SET_ASSISTANT_CANCELLING(state, { chat, value }) {
    chat.cancelling = value
  },

  SET_MESSAGES(state, messages) {
    state.messages = messages
  },

  ADD_MESSAGE(state, message) {
    state.messages.push(message)
  },

  UPDATE_MESSAGE(state, { id, updates }) {
    const messageIndex = state.messages.findIndex(
      (m) => m.id === id || m._uuid === id
    )
    if (messageIndex !== -1) {
      const updatedMessage = {
        ...state.messages[messageIndex],
        ...updates,
      }
      state.messages.splice(messageIndex, 1, updatedMessage)
    }
  },

  CLEAR_MESSAGES(state) {
    state.messages = []
  },

  SET_CURRENT_MESSAGE_ID(state, { chat, messageId }) {
    chat.currentMessageId = messageId
  },

  SET_CHATS(state, chats) {
    const fetched = chats.map((chat) => ({
      id: chat.uuid,
      chatId: chat.chat_id ?? null,
      title: chat.title,
      createdAt: chat.created_on,
      updatedAt: chat.updated_on,
      loading: false,
      running: false,
      reasoning: false,
      cancelling: false,
      currentMessageId: null,
    }))
    // A new chat is saved with its first message, so the fetched list can miss it.
    const current = state.chats.find((c) => c.id === state.currentChatId)
    const unsaved =
      current && !fetched.some((c) => c.id === current.id) ? [current] : []
    state.chats = [...unsaved, ...fetched]
  },

  SET_CHATS_LOADING(state, loading) {
    state.isLoadingChats = loading
  },

  REMOVE_CHAT(state, chatId) {
    const index = state.chats.findIndex((chat) => chat.id === chatId)
    if (index > -1) {
      state.chats.splice(index, 1)
    }
  },

  ADD_CHAT(state, chat) {
    state.chats = [chat, ...state.chats]
  },

  UPDATE_CHAT(state, { id, updates }) {
    const chat = state.chats.find((c) => c.id === id)
    if (chat) {
      Object.assign(chat, updates)
    }
  },

  SET_PANEL_OPEN(state, value) {
    state.panelOpen = value
  },

  UPSERT_MESSAGE(state, message) {
    const index = state.messages.findIndex((m) => m.id === message.id)
    if (index !== -1) {
      state.messages.splice(index, 1, message)
      return
    }
    // Saved ids grow in chat order, so a late answer goes back to its place.
    const next = Number.isInteger(message.id)
      ? state.messages.findIndex(
          (m) => Number.isInteger(m.id) && m.id > message.id
        )
      : -1
    if (next === -1) {
      state.messages.push(message)
    } else {
      state.messages.splice(next, 0, message)
    }
  },

  REMOVE_MESSAGE(state, id) {
    const index = state.messages.findIndex((m) => m.id === id)
    if (index !== -1) {
      state.messages.splice(index, 1)
    }
  },

  SET_UI_LOCATION(state, location) {
    state.uiLocation = location || null
    state.uiLocationHistory.push(location)
  },

  CLEAR_UI_LOCATION_HISTORY(state) {
    state.uiLocationHistory = []
  },
}

export const actions = {
  setPendingPrompt({ commit }, prompt) {
    commit('SET_PENDING_PROMPT', prompt)
  },

  setPanelOpen({ commit, rootGetters }, value) {
    commit('SET_PANEL_OPEN', value)
    const runId = getStoredOnboardingRunId()
    const follower = runId && rootGetters['chatRuns/getFollower'](runId)
    if (value && follower?.finished) {
      this.$registry
        .get('chatRunType', ASSISTANT_RUN_TYPE)
        .openOnboardingTable(follower)
    }
  },

  /**
   * Shows a message a run saved, by id so it never shows twice, when the
   * run's chat is the one shown.
   */
  forceAddRunMessage({ commit, getters }, { chatId, message }) {
    if (getters.currentChat?.chatId === chatId) {
      commit('UPSERT_MESSAGE', parseMessage(message))
    }
  },

  forceUpdateChatTitle({ commit, state }, { chatId, title }) {
    const chat = state.chats.find((c) => c.chatId === chatId)
    if (chat) {
      commit('UPDATE_CHAT', { id: chat.id, updates: { title } })
    }
  },

  forceNavigate({ commit }, location) {
    commit('SET_UI_LOCATION', location)
  },

  reset({ commit }) {
    commit('CLEAR_MESSAGES')
    commit('CLEAR_UI_LOCATION_HISTORY')
    commit('SET_CURRENT_CHAT_ID', null)
    commit('SET_CHATS', [])
  },

  createChat({ commit }) {
    const id = uuidv4()
    commit('ADD_CHAT', { id, title: '' })
    commit('CLEAR_MESSAGES')
    commit('CLEAR_UI_LOCATION_HISTORY')
    commit('SET_CURRENT_CHAT_ID', id)

    return id
  },

  async selectChat({ commit, dispatch }, chat) {
    const { $client } = this
    commit('SET_CHAT_LOADING', { chat, value: true })

    try {
      const snapshot = await assistant($client).fetchChatMessages(chat.id)
      commit('SET_CURRENT_CHAT_ID', chat.id)
      commit('SET_MESSAGES', snapshot.messages.map(parseMessage))
      if (usesBackgroundRuns(this.app)) {
        await dispatch('followChatRuns', { chat, snapshot })
      }
    } finally {
      commit('SET_CHAT_LOADING', { chat, value: false })
    }
  },

  /**
   * Shows a chat's runs: the answer of a run that finished while the snapshot
   * was read, and the run still answering, followed from the snapshot so its
   * past side effects aren't replayed.
   */
  async followChatRuns(
    { commit, dispatch, rootGetters },
    { chat, snapshot, subscribe = true }
  ) {
    const chatId = snapshot.chat_id
    commit('UPDATE_CHAT', {
      id: chat.id,
      updates: {
        chatId,
        ...(typeof snapshot.chat_title === 'string'
          ? { title: snapshot.chat_title }
          : {}),
      },
    })
    storeChatUuid(chat.id)
    if (subscribe) {
      await dispatch(
        'chatRuns/subscribeToChat',
        { runType: ASSISTANT_RUN_TYPE, chatId },
        { root: true }
      )
    }
    const historyMessages = new Map(
      snapshot.messages.map((message) => [message.id, message])
    )
    const latest = snapshot.latest_run
    if (latest && isTerminalStatus(latest.status)) {
      await dispatch(
        'chatRuns/follow',
        {
          runId: latest.id,
          runType: ASSISTANT_RUN_TYPE,
          chatId,
          context: { chatUuid: chat.id },
          attach: false,
        },
        { root: true }
      )
      await dispatch(
        'chatRuns/applySnapshot',
        {
          runId: latest.id,
          snapshot: {
            ...latest,
            message: historyMessages.get(latest.message?.id) || latest.message,
          },
        },
        { root: true }
      )
    }
    if (snapshot.active_run) {
      await dispatch(
        'chatRuns/follow',
        {
          runId: snapshot.active_run.id,
          runType: ASSISTANT_RUN_TYPE,
          chatId,
          context: { chatUuid: chat.id },
        },
        { root: true }
      )
    }
    // A final response can race the history read. Fill missing messages by saved
    // ID, while keeping newer mutable fields such as feedback from fresh history.
    const saved = rootGetters['chatRuns/getFollowersOfChat'](
      ASSISTANT_RUN_TYPE,
      chatId
    ).filter((follower) => follower.finished && follower.view.message)
    for (const follower of saved) {
      if (!historyMessages.has(follower.view.message.id)) {
        commit('UPSERT_MESSAGE', parseMessage(follower.view.message))
      }
    }
  },

  async refreshCurrentChat({ state, commit, dispatch }) {
    const chat = state.chats.find((c) => c.id === state.currentChatId)
    if (!chat || !usesBackgroundRuns(this.app)) return
    try {
      const snapshot = await assistant(this.$client).fetchChatMessages(chat.id)
      if (state.currentChatId !== chat.id) return
      commit('SET_MESSAGES', snapshot.messages.map(parseMessage))
      await dispatch('followChatRuns', { chat, snapshot, subscribe: false })
    } catch (error) {
      if (!error.handler && !error.response) throw error
    }
  },

  /**
   * Reopens the chat this tab showed before a reload, unless a chat was
   * chosen meanwhile. A chat that can't be read is forgotten.
   *
   * @throws Anything but a failed request, such as a run type's bug.
   */
  async restoreOpenChat({ state, dispatch }) {
    if (!usesBackgroundRuns(this.app) || state.currentChatId) {
      return
    }
    const chat = state.chats.find((c) => c.id === getStoredChatUuid())
    if (!chat) {
      return
    }
    try {
      await dispatch('selectChat', chat)
    } catch (error) {
      if (!error.handler) {
        throw error
      }
      storeChatUuid(null)
    }
  },

  clearChat({ commit }) {
    commit('CLEAR_MESSAGES')
    commit('CLEAR_UI_LOCATION_HISTORY')
    commit('SET_CURRENT_CHAT_ID', null)
    if (usesBackgroundRuns(this.app)) {
      storeChatUuid(null)
    }
  },

  async fetchChats({ commit }, workspaceId) {
    const { $client } = this
    commit('SET_CHATS_LOADING', true)

    try {
      const { results: chats } =
        await assistant($client).fetchChats(workspaceId)
      commit('SET_CHATS', chats)
    } finally {
      commit('SET_CHATS_LOADING', false)
    }
  },

  /**
   * Start the existing streamed POST and hand ownership to the shared follower as
   * soon as its committed run identity arrives. The original response stays open.
   * Early connection loss is recovered from history, never by resending content.
   */
  async startRun({ state, commit, dispatch, getters }, { message, workspace }) {
    let chat = state.chats.find((c) => c.id === state.currentChatId)
    if (!chat) {
      await dispatch('createChat', workspace.id)
      chat = state.chats.find((c) => c.id === state.currentChatId)
    }
    const draftId = uuidv4()
    const previousIds = new Set(state.messages.map((m) => m.id))
    commit('ADD_MESSAGE', {
      id: draftId,
      role: 'human',
      content: message,
      loading: false,
    })
    commit('SET_ASSISTANT_RUNNING', { chat, value: true })
    const controller = new AbortController()
    // Before identity arrives, this response is not yet owned by the shared
    // follower. Logout must also close it and reject already queued records.
    const unwatchAuth = this.watch(
      (_, rootGetters) => rootGetters['auth/isAuthenticated'],
      (authenticated) => {
        if (!authenticated) controller.abort()
      },
      { flush: 'sync' }
    )
    let runId = null
    let originalAdopted = false
    let legacyId = null
    let resolveAccepted
    const accepted = new Promise((resolve) => {
      resolveAccepted = resolve
    })
    const register = async (metadata, attach = false) => {
      if (runId) return
      runId = metadata.id
      originalAdopted = !attach
      const chatId = metadata.chat_id
      commit('UPDATE_CHAT', { id: chat.id, updates: { chatId } })
      await dispatch(
        'chatRuns/follow',
        {
          runId,
          runType: ASSISTANT_RUN_TYPE,
          chatId,
          context: { chatUuid: chat.id },
          controller: attach ? null : controller,
          attach,
        },
        { root: true }
      )
      if (state.currentChatId === chat.id) {
        if (legacyId) commit('REMOVE_MESSAGE', legacyId)
        commit('REMOVE_MESSAGE', draftId)
        storeChatUuid(chat.id)
        await dispatch(
          'chatRuns/subscribeToChat',
          {
            runType: ASSISTANT_RUN_TYPE,
            chatId,
          },
          { root: true }
        )
      }
      commit('SET_ASSISTANT_RUNNING', { chat, value: false })
      resolveAccepted({ outcome: SEND_OUTCOME.ACCEPTED, runId })
    }
    assistant(this.$client)
      .sendMessage(
        chat.id,
        message,
        getters.uiContext,
        async (record) => {
          if (controller.signal.aborted) return
          if (record._run?.id) {
            // Save the accepted human prompt before registering its follower,
            // which can already observe a terminal run and ignore later records.
            if (record.type === 'human' && state.currentChatId === chat.id) {
              commit('REMOVE_MESSAGE', draftId)
              commit('UPSERT_MESSAGE', parseMessage(record))
            }
            await register(record._run)
          }
          if (runId) {
            await dispatch(
              'chatRuns/acceptRecord',
              { runId, record, controller },
              { root: true }
            )
          } else {
            // Optional run metadata can be absent when talking to an older backend.
            // Keep consuming that same response with the established record reader.
            if (!legacyId) {
              legacyId = uuidv4()
              commit('ADD_MESSAGE', {
                id: legacyId,
                role: 'ai',
                content: '',
                loading: true,
              })
            }
            await dispatch('handleStreamingResponse', {
              chat,
              id: legacyId,
              update: record,
            })
          }
        },
        { tabId: getTabId(), signal: controller.signal }
      )
      .then(() => {
        if (!runId)
          resolveAccepted({ outcome: SEND_OUTCOME.ACCEPTED, runId: null })
      })
      .catch(async (error) => {
        if (controller.signal.aborted) {
          resolveAccepted({ outcome: SEND_OUTCOME.FAILED, runId: null })
          return
        }
        if (runId) return // The shared follower recovers status and reconnects read-only.
        const status = error.response?.status
        if (!status || status >= 500) {
          try {
            const snapshot = await assistant(this.$client).fetchChatMessages(
              chat.id
            )
            const candidate = snapshot.active_run || snapshot.latest_run
            const savedHuman = snapshot.messages.find(
              (m) =>
                m.type === 'human' &&
                m.content === message &&
                !previousIds.has(m.id)
            )
            if (
              candidate &&
              savedHuman &&
              candidate.human_message_id === savedHuman.id
            ) {
              await register(
                { id: candidate.id, chat_id: snapshot.chat_id },
                true
              )
              if (state.currentChatId === chat.id) {
                commit('UPSERT_MESSAGE', parseMessage(savedHuman))
              }
              if (isTerminalStatus(candidate.status)) {
                await dispatch(
                  'chatRuns/applySnapshot',
                  { runId, snapshot: candidate },
                  { root: true }
                )
              }
              return
            }
          } catch {
            /* Leave the failed send visible; never retry its prompt. */
          }
        }
        resolveAccepted(
          await dispatch('handleRefusedMessage', { chat, draftId, error })
        )
      })
      .finally(() => {
        unwatchAuth()
        if (runId && originalAdopted)
          dispatch(
            'chatRuns/streamEnded',
            { runId, controller },
            { root: true }
          )
        commit('SET_ASSISTANT_RUNNING', { chat, value: false })
      })
    return accepted
  },

  /**
   * Shows why Kuma refused a message, unless the user left its chat meanwhile.
   * A busy chat follows the message it is still answering instead, without
   * the draft, and is busy even when re-reading it failed, so the text can go
   * back into the input.
   *
   * @returns {Promise<{outcome: string, runId: null}>}
   * @throws Anything but a failed request while re-reading a busy chat.
   */
  async handleRefusedMessage(
    { state, commit, dispatch },
    { chat, draftId, error }
  ) {
    const { $i18n } = this
    if (state.currentChatId !== chat.id) {
      return { outcome: SEND_OUTCOME.FAILED, runId: null }
    }
    if (error.handler?.code === CHAT_RUN_IN_PROGRESS) {
      commit('REMOVE_MESSAGE', draftId)
      try {
        await dispatch('selectChat', chat)
      } catch (readError) {
        if (!readError.handler) {
          throw readError
        }
      }
      return { outcome: SEND_OUTCOME.BUSY, runId: null }
    }
    commit('ADD_MESSAGE', {
      id: uuidv4(),
      role: 'ai',
      content: refusalMessage(error, $i18n),
      loading: false,
      error: true,
      reasoning: false,
    })
    return { outcome: SEND_OUTCOME.FAILED, runId: null }
  },

  handleStreamingResponse({ commit, state }, { chat, id, update }) {
    const { $client, $i18n } = this
    switch (update.type) {
      case MESSAGE_TYPE.AI_STARTED:
        commit('SET_CURRENT_MESSAGE_ID', { chat, messageId: update.message_id })
        break
      case MESSAGE_TYPE.AI_CANCELLED:
        commit('UPDATE_MESSAGE', {
          id,
          updates: {
            content: $i18n.t('assistant.messageCancelled'),
            loading: false,
            error: false,
            reasoning: false,
            cancelled: true,
          },
        })
        commit('SET_ASSISTANT_CANCELLING', { chat, value: false })
        commit('SET_ASSISTANT_RUNNING', { chat, value: false })
        commit('SET_CURRENT_MESSAGE_ID', { chat, messageId: null })
        break
      case MESSAGE_TYPE.MESSAGE:
        commit('SET_ASSISTANT_RUNNING_MESSAGE', {
          chat,
          message: $i18n.t('assistant.statusAnswering'),
        })
        commit('UPDATE_MESSAGE', {
          id,
          updates: {
            id: update.id || id,
            content: update.content,
            sources: update.sources,
            can_submit_feedback: update.can_submit_feedback,
            loading: false,
            reasoning: false,
          },
        })
        break
      case MESSAGE_TYPE.REASONING:
        commit('UPDATE_MESSAGE', {
          id,
          updates: {
            id: update.id || id,
            content: update.content,
            can_submit_feedback: false,
            loading: false,
            reasoning: true,
          },
        })
        break
      case MESSAGE_TYPE.THINKING:
        commit('SET_ASSISTANT_RUNNING_MESSAGE', {
          chat,
          message: update.content,
        })
        break
      case MESSAGE_TYPE.NAVIGATION:
        commit('SET_UI_LOCATION', update.location)
        break
      case MESSAGE_TYPE.CHAT_TITLE:
        // The stream's own chat, because the user can have moved on to another
        // conversation by the time the title arrives.
        commit('UPDATE_CHAT', {
          id: chat.id,
          updates: { title: update.content },
        })
        break
      case MESSAGE_TYPE.ERROR:
        commit('UPDATE_MESSAGE', {
          id,
          updates: {
            content: update.content,
            loading: false,
            error: true,
            reasoning: false,
            can_submit_feedback: false,
          },
        })
        break
    }
  },

  async sendMessage(
    { commit, state, dispatch, getters },
    { message, workspace }
  ) {
    const { $client, $i18n } = this
    if (usesBackgroundRuns(this.app)) {
      const { outcome, runId } = await dispatch('startRun', {
        message,
        workspace,
      })
      if (outcome === SEND_OUTCOME.ACCEPTED && runId) {
        await dispatch('chatRuns/waitUntilFinished', runId, { root: true })
      }
      return outcome
    }
    let chat = state.chats.find((c) => c.id === state.currentChatId)
    if (!chat) {
      await dispatch('createChat', workspace.id)
      chat = state.chats.find((c) => c.id === state.currentChatId)
    }

    const userMessage = {
      id: uuidv4(),
      role: 'human',
      content: message,
      loading: false,
    }
    commit('ADD_MESSAGE', userMessage)
    const aiMessageId = uuidv4()
    const aiMessage = {
      _uuid: aiMessageId,
      id: aiMessageId, // Temporary ID, will be updated when the final message arrives
      role: 'ai',
      content: '',
      loading: true,
      reasoning: false,
    }
    commit('ADD_MESSAGE', aiMessage)
    commit('SET_ASSISTANT_RUNNING', { chat, value: true })
    commit('SET_ASSISTANT_RUNNING_MESSAGE', {
      chat,
      message: $i18n.t('assistant.statusThinking'),
    })
    const uiContext = getters.uiContext

    try {
      await assistant($client).sendMessage(
        state.currentChatId,
        message,
        uiContext,
        async (progressEvent) => {
          await dispatch('handleStreamingResponse', {
            chat,
            id: aiMessageId,
            update: progressEvent,
          })
        }
      )
      // If the AI message was never updated but the request finished, set a generic error message.
      if (
        state.messages.find((m) => m.id === aiMessageId && m.content === '')
      ) {
        throw new Error('The assistant did not provide a response.')
      }
    } catch (error) {
      // Don't show error if the request was cancelled by user
      if (error.cancelled) {
        return
      }
      commit('UPDATE_MESSAGE', {
        id: aiMessageId,
        updates: {
          content:
            error.data?.detail ||
            error.message ||
            'Oops! Something went wrong on the server. Please try again.',
          loading: false,
          error: true,
          reasoning: false,
        },
      })
    } finally {
      commit('SET_ASSISTANT_RUNNING', { chat, value: false })
      commit('SET_CURRENT_MESSAGE_ID', { chat, messageId: null })
    }
  },

  async cancelMessage({ commit, state }) {
    const { $client, $i18n } = this
    if (usesBackgroundRuns(this.app)) {
      // Background execution stays independent of this HTTP connection.
      return
    }
    if (!state.currentChatId) {
      return
    }

    const chat = state.chats.find((c) => c.id === state.currentChatId)
    if (!chat || !chat.running) {
      return
    }

    commit('SET_ASSISTANT_CANCELLING', { chat, value: true })
    commit('SET_ASSISTANT_RUNNING_MESSAGE', {
      chat,
      message: $i18n.t('assistant.statusCancelling'),
    })

    try {
      await assistant($client).cancelMessage(state.currentChatId)
    } catch (error) {
      commit('SET_ASSISTANT_CANCELLING', { chat, value: false })
      commit('SET_ASSISTANT_RUNNING', { chat, value: false })
      commit('SET_CURRENT_MESSAGE_ID', { chat, messageId: null })
    }
  },

  async submitFeedback({ commit, state }, { messageId, sentiment, feedback }) {
    const { $client, $i18n } = this
    const message = state.messages.find((m) => m.id === messageId)
    if (!message) {
      return
    }

    const originalSentiment = message.human_sentiment
    // Optimistically update the message with the new sentiment
    commit('UPDATE_MESSAGE', {
      id: messageId,
      updates: {
        human_sentiment: sentiment,
      },
    })

    try {
      await assistant($client).submitFeedback(
        message.id,
        sentiment,
        feedback?.trim()
      )
    } catch (error) {
      // Revert the optimistic update
      commit('UPDATE_MESSAGE', {
        id: messageId,
        updates: {
          human_sentiment: originalSentiment,
        },
      })
      throw error
    }
  },
}

export const getters = {
  currentChatId: (state) => state.currentChatId,

  pendingPrompt: (state) => state.pendingPrompt,

  isPanelOpen: (state) => state.panelOpen,

  currentChat: (state) => {
    return state.chats.find((chat) => chat.id === state.currentChatId)
  },

  activeFollower: (state, getters, rootState, rootGetters) => {
    const chatId = getters.currentChat?.chatId
    if (!chatId) {
      return null
    }
    const followers = rootGetters['chatRuns/getFollowersOfChat'](
      ASSISTANT_RUN_TYPE,
      chatId
    )
    return followers.filter((follower) => !follower.finished).at(-1) ?? null
  },

  messages: (state, getters) =>
    getters.activeFollower
      ? [...state.messages, inFlightMessage(getters.activeFollower)]
      : state.messages,

  chats: (state) => state.chats,

  isLoadingChats: (state) => state.isLoadingChats,

  uiContext: (state, getters, rootState, rootGetters) => {
    const scope = rootGetters['undoRedo/getCurrentScope']
    const workspace = rootGetters['workspace/get'](scope.workspace)

    const application = scope.application
      ? rootGetters['application/get'](scope.application)
      : null

    const table =
      application?.type === 'database' && scope.table
        ? application.tables?.find((t) => t.id === scope.table)
        : null

    const view =
      table && scope.view ? rootGetters['view/get'](scope.view) : null

    const uiContext = {
      applicationType: application?.type || null,
      // The workspace can be missing on workspace agnostic pages like the all
      // workspaces homepage.
      workspace: workspace ? { id: workspace.id, name: workspace.name } : null,
      timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
    }

    if (application) {
      const appType =
        application.type === 'builder' ? 'application' : application.type
      uiContext[appType] = {
        id: application.id,
        name: application.name,
      }
    }
    if (table) {
      uiContext.table = { id: table.id, name: table.name }
    }
    if (view) {
      uiContext.view = { id: view.id, name: view.name, type: view.type }
    }

    try {
      const workflow =
        application?.type === 'automation' && scope.workflow
          ? rootGetters['automationWorkflow/getById'](
              application,
              scope.workflow
            )
          : null
      if (workflow) {
        uiContext.workflow = { id: workflow.id, name: workflow.name }
      }
    } catch {}

    if (application?.type === 'builder') {
      if (scope.page && application.pages) {
        const page = application.pages.find((p) => p.id === scope.page)
        if (page) {
          uiContext.page = { id: page.id, name: page.name }
        }
      }
    }

    return uiContext
  },

  uiLocation: (state) => {
    return state.uiLocation
  },

  uiLocationHistory: (state) => {
    return state.uiLocationHistory
  },
}

export default {
  namespaced: true,
  state,
  getters,
  actions,
  mutations,
}
