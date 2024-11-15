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
      :placeholder="$t('pageForm.namePlaceholder')"
      :value="value"
      :disabled="disabled"
      @input="$emit('input', $event)"
      @blur="$emit('blur')"
      @focus.once="isCreation && $event.target.select()"
    >
    </FormInput>

    <template #error>
      <span v-if="validationState.$dirty && !validationState.required">
        {{ $t('error.requiredField') }}
      </span>
      <span v-if="validationState.$dirty && !validationState.maxLength">
        {{ $t('error.maxLength', { max: 255 }) }}
      </span>
      <span v-if="validationState.$dirty && !validationState.isUnique">
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
