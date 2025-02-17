<template>
  <form @submit.prevent>
    <FormSection :title="title" class="margin-bottom-2">
      <FormGroup
        v-if="borderIsAllowed"
        horizontal-narrow
        class="margin-bottom-2"
        small-label
        required
        :label="$t('styleBoxForm.borderColor')"
      >
        <ColorInput
          v-model="v$.values.border_color.$model"
          small
          :color-variables="colorVariables"
        />
      </FormGroup>
      <FormGroup
        v-if="borderIsAllowed"
        class="margin-bottom-2"
        small-label
        required
        :label="$t('styleBoxForm.borderLabel')"
        horizontal-narrow
        :error-message="getFirstErrorMessage('border_size')"
      >
        <PixelValueSelector v-model="v$.values.border_size.$model" />
      </FormGroup>
      <FormGroup
        v-if="paddingIsAllowed"
        class="margin-bottom-2"
        small-label
        required
        :label="$t('styleBoxForm.paddingLabel')"
        horizontal-narrow
        :error-message="getFirstErrorMessage('padding')"
      >
        <PixelValueSelector v-model="v$.values.padding.$model" />
      </FormGroup>
      <FormGroup
        v-if="marginIsAllowed"
        class="margin-bottom-2"
        small-label
        required
        :label="$t('styleBoxForm.marginLabel')"
        horizontal-narrow
        :error-message="getFirstErrorMessage('margin')"
      >
        <PixelValueSelector v-model="v$.values.margin.$model" />
      </FormGroup>
    </FormSection>
  </form>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import { required, integer, between, helpers } from '@vuelidate/validators'
import form from '@baserow/modules/core/mixins/form'
import { ThemeConfigBlockType } from '@baserow/modules/builder/themeConfigBlockTypes'

import PixelValueSelector from '@baserow/modules/builder/components/PixelValueSelector'

export default {
  name: 'StyleBoxForm',
  components: { PixelValueSelector },
  mixins: [form],
  inject: ['builder'],
  props: {
    title: {
      type: String,
      required: true,
    },
    value: {
      type: Object,
      required: true,
    },
    paddingIsAllowed: {
      type: Boolean,
      required: false,
      default: () => false,
    },
    marginIsAllowed: {
      type: Boolean,
      required: false,
      default: () => false,
    },
    borderIsAllowed: {
      type: Boolean,
      required: false,
      default: () => false,
    },
  },
  setup() {
    return { v$: useVuelidate() }
  },
  data() {
    return {
      values: {
        margin: 0,
        padding: 0,
        border_color: '',
        border_size: 0,
      },
    }
  },
  computed: {
    themeConfigBlocks() {
      return this.$registry.getOrderedList('themeConfigBlock')
    },
    colorVariables() {
      return ThemeConfigBlockType.getAllColorVariables(
        this.themeConfigBlocks,
        this.builder.theme
      )
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
        padding: {
          required: helpers.withMessage(
            this.$t('error.requiredField'),
            required
          ),
          integer: helpers.withMessage(this.$t('error.integerField'), integer),
          between: helpers.withMessage(
            this.$t('error.minMaxValueField', { min: 0, max: 200 }),
            between(0, 200)
          ),
        },
        border_size: {
          required: helpers.withMessage(
            this.$t('error.requiredField'),
            required
          ),
          integer: helpers.withMessage(this.$t('error.integerField'), integer),
          between: helpers.withMessage(
            this.$t('error.minMaxValueField', { min: 0, max: 200 }),
            between(0, 200)
          ),
        },
        margin: {
          required: helpers.withMessage(
            this.$t('error.requiredField'),
            required
          ),
          integer: helpers.withMessage(this.$t('error.integerField'), integer),
          between: helpers.withMessage(
            this.$t('error.minMaxValueField', { min: 0, max: 200 }),
            between(0, 200)
          ),
        },
        border_color: {
          required: helpers.withMessage(
            this.$t('error.requiredField'),
            required
          ),
        },
      },
    }
  },
}
</script>
