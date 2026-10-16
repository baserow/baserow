import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { useStore } from 'vuex'
import { useNuxtApp } from '#app'
import { uuid } from '@baserow/modules/core/utils/string'
import AgentApplicationService from '@baserow/modules/agent/services/agentApplication'

const uniqueBy = (items, key) => [
  ...new Map(items.map((item) => [item[key], item])).values(),
]

/** Page-local private conversations, gated by the Agent configuration. */
export function useAgentConversations(agent, configuration) {
  const store = useStore()
  const { $client, $hasPermission } = useNuxtApp()
  const service = AgentApplicationService($client)
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
  const conversationsLoading = ref(false)
  const conversationsError = ref(false)
  const selectedUuid = ref(null)
  const histories = reactive({})
  const drafts = reactive({})

  let scope = 0
  let conversationsRequest = 0
  let requestedConversationPage = 1
  let appendConversations = false
  let conversationWriteVersion = 0
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
  const canSend = computed(
    () =>
      configuration.isReady.value &&
      canReadConversations.value &&
      canCreateMessage.value &&
      Boolean(selectedConversation.value) &&
      (!selectedConversation.value.local || canCreateConversation.value) &&
      !currentHistory.value?.loading &&
      !currentHistory.value?.error &&
      !currentDraft.value?.sending
  )
  const composerDisabled = computed(
    () => !canSend.value || Boolean(currentDraft.value?.submission)
  )
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
    if (
      !configuration.isReady.value ||
      !canCreateConversation.value ||
      !canReadConversations.value
    )
      return
    createLocalConversation()
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
      }
    }
  }

  function retryConversations() {
    return fetchConversations(requestedConversationPage, appendConversations)
  }

  async function fetchMessages(conversationUuid, page = 1, prepend = false) {
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
        request: 0,
      }
    }
    const history = histories[conversationUuid]
    const request = ++history.request
    history.requestedPage = page
    history.prepend = prepend
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
      history.items = uniqueBy(
        prepend ? [...data.results, ...history.items] : data.results,
        'uuid'
      )
      history.page = page
      history.next = Boolean(data.next)
    } catch {
      if (scopeIsCurrent(currentScope) && history.request === request) {
        history.error = true
      }
    } finally {
      if (scopeIsCurrent(currentScope) && history.request === request) {
        history.loading = false
      }
    }
  }

  function selectConversation(conversation) {
    selectedUuid.value = conversation.uuid
    ensureDraft(conversation.uuid)
    if (!conversation.local && !histories[conversation.uuid]?.page) {
      fetchMessages(conversation.uuid)
    }
  }

  function updateMessage(content) {
    if (composerDisabled.value || !currentDraft.value) return
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
        ++history.request
        history.loading = false
        history.error = false
        history.items = uniqueBy([...history.items, data.message], 'uuid')
      } else {
        histories[conversationUuid] = {
          items: [data.message],
          page: 1,
          next: false,
          loading: false,
          error: false,
          request: 0,
        }
      }
      draft.content = ''
      draft.submission = null
    } catch (error) {
      if (!scopeIsCurrent(currentScope)) return
      const code = error.response?.data?.error
      draft.error =
        code === 'ERROR_AGENT_MESSAGE_CONFLICT' ? 'conflict' : 'failed'
      if (code === 'ERROR_AGENT_CONFIGURATION_INVALID') {
        await configuration.recheckReadiness()
      }
    } finally {
      if (scopeIsCurrent(currentScope)) draft.sending = false
    }
  }

  function clearConversations() {
    ++conversationsRequest
    conversations.value = []
    writtenConversations.clear()
    conversationWriteVersion = 0
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

  watch(
    () => [agent.value?.id, store.state.auth.user?.id],
    () => {
      reset()
      if (!agent.value) return
      if (canCreateConversation.value && canReadConversations.value)
        createLocalConversation()
      fetchConversations()
    },
    { immediate: true }
  )
  watch(canReadConversations, (allowed) => {
    if (allowed) fetchConversations()
    else clearConversations()
  })
  onBeforeUnmount(reset)

  return {
    canReadConversations,
    canCreateConversation,
    canCreateMessage,
    conversationItems,
    conversationsLoading,
    conversationsError,
    conversationsPage,
    conversationsNext,
    selectedUuid,
    selectedConversation,
    currentHistory,
    currentDraft,
    canSend,
    composerDisabled,
    newConversation,
    selectConversation,
    fetchConversations,
    retryConversations,
    fetchMessages,
    updateMessage,
    sendMessage,
  }
}
