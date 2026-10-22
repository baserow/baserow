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
        <div ref="historyElement" class="agent-chat__history">
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
              class="agent-chat__message"
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
            <div
              v-for="(message, index) in state.currentHistory.items"
              :key="message.uuid"
              class="agent-chat__message"
              :class="{
                'agent-chat__message--reply': message.role === 'assistant',
              }"
            >
              <div
                v-if="messageAuthor(message)"
                class="agent-chat__message-author"
              >
                {{ messageAuthor(message) }}
              </div>
              <div class="agent-chat__message-content">
                {{ message.content }}
              </div>
              <div v-if="messageNotices[index]" class="agent-chat__notice">
                {{ $t(messageNotices[index]) }}
              </div>
            </div>
            <div
              v-if="showReply"
              class="agent-chat__message agent-chat__message--reply"
              aria-live="polite"
              :aria-busy="replyRunning"
            >
              <div class="agent-chat__message-author">{{ agent.name }}</div>
              <div
                v-if="state.replyFollower.view.text"
                class="agent-chat__message-content"
              >
                {{ state.replyFollower.view.text }}
              </div>
              <div v-else class="loading" aria-hidden="true" />
            </div>
            <Alert v-if="state.refreshError" type="error">
              {{ $t('agent.messagesLoadError') }}
              <template #actions
                ><Button
                  type="secondary"
                  size="small"
                  @click="state.retryReply"
                  >{{ $t('action.retry') }}</Button
                ></template
              >
            </Alert>
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
            {{ $t(SEND_ERROR_MESSAGES[state.sendError]) }}
          </Alert>
          <form
            v-if="showComposer"
            class="agent-chat__composer"
            @submit.prevent="submitMessage"
          >
            <FormTextarea
              ref="messageInput"
              :model-value="state.currentDraft?.content || ''"
              :readonly="Boolean(state.currentDraft?.submission)"
              :placeholder="$t('agent.messagePlaceholder')"
              :aria-label="$t('agent.messagePlaceholder')"
              :aria-describedby="
                state.sendError ? 'agent-chat-send-error' : undefined
              "
              auto-expandable
              :min-rows="1"
              :max-rows="6"
              :maxlength="100000"
              @update:model-value="state.updateMessage"
              @keydown="handleEnter"
            />
            <Button
              v-if="replyRunning"
              type="secondary"
              button-type="button"
              class="agent-chat__stop"
              icon="iconoir-square"
              :aria-label="$t('agent.stop')"
              :title="$t('agent.stop')"
              :loading="state.replyFollower.stopRequested"
              @click="stopReply"
            />
            <Button
              v-else
              button-type="submit"
              class="agent-chat__send"
              icon="iconoir-arrow-up"
              :aria-label="$t(state.sendError ? 'action.retry' : 'agent.send')"
              :title="$t(state.sendError ? 'action.retry' : 'agent.send')"
              :loading="Boolean(state.currentDraft?.sending)"
              :disabled="!state.canSend || !state.currentDraft?.content.trim()"
            />
          </form>
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
import { computed, nextTick, reactive, ref, toRef, watch } from 'vue'
import agentOrb from '@baserow/modules/agent/assets/images/agent-orb.svg?url'
import AgentConversationList from '@baserow/modules/agent/components/AgentConversationList'
import AgentConfigurationSidebar from '@baserow/modules/agent/components/AgentConfigurationSidebar'
import { useAgentConfiguration } from '@baserow/modules/agent/composables/useAgentConfiguration'
import { useAgentConversations } from '@baserow/modules/agent/composables/useAgentConversations'

const props = defineProps({ agent: { type: Object, required: true } })
const agent = toRef(props, 'agent')
const configuration = useAgentConfiguration(agent)
const state = reactive({
  ...configuration,
  ...useAgentConversations(agent, configuration),
})
const configurationOpen = ref(true)
const showChatIntro = computed(
  () =>
    !state.currentHistory?.items.length &&
    !state.currentHistory?.loading &&
    !state.currentHistory?.error
)
const configurationSidebar = ref(null)
const historyElement = ref(null)
// Any selection change, even away and back, invalidates a pending scroll anchor.
let historySelectionRevision = 0
watch(
  [() => props.agent.id, () => state.selectedUuid],
  () => {
    ++historySelectionRevision
  },
  { flush: 'sync' }
)
const fieldLabels = {
  instructions: 'agent.instructions',
  provider_type: 'agent.provider',
  model_identifier: 'agent.model',
}
const SEND_ERROR_MESSAGES = {
  conflict: 'agent.messageConflict',
  inProgress: 'agent.replyInProgress',
  busy: 'agent.agentsBusy',
  failed: 'agent.messageSaveError',
}
const FAILED_REPLY_NOTICES = {
  timeout: 'agent.replyTimedOut',
  interrupted: 'agent.replyInterrupted',
  not_started: 'agent.replyNotStarted',
  not_ready: 'agent.replyNotReady',
  not_allowed: 'agent.replyNotAllowed',
}
/** The notice of a turn whose reply didn't complete, or null. */
function turnNotice(turn) {
  if (turn?.status === 'cancelled') return 'agent.replyStopped'
  if (turn?.status === 'failed') {
    return FAILED_REPLY_NOTICES[turn.error_code] || 'agent.replyFailed'
  }
  if (turn?.status === 'running' && !turn.run_id) {
    return 'agent.replyInterrupted'
  }
  return null
}
const replyRunning = computed(() =>
  Boolean(state.replyFollower && !state.replyFollower.finished)
)
const showReply = computed(
  () => replyRunning.value || Boolean(state.replyFollower?.view.text)
)
const announcement = ref('')
watch(
  () => {
    const follower = state.replyFollower
    if (!follower) return null
    if (!follower.finished) return 'agent.replying'
    const { status, errorCode } = follower.view
    return turnNotice({ status, error_code: errorCode }) || ''
  },
  (key) => {
    if (key !== null) announcement.value = key
  }
)
const isLastOfTurn = (items, index) =>
  items[index + 1]?.turn?.id !== items[index].turn?.id
const messageNotices = computed(() => {
  const items = state.currentHistory?.items || []
  return items.map((message, index) =>
    isLastOfTurn(items, index) ? turnNotice(message.turn) : null
  )
})
const messageAuthor = (message) =>
  message.role === 'assistant' ? props.agent.name : message.author?.name
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
const showComposer = computed(
  () =>
    state.readiness === 'ready' &&
    !showConfigurationWarning.value &&
    state.canWriteSelected
)
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
function handleEnter(event) {
  // Safari sends the Enter that commits an IME composition with keyCode 229.
  if (event.isComposing || event.keyCode === 229) return
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    submitMessage()
  }
}
async function loadMoreMessages() {
  const container = historyElement.value
  const loadingOlder =
    state.currentHistory?.page > 0 && !state.currentHistory.refreshError
  const selectionRevision = historySelectionRevision
  const anchor = container.querySelector('.agent-chat__message')
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
  () => [state.selectedUuid, state.currentHistory?.items.at(-1)?.uuid],
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
const NEAR_BOTTOM_PX = 48
watch(
  () => state.replyFollower?.view.text,
  async () => {
    const container = historyElement.value
    if (!container) return
    const nearBottom =
      container.scrollHeight - container.scrollTop - container.clientHeight <=
      NEAR_BOTTOM_PX
    await nextTick()
    if (nearBottom && historyElement.value === container) {
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
