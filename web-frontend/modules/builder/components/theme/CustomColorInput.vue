<template>
  <div class="custom-color-input__container margin-bottom-2">
    <FormGroup
      required
      class="custom-color-input__form-group"
      :error-message="err"
    >
      <FormInput
        :value="value.name"
        class="custom-color-input__input-name"
        @input="update({ name: $event })"
      />
    </FormGroup>

    <FormGroup required>
      <ColorInput
        :value="value.color"
        small
        @input="update({ color: $event })"
      />
    </FormGroup>
    <ButtonIcon icon="iconoir-bin" @click="$emit('deleteCustomColor')" />
  </div>
</template>

<script>
import { maxLength, required } from 'vuelidate/lib/validators'
const COLOR_NAME_MAX_LENGTH = 255

export default {
  props: {
    value: {
      type: Object,
      required: true,
    },
  },
  computed: {
    err() {
      return this.$v.value.name.$dirty
        ? !this.$v.value.name.required
          ? this.$t('error.requiredField')
          : !this.$v.value.name.maxLength
          ? this.$t('error.maxLength', {
              max: COLOR_NAME_MAX_LENGTH,
            })
          : ''
        : ''
    },
  },
  methods: {
    update(update) {
      this.$v.$touch()
      this.$emit('input', { ...this.value, ...update })
    },
  },
  validations() {
    return {
      value: {
        name: { maxLength: maxLength(COLOR_NAME_MAX_LENGTH), required },
      },
    }
  },
}
</script>
