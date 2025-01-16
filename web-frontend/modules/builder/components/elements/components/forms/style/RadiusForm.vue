<template>
  <form @submit.prevent>
    <FormSection
      :title="$t('radiusStyleForm.cornerRadiusLabel')"
      class="margin-bottom-2"
    >
      <FormGroup
        v-if="backgroundRadiusIsAllowed"
        :label="$t('radiusStyleForm.backgroundRadiusLabel')"
        class="margin-bottom-2"
        small-label
        required
        horizontal-narrow
        :error-message="backgroundRadiusError"
      >
        <PixelValueSelector v-model="values.background_radius" />
      </FormGroup>

      <FormGroup
        v-if="borderRadiusIsAllowed"
        :label="$t('radiusStyleForm.borderRadiusLabel')"
        class="margin-bottom-2"
        small-label
        required
        horizontal-narrow
        :error-message="borderRadiusError"
      >
        <PixelValueSelector v-model="values.border_radius" />
      </FormGroup>
    </FormSection>
  </form>
</template>

<script>
import { required, integer, between } from 'vuelidate/lib/validators'

import form from '@baserow/modules/core/mixins/form'
import PixelValueSelector from '@baserow/modules/builder/components/PixelValueSelector'

const MAX_RADIUS_PX = 100

export default {
  name: 'RadiusForm',
  components: { PixelValueSelector },
  mixins: [form],
  inject: ['builder'],
  props: {
    value: {
      type: Object,
      required: true,
    },
    backgroundRadiusIsAllowed: {
      type: Boolean,
      required: false,
      default: () => false,
    },
    borderRadiusIsAllowed: {
      type: Boolean,
      required: false,
      default: () => false,
    },
  },
  data() {
    return {
      values: {
        background_radius: 0,
        border_radius: 0,
      },
    }
  },
  computed: {
    backgroundRadiusError() {
      if (this.$v.values.background_radius.$invalid) {
        return this.$t('error.minMaxValueField', {
          min: 0,
          max: MAX_RADIUS_PX,
        })
      } else {
        return ''
      }
    },
    borderRadiusError() {
      if (this.$v.values.border_radius.$invalid) {
        return this.$t('error.minMaxValueField', {
          min: 0,
          max: MAX_RADIUS_PX,
        })
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
  },
  validations() {
    return {
      values: {
        background_radius: {
          required,
          integer,
          between: between(0, MAX_RADIUS_PX),
        },
        border_radius: {
          required,
          integer,
          between: between(0, MAX_RADIUS_PX),
        },
      },
    }
  },
}
</script>
