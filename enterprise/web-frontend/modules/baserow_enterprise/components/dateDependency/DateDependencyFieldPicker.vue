<template>
  <FormGroup
    :label="fieldName"
    :required="required"
    :small-label="true"
    :helper-text="helperText"
    :error="hasError"
  >
    <Dropdown
      ref="dropdown"
      :value="modelValue"
      show-search
      fixed-items
      show-footer
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
        :icon="r.icon ? r.icon : r.id ? icon : null"
      ></DropdownItem>

      <template #footer>
        <a
          class="select__footer-button"
          :class="{ 'button--loading': loading }"
          @click="$emit('add-new')"
        >
          <i class="iconoir-plus"></i>
          {{ $t('dateDependencyModal.addNewField') }}
        </a>
      </template>
    </Dropdown>
    <template #error>{{ errors[0].$message }}</template>
  </FormGroup>
</template>
<script>
import _ from 'lodash'

export default {
  name: 'DateDependencyFieldPicker',
  emits: ['update:modelValue', 'add-new'],
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
    addNew: { type: Boolean, required: false, default: false },
    loading: { type: Boolean, required: false, default: true },
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
  methods: {
    async hideDropdown() {
      await this.$nextTick()
      this.$refs.dropdown.hide()
    },
  },
}
</script>
