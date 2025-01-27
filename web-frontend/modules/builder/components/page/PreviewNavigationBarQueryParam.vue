<template>
  <div class="preview-navigation-bar-param">
    <label :for="name" class="preview-navigation-bar-param__label">
      {{ name }}=</label
    ><input
      :id="name"
      v-model="inputValue"
      class="preview-navigation-bar-input"
    />
  </div>
</template>

<script>
export default {
  props: {
    defaultValue: {
      type: [String, Number],
      required: false,
      default: '',
    },
    name: {
      type: String,
      required: true,
    },
  },
  data() {
    return {
      value: this.defaultValue,
    }
  },
  computed: {
    inputValue: {
      get() {
        return this.value
      },
      set(inputValue) {
        this.value = inputValue
        this.$emit('change', this.value)
      },
    },
  },
  watch: {
    defaultValue(newValue) {
      this.value = newValue
    },
  },
}
</script>
