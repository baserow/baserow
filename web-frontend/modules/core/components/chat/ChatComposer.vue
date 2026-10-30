<template>
  <form class="chat-composer" @submit.prevent="$emit('send')">
    <div
      class="chat-composer__activity"
      :class="{ 'chat-composer__activity--visible': Boolean(activity) }"
    >
      <i class="iconoir-sparks chat-composer__activity-icon"></i>
      <span :key="activity" class="chat-composer__activity-text">{{
        activity
      }}</span>
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
import { nextTick, ref, watch } from 'vue'

const props = defineProps({
  modelValue: { type: String, default: '' },
  placeholder: { type: String, default: '' },
  /** Keeps a message that is being sent from being edited. */
  readonly: { type: Boolean, default: false },
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
  sendLabel: { type: String, required: true },
  stopLabel: { type: String, required: true },
})
const emit = defineEmits(['update:modelValue', 'send', 'stop'])

const input = ref(null)

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
