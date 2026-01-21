<template>
  <input
    v-model="inputValue"
    v-bind="$attrs"
    class="preview-navigation-bar-input"
    :class="{
      'preview-navigation-bar-input--invalid': invalidValueForType,
    }"
  />
</template>

<script>
import _ from 'lodash'

export default {
  inheritAttrs: false,
  props: {
    defaultValue: {
      type: [String, Number, Array],
      required: false,
      default: '',
    },
    validationFn: {
      type: Function,
      required: true,
    },
  },
  emits: ['change'],
  data() {
    return {
      value: this.defaultValue,
      invalidValueForType: false,
    }
  },
  computed: {
    inputValue: {
      get() {
        return this.value
      },
      set(inputValue) {
        this.invalidValueForType = false
        this.value = inputValue
        try {
          this.$emit('change', this.validationFn(this.value))
        } catch (error) {
          this.invalidValueForType = true
        }
      },
    },
  },
  watch: {
    defaultValue(newValue) {
      if (!_.isEqual(this.inputValue, newValue)) {
        this.inputValue = newValue
      }
    },
  },
}
</script>
