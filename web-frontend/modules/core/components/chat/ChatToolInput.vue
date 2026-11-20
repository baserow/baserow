<template>
  <div v-if="input" class="chat-tool-input">
    <div v-if="rows" class="chat-tool-input__values" tabindex="0">
      <table
        class="chat-tool-input__table"
        :aria-label="$t('toolPresentation.input')"
      >
        <tbody>
          <tr v-for="[key, value] in rows" :key="key">
            <th scope="row">{{ key }}</th>
            <td>
              <pre>{{
                typeof value === 'string'
                  ? value
                  : JSON.stringify(value, null, 2)
              }}</pre>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <pre
      v-else
      class="chat-tool-input__values"
      tabindex="0"
      :aria-label="$t('toolPresentation.input')"
    ><code>{{ JSON.stringify(input.values, null, 2) }}</code></pre>
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

const rows = computed(() => {
  const values = props.input?.values
  return values &&
    typeof values === 'object' &&
    !Array.isArray(values) &&
    Object.keys(values).length
    ? Object.entries(values)
    : null
})
</script>
