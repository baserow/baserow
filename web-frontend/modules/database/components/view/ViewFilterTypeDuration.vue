<template>
  <FormInput
    ref="input"
    v-model="formattedValue"
    :placeholder="field.duration_format"
    :error="v$.formattedValue.$error"
    :disabled="disabled"
    @blur="updateFormattedValue(field, copy)"
    @keypress="onKeyPress(field, $event)"
    @keyup="setCopyAndDelayedUpdate($event.target.value)"
    @keydown.enter="setCopyAndDelayedUpdate($event.target.value, true)"
  >
  </FormInput>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import filterTypeInput from '@baserow/modules/database/mixins/filterTypeInput'
import durationField from '@baserow/modules/database/mixins/durationField'

export default {
  name: 'ViewFilterTypeDuration',
  mixins: [filterTypeInput, durationField],
  setup() {
    return { v$: useVuelidate({ $lazy: true }) }
  },
  watch: {
    'field.duration_format': {
      handler() {
        this.updateFormattedValue(this.field, this.filter.value)
      },
    },
  },
  created() {
    this.updateCopy(this.field, this.filter.value)
    this.updateFormattedValue(this.field, this.filter.value)
  },
  methods: {
    isInputValid() {
      return !this.v$.formattedValue.$error
    },
    focus() {
      this.$refs.input.focus()
    },
    afterValueChanged(value, oldValue) {
      this.updateFormattedValue(this.field, value)
    },
    setCopyAndDelayedUpdate(value, immediately = false) {
      const newValue = this.updateCopy(this.field, value)
      if (newValue !== undefined) {
        // a filter Value cannot be null, so send an empty string in case.
        const filterValue = newValue === null ? '' : newValue
        this.delayedUpdate(filterValue, immediately)
      }
    },
    getValidationError(value) {
      const fieldType = this.$registry.get('field', this.field.type)
      return fieldType.getValidationError(this.field, value)
    },
  },
  validations() {
    return {
      copy: {},
      formattedValue: {
        isValid(value) {
          return this.getValidationError(value) === null
        },
      },
    }
  },
}
</script>
