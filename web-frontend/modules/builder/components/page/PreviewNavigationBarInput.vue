<template>
  <input
    v-model="inputValue"
    class="preview-navigation-bar-input"
    :class="{
      'preview-navigation-bar-input--invalid': invalidValueForType,
    }"
  />
</template>

<script>
import _ from 'lodash'

export default {
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
