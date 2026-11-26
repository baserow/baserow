<template>
  <FormGroup
    class="agent-channel-section__field"
    :label="label"
    small-label
    required
  >
    <p class="agent-channel-copy-field__note">{{ note }}</p>
    <div class="agent-channel-copy-field">
      <div class="agent-channel-copy-field__text">{{ text }}</div>
      <a
        v-tooltip="copyLabel"
        href="#"
        class="agent-channel-copy-field__copy"
        :aria-label="copyLabel"
        @click.prevent="copy"
      >
        <i class="iconoir-copy" aria-hidden="true" />
        <Copied ref="copied" />
      </a>
    </div>
  </FormGroup>
</template>

<script setup>
import { ref } from 'vue'
import { copyToClipboard } from '@baserow/modules/core/utils/clipboard'

const props = defineProps({
  label: { type: String, required: true },
  /** What the text is for, above it. */
  note: { type: String, required: true },
  /** The text to show on one line and copy. */
  text: { type: String, required: true },
  copyLabel: { type: String, required: true },
})
const copied = ref(null)

function copy() {
  copyToClipboard(props.text)
  copied.value.show()
}
</script>
