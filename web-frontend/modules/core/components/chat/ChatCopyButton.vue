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

const props = defineProps({
  /** The text to copy. */
  text: { type: String, required: true },
})

const copied = ref(null)

async function copy() {
  await navigator.clipboard.writeText(props.text)
  copied.value.show()
}
</script>
