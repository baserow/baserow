<template>
  <template v-if="available">
    <button
      ref="trigger"
      type="button"
      class="prompt-context__trigger"
      aria-haspopup="dialog"
      :aria-expanded="open"
      @click.stop="toggle"
    >
      <i class="iconoir-sparks" aria-hidden="true"></i>
      {{ $t('kumaPrompt.askKuma') }}
    </button>
    <Context
      ref="context"
      class="prompt-context"
      role="dialog"
      :aria-label="title"
      :hide-on-click-outside="!busy"
      :horizontal-viewport-margin="8"
      @hidden="onHidden"
      @keydown.esc.stop.prevent="close"
    >
      <div v-if="open && summary" class="kuma-prompt__result" role="status">
        <span>{{ summary }}</span>
        <ButtonText
          v-if="changed && action === 'update_service_filters'"
          size="small"
          @click="undo"
        >
          {{ $t('kumaInlinePrompt.undo') }}
        </ButtonText>
        <ButtonIcon
          ref="dismissButton"
          icon="iconoir-cancel"
          type="secondary"
          size="small"
          :aria-label="$t('kumaInlinePrompt.dismiss')"
          @click.prevent="close"
        />
      </div>
      <template v-else-if="open">
        <div class="prompt-context__input">
          <textarea
            ref="input"
            v-model="message"
            class="form-textarea"
            :aria-label="placeholder"
            :placeholder="placeholder"
            :disabled="busy"
            maxlength="2000"
            rows="2"
            @keydown.enter.exact="onEnter"
          />
          <Button
            button-type="button"
            size="small"
            append-icon="iconoir-arrow-up"
            :disabled="!canSend"
            :loading="busy"
            @click="send"
            >{{ $t('kumaPrompt.send') }}</Button
          >
        </div>
        <p v-if="busy || notice" class="prompt-context__notice" role="status">
          {{ busy ? $t('kumaInlinePrompt.working') : notice }}
        </p>
      </template>
    </Context>
  </template>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { useStore } from 'vuex'
import AssistantService from '@baserow_enterprise/services/assistant'
import { isAssistantAvailable } from '@baserow_enterprise/utils/assistant'

const props = defineProps({
  enabled: { type: Boolean, default: true },
  workspace: { type: Object, default: null },
  title: { type: String, required: true },
  placeholder: { type: String, required: true },
  blockedMessage: { type: String, default: '' },
  action: { type: String, required: true },
  parameters: { type: Object, required: true },
})
const emit = defineEmits(['active', 'completed'])
const app = useNuxtApp()
const store = useStore()
const available = computed(() => {
  const workspace = props.workspace || store.getters['workspace/getSelected']
  return props.enabled && workspace?.id && isAssistantAvailable(app, workspace)
})
const summary = ref('')
const dismissButton = ref(null)
const changed = ref(false)

function dismiss() {
  if (summary.value) context.value?.hide()
}

watch(available, (shown) => {
  if (!shown) {
    onHidden()
  }
})

async function undo() {
  close()
  await store.dispatch('undoRedo/undo', { showLoadingToast: true })
}

const trigger = ref(null)
const context = ref(null)
const input = ref(null)
const open = ref(false)
const message = ref('')
const busy = ref(false)
const error = ref('')
const notice = computed(() => props.blockedMessage || error.value)
const canSend = computed(
  () =>
    open.value && !busy.value && !props.blockedMessage && !!message.value.trim()
)
let mounted = true
onBeforeUnmount(() => {
  mounted = false
})

async function toggle() {
  if (open.value) return close()
  open.value = true
  error.value = ''
  emit('active', true)
  await context.value.show(trigger.value, 'bottom', 'left', 5)
  await nextTick()
  input.value?.focus()
}

function close() {
  if (busy.value) return
  context.value?.hide()
  trigger.value?.focus()
}

function onHidden() {
  if (open.value && !summary.value) emit('active', false)
  summary.value = ''
  changed.value = false
  open.value = false
}

function onEnter(event) {
  if (event.isComposing || event.keyCode === 229) return
  event.preventDefault()
  send()
}

async function send() {
  if (!canSend.value) return
  busy.value = true
  error.value = ''
  try {
    const result = await AssistantService(app.$client).runAction(
      props.action,
      message.value.trim(),
      props.parameters
    )
    if (!mounted || !available.value || !open.value) return
    busy.value = false
    message.value = ''
    const showSummary =
      !result.changed || props.action === 'update_service_filters'
    if (showSummary && result.summary) {
      summary.value = result.summary
      changed.value = result.changed
      emit('active', false)
      await nextTick()
      dismissButton.value?.$el.focus()
    } else {
      close()
    }
    emit('completed', result.result)
  } catch (err) {
    if (!err.handler) throw err
    error.value = err.handler.getMessage().message
    err.handler.handled()
  } finally {
    busy.value = false
    if (mounted && open.value) {
      await nextTick()
      input.value?.focus()
    }
  }
}

defineExpose({ dismiss })
</script>
