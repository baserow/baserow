<template>
  <form @submit.prevent>
    <FormSection
      :title="$t('borderStyleForm.borderRadiusLabel')"
      class="margin-bottom-2"
    >
      <FormGroup
        v-for="{name, label} in borderRadiuses"
        v-if="styleIsAllowed(name)"
        :key="name"
        :label="label"
        class="margin-bottom-2"
        small-label
        required
        horizontal-narrow
        :error-message="getBorderRadiusError(label)"
      >
        <PixelValueSelector v-model="values[name]" />
      </FormGroup>
    </FormSection>
  </form>
</template>

<script>
import _ from 'lodash'
import { required, integer, between } from 'vuelidate/lib/validators'

import form from '@baserow/modules/core/mixins/form'
import PixelValueSelector from '@baserow/modules/builder/components/PixelValueSelector'

export default {
  name: 'BorderRadiusForm',
  components: { PixelValueSelector },
  mixins: [form],
  inject: ['builder'],
  props: {
    value: {
      type: Object,
      required: true,
    },
    borderRadiuses: {
      type: Array,
      required: true,
    },
    topLeftIsAllowed: {
      type: Boolean,
      required: false,
      default: () => false,
    },
    topRightIsAllowed: {
      type: Boolean,
      required: false,
      default: () => false,
    },
    bottomLeftIsAllowed: {
      type: Boolean,
      required: false,
      default: () => false,
    },
    bottomRightIsAllowed: {
      type: Boolean,
      required: false,
      default: () => false,
    },
  },
  data() {
    return {
      values: {
        top_left: 0,
        top_right: 0,
        bottom_left: 0,
        bottom_right: 0,
      },
    }
  },
  computed: {
    borderRadiusTopLeftError() {
      if (this.$v.values.top_left.$invalid) {
        return this.$t('error.minMaxValueField', { min: 0, max: 100 })
      } else {
        return ''
      }
    },
    borderRadiusTopRightError() {
      if (this.$v.values.top_right.$invalid) {
        return this.$t('error.minMaxValueField', { min: 0, max: 100 })
      } else {
        return ''
      }
    },
    borderRadiusBottomLeftError() {
      if (this.$v.values.bottom_left.$invalid) {
        return this.$t('error.minMaxValueField', { min: 0, max: 100 })
      } else {
        return ''
      }
    },
    borderRadiusBottomRightError() {
      if (this.$v.values.bottom_right.$invalid) {
        return this.$t('error.minMaxValueField', { min: 0, max: 100 })
      } else {
        return ''
      }
    },
  },
  methods: {
    getDefaultValues() {
      return this.value
    },
    emitChange(newValues) {
      this.$emit('input', newValues)
    },
    getBorderRadiusError(name) {
      // Convert name to title-case, e.g. "Top right" to "Top Right"
      const title = _.startCase(name).replace(/ /g, '')
      console.log('checking error: ', title)
      return this[`borderRadius${title}Error`];
    },
    styleIsAllowed(name) {
      const camelCase = _.camelCase(name)
      return this[`${camelCase}IsAllowed`]
    },
  },
  validations() {
    return {
      values: {
        top_left: {
          required,
          integer,
          between: between(0, 100),
        },
        top_right: {
          required,
          integer,
          between: between(0, 100),
        },
        bottom_left: {
          required,
          integer,
          between: between(0, 100),
        },
        bottom_right: {
          required,
          integer,
          between: between(0, 100),
        },
      },
    }
  },
}
</script>
