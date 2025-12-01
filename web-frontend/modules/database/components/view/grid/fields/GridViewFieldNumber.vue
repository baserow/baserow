<template>
  <div
    class="grid-view__cell active"
    :class="{
      editing: editing,
      invalid: editing && !valid,
    }"
    @contextmenu="stopContextIfEditing($event)"
  >
    <div v-show="!editing" class="grid-field-number">{{ formattedValue }}</div>
    <template v-if="editing">
      <input
        ref="input"
        v-model="copy"
        type="text"
        class="grid-field-number__input"
        @keypress="onKeyPress($event)"
        @paste="onPaste($event)"
      />
      <div v-show="!valid" class="grid-view__cell-error align-right">
        {{ error }}
      </div>
    </template>
  </div>
</template>

<script>
import gridField from '@baserow/modules/database/mixins/gridField'
import gridFieldInput from '@baserow/modules/database/mixins/gridFieldInput'
import numberField from '@baserow/modules/database/mixins/numberField'

export default {
  mixins: [gridField, gridFieldInput, numberField],
  watch: {
    value: {
      handler(newVal) {
        if (!this.editing) {
          this.copy = this.prepareCopy(newVal)
          this.updateFormattedValue(this.field, this.copy ?? '')
        }
      },
      immediate: true,
    },
    editing: {
      handler(newVal, oldVal) {
        if (newVal && !oldVal) {
          // Put the cursor before the decimal separator or the suffix
          // for a better editing experience.
          this.$nextTick(() => {
            const input = this.$refs.input
            const cursorPos = this.getStartEditIndex(this.field, input.value)
            input.focus()
            input.setSelectionRange(cursorPos, cursorPos)
          })
        }
      },
    },
  },
  methods: {
    onPaste(event) {
      event.preventDefault()
      const pastedText = (event.clipboardData || window.clipboardData).getData(
        'text'
      )
      this.copy = this.formatNumberValueForEdit(
        this.field,
        this.parseNumberValue(this.field, pastedText)
      )
      this.updateFormattedValue(this.field, this.copy ?? '')
    },
    afterEdit(event, value) {
      this.updateFormattedValue(this.field, this.copy ?? '')
      this.$nextTick(() => {
        this.$refs.input.focus()
        this.$refs.input.selectionStart = this.$refs.input.selectionEnd = 100000
      })
    },
  },
}
</script>
