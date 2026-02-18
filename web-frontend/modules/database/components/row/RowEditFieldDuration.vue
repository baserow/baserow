<template>
  <FormGroup class="margin-bottom-2" :error="touched && !valid">
    <FormInput
      ref="input"
      v-model="formattedValue"
      size="large"
      :placeholder="field.duration_format"
      :error="touched && !valid"
      :disabled="readOnly"
      class="field-duration"
      @keypress="onKeyPress(field, $event)"
      @keyup.enter="$refs.input?.$el?.blur()"
      @keyup="updateCopy(field, $event.target.value)"
      @focus="select()"
      @blur="unselect()"
    ></FormInput>

    <template #error>
      {{ error }}
    </template>
  </FormGroup>
</template>

<script>
import rowEditField from '@baserow/modules/database/mixins/rowEditField'
import rowEditFieldInput from '@baserow/modules/database/mixins/rowEditFieldInput'
import durationField from '@baserow/modules/database/mixins/durationField'

export default {
  mixins: [rowEditField, rowEditFieldInput, durationField],
  watch: {
    'field.duration_format': {
      handler() {
        this.updateCopy(this.field, this.value)
        this.updateFormattedValue(this.field, this.copy)
      },
    },
    value: {
      handler(newValue) {
        this.updateCopy(this.field, newValue)
        this.updateFormattedValue(this.field, this.copy)
      },
    },
  },
}
</script>
