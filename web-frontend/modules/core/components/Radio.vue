<template>
  <div class="radio" :class="classNames" @click="select(value)">
    <div v-if="loading" class="radio__loading"></div>
    <div v-else class="radio__input">
      <input
        type="radio"
        :value="value"
        :checked="modelValue === value"
        :disabled="disabled || loading"
      />
      <label></label>
    </div>
    <div v-if="hasSlot" class="radio__label">
      <slot></slot>
    </div>
  </div>
</template>

<script>
export default {
  name: 'Radio',
  props: {
    value: {
      type: [String, Number, Boolean, Object],
      required: false,
      default: '',
    },
    modelValue: {
      type: [String, Number, Boolean, Object],
      required: false,
      default: '',
    },
    disabled: {
      type: Boolean,
      required: false,
      default: false,
    },
    loading: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  emits: ['input', 'update:modelValue'],
  computed: {
    classNames() {
      return {
        'radio--active': this.modelValue === this.value,
        'radio--disabled': this.disabled,
        'radio--loading': this.loading,
        selected: this.modelValue === this.value,
      }
    },
    selected() {
      return this.modelValue === this.value
    },
    hasSlot() {
      return !!this.$slots.default
    },
  },
  methods: {
    select(value) {
      if (this.disabled || this.selected || this.loading) {
        return
      }
      this.$emit('update:modelValue', value)
      this.$emit('input', value)
    },
  },
}
</script>
