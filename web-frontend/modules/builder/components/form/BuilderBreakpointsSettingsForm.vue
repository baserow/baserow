<template>
  <form @submit.prevent @keydown.enter.prevent>
    <FormGroup
      :label="$t('breakpointSettings.mobileLabel')"
      :error-message="getFirstErrorMessage('mobile_breakpoint')"
      required
      small-label
      class="margin-bottom-2"
    >
      <FormInput
        v-model="v$.values.mobile_breakpoint.$model"
        class="builder-breakpoints-settings-form__input"
        type="number"
        :to-value="toBreakpointValue"
      >
        <template #suffix>px</template>
      </FormInput>
    </FormGroup>
    <FormGroup
      :label="$t('breakpointSettings.tabletLabel')"
      :error-message="getFirstErrorMessage('tablet_breakpoint')"
      required
      small-label
      class="margin-bottom-2"
    >
      <FormInput
        v-model="v$.values.tablet_breakpoint.$model"
        class="builder-breakpoints-settings-form__input"
        type="number"
        :to-value="toBreakpointValue"
      >
        <template #suffix>px</template>
      </FormInput>
    </FormGroup>
    <p class="margin-top-3">
      {{
        $t('breakpointSettings.desktopDescription', {
          breakpoint: values.tablet_breakpoint,
        })
      }}
    </p>
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
        mobile_breakpoint: null,
        tablet_breakpoint: null,
      },
      allowedValues: ['mobile_breakpoint', 'tablet_breakpoint'],
    }
  },
  methods: {
    toBreakpointValue(value) {
      return value === '' ? null : Number(value)
    },
  },
  validations() {
    return {
      values: {
        mobile_breakpoint: {
          required: helpers.withMessage(
            this.$t('error.requiredField'),
            required
          ),
          integer: helpers.withMessage(this.$t('error.integerField'), integer),
          lessThanTablet: helpers.withMessage(
            this.$t('breakpointSettings.mobileMustBeLessThanTablet'),
            (value) => value < this.values.tablet_breakpoint
          ),
        },
        tablet_breakpoint: {
          required: helpers.withMessage(
            this.$t('error.requiredField'),
            required
          ),
          integer: helpers.withMessage(this.$t('error.integerField'), integer),
          greaterThanMobile: helpers.withMessage(
            this.$t('breakpointSettings.tabletMustBeGreaterThanMobile'),
            (value) => value > this.values.mobile_breakpoint
          ),
        },
      },
    }
  },
}
</script>
