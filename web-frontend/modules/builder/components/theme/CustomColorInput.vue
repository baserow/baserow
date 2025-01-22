<template>
  <div class="custom-color-input__container">
    <FormInput
      :value="value.name"
      class="custom-color-input__input-name margin-bottom-2"
      @input="(newValue) => updateCustomColorName(newValue)"
    />

    <ColorInput
      :value="value.color"
      small
      @input="(newValue) => updateExistingColor(newValue)"
    />
    
    <ButtonIcon icon="iconoir-bin" @click="$emit('deleteCustomColor')" />
  </div>
</template>

<script>
export default {
  props: {
    value: {
      type: Object,
      required: true,
    },
  },
  data() {
    return {
      nameTimeout: null,
      colorTimeout: null,
    }
  },
  methods: {
    updateCustomColorName(newValue) {
      clearTimeout(this.nameTimeout)
      this.nameTimeout = setTimeout(() => {
        this.$emit('input', {name: newValue, color: this.value.color})
      }, 500)      
    },
    updateExistingColor(newValue) {
      clearTimeout(this.colorTimeout)
      this.colorTimeout = setTimeout(() => {
        this.$emit('input', {name: this.value.name, color: newValue})
      }, 500)      
    },
  },
  beforeDestroy() {
    clearTimeout(this.nameTimeout)
    clearTimeout(this.colorTimeout)
  },
}
</script>
