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
          v-model="v$.border_color.$model"
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
        <PixelValueSelector v-model="v$.border_size.$model" />
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
        <PixelValueSelector v-model="v$.padding.$model" />
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
        <PixelValueSelector v-model="v$.margin.$model" />
      </FormGroup>
    </FormSection>
  </form>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import { reactive, computed } from 'vue'
import { required, integer, between } from '@vuelidate/validators'
import form from '@baserow/modules/core/mixins/form'
import { themeToColorVariables } from '@baserow/modules/builder/utils/theme'

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
      v$: null,
      values: null,
    }
  },
  computed: {
    colorVariables() {
      return themeToColorVariables(this.builder.theme)
    },
    marginError() {
      if (this.v$.margin.$invalid) {
        return this.$t('error.minMaxValueField', { min: 0, max: 200 })
      } else {
        return ''
      }
    },
    paddingError() {
      if (this.v$.padding.$invalid) {
        return this.$t('error.minMaxValueField', { min: 0, max: 200 })
      } else {
        return ''
      }
    },
    sizeError() {
      if (this.v$.border_size.$invalid) {
        return this.$t('error.minMaxValueField', { min: 0, max: 200 })
      } else {
        return ''
      }
    },
  },
  created() {
    const values = reactive({
      margin: 0,
      padding: 0,
      border_color: '',
      border_size: 0,
    })

    const rules = computed(() => ({
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
      border_color: {
        required,
      },
    }))
    this.v$ = useVuelidate(rules, values, { $lazy: true })
    this.values = values
  },
  methods: {
    getDefaultValues() {
      return this.value
    },
    emitChange(newValues) {
      this.$emit('input', newValues)
    },
  },
}
</script>
