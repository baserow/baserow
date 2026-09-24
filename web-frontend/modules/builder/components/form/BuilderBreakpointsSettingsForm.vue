<template>
  <form @submit.prevent @keydown.enter.prevent>
    <p class="builder-breakpoints-settings-form__description margin-bottom-3">
      {{ $t('breakpointSettings.description') }}
    </p>
    <FormGroup
      :error-message="getBreakpointErrorMessage('mobile')"
      required
      small-label
      class="margin-bottom-2"
    >
      <template #label>
        <i
          class="builder-breakpoints-settings-form__label-icon baserow-icon-smartphone"
          aria-hidden="true"
        ></i>
        {{ $t('breakpointSettings.mobileLabel') }}
      </template>
      <FormInput
        v-model="v$.values.breakpoints.mobile.$model"
        class="builder-breakpoints-settings-form__input"
        type="number"
        :min="minimumBreakpoint"
        :max="maximumBreakpoint"
        :step="1"
        :to-value="toBreakpointValue"
      >
        <template #suffix>px</template>
      </FormInput>
    </FormGroup>
    <FormGroup
      :error-message="getBreakpointErrorMessage('tablet')"
      required
      small-label
      class="margin-bottom-2"
    >
      <template #label>
        <i
          class="builder-breakpoints-settings-form__label-icon baserow-icon-tablet"
          aria-hidden="true"
        ></i>
        {{ $t('breakpointSettings.tabletLabel') }}
      </template>
      <FormInput
        v-model="v$.values.breakpoints.tablet.$model"
        class="builder-breakpoints-settings-form__input"
        type="number"
        :min="minimumBreakpoint"
        :max="maximumBreakpoint"
        :step="1"
        :to-value="toBreakpointValue"
      >
        <template #suffix>px</template>
      </FormInput>
    </FormGroup>
    <FormGroup small-label class="margin-top-3">
      <template #label>
        <i
          class="builder-breakpoints-settings-form__label-icon iconoir-apple-imac-2021"
          aria-hidden="true"
        ></i>
        {{ $t('breakpointSettings.desktopLabel') }}
      </template>
      <p
        v-if="!v$.values.breakpoints.tablet.$invalid"
        class="builder-breakpoints-settings-form__desktop-value"
      >
        {{
          $t('breakpointSettings.desktopDescription', {
            breakpoint: values.breakpoints.tablet,
          })
        }}
      </p>
    </FormGroup>
  </form>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import {
  helpers,
  integer,
  maxValue,
  minValue,
  required,
} from '@vuelidate/validators'
import form from '@baserow/modules/core/mixins/form'
import {
  MAX_BUILDER_BREAKPOINT,
  MIN_BUILDER_BREAKPOINT,
} from '@baserow/modules/builder/utils/breakpoints'

export default {
  name: 'BuilderBreakpointsSettingsForm',
  mixins: [form],
  setup() {
    return { v$: useVuelidate() }
  },
  data() {
    return {
      minimumBreakpoint: MIN_BUILDER_BREAKPOINT,
      maximumBreakpoint: MAX_BUILDER_BREAKPOINT,
      values: {
        breakpoints: {
          mobile: null,
          tablet: null,
        },
      },
      allowedValues: ['breakpoints'],
    }
  },
  methods: {
    toBreakpointValue(value) {
      return value === '' ? null : Number(value)
    },
    getBreakpointErrorMessage(breakpoint) {
      return this.v$.values.breakpoints[breakpoint].$errors[0]?.$message
    },
  },
  validations() {
    return {
      values: {
        breakpoints: {
          mobile: {
            required: helpers.withMessage(
              this.$t('error.requiredField'),
              required
            ),
            integer: helpers.withMessage(
              this.$t('error.integerField'),
              integer
            ),
            minValue: helpers.withMessage(
              this.$t('error.minValueField', {
                min: MIN_BUILDER_BREAKPOINT,
              }),
              minValue(MIN_BUILDER_BREAKPOINT)
            ),
            maxValue: helpers.withMessage(
              this.$t('error.maxValueField', {
                max: MAX_BUILDER_BREAKPOINT,
              }),
              maxValue(MAX_BUILDER_BREAKPOINT)
            ),
            lessThanTablet: helpers.withMessage(
              this.$t('breakpointSettings.mobileMustBeLessThanTablet'),
              (value) => value < this.values.breakpoints.tablet
            ),
          },
          tablet: {
            required: helpers.withMessage(
              this.$t('error.requiredField'),
              required
            ),
            integer: helpers.withMessage(
              this.$t('error.integerField'),
              integer
            ),
            minValue: helpers.withMessage(
              this.$t('error.minValueField', {
                min: MIN_BUILDER_BREAKPOINT,
              }),
              minValue(MIN_BUILDER_BREAKPOINT)
            ),
            maxValue: helpers.withMessage(
              this.$t('error.maxValueField', {
                max: MAX_BUILDER_BREAKPOINT,
              }),
              maxValue(MAX_BUILDER_BREAKPOINT)
            ),
            greaterThanMobile: helpers.withMessage(
              this.$t('breakpointSettings.tabletMustBeGreaterThanMobile'),
              (value) => value > this.values.breakpoints.mobile
            ),
          },
        },
      },
    }
  },
}
</script>
