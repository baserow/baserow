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
  methods: {
    updateCustomColorName(newValue) {
      this.$emit('input', {name: newValue, color: this.value.color})
    },
    updateExistingColor(newValue) {
      this.$emit('input', {name: this.value.name, color: newValue})
    },
  },
}
</script>
