<template>
  <div v-if="text" class="chat-tool-input">
    <pre
      class="chat-tool-input__values"
      tabindex="0"
      :aria-label="$t('toolPresentation.input')"
    ><code>{{ text }}</code></pre>
    <p v-if="input.truncated" class="chat-tool-input__note">
      {{ $t('toolPresentation.inputTruncated') }}
    </p>
  </div>
</template>

<script setup>
import { computed } from 'vue'

/** A tool's input preview, with a note when the backend shortened it. */
const props = defineProps({
  /** `{values, truncated}`, as `toolActivity` resolves it. */
  input: { type: Object, default: null },
})

const text = computed(() =>
  props.input ? JSON.stringify(props.input.values, null, 2) : ''
)
</script>
