<template>
  <FormGroup
    :error="hasError"
    class="ab-form-group"
    :class="{
      'ab-form-group--horizontal': horizontal,
      'ab-form-group--horizontal-variable': horizontalVariable,
      'ab-form-group--with-label': label,
      'ab-form-group--error': hasError,
    }"
  >
    <label
      v-if="label"
      class="ab-form-group__label"
      :class="{ 'ab-form-group__label--small': smallLabel }"
    >
      <ABFormattedText :value="label" :format="labelFormat" profile="inline" />
      <span v-if="required" :title="$t('error.requiredField')"> *</span>
    </label>
    <div class="ab-form-group__children">
      <slot />
      <div v-if="hasError" class="ab-form-group__error-message">
        <i class="iconoir-warning-triangle"></i>
        {{ errorMessage }}
      </div>
    </div>
  </FormGroup>
</template>

<script>
import { BASEROW_FORMULA_FORMAT_PLAIN } from '@baserow/modules/core/formula/constants'

export default {
  name: 'ABFormGroup',
  props: {
    errorMessage: {
      type: String,
      required: false,
      default: null,
    },
    label: {
      type: String,
      required: false,
      default: null,
    },
    /**
     * The `format` of the formula the label was resolved from, so that a
     * markdown label renders inline.
     */
    labelFormat: {
      type: String,
      required: false,
      default: BASEROW_FORMULA_FORMAT_PLAIN,
    },
    smallLabel: {
      type: Boolean,
      required: false,
      default: false,
    },
    horizontal: {
      type: Boolean,
      required: false,
      default: false,
    },
    horizontalVariable: {
      type: Boolean,
      required: false,
      default: false,
    },
    required: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  computed: {
    hasError() {
      return Boolean(this.errorMessage)
    },
  },
}
</script>
