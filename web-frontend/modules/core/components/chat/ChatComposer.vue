<template>
  <form class="chat-composer" @submit.prevent="send">
    <div
      :id="error ? errorId : undefined"
      class="chat-composer__activity"
      :class="{
        'chat-composer__activity--visible': Boolean(error || activity),
        'chat-composer__activity--error': Boolean(error),
        'chat-composer__activity--waiting':
          !error && activityTone === 'waiting',
      }"
      :role="error ? 'alert' : undefined"
    >
      <i
        class="chat-composer__activity-icon"
        :class="activityIcon"
        aria-hidden="true"
      ></i>
      <span :key="error || activity" class="chat-composer__activity-text">{{
        error || activity
      }}</span>
    </div>
    <div class="chat-composer__box">
      <FormTextarea
        ref="input"
        :model-value="modelValue"
        :readonly="readonly"
        :disabled="disabled"
        :placeholder="placeholder"
        :aria-label="placeholder"
        :aria-describedby="describedBy"
        auto-expandable
        :min-rows="1"
        :max-rows="6"
        :maxlength="maxlength"
        @update:model-value="$emit('update:modelValue', $event)"
        @keydown="sendOnEnter"
      />
      <button
        v-if="running"
        type="button"
        class="chat-composer__button chat-composer__button--stop"
        :class="{ 'chat-composer__button--loading': stopping }"
        :disabled="stopping"
        :aria-label="stopLabel"
        :title="stopLabel"
        @click="$emit('stop')"
      >
        <span class="chat-composer__stop-icon"></span>
      </button>
      <button
        v-else
        type="submit"
        class="chat-composer__button"
        :class="{
          'chat-composer__button--ready': canSend && !disabled,
          'chat-composer__button--loading': sending,
        }"
        :disabled="!canSend || sending || disabled"
        :aria-label="sendLabel"
        :title="sendLabel"
      >
        <i class="iconoir-arrow-up"></i>
      </button>
    </div>
  </form>
</template>

<script setup>
import { computed, nextTick, ref, watch } from 'vue'

const props = defineProps({
  modelValue: { type: String, default: '' },
  placeholder: { type: String, default: '' },
  /** Keeps a message that is being sent from being edited. */
  readonly: { type: Boolean, default: false },
  /** Blocks writing and sending while the conversation can't continue. */
  disabled: { type: Boolean, default: false },
  maxlength: { type: Number, default: null },
  /** The id of the element describing the input, like a send error. */
  describedBy: { type: String, default: undefined },
  canSend: { type: Boolean, default: false },
  sending: { type: Boolean, default: false },
  /** Whether a reply is being written, which turns send into stop. */
  running: { type: Boolean, default: false },
  stopping: { type: Boolean, default: false },
  /** What the reply is doing, shown above the input while it runs. */
  activity: { type: String, default: '' },
  /** `waiting` marks an activity that needs the reader to act. */
  activityTone: {
    type: String,
    default: 'default',
    validator: (tone) => ['default', 'waiting'].includes(tone),
  },
  /** A request error takes precedence over the reply's activity. */
  error: { type: String, default: '' },
  errorId: { type: String, default: undefined },
  sendLabel: { type: String, required: true },
  stopLabel: { type: String, required: true },
})
const emit = defineEmits(['update:modelValue', 'send', 'stop'])

const input = ref(null)
const activityIcon = computed(() => {
  if (props.error) return 'iconoir-warning-circle'
  return props.activityTone === 'waiting'
    ? 'iconoir-shield-check'
    : 'iconoir-sparks'
})

// Send and Stop are separate buttons, so a focused one goes away when they swap.
watch(
  () => props.running,
  async () => {
    if (!document.activeElement?.classList.contains('chat-composer__button')) {
      return
    }
    await nextTick()
    input.value?.focus()
  }
)

function send() {
  if (props.canSend && !props.sending && !props.running && !props.disabled) {
    emit('send')
  }
}

function sendOnEnter(event) {
  // Safari sends the Enter that commits an IME composition with keyCode 229.
  if (event.isComposing || event.keyCode === 229) return
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    send()
  }
}

defineExpose({ focus: () => input.value?.focus() })
</script>
