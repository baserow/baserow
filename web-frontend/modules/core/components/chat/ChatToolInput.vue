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

<script>
import { computed } from 'vue'

/**
 * Formats a tool's input preview, so callers can also tell whether there is
 * anything to show.
 *
 * @param {{values: object, truncated: boolean}|null} input The input preview.
 * @returns {string} The values as indented JSON, or '' when none can be shown.
 */
export function toolInputText(input) {
  const values = input?.values
  if (
    !values ||
    typeof values !== 'object' ||
    Array.isArray(values) ||
    !Object.keys(values).length
  ) {
    return ''
  }
  try {
    return JSON.stringify(values, null, 2)
  } catch {
    return ''
  }
}
</script>

<script setup>
/** A tool's input preview, with a note when the backend shortened it. */
const props = defineProps({
  /** `{values, truncated}`, as `toolActivity` resolves it. */
  input: { type: Object, default: null },
})

const text = computed(() => toolInputText(props.input))
</script>
