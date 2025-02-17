<template>
  <FormInput
    ref="input"
    :value="focused ? copy : formattedValue"
    :error="v$.copy.$error"
    :disabled="disabled"
    @blur="onBlur()"
    @keypress="onKeyPress($event)"
    @input="setCopyAndDelayedUpdate($event)"
    @keydown.enter="setCopyAndDelayedUpdate($event.target.value, true)"
    @focus="onFocus()"
  >
  </FormInput>
</template>

<script>
import filterTypeInput from '@baserow/modules/database/mixins/filterTypeInput'
import numberField from '@baserow/modules/database/mixins/numberField'

export default {
  name: 'ViewFilterTypeNumber',
  mixins: [filterTypeInput, numberField],
  data() {
    return {
      // Avoid rounding decimals to ensure filter values match backend behavior.
      roundDecimals: false,
    }
  },
  watch: {
    field: {
      handler() {
        if (!this.focused) {
          this.copy = this.prepareCopy(this.filter.value)
          this.updateFormattedValue(this.field, this.filter.value)
        }
      },
    },
  },
  created() {
    this.updateFormattedValue(this.field, this.copy)
  },
  methods: {
    afterValueChanged() {
      if (!this.focused) {
        this.updateFormattedValue(this.field, this.copy)
      }
    },
    setCopyAndDelayedUpdate(value, immediately = false) {
      this.updateCopy(this.field, value)
      const newValue = String(this.prepareValue(this.copy) ?? '')
      if (newValue !== this.filter.value) {
        this.delayedUpdate(newValue, immediately)
      }
    },
  },
}
</script>
