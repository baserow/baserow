import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useStore } from 'vuex'
import { useNuxtApp } from '#app'
import { uuid } from '@baserow/modules/core/utils/string'
import { notifyIf } from '@baserow/modules/core/utils/error'
import { AGENT_RUN_TYPE } from '@baserow/modules/agent/chatRunTypes'
import AgentApplicationService from '@baserow/modules/agent/services/agentApplication'

const uniqueBy = (items, key) => [
  ...new Map(items.map((item) => [item[key], item])).values(),
]

// IDs are the API's chronological order, including equal/imported timestamps.
const mergeMessages = (...pages) =>
  uniqueBy(pages.flat(), 'uuid').sort((a, b) =>
    a.id != null && b.id != null ? a.id - b.id : 0
  )

const REJECTED_MESSAGE_ERRORS = [
  'ERROR_AGENT_NOT_READY',
  'ERROR_REQUEST_BODY_VALIDATION',
  'ERROR_CHAT_RUN_IN_PROGRESS',
  'ERROR_AGENT_BUSY',
]

const SEND_ERRORS = {
  ERROR_AGENT_MESSAGE_CONFLICT: 'conflict',
  ERROR_CHAT_RUN_IN_PROGRESS: 'inProgress',
  ERROR_AGENT_BUSY: 'busy',
}

/** Page-local private conversations, gated by the Agent configuration. */
export function useAgentConversations(agent, configuration) {
  const store = useStore()
  const { $client, $hasPermission, $registry } = useNuxtApp()
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

  const conversations = ref([])
  const localConversations = ref([])
  const conversationsPage = ref(0)
  const conversationsNext = ref(false)
  // The first load starts on mount, so the server renders the same pending state.
  const conversationsLoading = ref(canReadConversations.value)
  const conversationsError = ref(false)
  const selectedUuid = ref(null)
  const histories = reactive({})
  const drafts = reactive({})

  let scope = 0
  let conversationsRequest = 0
  let requestedConversationPage = 1
  let appendConversations = false
  let conversationWriteVersion = 0
  let conversationsRefreshPending = false
  const writtenConversations = new Map()

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

  /** The running reply, or a finished one until a refresh merged its saved turn. */
  function replyFollowerOf(conversationUuid) {
    const id = findConversation(conversationUuid)?.id
    if (!id) return null
    const followers = store.getters['chatRuns/getFollowersOfChat'](
      AGENT_RUN_TYPE,
      id
    )
    const settlingRunId = histories[conversationUuid]?.settlingRunId
    return (
      followers.find((follower) => !follower.finished) ||
      followers.find((follower) => follower.runId === settlingRunId) ||
      null
    )
  }

  /** The draft's send error; a refusal by a running reply lasts as long as it. */
  function sendErrorOf(conversationUuid) {
    const error = drafts[conversationUuid]?.error || null
    return error === 'inProgress' && !replyFollowerOf(conversationUuid)
      ? null
      : error
  }

  const replyFollower = computed(() => replyFollowerOf(selectedUuid.value))
  const sendError = computed(() => sendErrorOf(selectedUuid.value))
  const refreshError = computed(() =>
    Boolean(
      currentHistory.value &&
      currentHistory.value.failedRefresh > currentHistory.value.appliedRefresh
    )
  )
  const canWriteSelected = computed(
    () =>
      canReadConversations.value &&
      canCreateMessage.value &&
      Boolean(selectedConversation.value) &&
      (!selectedConversation.value.local || canCreateConversation.value)
  )
  const canSend = computed(
    () =>
      configuration.readyToSend.value &&
      canWriteSelected.value &&
      // Sending appends to the newest page, so only that page must be loaded.
      (!currentHistory.value || currentHistory.value.page > 0) &&
      !currentDraft.value?.sending &&
      !replyFollower.value
  )
  const scopeIsCurrent = (currentScope) => scope === currentScope

  const createHistory = (values = {}) => ({
    items: [],
    page: 0,
    next: false,
    loading: false,
    error: false,
    stale: false,
    refreshError: false,
    request: 0,
    refreshRequest: 0,
    appliedRefresh: 0,
    failedRefresh: 0,
    settlingRunId: null,
    ...values,
  })

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

  async function fetchConversations(page = 1, append = false) {
    if (!canReadConversations.value) return
    const currentScope = scope
    const agentId = agent.value.id
    const request = ++conversationsRequest
    const writeVersion = conversationWriteVersion
    requestedConversationPage = page
    appendConversations = append
    conversationsLoading.value = true
    conversationsError.value = false
    try {
      const { data } = await service.getConversations(agentId, page)
      if (
        !scopeIsCurrent(currentScope) ||
        request !== conversationsRequest ||
        !canReadConversations.value
      ) {
        return
      }
      const recentWrites = [...writtenConversations.values()]
        .filter((item) => item.version > writeVersion)
        .map((item) => item.conversation)
      conversations.value = uniqueBy(
        append
          ? [...conversations.value, ...data.results, ...recentWrites]
          : [...data.results, ...recentWrites],
        'uuid'
      ).sort((a, b) => b.updated_on.localeCompare(a.updated_on))
      conversationsPage.value = page
      conversationsNext.value = Boolean(data.next)
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

  function refreshConversations() {
    if (conversationsLoading.value) {
      conversationsRefreshPending = true
      return
    }
    // Keep selected/previously loaded rows. Restart the pagination boundary so
    // insertions ahead of older pages cannot make the next read skip any rows.
    return fetchConversations(1, true)
  }

  /** Follow the newest turn's reply, and resume replies a logout suspended. */
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
    if (newestMessage?.turn?.run_id) runIds.add(newestMessage.turn.run_id)
    runIds.forEach((runId) =>
      store.dispatch('chatRuns/follow', {
        runId,
        runType: AGENT_RUN_TYPE,
        chatId: conversation.id,
      })
    )
  }

  function loadMoreConversations() {
    return fetchConversations(conversationsPage.value + 1, true)
  }

  function retryConversations() {
    return fetchConversations(requestedConversationPage, appendConversations)
  }

  async function fetchMessages(conversationUuid, page = 1) {
    if (!canReadConversations.value) return
    const currentScope = scope
    const agentId = agent.value.id
    if (!histories[conversationUuid]) {
      histories[conversationUuid] = createHistory()
    }
    const history = histories[conversationUuid]
    if (history.loading) return
    const request = ++history.request
    history.loading = true
    history.error = false
    try {
      const { data } = await service.getMessages(
        agentId,
        conversationUuid,
        page
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
          page
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
          // Immutable messages can be merged safely, retaining older pages and
          // any send accepted while this refresh was in flight.
          history.items = mergeMessages(latest, history.items)
          history.page = page
          history.next = Boolean(data.next)
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

  async function refreshNewestPage(conversationUuid) {
    const history = histories[conversationUuid]
    if (!canReadConversations.value || !history?.page) return
    const currentScope = scope
    const agentId = agent.value.id
    const settlingRunId = history.settlingRunId
    const request = ++history.refreshRequest
    // Not latest-wins: an older success still applies when a newer refresh fails.
    const isNewerThanApplied = () =>
      scopeIsCurrent(currentScope) && request > history.appliedRefresh
    try {
      // A lagging replica would miss the reply this refresh is for.
      const { data } = await service.getMessages(
        agentId,
        conversationUuid,
        1,
        true
      )
      if (!isNewerThanApplied() || !canReadConversations.value) return
      history.appliedRefresh = request
      const newest = new Set(data.results.map((item) => item.uuid))
      history.items = [
        ...history.items.filter((item) => !newest.has(item.uuid)),
        ...data.results,
      ]
      if (history.settlingRunId === settlingRunId) history.settlingRunId = null
      followReplies(findConversation(conversationUuid), data.results.at(-1))
    } catch {
      if (isNewerThanApplied()) {
        history.failedRefresh = Math.max(history.failedRefresh, request)
      }
    }
  }

  function retryReply() {
    return refreshNewestPage(selectedUuid.value)
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
      writtenConversations.set(conversationUuid, {
        version: ++conversationWriteVersion,
        conversation: data.conversation,
      })
      conversations.value = uniqueBy(
        [...conversations.value, data.conversation],
        'uuid'
      ).sort((a, b) => b.updated_on.localeCompare(a.updated_on))
      localConversations.value = localConversations.value.filter(
        (item) => item.uuid !== conversationUuid
      )
      const history = histories[conversationUuid]
      if (history) {
        history.items = mergeMessages(history.items, [data.message])
      } else {
        histories[conversationUuid] = createHistory({
          items: [data.message],
          page: 1,
        })
      }
      draft.content = ''
      draft.submission = null
      followReplies(data.conversation, data.message)
    } catch (error) {
      if (!scopeIsCurrent(currentScope)) return
      const code = error.response?.data?.error
      draft.error = SEND_ERRORS[code] || 'failed'
      // The server rejected the message outright, so it can be edited and resent.
      if (REJECTED_MESSAGE_ERRORS.includes(code)) draft.submission = null
      if (code === 'ERROR_AGENT_NOT_READY') {
        await configuration.refreshConfiguration()
      }
      if (code === 'ERROR_CHAT_RUN_IN_PROGRESS' && !conversation.local) {
        await refreshNewestPage(conversationUuid)
      }
    } finally {
      if (scopeIsCurrent(currentScope)) {
        draft.sending = false
        if (histories[conversationUuid]?.stale)
          refreshMessages(conversationUuid)
      }
    }
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
    writtenConversations.clear()
    conversationWriteVersion = 0
    conversationsRefreshPending = false
    localConversations.value = []
    selectedUuid.value = null
    Object.keys(histories).forEach((key) => delete histories[key])
    Object.keys(drafts).forEach((key) => delete drafts[key])
  }

  function reset() {
    ++scope
    clearConversations()
    conversationsPage.value = 0
    conversationsNext.value = false
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
      refreshConversations()
      const history = histories[update.uuid]
      if (!history) return
      history.stale = true
      if (update.uuid === selectedUuid.value) refreshMessages(update.uuid)
    },
    // Each event marks its conversation, even if several arrive in one tick.
    { flush: 'sync' }
  )
  watch(
    () => selectedConversation.value?.id,
    (id) => {
      if (id) {
        store.dispatch('chatRuns/subscribeToChat', {
          runType: AGENT_RUN_TYPE,
          chatId: id,
        })
      }
    }
  )
  const removeRefreshListener = runType.onRefresh((chatId, finishedRunId) => {
    const conversation = conversations.value.find((item) => item.id === chatId)
    if (!conversation) return
    const history = histories[conversation.uuid]
    if (finishedRunId && history?.page) history.settlingRunId = finishedRunId
    refreshNewestPage(conversation.uuid)
  })
  onBeforeUnmount(reset)
  onBeforeUnmount(removeRefreshListener)

  return {
    canReadConversations,
    canCreateConversation,
    conversationItems,
    conversationsLoading,
    conversationsError,
    conversationsNext,
    selectedUuid,
    currentHistory,
    currentDraft,
    replyFollower,
    sendError,
    refreshError,
    canWriteSelected,
    canSend,
    newConversation,
    selectConversation,
    loadMoreConversations,
    retryConversations,
    loadMoreMessages,
    retryReply,
    updateMessage,
    sendMessage,
    stopReply,
  }
}
