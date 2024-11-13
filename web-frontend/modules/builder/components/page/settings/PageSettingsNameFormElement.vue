<template>
  <FormGroup
    required
    small-label
    :label="$t('pageForm.nameTitle')"
    :error="hasErrors"
    :helper-text="$t('pageForm.nameSubtitle')"
  >
    <FormInput
      ref="input"
      size="large"
      :value="value"
      :disabled="disabled"
      @input="$emit('input', $event)"
      @blur="$emit('blur')"
      @focus.once="isCreation && $event.target.select()"
    >
    </FormInput>

    <template #error>
      <span v-if="validationState.required.$invalid">
        {{ $t('error.requiredField') }}
      </span>
      <span v-else-if="validationState.maxLength.$invalid">
        {{ $t('error.maxLength', { max: 255 }) }}
      </span>
      <span v-else-if="validationState.isUnique.$invalid">
        {{ $t('pageErrors.errorNameNotUnique') }}
      </span>
    </template>
  </FormGroup>
</template>

<script>
export default {
  name: 'PageSettingsNameFormElement',
  props: {
    value: {
      type: String,
      required: false,
      default: '',
    },
    hasErrors: {
      type: Boolean,
      required: false,
      default: false,
    },
    disabled: {
      type: Boolean,
      required: false,
      default: false,
    },
    validationState: {
      type: Object,
      required: false,
      default: () => ({}),
    },
    isCreation: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
}
</script>
