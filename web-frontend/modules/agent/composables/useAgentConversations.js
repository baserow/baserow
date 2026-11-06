import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useStore } from 'vuex'
import { useNuxtApp } from '#app'
import { uuid } from '@baserow/modules/core/utils/string'
import { notifyIf } from '@baserow/modules/core/utils/error'
import { ResponseErrorMessage } from '@baserow/modules/core/plugins/clientHandler'
import { isTerminalStatus } from '@baserow/modules/core/chatRuns/constants'
import { AGENT_RUN_TYPE } from '@baserow/modules/agent/chatRunTypes'
import AgentApplicationService from '@baserow/modules/agent/services/agentApplication'
import { API_ERROR_CODE } from '@baserow/modules/agent/constants'
import { pendingApprovals } from '@baserow/modules/agent/utils/replies'

const byNewest = (a, b) => Date.parse(b.updated_on) - Date.parse(a.updated_on)
const pick = (source, fields) =>
  Object.fromEntries(fields.map((field) => [field, source[field]]))

/** Merge pages given oldest first in place, never undoing a reply's end. */
function mergeMessages(...pages) {
  const merged = new Map()
  for (const message of pages.flat()) {
    const current = merged.get(message.uuid)
    if (!current) {
      merged.set(message.uuid, message)
    } else if (
      !isTerminalStatus(current.status) ||
      isTerminalStatus(message.status)
    ) {
      Object.assign(current, message)
    }
  }
  // IDs are the API's chronological order, including equal/imported timestamps.
  return [...merged.values()].sort((a, b) =>
    a.id != null && b.id != null ? a.id - b.id : 0
  )
}

const REJECTED_MESSAGE_ERRORS = [
  API_ERROR_CODE.AGENT_NOT_READY,
  API_ERROR_CODE.REQUEST_BODY_VALIDATION,
  API_ERROR_CODE.CHAT_RUN_IN_PROGRESS,
  API_ERROR_CODE.AGENT_BUSY,
  API_ERROR_CODE.AGENT_CONVERSATION_WAITING_FOR_APPROVAL,
]

const SEND_ERRORS = {
  [API_ERROR_CODE.AGENT_MESSAGE_CONFLICT]: 'agent.messageConflict',
  [API_ERROR_CODE.CHAT_RUN_IN_PROGRESS]: 'agent.replyInProgress',
  [API_ERROR_CODE.AGENT_BUSY]: 'agent.agentsBusy',
  [API_ERROR_CODE.AGENT_CONVERSATION_WAITING_FOR_APPROVAL]:
    'agent.conversationWaitingForApproval',
}

// Another session changed the conversation, so a refusal re-reads it.
const CONVERSATION_CHANGED_ERRORS = [
  API_ERROR_CODE.CHAT_RUN_IN_PROGRESS,
  API_ERROR_CODE.AGENT_CONVERSATION_WAITING_FOR_APPROVAL,
  API_ERROR_CODE.AGENT_TOOL_APPROVAL_NOT_PENDING,
]

/** Page-local private conversations, gated by the Agent configuration. */
export function useAgentConversations(agent, configuration) {
  const store = useStore()
  const { $client, $hasPermission, $i18n, $registry } = useNuxtApp()
  const service = AgentApplicationService($client)
  const runType = $registry.get('chatRunType', AGENT_RUN_TYPE)
  const permission = (operation) =>
    Boolean(
      agent.value &&
      $hasPermission(operation, agent.value, agent.value.workspace.id)
    )

  const canReadConversations = computed(() =>
    permission('agent_application.read_conversations')
  )
  const canCreateConversation = computed(() =>
    permission('agent_application.create_conversation')
  )
  const canCreateMessage = computed(() =>
    permission('agent_application.create_message')
  )
  const canUpdateConversation = computed(() =>
    permission('agent_application.update_conversation')
  )
  const canDeleteConversation = computed(() =>
    permission('agent_application.delete_conversation')
  )

  const conversations = ref([])
  const localConversations = ref([])
  // Where the next page continues, after the last loaded conversation.
  const conversationsCursor = ref(null)
  const conversationsNext = computed(() => Boolean(conversationsCursor.value))
  // The first load starts on mount, so the server renders the same pending state.
  const conversationsLoading = ref(canReadConversations.value)
  const conversationsError = ref(false)
  const selectedUuid = ref(null)
  const histories = reactive({})
  const drafts = reactive({})

  let scope = 0
  let conversationsRequest = 0
  let requestedConversationsCursor = null
  let conversationsRefreshPending = false
  // Deletes and updates since a list read started, whose older copy would undo them.
  let conversationChanges = 0

  const conversationItems = computed(() => [
    ...localConversations.value.filter((item) =>
      drafts[item.uuid]?.content.trim()
    ),
    ...conversations.value,
  ])
  const selectedConversation = computed(() =>
    [...localConversations.value, ...conversations.value].find(
      (item) => item.uuid === selectedUuid.value
    )
  )
  const currentHistory = computed(() => histories[selectedUuid.value] || null)
  const currentDraft = computed(() => drafts[selectedUuid.value] || null)
  const findConversation = (conversationUuid) =>
    conversations.value.find((item) => item.uuid === conversationUuid)

  const replyFollower = computed(() => {
    const id = selectedConversation.value?.id
    if (!id) return null
    const followers = store.getters['chatRuns/getFollowersOfChat'](
      AGENT_RUN_TYPE,
      id
    )
    return followers.find((follower) => !follower.finished) || null
  })

  // A refusal expires with the running reply, including in an inactive chat.
  const sendError = computed(() => {
    const error = currentDraft.value?.error || null
    return error === SEND_ERRORS[API_ERROR_CODE.CHAT_RUN_IN_PROGRESS] &&
      !replyFollower.value
      ? null
      : error
  })
  const canWriteSelected = computed(
    () =>
      canReadConversations.value &&
      canCreateMessage.value &&
      Boolean(selectedConversation.value) &&
      (!selectedConversation.value.local || canCreateConversation.value)
  )
  // Sending is blocked while a reply waits, so the waiting reply is the newest.
  const pendingApprovalCount = computed(
    () => pendingApprovals(currentHistory.value?.items.at(-1)).length
  )
  const waitingForApproval = computed(() => pendingApprovalCount.value > 0)
  const canSend = computed(
    () =>
      configuration.readyToSend.value &&
      canWriteSelected.value &&
      // Sending appends to the newest page, so only that page must be loaded.
      (!currentHistory.value || currentHistory.value.page > 0) &&
      !currentDraft.value?.sending &&
      !replyFollower.value &&
      !waitingForApproval.value
  )
  // Deciding continues the reply, so it needs what sending a message needs.
  const canDecide = computed(
    () => configuration.readyToSend.value && canWriteSelected.value
  )
  const decidingReplies = reactive(new Set())
  const scopeIsCurrent = (currentScope) => scope === currentScope

  function ensureDraft(conversationUuid) {
    if (!drafts[conversationUuid]) {
      drafts[conversationUuid] = {
        content: '',
        sending: false,
        error: null,
        // Kept immutable so a retry cannot duplicate an already accepted message.
        submission: null,
      }
    }
    return drafts[conversationUuid]
  }

  function createLocalConversation() {
    if (!canCreateConversation.value || !canReadConversations.value) return
    const conversationUuid = uuid()
    localConversations.value.unshift({
      uuid: conversationUuid,
      title: '',
      local: true,
    })
    selectedUuid.value = conversationUuid
    ensureDraft(conversationUuid)
  }

  function newConversation() {
    if (configuration.readyToSend.value) createLocalConversation()
  }

  /** Keep the newest copy of each conversation, newest first. */
  function mergeConversations(incoming) {
    const known = new Map(conversations.value.map((item) => [item.uuid, item]))
    for (const conversation of incoming) {
      const current = known.get(conversation.uuid)
      if (!current) {
        known.set(conversation.uuid, conversation)
      } else if (byNewest(current, conversation) >= 0) {
        Object.assign(current, conversation)
      }
    }
    conversations.value = [...known.values()].sort(byNewest)
  }

  async function fetchConversations(cursor = null, realtimeRecovery = false) {
    if (!canReadConversations.value) return
    const currentScope = scope
    const agentId = agent.value.id
    const request = ++conversationsRequest
    const changes = conversationChanges
    requestedConversationsCursor = cursor
    conversationsLoading.value = true
    conversationsError.value = false
    try {
      const { data } = await service.getConversations(
        agentId,
        cursor,
        realtimeRecovery
      )
      if (
        !scopeIsCurrent(currentScope) ||
        request !== conversationsRequest ||
        !canReadConversations.value
      ) {
        return
      }
      if (changes !== conversationChanges) {
        return fetchConversations(cursor, realtimeRecovery)
      }
      mergeConversations(data.results)
      // Reading the newest ones again leaves the loaded pages after them as they are.
      if (cursor === conversationsCursor.value) {
        conversationsCursor.value = data.next_cursor
      }
    } catch {
      if (scopeIsCurrent(currentScope) && request === conversationsRequest) {
        conversationsError.value = true
      }
    } finally {
      if (scopeIsCurrent(currentScope) && request === conversationsRequest) {
        conversationsLoading.value = false
        if (conversationsRefreshPending) {
          conversationsRefreshPending = false
          refreshConversations()
        }
      }
    }
  }

  /** Read the newest conversations again after an event that changed them. */
  function refreshConversations() {
    if (conversationsLoading.value) {
      conversationsRefreshPending = true
      return
    }
    return fetchConversations(null, true)
  }

  /** Follow the conversation's reply, and resume replies a logout suspended. */
  function followReplies(conversation, newestMessage) {
    if (!conversation?.id) return
    const runIds = new Set(
      store.getters['chatRuns/getFollowersOfChat'](
        AGENT_RUN_TYPE,
        conversation.id
      )
        .filter((follower) => !follower.finished)
        .map((follower) => follower.runId)
    )
    for (const runId of [newestMessage?.run_id, conversation.run_id]) {
      if (runId) runIds.add(runId)
    }
    runIds.forEach((runId) =>
      store.dispatch('chatRuns/follow', {
        runId,
        runType: AGENT_RUN_TYPE,
        chatId: conversation.id,
      })
    )
  }

  function loadMoreConversations() {
    return fetchConversations(conversationsCursor.value)
  }

  function retryConversations() {
    return fetchConversations(requestedConversationsCursor)
  }

  async function fetchMessages(conversationUuid, page = 1) {
    if (!canReadConversations.value) return
    const currentScope = scope
    const agentId = agent.value.id
    if (!histories[conversationUuid]) {
      histories[conversationUuid] = {
        items: [],
        page: 0,
        next: false,
        loading: false,
        error: false,
        stale: false,
        refreshError: false,
        request: 0,
      }
    }
    const history = histories[conversationUuid]
    if (history.loading) return
    const request = ++history.request
    history.loading = true
    history.error = false
    try {
      // The rows of a reply being written must be as fresh as its run.
      const { data } = await service.getMessages(
        agentId,
        conversationUuid,
        page,
        page === 1 && Boolean(findConversation(conversationUuid)?.run_id)
      )
      if (
        !scopeIsCurrent(currentScope) ||
        history.request !== request ||
        !canReadConversations.value
      )
        return
      history.items = mergeMessages(data.results, page > 1 ? history.items : [])
      history.page = page
      history.next = Boolean(data.next)
      if (page === 1) {
        followReplies(findConversation(conversationUuid), data.results.at(-1))
      }
    } catch {
      if (scopeIsCurrent(currentScope) && history.request === request) {
        history.error = true
      }
    } finally {
      if (scopeIsCurrent(currentScope) && history.request === request) {
        history.loading = false
        if (history.stale) refreshMessages(conversationUuid)
      }
    }
  }

  async function refreshMessages(conversationUuid) {
    const history = histories[conversationUuid]
    if (!history || !canReadConversations.value) return
    history.stale = true
    if (history.loading || drafts[conversationUuid]?.sending) return

    const currentScope = scope
    const agentId = agent.value.id
    const request = ++history.request
    const knownMessages = new Set(history.items.map(({ uuid }) => uuid))
    history.stale = false
    history.loading = true
    history.error = false
    history.refreshError = false
    const latest = []
    let page = 1
    try {
      while (true) {
        const { data } = await service.getMessages(
          agentId,
          conversationUuid,
          page,
          true
        )
        if (
          !scopeIsCurrent(currentScope) ||
          history.request !== request ||
          !canReadConversations.value
        )
          return
        latest.push(...data.results)
        if (
          !data.next ||
          !knownMessages.size ||
          data.results.some(({ uuid }) => knownMessages.has(uuid))
        ) {
          // Refresh reply outcomes while retaining older pages and accepted sends.
          history.items = mergeMessages(history.items, latest)
          history.page = page
          history.next = Boolean(data.next)
          followReplies(
            findConversation(conversationUuid),
            history.items.at(-1)
          )
          break
        }
        page++
      }
    } catch {
      if (scopeIsCurrent(currentScope) && history.request === request) {
        history.error = true
        history.refreshError = true
      }
    } finally {
      if (scopeIsCurrent(currentScope) && history.request === request) {
        history.loading = false
        if (history.stale) refreshMessages(conversationUuid)
      }
    }
  }

  // A failed page keeps the last loaded page number, so this also retries it.
  function loadMoreMessages() {
    if (currentHistory.value.refreshError) {
      return refreshMessages(selectedUuid.value)
    }
    return fetchMessages(selectedUuid.value, currentHistory.value.page + 1)
  }

  function selectConversation(conversation) {
    selectedUuid.value = conversation.uuid
    ensureDraft(conversation.uuid)
    if (!conversation.local && !histories[conversation.uuid]?.page) {
      fetchMessages(conversation.uuid)
    } else if (histories[conversation.uuid]?.stale) {
      refreshMessages(conversation.uuid)
    }
  }

  function updateMessage(content) {
    if (!currentDraft.value || currentDraft.value.submission) return
    currentDraft.value.content = content
  }

  async function sendMessage() {
    if (!canSend.value || !currentDraft.value?.content.trim()) return
    const currentScope = scope
    const agentId = agent.value.id
    const conversation = selectedConversation.value
    const conversationUuid = conversation.uuid
    const draft = currentDraft.value
    if (!draft.submission) {
      draft.submission = { uuid: uuid(), content: draft.content }
    }
    const submission = { ...draft.submission }
    draft.sending = true
    draft.error = null
    try {
      const { data } = conversation.local
        ? await service.createConversation(agentId, {
            uuid: conversationUuid,
            message_uuid: submission.uuid,
            content: submission.content,
          })
        : await service.createMessage(agentId, conversationUuid, submission)
      if (!scopeIsCurrent(currentScope) || !canReadConversations.value) return
      // Deleted while sending, so it must not come back.
      if (drafts[conversationUuid] !== draft) return
      mergeConversations([data.conversation])
      localConversations.value = localConversations.value.filter(
        (item) => item.uuid !== conversationUuid
      )
      const sent = [data.message, data.reply].filter(Boolean)
      const history = histories[conversationUuid]
      if (history) {
        history.items = mergeMessages(history.items, sent)
      } else {
        histories[conversationUuid] = {
          items: sent,
          page: 1,
          next: false,
          loading: false,
          error: false,
          stale: false,
          refreshError: false,
          request: 0,
        }
      }
      draft.content = ''
      draft.submission = null
      followReplies(data.conversation, data.reply)
    } catch (error) {
      if (!scopeIsCurrent(currentScope)) return
      const code = error.response?.data?.error
      draft.error = SEND_ERRORS[code] || 'agent.messageSaveError'
      // The server rejected the message outright, so it can be edited and resent.
      if (REJECTED_MESSAGE_ERRORS.includes(code)) draft.submission = null
      if (code === API_ERROR_CODE.AGENT_NOT_READY) {
        await configuration.refreshConfiguration()
      }
      if (CONVERSATION_CHANGED_ERRORS.includes(code) && !conversation.local) {
        await refreshMessages(conversationUuid)
      }
    } finally {
      if (scopeIsCurrent(currentScope)) {
        draft.sending = false
        if (histories[conversationUuid]?.stale)
          refreshMessages(conversationUuid)
      }
    }
  }

  /** Decide held steps of a reply, then follow the run that resumes it. */
  async function decideApprovals(reply, decisions) {
    if (!canDecide.value || decidingReplies.has(reply.uuid)) return
    const currentScope = scope
    const agentId = agent.value.id
    const conversationUuid = selectedUuid.value
    decidingReplies.add(reply.uuid)
    try {
      const { data } = await service.decideApprovals(
        agentId,
        conversationUuid,
        decisions
      )
      if (!scopeIsCurrent(currentScope) || !canReadConversations.value) return
      const history = histories[conversationUuid]
      if (history) history.items = mergeMessages(history.items, [data])
      const conversation = findConversation(conversationUuid)
      if (data.run_id && conversation) {
        conversation.run_id = data.run_id
        followReplies(conversation, data)
      }
    } catch (error) {
      if (!scopeIsCurrent(currentScope)) return
      const code = error.response?.data?.error
      if (SEND_ERRORS[code]) {
        error.handler.notifyIf(
          null,
          new ResponseErrorMessage(
            $i18n.t('clientHandler.notCompletedTitle'),
            $i18n.t(SEND_ERRORS[code])
          )
        )
      } else {
        notifyIf(error)
      }
      if (code === API_ERROR_CODE.AGENT_NOT_READY) {
        await configuration.refreshConfiguration()
      }
      if (CONVERSATION_CHANGED_ERRORS.includes(code)) {
        await refreshMessages(conversationUuid)
      }
    } finally {
      decidingReplies.delete(reply.uuid)
    }
  }

  async function updateConversation(conversation, values) {
    const fields = Object.keys(values)
    const previous = pick(conversation, fields)
    applyConversationValues(conversation, values)
    try {
      const { data } = await service.updateConversation(
        agent.value.id,
        conversation.uuid,
        values
      )
      applyConversationValues(conversation, pick(data, fields))
    } catch (error) {
      applyConversationValues(conversation, previous)
      if (isDeletedElsewhere(error)) removeConversation(conversation.uuid)
      else notifyIf(error)
    }
  }

  function applyConversationValues(conversation, values) {
    conversationChanges++
    Object.assign(conversation, values)
  }

  function isDeletedElsewhere(error) {
    return (
      error.response?.data?.error ===
      API_ERROR_CODE.AGENT_CONVERSATION_DOES_NOT_EXIST
    )
  }

  /** Drop a conversation, selecting the one that takes its place in the list. */
  function removeConversation(conversationUuid) {
    const index = conversationItems.value.findIndex(
      (item) => item.uuid === conversationUuid
    )
    conversationChanges++
    conversations.value = conversations.value.filter(
      (item) => item.uuid !== conversationUuid
    )
    delete histories[conversationUuid]
    delete drafts[conversationUuid]
    if (selectedUuid.value !== conversationUuid) return
    const next =
      conversationItems.value[index] || conversationItems.value.at(-1)
    selectedUuid.value = null
    if (next) selectConversation(next)
    else createLocalConversation()
  }

  async function deleteConversation(conversation) {
    try {
      await service.deleteConversation(agent.value.id, conversation.uuid)
    } catch (error) {
      if (isDeletedElsewhere(error)) removeConversation(conversation.uuid)
      else notifyIf(error)
      return
    }
    removeConversation(conversation.uuid)
    await store.dispatch('toast/restore', {
      trash_item_type: 'agent_conversation',
      trash_item_id: conversation.id,
    })
  }

  async function stopReply() {
    const runId = replyFollower.value?.runId
    if (!runId) return
    try {
      await store.dispatch('chatRuns/cancelRun', runId)
    } catch (error) {
      notifyIf(error)
    }
  }

  function clearConversations() {
    ++conversationsRequest
    conversations.value = []
    conversationsCursor.value = null
    conversationsRefreshPending = false
    localConversations.value = []
    selectedUuid.value = null
    Object.keys(histories).forEach((key) => delete histories[key])
    Object.keys(drafts).forEach((key) => delete drafts[key])
  }

  function reset() {
    ++scope
    clearConversations()
    conversationsLoading.value = false
    conversationsError.value = false
  }

  createLocalConversation()
  onMounted(() => fetchConversations())
  watch([() => agent.value?.id, () => store.state.auth.user?.id], () => {
    reset()
    createLocalConversation()
    fetchConversations()
  })
  watch(canReadConversations, (allowed) => {
    if (allowed) fetchConversations()
    else clearConversations()
  })
  watch(
    () => agent.value?._?.conversationUpdate,
    (update) => {
      if (!update || !canReadConversations.value) return
      if (update.kind === 'deleted') return removeConversation(update.uuid)
      const conversation = findConversation(update.uuid)
      if (update.kind === 'updated') {
        if (conversation) applyConversationValues(conversation, update.values)
        return
      }
      if (!conversation) return refreshConversations()
      mergeConversations([
        {
          uuid: update.uuid,
          run_id: update.runId,
          updated_on: update.updatedOn,
        },
      ])
      if (update.uuid === selectedUuid.value) followReplies(conversation)
      else if (histories[update.uuid]) histories[update.uuid].stale = true
    },
    // Each event applies to its conversation, even if several arrive in one tick.
    { flush: 'sync' }
  )
  // A reply another session started needs its prompt and its own row.
  watch(
    () => {
      const runId = replyFollower.value?.runId
      const history = currentHistory.value
      return Boolean(
        runId &&
        history?.page &&
        !currentDraft.value?.sending &&
        !history.items.some((message) => message.run_id === runId)
      )
    },
    (missing) => {
      if (missing) refreshMessages(selectedUuid.value)
    }
  )
  function unsubscribeFromConversation() {
    const chatId = store.state.chatRuns.subscriptions[AGENT_RUN_TYPE]
    if (chatId === undefined) return
    store.dispatch('chatRuns/unsubscribeFromChat', {
      runType: AGENT_RUN_TYPE,
      chatId,
    })
  }
  watch(
    () => selectedConversation.value?.id,
    (id) => {
      if (id) {
        store.dispatch('chatRuns/subscribeToChat', {
          runType: AGENT_RUN_TYPE,
          chatId: id,
        })
      } else {
        unsubscribeFromConversation()
      }
    }
  )
  const stopListening = runType.listen({
    /** Apply the saved reply its run ended with, or read it when it has none. */
    replyFinished(follower) {
      const conversation = conversations.value.find(
        (item) => item.id === follower.chatId
      )
      if (!conversation) return
      if (conversation.run_id === follower.runId) conversation.run_id = null
      const history = histories[conversation.uuid]
      const saved = follower.view.message
      const row =
        saved && history?.items.find((message) => message.uuid === saved.uuid)
      if (row) Object.assign(row, saved)
      else if (conversation.uuid === selectedUuid.value)
        refreshMessages(conversation.uuid)
      else if (history) history.stale = true
    },
    /** Events missed while the websocket was down change lists and histories. */
    chatReconnected(chatId) {
      refreshConversations()
      for (const [conversationUuid, history] of Object.entries(histories)) {
        if (conversationUuid !== selectedUuid.value) history.stale = true
      }
      const conversation = conversations.value.find(
        (item) => item.id === chatId
      )
      if (conversation) refreshMessages(conversation.uuid)
    },
  })
  onBeforeUnmount(reset)
  onBeforeUnmount(unsubscribeFromConversation)
  onBeforeUnmount(stopListening)

  return {
    canReadConversations,
    canCreateConversation,
    canUpdateConversation,
    canDeleteConversation,
    conversationItems,
    conversationsLoading,
    conversationsError,
    conversationsNext,
    selectedUuid,
    currentHistory,
    currentDraft,
    replyFollower,
    sendError,
    canWriteSelected,
    canSend,
    pendingApprovalCount,
    waitingForApproval,
    canDecide,
    decidingReplies,
    newConversation,
    selectConversation,
    loadMoreConversations,
    retryConversations,
    loadMoreMessages,
    updateMessage,
    sendMessage,
    decideApprovals,
    stopReply,
    updateConversation,
    deleteConversation,
  }
}
