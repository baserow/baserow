<template>
  <form class="chat-composer" @submit.prevent="$emit('send')">
    <div
      class="chat-composer__status"
      :class="{ 'chat-composer__status--visible': Boolean(status) }"
    >
      <i class="iconoir-sparks chat-composer__status-icon"></i>
      <span :key="status" class="chat-composer__status-text">{{ status }}</span>
    </div>
    <div class="chat-composer__box">
      <FormTextarea
        ref="input"
        :model-value="modelValue"
        :readonly="readonly"
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
          'chat-composer__button--ready': canSend,
          'chat-composer__button--loading': sending,
        }"
        :disabled="!canSend || sending"
        :aria-label="sendLabel"
        :title="sendLabel"
      >
        <i class="iconoir-arrow-up"></i>
      </button>
    </div>
  </form>
</template>

<script setup>
import { ref } from 'vue'

const props = defineProps({
  modelValue: { type: String, default: '' },
  placeholder: { type: String, default: '' },
  /** Keeps a message that is being sent from being edited. */
  readonly: { type: Boolean, default: false },
  maxlength: { type: Number, default: null },
  /** The id of the element describing the input, like a send error. */
  describedBy: { type: String, default: undefined },
  /** Whether the message can be sent now. */
  canSend: { type: Boolean, default: false },
  sending: { type: Boolean, default: false },
  /** Whether a reply is being written, which turns send into stop. */
  running: { type: Boolean, default: false },
  stopping: { type: Boolean, default: false },
  /** What the reply is doing, shown above the input while it runs. */
  status: { type: String, default: '' },
  sendLabel: { type: String, required: true },
  stopLabel: { type: String, required: true },
})
const emit = defineEmits(['update:modelValue', 'send', 'stop'])

const input = ref(null)

function sendOnEnter(event) {
  // Safari sends the Enter that commits an IME composition with keyCode 229.
  if (event.isComposing || event.keyCode === 229) return
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    if (props.canSend && !props.sending && !props.running) emit('send')
  }
}

defineExpose({ focus: () => input.value?.focus() })
</script>
