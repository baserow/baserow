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

const { data, error: fetchError } = await useAsyncData(
  `agent-application-${route.params.agentApplicationId}`,
  async () => {
    try {
      const application = store.getters['application/getSelected']
      const workspace = store.getters['workspace/getSelected']

      return {
        workspace,
        application,
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
const autoOpenConfiguration = ref(false)

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

// Store -> URL: opening a conversation (from the list, or by sending the
// first message of a new one) adds its uuid to the URL, while starting a new
// conversation (including the open one being deleted) removes it.
watch(persistedChatUuid, (uuid) => {
  if (querySyncReady.value) {
    setChatQueryParam(uuid)
  }
})

// URL -> store: browser back/forward navigates between conversations.
watch(chatQueryParam, async (uuid) => {
  if (!querySyncReady.value) {
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

onMounted(async () => {
  if (application.value) {
    // Clear any conversation state left behind by a previously opened agent.
    store.dispatch('agentChat/newConversation')
    store.dispatch('agentHistory/clear')
    $realtime.subscribe('agent_application', {
      agent_application_id: application.value.id,
    })
    await Promise.all([
      store.dispatch('agentApplication/fetch', {
        applicationId: application.value.id,
      }),
      store.dispatch('agentHistory/fetch', {
        applicationId: application.value.id,
      }),
      store.dispatch('agentApplication/fetchTriggers', {
        applicationId: application.value.id,
      }),
      store.dispatch('agentApplication/fetchTools', {
        applicationId: application.value.id,
      }),
      store.dispatch('agentApplication/fetchChannels', {
        applicationId: application.value.id,
      }),
    ])

    // Reopen the conversation the URL points at, e.g. after a refresh.
    if (chatQueryParam.value !== null) {
      await openConversationFromQuery(chatQueryParam.value)
    }
    querySyncReady.value = true

    // A freshly created agent has nothing configured yet; open the
    // configuration panel automatically so the user can set it up.
    const agent = store.getters['agentApplication/getAgent']
    const triggers = store.getters['agentApplication/getTriggers']
    const tools = store.getters['agentApplication/getTools']
    if (
      agent &&
      !agent.instructions &&
      triggers.length === 0 &&
      tools.length === 0
    ) {
      autoOpenConfiguration.value = true
    }
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
