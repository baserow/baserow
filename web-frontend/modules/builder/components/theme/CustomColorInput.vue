<template>
  <div class="custom-color-input__container margin-bottom-2">
    <FormGroup
      required
      class="custom-color-input__form-group"
      :error-message="colorNameError"
    >
      <FormInput
        :value="value.name"
        class="custom-color-input__input-name"
        @input="(newValue) => updateCustomColorName(newValue)"
      />
    </FormGroup>

    <FormGroup required>
      <ColorInput
        :value="value.color"
        small
        @input="(newValue) => updateExistingColor(newValue)"
      />
    </FormGroup>
    <ButtonIcon icon="iconoir-bin" @click="$emit('deleteCustomColor')" />
  </div>
</template>

<script>
const COLOR_NAME_MAX_LENGTH = 255

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
      colorNameError: '',
    }
  },
  beforeDestroy() {
    clearTimeout(this.nameTimeout)
    clearTimeout(this.colorTimeout)
  },
  methods: {
    updateCustomColorName(newValue) {
      this.colorNameError = ''

      const name = newValue.trim()
      if (!name) {
        this.colorNameError = this.$t('error.requiredField')
      } else if (name.length > COLOR_NAME_MAX_LENGTH) {
        this.colorNameError = this.$t('error.maxLength', {
          max: COLOR_NAME_MAX_LENGTH,
        })
      }

      if (this.colorNameError) {
        return
      }

      clearTimeout(this.nameTimeout)
      this.nameTimeout = setTimeout(() => {
        this.$emit('input', {
          name,
          color: this.value.color,
          value: this.value.value,
        })
      }, 500)
    },

    updateExistingColor(newValue) {
      clearTimeout(this.colorTimeout)
      this.colorTimeout = setTimeout(() => {
        this.$emit('input', {
          name: this.value.name,
          color: newValue,
          value: this.value.value,
        })
      }, 500)
    },
  },
}
</script>
