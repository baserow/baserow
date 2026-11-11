<template>
  <div class="agent-application">
    <header
      class="layout__col-2-1 header header--space-between agent-application__header"
    >
      <div class="agent-application__header-title">
        <div class="agent-application__header-name">{{ agent.name }}</div>
        <button
          v-if="agent.pending_count > 0"
          type="button"
          class="agent-application__approvals"
          @click="state.selectNextWaitingConversation"
        >
          <i
            class="agent-application__approvals-icon iconoir-shield-check"
            aria-hidden="true"
          ></i>
          {{ $t('agent.approvalsWaiting', { count: agent.pending_count }) }}
        </button>
      </div>
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
        :filter="state.conversationFilter"
        :selected="state.selectedUuid"
        :loading="state.conversationsLoading"
        :error="state.conversationsError"
        :has-more="state.conversationsNext"
        :can-create="state.canCreateConversation"
        :ready-to-send="state.readyToSend"
        :can-update="state.canUpdateConversation"
        :can-delete="state.canDeleteConversation"
        @filter="state.setConversationFilter"
        @select="state.selectConversation"
        @create="startConversation"
        @retry="state.retryConversations"
        @load-more="state.loadMoreConversations"
        @update="state.updateConversation"
        @delete="state.deleteConversation"
      />
      <main class="agent-chat" :class="{ 'agent-chat--empty': showChatIntro }">
        <div class="agent-chat__announcement" role="status">
          {{ announcement }}
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
                :can-decide="state.canDecide"
                :can-always-allow="state.canUpdateConfiguration"
                :deciding="state.decidingReplies.has(message.uuid)"
                @decide="
                  (decisions, options) =>
                    state.decideApprovals(message, decisions, options)
                "
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
                v-if="warningAction === WARNING_ACTION.RELOAD"
                type="secondary"
                size="small"
                @click="state.refreshConfiguration"
                >{{ $t('action.retry') }}</Button
              >
              <Button
                v-else-if="warningAction === WARNING_ACTION.SAVE"
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
          <ChatComposer
            v-if="showComposer"
            ref="messageInput"
            class="agent-chat__composer"
            :model-value="state.currentDraft?.content || ''"
            :readonly="Boolean(state.currentDraft?.submission)"
            :disabled="state.waitingForApproval"
            :placeholder="
              state.waitingForApproval
                ? $t('agent.approvalPlaceholder')
                : $t('agent.messagePlaceholder', { name: agent.name })
            "
            :described-by="
              sendErrorVisible ? 'agent-chat-send-error' : undefined
            "
            :maxlength="100000"
            :can-send="
              state.canSend && Boolean(state.currentDraft?.content.trim())
            "
            :sending="Boolean(state.currentDraft?.sending)"
            :running="replyRunning"
            :stopping="Boolean(state.replyFollower?.stopRequested)"
            :activity="composerActivity"
            :activity-tone="state.waitingForApproval ? 'waiting' : 'default'"
            :error="sendErrorVisible ? $t(state.sendError) : ''"
            error-id="agent-chat-send-error"
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
import { useI18n } from 'vue-i18n'
import { useNuxtApp } from '#app'
import agentOrb from '@baserow/modules/agent/assets/images/agent-orb.svg?url'
import ChatComposer from '@baserow/modules/core/components/chat/ChatComposer'
import { STEP_STATUS } from '@baserow/modules/core/chatRuns/constants'
import {
  stepStatusText,
  toolActivity,
} from '@baserow/modules/core/toolPresentationTypes'
import { provideNow } from '@baserow/modules/core/composables/useNow'
import AgentConversationList from '@baserow/modules/agent/components/AgentConversationList'
import AgentMessage from '@baserow/modules/agent/components/AgentMessage'
import AgentConfigurationSidebar from '@baserow/modules/agent/components/AgentConfigurationSidebar'
import { useAgentConfiguration } from '@baserow/modules/agent/composables/useAgentConfiguration'
import { useAgentConversations } from '@baserow/modules/agent/composables/useAgentConversations'
import {
  AGENT_REPLY_STATUS,
  replyOutcome,
} from '@baserow/modules/agent/utils/replies'
import {
  AGENT_READINESS,
  CONFIGURATION_ERROR,
} from '@baserow/modules/agent/constants'

const WARNING_ACTION = Object.freeze({
  RELOAD: 'reload',
  SAVE: 'save',
  FIELDS: 'fields',
})

const props = defineProps({ agent: { type: Object, required: true } })
const { $registry } = useNuxtApp()
const { t } = useI18n()
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
  if (!replyRunning.value) {
    if (!state.waitingForApproval) return ''
    const count = state.pendingApprovalCount
    return count > 1
      ? t('agent.waitingForApprovalSteps', { count })
      : t('agent.waitingForApproval')
  }
  // Held calls are waiting; name the first call that can actually be running.
  const runningStep = state.replyFollower.view.steps?.find(
    (step) => step.status === STEP_STATUS.RUNNING
  )
  if (runningStep) return `${toolActivity(runningStep, $registry, t).title}…`
  return t(state.replyFollower.view.text ? 'agent.writing' : 'agent.thinking')
})
// Expire the notice without changing the draft or its safe retry identity.
// Remember the expiry when switching chats so an old error cannot reappear.
const sendErrorVisible = ref(false)
const sendErrorExpiry = new WeakMap()
watch(
  [() => state.currentDraft, () => state.sendError],
  ([draft, error], _, onCleanup) => {
    sendErrorVisible.value = false
    if (!draft) return
    if (!error) {
      sendErrorExpiry.delete(draft)
      return
    }
    const expiry = sendErrorExpiry.get(draft) ?? Date.now() + 10000
    sendErrorExpiry.set(draft, expiry)
    const remaining = expiry - Date.now()
    if (remaining <= 0) return
    sendErrorVisible.value = true
    const timeout = setTimeout(
      () => (sendErrorVisible.value = false),
      remaining
    )
    onCleanup(() => clearTimeout(timeout))
  },
  { immediate: true, flush: 'sync' }
)
watch(
  () => state.replyFollower,
  (follower, previous) => {
    if (follower) {
      announcedSteps.clear()
      for (const step of follower.view.steps ?? []) {
        announcedSteps.set(step.id, step.status)
      }
      announcement.value = t('agent.replying')
    } else if (previous?.finished) {
      // A paused run ends completed; only its saved reply says it waits.
      if (previous.view.message?.status === AGENT_REPLY_STATUS.WAITING) {
        announcement.value = t('agent.waitingForApproval')
        return
      }
      const { note, error } = replyOutcome({
        status: previous.view.status,
        error_code: previous.view.errorCode,
      })
      announcement.value = note || error ? t(note || error) : ''
    }
  }
)
// Steps arrive as whole lists; announce only the steps whose status changed.
const announcedSteps = new Map()
watch(
  () => state.replyFollower?.view.steps,
  (steps) => {
    for (const step of steps ?? []) {
      if (step.status === STEP_STATUS.SKIPPED) continue
      if (announcedSteps.get(step.id) === step.status) continue
      announcedSteps.set(step.id, step.status)
      const activity = toolActivity(step, $registry, t)
      announcement.value = t('toolPresentation.stepAnnouncement', {
        title: activity.title,
        status: stepStatusText(activity, t),
      })
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
    [AGENT_READINESS.INCOMPLETE, AGENT_READINESS.UNAVAILABLE].includes(
      state.readiness
    )
  )
)
const warningAction = computed(() => {
  if (hasLoadError.value) return WARNING_ACTION.RELOAD
  if (!state.canUpdateConfiguration) return null
  if (warningFields.value.length) return WARNING_ACTION.FIELDS
  return state.configurationSaveError ? WARNING_ACTION.SAVE : null
})
// Transient requests only block sending, so saving never moves the chat.
const canCompose = computed(
  () =>
    state.readiness === AGENT_READINESS.READY &&
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
      ? state.readiness === AGENT_READINESS.UNAVAILABLE ||
        state.fieldErrors.model_identifier === CONFIGURATION_ERROR.UNAVAILABLE
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
    () => state.replyFollower?.view.steps,
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
