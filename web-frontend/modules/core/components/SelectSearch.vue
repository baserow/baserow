<template>
  <div class="select__search">
    <i class="select__search-icon iconoir-search"></i>
    <input
      :value="currentValue"
      type="text"
      class="select__search-input"
      v-bind="$attrs"
      :placeholder="placeholder || $t('action.search')"
      @input="emitChange($event.target.value)"
    />
  </div>
</template>

<script>
export default {
  name: 'SelectSearch',
  props: {
    value: {
      type: String,
      default: undefined,
    },
    modelValue: {
      type: String,
      default: undefined,
    },
    placeholder: {
      type: String,
      required: false,
      default: '',
    },
  },
  emits: ['input', 'update:modelValue'],
  computed: {
    currentValue() {
      return this.modelValue !== undefined ? this.modelValue : this.value
    },
  },
  methods: {
    emitChange(newValue) {
      this.$emit('input', newValue)
      this.$emit('update:modelValue', newValue)
    },
  },
}
</script>
