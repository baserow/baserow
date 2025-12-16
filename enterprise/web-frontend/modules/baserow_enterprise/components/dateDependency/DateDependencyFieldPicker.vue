<template>
  <FormGroup
    :label="fieldName"
    :required="required"
    :small-label="true"
    :helper-text="helperText"
    :error="hasError"
  >
    <Dropdown
      :value="modelValue"
      :show-search="true"
      :fixed-items="true"
      :disabled="disabled"
      :error="hasError"
      size="regular"
      @update:model-value="$emit('update:modelValue', $event)"
    >
      <DropdownItem
        v-for="r in fields"
        :key="r.id"
        :name="r.name"
        :value="r.id"
        :icon="r.id ? icon : null"
      ></DropdownItem>
    </Dropdown>
    <template #error>{{ errors[0].$message }}</template>
  </FormGroup>
</template>
<script>
import _ from 'lodash'

export default {
  name: 'DateDependencyFieldPicker',
  emits: ['update:modelValue'],
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
    modelValue: {
      type: [Number, String],
      required: false,
      default: null,
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
    errors: {
      type: [Array, null],
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
      return Boolean(this.errors?.length > 0)
    },
  },
}
</script>
