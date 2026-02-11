<template>
  <ButtonIcon
    v-if="propertyModified()"
    v-tooltip="$t('resetButton.reset')"
    tooltip-position="bottom-left"
    icon="iconoir-erase"
    @click="resetProperty()"
  />
</template>

<script>
import _ from 'lodash'

export default {
  inject: ['builder'],
  props: {
    value: { default: undefined, validator: (v) => true },
    modelValue: { default: undefined, validator: (v) => true },
    defaultValue: {
      required: false,
      validator: (v) => true,
      default: undefined,
    },
  },
  emits: ['input', 'update:modelValue'],
  data() {
    return {}
  },
  computed: {
    currentValue() {
      return this.modelValue !== undefined ? this.modelValue : this.value
    },
  },
  methods: {
    propertyModified() {
      return (
        this.defaultValue !== undefined &&
        !_.isEqual(this.currentValue, this.defaultValue)
      )
    },
    resetProperty() {
      this.$emit('input', this.defaultValue)
      this.$emit('update:modelValue', this.defaultValue)
    },
  },
}
</script>
