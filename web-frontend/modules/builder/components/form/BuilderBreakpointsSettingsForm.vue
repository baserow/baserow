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
      <p class="builder-breakpoints-settings-form__desktop-value">
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
import { helpers, integer, required } from '@vuelidate/validators'
import form from '@baserow/modules/core/mixins/form'

export default {
  name: 'BuilderBreakpointsSettingsForm',
  mixins: [form],
  setup() {
    return { v$: useVuelidate() }
  },
  data() {
    return {
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
