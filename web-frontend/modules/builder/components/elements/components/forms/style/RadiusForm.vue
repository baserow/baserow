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
        :error-message="getFirstErrorMessage('background_radius')"
      >
        <PixelValueSelector v-model="v$.values.background_radius.$model" />
      </FormGroup>

      <FormGroup
        v-if="borderRadiusIsAllowed"
        :label="$t('radiusStyleForm.borderRadiusLabel')"
        class="margin-bottom-2"
        small-label
        required
        horizontal-narrow
        :error-message="getFirstErrorMessage('border_radius')"
      >
        <PixelValueSelector v-model="v$.values.border_radius.$model" />
      </FormGroup>
    </FormSection>
  </form>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import { required, integer, between, helpers } from '@vuelidate/validators'
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
      default: undefined,
    },
    modelValue: {
      type: Object,
      default: undefined,
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
  emits: ['input', 'update:modelValue'],
  setup() {
    return { v$: useVuelidate({ $lazy: true }) }
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
    currentValue() {
      return this.modelValue !== undefined ? this.modelValue : this.value
    },
  },
  methods: {
    getDefaultValues() {
      return this.currentValue
    },
    emitChange(newValues) {
      this.$emit('input', newValues)
      this.$emit('update:modelValue', newValues)
    },
  },
  validations() {
    return {
      values: {
        background_radius: {
          required: helpers.withMessage(
            this.$t('error.requiredField'),
            required
          ),
          integer: helpers.withMessage(this.$t('error.integerField'), integer),
          between: helpers.withMessage(
            this.$t('error.minMaxValueField', {
              min: 0,
              max: MAX_RADIUS_PX,
            }),
            between(0, MAX_RADIUS_PX)
          ),
        },
        border_radius: {
          required: helpers.withMessage(
            this.$t('error.requiredField'),
            required
          ),
          integer: helpers.withMessage(this.$t('error.integerField'), integer),
          between: helpers.withMessage(
            this.$t('error.minMaxValueField', {
              min: 0,
              max: MAX_RADIUS_PX,
            }),
            between(0, MAX_RADIUS_PX)
          ),
        },
      },
    }
  },
}
</script>
