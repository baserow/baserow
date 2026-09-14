<template>
  <AgentPageContent
    v-if="workspace && application"
    :workspace="workspace"
    :application="application"
    :auto-open-configuration="autoOpenConfiguration"
  />
</template>

<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { useStore } from 'vuex'
import { useRoute, useRouter } from 'vue-router'
import { useNuxtApp, useAsyncData, createError, useHead } from '#app'
import { StoreItemLookupError } from '@baserow/modules/core/errors'
import { normalizeError } from '@baserow/modules/database/utils/errors'

import AgentPageContent from '@baserow_enterprise/components/agentApplication/AgentPageContent'

definePageMeta({
  layout: 'app',
  // The page must fully remount when navigating between agent applications,
  // so the realtime subscription, fetches, and chat state follow the route.
  // Only the path matters; the `chat` query param changes when a conversation
  // is opened and must not remount the page.
  key: (route) => route.path,
  middleware: [
    'settings',
    'authenticated',
    'workspacesAndApplications',
    'selectWorkspaceAgentApplication',
  ],
})

const store = useStore()
const route = useRoute()
const router = useRouter()
const { $realtime } = useNuxtApp()

// Everything the page renders is fetched here so server side rendering (and
// a client navigation) paints the populated page in one go instead of the
// empty state first. The conversation in the `chat` query param is opened as
// part of it for the same reason.
const { data, error: fetchError } = await useAsyncData(
  `agent-application-${route.params.agentApplicationId}-${
    route.query.chat || ''
  }`,
  async () => {
    try {
      const application = store.getters['application/getSelected']
      const workspace = store.getters['workspace/getSelected']

      // When switching between agents the previous page stays on screen
      // until this resolves, so the store is not cleared up front (the
      // fetches below replace it) and the conversation is reset at the end.
      await Promise.all([
        store.dispatch('agentApplication/fetch', {
          applicationId: application.id,
        }),
        store.dispatch('agentHistory/fetch', { applicationId: application.id }),
        store.dispatch('agentApplication/fetchTriggers', {
          applicationId: application.id,
        }),
        store.dispatch('agentApplication/fetchTools', {
          applicationId: application.id,
        }),
        store.dispatch('agentApplication/fetchChannels', {
          applicationId: application.id,
        }),
        // Labels for tool names and the identity name are cosmetic; the page
        // must still work when either of these fails.
        store
          .dispatch('agentApplication/fetchWorkspaceToolCatalog', {
            applicationId: application.id,
          })
          .catch(() => {}),
        store.dispatch('agent/fetchAll', workspace.id).catch(() => {}),
      ])

      const chatUuid = Array.isArray(route.query.chat)
        ? route.query.chat[0]
        : route.query.chat
      let staleChatQuery = false
      let opened = false
      if (chatUuid) {
        try {
          await store.dispatch('agentChat/openConversation', {
            applicationId: application.id,
            chatUuid,
          })
          opened = true
        } catch {
          // The conversation no longer exists (or cannot be loaded); the
          // page starts with a fresh conversation and drops the param.
          staleChatQuery = true
        }
      }
      if (!opened) {
        store.dispatch('agentChat/newConversation')
      }

      // A freshly created agent has nothing configured yet; the configuration
      // panel opens automatically so the user can set it up.
      const agent = store.getters['agentApplication/getAgent']
      const autoOpenConfiguration = Boolean(
        agent &&
        !agent.instructions &&
        store.getters['agentApplication/getTriggers'].length === 0 &&
        store.getters['agentApplication/getTools'].length === 0
      )

      return {
        workspace,
        application,
        autoOpenConfiguration,
        staleChatQuery,
      }
    } catch (e) {
      if (e.response === undefined && !(e instanceof StoreItemLookupError)) {
        throw e
      }

      const statusCode = e.response?.status || 500

      throw createError({
        statusCode,
        message:
          statusCode === 404 ? 'Agent not found.' : normalizeError(e).message,
        data: {
          report: statusCode >= 500,
        },
        fatal: true,
      })
    }
  }
)

if (fetchError.value) {
  throw fetchError.value
}

const application = computed(() => data.value?.application)
const workspace = computed(() => data.value?.workspace)
const autoOpenConfiguration = computed(
  () => data.value?.autoOpenConfiguration || false
)

useHead(() => ({
  title: application.value?.name || '',
}))

// The uuid of the open conversation is mirrored into the `chat` query param so
// a refresh or a shared link reopens the same conversation. The two watchers
// below sync in both directions and only act when the other side is out of
// date, so they cannot trigger each other in a loop. They stay inert until the
// mount initialization (which clears leftover state and opens the conversation
// the URL points at) has finished.
const querySyncReady = ref(false)

const chatQueryParam = computed(() => {
  const value = route.query.chat
  return (Array.isArray(value) ? value[0] : value) || null
})

// Only conversations that exist on the backend belong in the URL; a fresh
// empty conversation has a client-generated uuid but no chat id yet.
const persistedChatUuid = computed(() =>
  store.getters['agentChat/getChatId'] !== null
    ? store.getters['agentChat/getCurrentChatUuid']
    : null
)

const setChatQueryParam = (uuid) => {
  if (chatQueryParam.value === (uuid || null)) {
    return
  }
  const query = { ...route.query }
  if (uuid) {
    query.chat = uuid
  } else {
    delete query.chat
  }
  router.replace({ query })
}

const openConversationFromQuery = async (chatUuid) => {
  try {
    await store.dispatch('agentChat/openConversation', {
      applicationId: application.value.id,
      chatUuid,
    })
  } catch {
    // The conversation no longer exists (or cannot be loaded); fall back to a
    // fresh empty conversation and drop the stale param.
    store.dispatch('agentChat/newConversation')
    setChatQueryParam(null)
  }
}

// While the next agent's page is loading, this instance is still mounted
// but the route already points at the other agent; its watchers must leave
// the store and URL alone then.
const agentApplicationId = route.params.agentApplicationId
const routeIsMine = () => route.params.agentApplicationId === agentApplicationId

// Store -> URL: opening a conversation (from the list, or by sending the
// first message of a new one) adds its uuid to the URL, while starting a new
// conversation (including the open one being deleted) removes it.
watch(persistedChatUuid, (uuid) => {
  if (querySyncReady.value && routeIsMine()) {
    setChatQueryParam(uuid)
  }
})

// URL -> store: browser back/forward navigates between conversations.
watch(chatQueryParam, async (uuid) => {
  if (!querySyncReady.value || !routeIsMine()) {
    return
  }
  if (uuid === null) {
    if (store.getters['agentChat/getChatId'] !== null) {
      store.dispatch('agentChat/newConversation')
    }
  } else if (uuid !== store.getters['agentChat/getCurrentChatUuid']) {
    await openConversationFromQuery(uuid)
  }
})

onMounted(() => {
  if (application.value) {
    $realtime.subscribe('agent_application', {
      agent_application_id: application.value.id,
    })
    if (data.value?.staleChatQuery) {
      setChatQueryParam(null)
    }
    querySyncReady.value = true
  }
})

onBeforeUnmount(() => {
  if (application.value) {
    $realtime.unsubscribe('agent_application', {
      agent_application_id: application.value.id,
    })
  }
})
</script>
