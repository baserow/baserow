<template>
  <section class="assistant-editor" @keyup.esc.stop="closePanel">
    <div class="assistant__header">
      <div class="assistant__title">
        <i class="iconoir-sparks" aria-hidden="true"></i
        >{{ $t('assistantPanel.title') }}
      </div>
      <ButtonIcon
        icon="iconoir-cancel"
        size="small"
        type="secondary"
        :aria-label="$t('assistantPanel.close')"
        @click="closePanel"
      />
    </div>
    <div ref="thread" class="assistant__content">
      <div v-if="!turns.length" class="assistant-editor__welcome">
        <img :src="kuma" alt="" width="54" height="54" />
        <h2>{{ target.placeholder }}</h2>
      </div>
      <div v-else class="assistant__messages-list" role="log">
        <ChatMessage v-for="(turn, i) in turns" :key="i" :own="turn.own">
          <div class="chat-message__bubble">{{ turn.text }}</div>
        </ChatMessage>
        <ButtonText v-if="target.undoable.value" size="small" @click="undo">{{
          $t('kumaInlinePrompt.undo')
        }}</ButtonText>
      </div>
    </div>
    <div class="assistant__footer">
      <p v-if="notice" class="assistant-editor__notice" role="status">
        {{ notice }}
      </p>
      <AssistantInputMessage
        ref="composer"
        :sending="busy"
        :send-disabled="!!target.blockedMessage"
        :starter="target.starter"
        :maxlength="2000"
        @send-message="send"
      >
        <template #context>
          <div class="assistant-editor__chip">
            <i class="iconoir-sparks" aria-hidden="true"></i>
            <span>{{ contextLabel }}</span>
            <button
              type="button"
              :aria-label="$t('kumaPrompt.detach')"
              :title="$t('kumaPrompt.detach')"
              @click="leave"
            >
              <i class="iconoir-cancel" aria-hidden="true"></i>
            </button>
          </div>
        </template>
      </AssistantInputMessage>
    </div>
  </section>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import isEqual from 'lodash/isEqual'
import { useStore } from 'vuex'
import kuma from '@baserow_enterprise/assets/images/kuma.svg?url'
import AssistantInputMessage from '@baserow_enterprise/components/assistant/AssistantInputMessage'
import AssistantService from '@baserow_enterprise/services/assistant'
import ChatMessage from '@baserow/modules/core/components/chat/ChatMessage'

const props = defineProps({ target: { type: Object, required: true } })
const app = useNuxtApp()
const store = useStore()
const composer = ref(null)
const thread = ref(null)
const turns = ref([])
const busy = ref(false)
const error = ref('')
const contextLabel = computed(() =>
  [props.target.title, props.target.label].filter(Boolean).join(' · ')
)
const notice = computed(() => props.target.blockedMessage || error.value)
const isCurrent = (target) => app.$kumaEditor.target.value === target
onMounted(() => composer.value.focus())
onBeforeUnmount(() => {
  if (busy.value) props.target.busy(false)
})
function leave() {
  app.$kumaEditor.target.value = null
  props.target.focus()
}
function closePanel() {
  leave()
  app.$bus.$emit('toggle-right-sidebar', false)
}
async function undo() {
  props.target.undoable.value = false
  await store.dispatch('undoRedo/undo', { showLoadingToast: true })
}
async function send(text) {
  const target = props.target
  if (busy.value || !isCurrent(target) || target.blockedMessage || !text.trim())
    return
  const parameters = { ...target.parameters }
  busy.value = true
  target.busy(true)
  target.undoable.value = false
  error.value = ''
  turns.value.push({ own: true, text })
  try {
    const response = await AssistantService(app.$client).runAction(
      target.action,
      text,
      parameters,
      target.workspaceId
    )
    if (!isCurrent(target)) return
    const draft =
      response.result?.instructions ??
      response.result?.formula ??
      response.result?.ai_prompt
    if (draft !== undefined && !isEqual(parameters, target.parameters)) {
      error.value = app.$i18n.t('kumaPrompt.draftChanged')
      if (!composer.value.currentMessage) composer.value.setCurrentMessage(text)
      return
    }
    target.apply(response.result)
    target.undoable.value =
      target.action === 'update_service_filters' && response.changed
    const confirmation = {
      generate_formula: 'kumaPrompt.formulaDraftUpdated',
      generate_ai_field_prompt: 'kumaPrompt.aiPromptDraftUpdated',
      add_row_color: 'kumaPrompt.rowColorAdded',
    }[target.action]
    const reply =
      response.summary || (confirmation ? app.$i18n.t(confirmation) : draft)
    if (reply) turns.value.push({ own: false, text: reply })
  } catch (err) {
    if (!err.handler) throw err
    err.handler.handled()
    if (isCurrent(target)) {
      error.value = err.handler.getMessage().message
      if (!composer.value.currentMessage) composer.value.setCurrentMessage(text)
    }
  } finally {
    if (isCurrent(target)) {
      target.busy(false)
      busy.value = false
      await nextTick()
      if (thread.value) thread.value.scrollTop = thread.value.scrollHeight
    }
  }
}
</script>
