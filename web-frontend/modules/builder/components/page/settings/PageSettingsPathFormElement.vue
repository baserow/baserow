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
      :disabled="disabled"
      @input="$emit('input', $event)"
      @blur="$emit('blur')"
    ></FormInput>

    <template #error>
      <span v-if="validationState.required.$invalid">
        {{ $t('error.requiredField') }}
      </span>
      <span v-else-if="validationState.isUnique.$invalid">
        {{ $t('pageErrors.errorPathNotUnique') }}
      </span>
      <span v-else-if="validationState.maxLength.$invalid">
        {{ $t('error.maxLength', { max: 255 }) }}
      </span>
      <span v-else-if="validationState.startingSlash.$invalid">
        {{ $t('pageErrors.errorStartingSlash') }}
      </span>
      <span v-else-if="validationState.validPathCharacters.$invalid">
        {{ $t('pageErrors.errorValidPathCharacters') }}
      </span>
      <span v-else-if="validationState.uniquePathParams.$invalid">
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
