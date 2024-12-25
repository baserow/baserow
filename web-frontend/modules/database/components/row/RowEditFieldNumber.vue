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
import rowEditField from '@baserow/modules/database/mixins/rowEditField'
import rowEditFieldInput from '@baserow/modules/database/mixins/rowEditFieldInput'
import numberField from '@baserow/modules/database/mixins/numberField'

export default {
  mixins: [rowEditField, rowEditFieldInput, numberField],
  watch: {
    field: {
      handler() {
        this.initCopy(this.value)
      },
    },
    value: {
      handler(newValue) {
        this.initCopy(newValue)
      },
      immediate: true,
    },
  },
  methods: {
    initCopy(value) {
      this.copy = this.prepareCopy(value ?? '')
      this.updateCopy(this.field, this.copy)
      this.updateFormattedValue(this.field, this.copy)
    },
    handleInput(value) {
      this.updateCopy(this.field, value)
      this.$emit('input', this.copy)
    },
  },
}
</script>
