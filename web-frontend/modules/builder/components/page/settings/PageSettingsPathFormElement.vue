<template>
  <FormGroup
    required
    small-label
    :label="$t('pageForm.pathTitle')"
    :error="hasErrors"
    :helper-text="$t('pageForm.pathSubtitle')"
  >
    <FormInput
      size="large"
      :value="value"
      :placeholder="$t('pageForm.pathPlaceholder')"
      :disabled="disabled"
      @input="$emit('input', $event)"
      @blur="$emit('blur')"
    ></FormInput>

    <template #error>
      <span v-if="validationState.$dirty && !validationState.required">
        {{ $t('error.requiredField') }}
      </span>
      <span v-if="validationState.$dirty && !validationState.isUnique">
        {{ $t('pageErrors.errorPathNotUnique') }}
      </span>
      <span v-if="validationState.$dirty && !validationState.maxLength">
        {{ $t('error.maxLength', { max: 255 }) }}
      </span>
      <span v-if="validationState.$dirty && !validationState.startingSlash">
        {{ $t('pageErrors.errorStartingSlash') }}
      </span>
      <span
        v-if="validationState.$dirty && !validationState.validPathCharacters"
      >
        {{ $t('pageErrors.errorValidPathCharacters') }}
      </span>
      <span v-if="validationState.$dirty && !validationState.uniquePathParams">
        {{ $t('pageErrors.errorUniquePathParams') }}
      </span>
    </template>
  </FormGroup>
</template>

<script>
export default {
  name: 'PageSettingsPathFormElement',
  props: {
    value: {
      type: String,
      required: false,
      default: '',
    },
    disabled: {
      type: Boolean,
      required: false,
      default: false,
    },
    hasErrors: {
      type: Boolean,
      required: false,
      default: false,
    },
    validationState: {
      type: Object,
      required: false,
      default: () => ({}),
    },
  },
}
</script>
