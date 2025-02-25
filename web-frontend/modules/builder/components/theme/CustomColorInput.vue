<template>
  <div class="custom-color-input__container margin-bottom-2">
    <FormGroup
      required
      class="custom-color-input__form-group"
      :error="v$.value.name.$error"
    >
      <FormInput
        :value="v$.value.name.$model"
        class="custom-color-input__input-name"
        @input="update({ name: $event })"
      />

      <template #error>
        {{ v$.value.name.$errors[0].$message }}
      </template>
    </FormGroup>

    <FormGroup required>
      <ColorInput
        :value="v$.value.color.$model"
        small
        @input="update({ color: $event })"
      />
    </FormGroup>
    <ButtonIcon icon="iconoir-bin" @click="$emit('deleteCustomColor')" />
  </div>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import { maxLength, required, helpers } from '@vuelidate/validators'
const COLOR_NAME_MAX_LENGTH = 255

export default {
  props: {
    value: {
      type: Object,
      required: true,
    },
  },
  setup() {
    return { v$: useVuelidate({ $lazy: true }) }
  },

  methods: {
    update(update) {
      this.v$.$touch()
      this.$emit('input', { ...this.value, ...update })
    },
  },
  validations() {
    return {
      value: {
        name: {
          maxLength: helpers.withMessage(
            this.$t('error.maxLength', { max: COLOR_NAME_MAX_LENGTH }),
            maxLength(COLOR_NAME_MAX_LENGTH)
          ),
          required: helpers.withMessage(
            this.$t('error.requiredField'),
            required
          ),
        },
        color: {},
      },
    }
  },
}
</script>
