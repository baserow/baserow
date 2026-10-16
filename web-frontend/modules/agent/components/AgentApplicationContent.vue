<template>
  <div class="agent-application">
    <header class="layout__col-2-1 header agent-application__header">
      <div class="agent-application__header-name">{{ agent.name }}</div>
      <ButtonIcon
        v-if="state.canReadSettings"
        icon="iconoir-settings"
        :active="configurationOpen"
        class="agent-application__configuration-toggle"
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
        :ready="state.isReady"
        @select="state.selectConversation"
        @create="state.newConversation"
        @retry="state.retryConversations"
        @load-more="state.fetchConversations(state.conversationsPage + 1, true)"
      />
      <main class="agent-chat">
        <div ref="historyElement" class="agent-chat__history">
          <div
            v-if="
              state.currentHistory?.loading &&
              !state.currentHistory.items.length
            "
            class="agent-chat__loading loading"
          />
          <Alert v-if="state.currentHistory?.error" type="error">
            {{ $t('agent.messagesLoadError') }}
            <template #actions
              ><Button type="secondary" size="small" @click="retryMessages">{{
                $t('action.retry')
              }}</Button></template
            >
          </Alert>
          <template v-if="state.currentHistory?.items.length">
            <Button
              v-if="state.currentHistory.next"
              type="secondary"
              size="small"
              :loading="state.currentHistory.loading"
              class="agent-chat__older"
              @click="loadOlderMessages"
              >{{ $t('agent.olderMessages') }}</Button
            >
            <div
              v-for="message in state.currentHistory.items"
              :key="message.uuid"
              class="agent-chat__message"
            >
              <div class="agent-chat__message-content">
                {{ message.content }}
              </div>
            </div>
          </template>
          <div
            v-else-if="
              !state.currentHistory?.loading && !state.currentHistory?.error
            "
            class="agent-chat__intro"
          >
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
            <template #actions>
              <template
                v-if="
                  state.canReadSettings &&
                  state.canUpdateSettings &&
                  warningFields.length
                "
              >
                <button
                  v-for="field in warningFields"
                  :key="field"
                  class="agent-chat__warning-link"
                  @click="focusConfiguration(field)"
                >
                  {{ $t(fieldLabels[field]) }}
                </button>
              </template>
              <Button
                v-else-if="hasLoadError"
                type="secondary"
                size="small"
                @click="state.refreshConfiguration"
                >{{ $t('action.retry') }}</Button
              >
              <Button
                v-else-if="state.canUpdateSettings && state.settingsSaveError"
                type="secondary"
                size="small"
                @click="state.saveSettings"
                >{{ $t('action.retry') }}</Button
              >
            </template>
          </Alert>
          <Alert
            v-if="state.currentDraft?.error"
            type="error"
            class="margin-bottom-2"
          >
            {{
              $t(
                state.currentDraft.error === 'conflict'
                  ? 'agent.messageConflict'
                  : 'agent.messageSaveError'
              )
            }}
          </Alert>
          <form
            v-if="showComposer"
            class="agent-chat__composer"
            @submit.prevent="state.sendMessage"
          >
            <FormTextarea
              ref="messageInput"
              :model-value="state.currentDraft?.content || ''"
              :disabled="state.composerDisabled"
              :placeholder="$t('agent.messagePlaceholder')"
              :aria-label="$t('agent.messagePlaceholder')"
              auto-expandable
              :min-rows="1"
              :max-rows="6"
              :maxlength="100000"
              @update:model-value="state.updateMessage"
              @keydown="handleEnter"
            />
            <Button
              button-type="submit"
              class="agent-chat__send"
              icon="iconoir-arrow-up"
              :aria-label="
                $t(state.currentDraft?.error ? 'action.retry' : 'agent.send')
              "
              :title="
                $t(state.currentDraft?.error ? 'action.retry' : 'agent.send')
              "
              :loading="Boolean(state.currentDraft?.sending)"
              :disabled="!state.canSend || !state.currentDraft?.content.trim()"
            />
          </form>
        </div>
      </main>
      <AgentConfigurationSidebar
        v-if="state.canReadSettings && configurationOpen"
        ref="configurationSidebar"
        :configuration="state.configuration"
        :errors="state.fieldErrors"
        :enabled-models="state.enabledModels"
        :editable="state.canUpdateSettings"
        :loading="state.configurationLoading"
        :load-error="state.configurationLoadError"
        :availability-loading="state.availabilityLoading"
        :saving="state.savingSettings"
        :save-error="state.settingsSaveError"
        @close="configurationOpen = false"
        @change="state.updateConfiguration"
        @flush="state.saveSettings"
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
const configurationSidebar = ref(null)
const messageInput = ref(null)
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
  name: 'agent.name',
  instructions: 'agent.instructions',
  provider_type: 'agent.provider',
  model_identifier: 'agent.model',
}
const warningFields = computed(() => Object.keys(state.fieldErrors))
const hasLoadError = computed(
  () =>
    state.readinessError ||
    state.availabilityError ||
    (state.canReadSettings && state.configurationLoadError)
)
const showConfigurationWarning = computed(() =>
  Boolean(
    hasLoadError.value ||
    (state.canReadSettings &&
      (state.settingsSaveError ||
        (!state.configurationLoading && warningFields.value.length))) ||
    ['incomplete', 'unavailable'].includes(state.readiness)
  )
)
// Transient requests only disable the composer, so saving never moves the chat.
const showComposer = computed(
  () =>
    state.readiness === 'ready' &&
    !showConfigurationWarning.value &&
    state.canReadConversations &&
    state.canCreateMessage &&
    Boolean(state.selectedConversation) &&
    (!state.selectedConversation.local || state.canCreateConversation)
)
const warningTitle = computed(() =>
  hasLoadError.value
    ? 'agent.readinessLoadError'
    : state.settingsSaveError
      ? 'agent.configurationSaveError'
      : 'agent.configurationRequired'
)
const warningMessage = computed(() =>
  hasLoadError.value
    ? 'agent.readinessRetry'
    : state.canReadSettings && state.canUpdateSettings
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
  if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
    event.preventDefault()
    state.sendMessage()
  }
}
function retryMessages() {
  state.fetchMessages(
    state.selectedUuid,
    state.currentHistory?.requestedPage || 1,
    Boolean(state.currentHistory?.prepend)
  )
}
async function loadOlderMessages() {
  const container = historyElement.value
  const selectionRevision = historySelectionRevision
  const previousHeight = container.scrollHeight
  const previousTop = container.scrollTop
  await state.fetchMessages(
    state.selectedUuid,
    state.currentHistory.page + 1,
    true
  )
  await nextTick()
  if (
    selectionRevision !== historySelectionRevision ||
    historyElement.value !== container
  ) {
    return
  }
  container.scrollTop = previousTop + container.scrollHeight - previousHeight
}
watch(
  () => state.currentHistory?.items.at(-1)?.uuid,
  async () => {
    await nextTick()
    if (historyElement.value)
      historyElement.value.scrollTop = historyElement.value.scrollHeight
  }
)
</script>
