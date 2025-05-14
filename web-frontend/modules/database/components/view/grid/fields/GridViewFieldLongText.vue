<template>
  <div
    ref="cell"
    class="grid-view__cell grid-field-long-text__cell active"
    :class="{ editing: opened }"
    @contextmenu="stopContextIfEditing($event)"
  >
    <div v-if="!opened" class="grid-field-long-text">{{ value }}</div>
    <textarea
      v-else-if="editing"
      ref="input"
      v-model="copy"
      v-prevent-parent-scroll
      :disabled="readOnly"
      type="text"
      class="grid-field-long-text__textarea"
    />
    <div v-else class="grid-field-long-text__textarea">{{ value }}</div>
    <slot name="default" :slot-props="{ editing, opened }"></slot>
  </div>
</template>

<script>
import gridField from '@baserow/modules/database/mixins/gridField'
import gridFieldInput from '@baserow/modules/database/mixins/gridFieldInput'

export default {
  mixins: [gridField, gridFieldInput],
  methods: {
    afterEdit(event) {
      // If the enter key is pressed we do not want to add a new line to the textarea.
      if (event.type === 'keydown' && event.key === 'Enter') {
        event.preventDefault()
      }
      this.$nextTick(() => {
        this.$refs.input.focus()
        this.$refs.input.selectionStart = this.$refs.input.selectionEnd = 100000
      })
    },
    canSaveByPressingEnter(event) {
      // Save only if shiftKey is pressed
      return event.shiftKey
    },
  },
}
</script>
