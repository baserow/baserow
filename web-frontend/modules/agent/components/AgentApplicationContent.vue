<template>
  <div class="agent-application">
    <header
      class="layout__col-2-1 header header--space-between agent-application__header"
    >
      <div class="agent-application__header-name">{{ agent.name }}</div>
      <ButtonIcon
        v-if="state.canReadConfiguration"
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
        v-if="state.canReadConversations"
        :items="state.conversationItems"
        :selected="state.selectedUuid"
        :loading="state.conversationsLoading"
        :error="state.conversationsError"
        :has-more="state.conversationsNext"
        :can-create="state.canCreateConversation"
        :ready-to-send="state.readyToSend"
        @select="state.selectConversation"
        @create="startConversation"
        @retry="state.retryConversations"
        @load-more="state.loadMoreConversations"
      />
      <main class="agent-chat" :class="{ 'agent-chat--empty': showChatIntro }">
        <div class="agent-chat__announcement" role="status">
          {{ announcement ? $t(announcement) : '' }}
        </div>
        <div
          ref="historyElement"
          class="agent-chat__history chat-thread"
          :class="{ 'chat-thread--scrolled': historyScrolled }"
          @scroll="historyScrolled = $event.target.scrollTop > 2"
        >
          <div class="chat-thread__column">
            <div
              v-if="
                state.currentHistory?.loading &&
                !state.currentHistory.items.length
              "
              class="agent-chat__loading skeleton"
              role="status"
              :aria-label="$t('agent.loadingMessages')"
            >
              <div
                v-for="row in 3"
                :key="row"
                class="agent-chat__skeleton-row"
                aria-hidden="true"
              >
                <SkeletonBlock :width="`${row % 2 ? 60 : 40}%`" height="44px" />
              </div>
            </div>
            <Alert v-if="state.currentHistory?.error" type="error">
              {{ $t('agent.messagesLoadError') }}
              <template #actions
                ><Button
                  type="secondary"
                  size="small"
                  button-type="button"
                  @click="loadMoreMessages"
                  >{{ $t('action.retry') }}</Button
                ></template
              >
            </Alert>
            <template v-if="state.currentHistory?.items.length">
              <Button
                v-if="state.currentHistory.next"
                type="secondary"
                size="small"
                button-type="button"
                :loading="state.currentHistory.loading"
                class="agent-chat__older"
                @click="loadMoreMessages"
                >{{ $t('agent.olderMessages') }}</Button
              >
              <AgentMessage
                v-for="message in state.currentHistory.items"
                :key="message.uuid"
                :message="message"
              />
            </template>
            <div v-else-if="showChatIntro" class="agent-chat__intro">
              <div class="agent-chat__avatar">
                <img :src="agentOrb" alt="" />
              </div>
              <i18n-t scope="global" keypath="agent.talkTo" tag="h1">
                <template #name>
                  <span class="agent-chat__intro-name">{{ agent.name }}</span>
                </template>
              </i18n-t>
              <p>{{ $t('agent.chatDescription') }}</p>
            </div>
          </div>
        </div>
        <div class="agent-chat__footer">
          <Alert
            v-if="showConfigurationWarning"
            type="warning"
            class="agent-chat__warning"
          >
            <template #title>{{ $t(warningTitle) }}</template>
            <p>{{ $t(warningMessage) }}</p>
            <template v-if="warningAction" #actions>
              <Button
                v-if="warningAction === 'reload'"
                type="secondary"
                size="small"
                @click="state.refreshConfiguration"
                >{{ $t('action.retry') }}</Button
              >
              <Button
                v-else-if="warningAction === 'save'"
                type="secondary"
                size="small"
                @click="state.saveConfiguration"
                >{{ $t('action.retry') }}</Button
              >
              <template v-else>
                <ButtonText
                  v-for="field in warningFields"
                  :key="field"
                  button-type="button"
                  type="secondary"
                  size="small"
                  class="alert__actions-button-text alert__actions-button-text--normal agent-chat__warning-link"
                  @click="focusConfiguration(field)"
                >
                  {{ $t(fieldLabels[field]) }}
                </ButtonText>
              </template>
            </template>
          </Alert>
          <Alert
            v-if="state.sendError"
            id="agent-chat-send-error"
            type="error"
            role="alert"
            class="margin-bottom-2"
          >
            {{ $t(state.sendError) }}
          </Alert>
          <ChatComposer
            v-if="showComposer"
            ref="messageInput"
            class="agent-chat__composer"
            :model-value="state.currentDraft?.content || ''"
            :readonly="Boolean(state.currentDraft?.submission)"
            :placeholder="$t('agent.messagePlaceholder', { name: agent.name })"
            :described-by="
              state.sendError ? 'agent-chat-send-error' : undefined
            "
            :maxlength="100000"
            :can-send="
              state.canSend && Boolean(state.currentDraft?.content.trim())
            "
            :sending="Boolean(state.currentDraft?.sending)"
            :running="replyRunning"
            :stopping="Boolean(state.replyFollower?.stopRequested)"
            :activity="composerActivity ? $t(composerActivity) : ''"
            :send-label="$t(state.sendError ? 'action.retry' : 'agent.send')"
            :stop-label="$t('agent.stop')"
            @update:model-value="state.updateMessage"
            @send="submitMessage"
            @stop="stopReply"
          />
        </div>
      </main>
      <AgentConfigurationSidebar
        v-if="state.canReadConfiguration && configurationOpen"
        ref="configurationSidebar"
        v-model:name="state.name"
        :configuration="state.configuration"
        :errors="state.fieldErrors"
        :enabled-models="state.enabledModels"
        :editable="state.canUpdateConfiguration"
        :loading="state.configurationLoading"
        :load-error="state.configurationLoadError && !state.configurationLoaded"
        :availability-loading="state.availabilityLoading"
        :saving="state.savingConfiguration || state.savingName"
        :save-error="state.configurationSaveError"
        @close="configurationOpen = false"
        @rename="state.renameAgent"
        @change="state.updateConfiguration"
        @flush="state.saveConfiguration"
        @reload="state.refreshConfiguration"
      />
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, provide, reactive, ref, toRef, watch } from 'vue'
import agentOrb from '@baserow/modules/agent/assets/images/agent-orb.svg?url'
import ChatComposer from '@baserow/modules/core/components/chat/ChatComposer'
import { provideNow } from '@baserow/modules/core/composables/useNow'
import AgentConversationList from '@baserow/modules/agent/components/AgentConversationList'
import AgentMessage from '@baserow/modules/agent/components/AgentMessage'
import AgentConfigurationSidebar from '@baserow/modules/agent/components/AgentConfigurationSidebar'
import { useAgentConfiguration } from '@baserow/modules/agent/composables/useAgentConfiguration'
import { useAgentConversations } from '@baserow/modules/agent/composables/useAgentConversations'
import { replyOutcome } from '@baserow/modules/agent/utils/replies'

const props = defineProps({ agent: { type: Object, required: true } })
const agent = toRef(props, 'agent')
const configuration = useAgentConfiguration(agent)
const state = reactive({
  ...configuration,
  ...useAgentConversations(agent, configuration),
})
const configurationOpen = ref(true)
provideNow()
// Configuration sections read the Agent's workspace from here.
provide('agentApplication', agent)
const showChatIntro = computed(
  () =>
    !state.currentHistory?.items.length &&
    !state.currentHistory?.loading &&
    !state.currentHistory?.error
)
const configurationSidebar = ref(null)
const historyElement = ref(null)
const historyScrolled = ref(false)
const announcement = ref('')
// Any selection change, even away and back, invalidates a pending scroll anchor.
let historySelectionRevision = 0
watch(
  [() => props.agent.id, () => state.selectedUuid],
  () => {
    ++historySelectionRevision
    historyScrolled.value = false
    announcement.value = ''
  },
  { flush: 'sync' }
)
const fieldLabels = {
  instructions: 'agent.instructions',
  provider_type: 'agent.provider',
  model_identifier: 'agent.model',
}
const replyRunning = computed(() => Boolean(state.replyFollower))
const composerActivity = computed(() => {
  if (!replyRunning.value) return null
  return state.replyFollower.view.text ? 'agent.writing' : 'agent.thinking'
})
watch(
  () => state.replyFollower,
  (follower, previous) => {
    if (follower) {
      announcement.value = 'agent.replying'
    } else if (previous?.finished) {
      const { note, error } = replyOutcome({
        status: previous.view.status,
        error_code: previous.view.errorCode,
      })
      announcement.value = note || error || ''
    }
  }
)
const warningFields = computed(() => Object.keys(state.fieldErrors))
const hasLoadError = computed(
  () =>
    state.readinessError ||
    (state.canReadConfiguration &&
      (state.availabilityError || state.configurationLoadError))
)
const showConfigurationWarning = computed(() =>
  Boolean(
    hasLoadError.value ||
    (state.canReadConfiguration &&
      (state.configurationSaveError ||
        (!state.configurationLoading && warningFields.value.length))) ||
    ['incomplete', 'unavailable'].includes(state.readiness)
  )
)
const warningAction = computed(() => {
  if (hasLoadError.value) return 'reload'
  if (!state.canUpdateConfiguration) return null
  if (warningFields.value.length) return 'fields'
  return state.configurationSaveError ? 'save' : null
})
// Transient requests only block sending, so saving never moves the chat.
const canCompose = computed(
  () =>
    state.readiness === 'ready' &&
    !showConfigurationWarning.value &&
    state.canWriteSelected
)
const showComposer = computed(() => canCompose.value || replyRunning.value)
const warningTitle = computed(() =>
  hasLoadError.value
    ? 'agent.readinessLoadError'
    : state.configurationSaveError
      ? 'agent.configurationSaveError'
      : 'agent.configurationRequired'
)
const warningMessage = computed(() =>
  hasLoadError.value
    ? 'agent.readinessRetry'
    : state.canUpdateConfiguration
      ? state.readiness === 'unavailable' ||
        state.fieldErrors.model_identifier === 'unavailable'
        ? 'agent.modelUnavailable'
        : 'agent.completeConfiguration'
      : 'agent.configurationPermissionRequired'
)
async function focusConfiguration(field) {
  configurationOpen.value = true
  await nextTick()
  await configurationSidebar.value?.focusField(field)
}
async function loadMoreMessages() {
  const container = historyElement.value
  const loadingOlder =
    state.currentHistory?.page > 0 && !state.currentHistory.refreshError
  const selectionRevision = historySelectionRevision
  const anchor = container.querySelector('.chat-message')
  const previousOffset = anchor?.offsetTop
  await state.loadMoreMessages()
  await nextTick()
  if (
    !loadingOlder ||
    !anchor ||
    selectionRevision !== historySelectionRevision ||
    historyElement.value !== container ||
    !container.contains(anchor)
  ) {
    return
  }
  container.scrollTop += anchor.offsetTop - previousOffset
}
watch(
  [
    () => state.selectedUuid,
    () => state.currentHistory?.items.at(-1)?.uuid,
    () => state.replyFollower?.view.text,
  ],
  async ([selection], [previousSelection, previousLast]) => {
    const container = historyElement.value
    if (!container) return
    const revision = historySelectionRevision
    const followLatest =
      selection !== previousSelection ||
      !previousLast ||
      container.scrollHeight - container.scrollTop - container.clientHeight < 40
    await nextTick()
    if (
      followLatest &&
      revision === historySelectionRevision &&
      historyElement.value === container
    ) {
      container.scrollTop = container.scrollHeight
    }
  }
)
const messageInput = ref(null)
async function submitMessage() {
  if (!state.canSend || !state.currentDraft?.content.trim()) return
  // Move focus before the send button becomes disabled, keeping the composer
  // ready for the next message without stealing focus after an async response.
  messageInput.value?.focus()
  const revision = historySelectionRevision
  await state.sendMessage()
  await nextTick()
  if (
    revision === historySelectionRevision &&
    !state.currentDraft?.error &&
    !state.currentDraft?.content &&
    historyElement.value
  ) {
    historyElement.value.scrollTop = historyElement.value.scrollHeight
  }
}
function stopReply() {
  messageInput.value?.focus()
  state.stopReply()
}
async function startConversation() {
  state.newConversation()
  await nextTick()
  messageInput.value?.focus()
}
</script>
