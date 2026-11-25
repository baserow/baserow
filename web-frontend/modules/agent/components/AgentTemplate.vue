<template>
  <div class="agent-application">
    <header
      class="layout__col-2-1 header header--space-between agent-application__header"
    >
      <div class="agent-application__header-title">
        <ButtonIcon
          v-if="hasConversations"
          icon="baserow-icon-sidebar"
          :active="conversationsOpen"
          :aria-label="conversationsToggleLabel"
          :title="conversationsToggleLabel"
          :aria-expanded="conversationsOpen"
          aria-controls="agent-conversations"
          @click="conversationsOpen = !conversationsOpen"
        />
        <div class="agent-application__header-name">{{ agent.name }}</div>
      </div>
      <ButtonIcon
        icon="iconoir-settings"
        :active="configurationOpen"
        :aria-label="$t('agent.configuration')"
        :title="$t('agent.configuration')"
        :aria-expanded="configurationOpen"
        @click="configurationOpen = !configurationOpen"
      />
    </header>
    <div class="layout__col-2-2 agent-application__content">
      <AgentConversationList
        v-if="hasConversations"
        v-show="conversationsOpen"
        id="agent-conversations"
        :items="conversations"
        :filter="conversationFilter"
        :selected="selectedConversation?.uuid"
        :loading="conversationsLoading"
        :has-more="Boolean(conversationsCursor)"
        :error="conversationsError"
        @select="selectConversation"
        @load-more="loadConversations(conversationsCursor)"
        @retry="loadConversations(conversationsCursor)"
      />
      <main
        class="agent-chat"
        :class="{ 'agent-chat--empty': !history.items.length }"
      >
        <div ref="historyElement" class="agent-chat__history chat-thread">
          <div class="chat-thread__column">
            <Alert v-if="history.error" type="error">
              {{ $t('agent.messagesLoadError') }}
              <template #actions
                ><Button
                  type="secondary"
                  size="small"
                  button-type="button"
                  @click="loadMessages(history.page + 1)"
                  >{{ $t('action.retry') }}</Button
                ></template
              >
            </Alert>
            <template v-if="history.items.length">
              <Button
                v-if="history.next"
                type="secondary"
                size="small"
                button-type="button"
                :loading="history.loading"
                class="agent-chat__older"
                @click="loadMessages(history.page + 1)"
                >{{ $t('agent.olderMessages') }}</Button
              >
              <AgentMessage
                v-for="message in history.items"
                :key="message.uuid"
                :message="message"
                :trigger-type="selectedConversation.trigger_type"
                :trigger-name="selectedConversation.trigger_name"
              />
            </template>
            <AgentChatIntro v-else-if="showsIntro" :name="agent.name" />
          </div>
        </div>
        <div class="agent-chat__footer">
          <div class="agent-chat__shared">
            <i
              class="agent-chat__shared-icon iconoir-info-empty"
              aria-hidden="true"
            ></i>
            <span class="agent-chat__shared-text">{{
              $t('agent.templatePreviewHint')
            }}</span>
          </div>
        </div>
      </main>
      <AgentConfigurationSidebar
        v-if="configurationOpen"
        :name="agent.name"
        :configuration="configuration"
        :errors="NOTHING"
        :enabled-models="NOTHING"
        :loading="configurationLoading"
        :load-error="configurationLoadError"
        @close="configurationOpen = false"
        @reload="loadConfiguration"
      />
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, provide, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useNuxtApp } from '#app'
import { provideNow } from '@baserow/modules/core/composables/useNow'
import AgentApplicationService from '@baserow/modules/agent/services/agentApplication'
import AgentChatIntro from '@baserow/modules/agent/components/AgentChatIntro'
import AgentConversationList from '@baserow/modules/agent/components/AgentConversationList'
import AgentMessage from '@baserow/modules/agent/components/AgentMessage'
import AgentConfigurationSidebar from '@baserow/modules/agent/components/AgentConfigurationSidebar'
import {
  CONVERSATION_FILTERS,
  mergeMessages,
} from '@baserow/modules/agent/composables/useAgentConversations'

// A preview doesn't check the setup against the visitor's workspace, so it
// reports no errors and offers no other models.
const NOTHING = Object.freeze({})

/**
 * Shows an Agent of a template like its real page, read-only: the example
 * conversations it came with, if any, and its configuration. It only reads, so
 * the visitor doesn't have to be a workspace member or signed in.
 */
const props = defineProps({
  pageValue: { type: Object, required: true },
})
const { $client } = useNuxtApp()
const { t } = useI18n()
const service = AgentApplicationService($client)
const agent = computed(() => props.pageValue.agent)
// Configuration sections read the Agent from here, and what to leave out.
provide('agentApplication', agent)
provide('agentTemplatePreview', true)
provideNow()

const configurationOpen = ref(true)
const configuration = ref({})
const configurationLoading = ref(true)
const configurationLoadError = ref(false)

const conversationsOpen = ref(true)
const conversationsToggleLabel = computed(() =>
  t(
    conversationsOpen.value
      ? 'agent.hideConversations'
      : 'agent.showConversations'
  )
)
const hasConversations = ref(false)
const conversations = ref([])
// The examples are all shared and never wait or fail, so they aren't filtered.
const conversationFilter = 'all'
const conversationsCursor = ref(null)
const conversationsLoading = ref(false)
const conversationsError = ref(false)
// Whether the first page answered, so the intro doesn't show before an example.
const conversationsSettled = ref(false)
const selectedConversation = ref(null)
const emptyHistory = () => ({
  items: [],
  page: 0,
  next: false,
  loading: false,
  error: false,
})
const history = reactive(emptyHistory())
const showsIntro = computed(
  () =>
    conversationsSettled.value &&
    !conversationsError.value &&
    !selectedConversation.value &&
    !history.items.length
)
const historyElement = ref(null)
// Bumped for every Agent shown, so a late answer for another one is dropped.
let scope = 0
let conversationsRequest = 0

async function loadConfiguration() {
  const current = scope
  configurationLoading.value = true
  configurationLoadError.value = false
  try {
    const { data } = await service.getConfiguration(agent.value.id)
    if (current === scope) configuration.value = data
  } catch {
    if (current === scope) configurationLoadError.value = true
  } finally {
    if (current === scope) configurationLoading.value = false
  }
}

/**
 * Loads a page of the example conversations. They are optional: an Agent
 * without any, or one whose conversations the visitor may not read, shows the
 * chat intro instead of a list. Any other failure shows the list with a retry.
 *
 * @param {string|null} cursor The cursor of the page, or null for the first.
 */
async function loadConversations(cursor = null) {
  const current = scope
  const request = ++conversationsRequest
  const isCurrent = () => current === scope && request === conversationsRequest
  conversationsLoading.value = true
  conversationsError.value = false
  try {
    const { data } = await service.getConversations(
      agent.value.id,
      cursor,
      CONVERSATION_FILTERS[conversationFilter].params
    )
    if (!isCurrent()) return
    conversations.value = cursor
      ? [...conversations.value, ...data.results]
      : data.results
    conversationsCursor.value = data.next_cursor
    if (!cursor) {
      hasConversations.value = data.results.length > 0
      if (!selectedConversation.value && data.results.length) {
        selectConversation(data.results[0])
      }
    }
  } catch (error) {
    if (!isCurrent()) return
    // Kept, so that a retry asks for the same page.
    conversationsCursor.value = cursor
    if (![401, 403].includes(error.response?.status)) {
      conversationsError.value = true
      hasConversations.value = true
    }
  } finally {
    if (isCurrent()) {
      conversationsLoading.value = false
      conversationsSettled.value = true
    }
  }
}

function selectConversation(conversation) {
  if (conversation.uuid === selectedConversation.value?.uuid) return
  selectedConversation.value = conversation
  Object.assign(history, emptyHistory())
  loadMessages()
}

/**
 * Loads a page of the selected conversation's messages, the newest first.
 *
 * @param {number} page The page to load; older pages go above the loaded ones.
 */
async function loadMessages(page = 1) {
  const current = scope
  const conversation = selectedConversation.value
  const isCurrent = () =>
    current === scope && conversation === selectedConversation.value
  history.loading = true
  history.error = false
  try {
    const { data } = await service.getMessages(
      agent.value.id,
      conversation.uuid,
      page
    )
    if (!isCurrent()) return
    history.items = mergeMessages(data.results, page > 1 ? history.items : [])
    history.page = page
    history.next = Boolean(data.next)
    if (page === 1) {
      await nextTick()
      if (historyElement.value) {
        historyElement.value.scrollTop = historyElement.value.scrollHeight
      }
    }
  } catch {
    if (isCurrent()) history.error = true
  } finally {
    if (isCurrent()) history.loading = false
  }
}

watch(
  () => agent.value.id,
  () => {
    ++scope
    configuration.value = {}
    hasConversations.value = false
    conversations.value = []
    conversationsCursor.value = null
    conversationsError.value = false
    conversationsSettled.value = false
    selectedConversation.value = null
    Object.assign(history, emptyHistory())
    loadConfiguration()
    loadConversations()
  },
  { immediate: true }
)
</script>
