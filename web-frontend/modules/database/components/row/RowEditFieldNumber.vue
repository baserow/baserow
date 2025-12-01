<template>
  <FormGroup :error="touched && !valid">
    <FormInput
      ref="input"
      :value="focused ? copy : formattedValue"
      size="large"
      :error="touched && !valid"
      :disabled="readOnly"
      @keypress="onKeyPress"
      @keyup.enter="
        onBlur()
        $refs.input.blur()
      "
      @focus="
        onFocus()
        select()
      "
      @blur="
        onBlur()
        unselect()
      "
      @input="handleInput"
    />

    <template #error>
      <span v-show="touched && !valid">
        {{ error }}
      </span>
    </template>
  </FormGroup>
</template>

<script>
import BigNumber from 'bignumber.js'
import rowEditField from '@baserow/modules/database/mixins/rowEditField'
import rowEditFieldInput from '@baserow/modules/database/mixins/rowEditFieldInput'
import numberField from '@baserow/modules/database/mixins/numberField'

export default {
  mixins: [rowEditField, rowEditFieldInput, numberField],
  watch: {
    field: {
      immediate: true,
      handler() {
        this.initCopy(this.value)
      },
    },
    value: {
      handler(newValue) {
        this.initCopy(newValue)
      },
    },
  },
  created() {
    // Backend values are unformatted decimals, so make sure to format them correctly.
    if (this.value != null && this.value !== '') {
      this.updateFormattedValue(this.field, new BigNumber(this.value))
    }
  },
  methods: {
    initCopy(value) {
      this.copy = this.prepareCopy(value ?? '')
      this.updateFormattedValue(this.field, this.copy ?? '')
    },
    handleInput(newCopy) {
      this.updateCopy(this.field, newCopy)
      this.$emit('input', this.copy)
    },
  },
}
</script>
