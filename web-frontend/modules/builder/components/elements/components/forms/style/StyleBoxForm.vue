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
          v-model="values.border_color"
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
        :error-message="sizeError"
      >
        <PixelValueSelector v-model="values.border_size" />
      </FormGroup>
      <FormGroup
        v-if="paddingIsAllowed"
        class="margin-bottom-2"
        small-label
        required
        :label="$t('styleBoxForm.paddingLabel')"
        horizontal-narrow
        :error-message="paddingError"
      >
        <PixelValueSelector v-model="values.padding" />
      </FormGroup>
      <FormGroup
        v-if="marginIsAllowed"
        class="margin-bottom-2"
        small-label
        required
        :label="$t('styleBoxForm.marginLabel')"
        horizontal-narrow
        :error-message="marginError"
      >
        <PixelValueSelector v-model="values.margin" />
      </FormGroup>
    </FormSection>
  </form>
</template>

<script>
import { required, integer, between } from 'vuelidate/lib/validators'
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
  data() {
    return {
      values: {
        margin: 0,
        padding: 0,
        border_color: 'border',
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
    marginError() {
      if (this.$v.values.margin.$invalid) {
        return this.$t('error.minMaxValueField', { min: 0, max: 200 })
      } else {
        return ''
      }
    },
    paddingError() {
      if (this.$v.values.padding.$invalid) {
        return this.$t('error.minMaxValueField', { min: 0, max: 200 })
      } else {
        return ''
      }
    },
    sizeError() {
      if (this.$v.values.border_size.$invalid) {
        return this.$t('error.minMaxValueField', { min: 0, max: 200 })
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
        padding: {
          required,
          integer,
          between: between(0, 200),
        },
        border_size: {
          required,
          integer,
          between: between(0, 200),
        },
        margin: {
          required,
          integer,
          between: between(0, 200),
        },
      },
    }
  },
}
</script>
