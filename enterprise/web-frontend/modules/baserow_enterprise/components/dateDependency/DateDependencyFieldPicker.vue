<template>
  <FormGroup
    :label="fieldName"
    :required="required"
    :small-label="true"
    :helper-text="helperText"
  >
    <Dropdown
      :value="value"
      :show-search="true"
      :fixed-items="true"
      :error="error"
      :disabled="disabled"
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
    <slot name="error"></slot>
  </FormGroup>
</template>
<script>
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
    error: {
      type: Boolean,
      required: false,
      default: null,
    },
    disabled: { type: Boolean, required: false, default: false },
  },
  methods: {},
}
</script>
