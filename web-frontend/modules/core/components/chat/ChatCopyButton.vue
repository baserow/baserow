<template>
  <button
    v-tooltip="$t('action.copy')"
    type="button"
    class="chat-message__action"
    :aria-label="$t('action.copy')"
    @click="copy"
  >
    <i class="iconoir-copy"></i>
    <Copied ref="copied" />
  </button>
</template>

<script setup>
import { ref } from 'vue'

const props = defineProps({ text: { type: String, required: true } })
const emit = defineEmits(['error'])

const copied = ref(null)

async function copy() {
  try {
    await navigator.clipboard.writeText(props.text)
  } catch (error) {
    emit('error', error)
    return
  }
  copied.value?.show()
}
</script>
