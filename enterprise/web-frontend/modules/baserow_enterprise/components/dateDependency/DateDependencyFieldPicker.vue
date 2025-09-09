<template>
  <FormGroup
    :label="fieldName"
    :required="required"
    :small-label="true"
    :helper-text="helperText"
    :error="hasError"
    :error-message="errorMessageStr"
  >
    <Dropdown
      :value="value"
      :show-search="true"
      :fixed-items="true"
      :disabled="disabled"
      :error="hasError"
      size="regular"
      @change="$emit('change', $event)"
    >
      <DropdownItem
        v-for="r in fields"
        :key="r.id"
        :name="r.name"
        :value="r.id"
        :icon="r.id ? icon : null"
      ></DropdownItem>
    </Dropdown>
  </FormGroup>
</template>
<script>
import _ from 'lodash'

export default {
  name: 'DateDependencyFieldPicker',
  props: {
    required: {
      type: Boolean,
      required: false,
      default: false,
    },
    fieldName: {
      type: String,
      required: true,
    },
    fields: {
      type: Array,
      required: true,
    },
    value: {
      type: [Number, String],
      required: false,
      default: null,
    },
    helperText: {
      type: String,
      required: false,
      default: null,
    },
    icon: {
      type: String,
      required: false,
      default: null,
    },
    errorMessage: {
      type: [String, Array],
      required: false,
      default: null,
    },
    disabled: { type: Boolean, required: false, default: false },
  },
  computed: {
    errorMessageStr() {
      if (_.isArray(this.errorMessage)) {
        return this.errorMessage.join('\n')
      }
      return this.errorMessage || ''
    },
    hasError() {
      return this.errors && this.errors.length > 0
    },
  },
}
</script>
