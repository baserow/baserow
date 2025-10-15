<template>
  <form @submit.prevent @keydown.enter.prevent>
    <FormGroup
      :label="$t('iframeElementForm.sourceTypeLabel')"
      small-label
      required
      class="margin-bottom-2"
    >
      <RadioGroup
        v-model="v$.values.source_type.$model"
        :options="iframeSourceTypeOptions"
        type="button"
      >
      </RadioGroup>
    </FormGroup>

    <FormGroup
      v-if="v$.values.source_type.$model === IFRAME_SOURCE_TYPES.URL"
      key="url"
      small-label
      :label="$t('iframeElementForm.urlLabel')"
      class="margin-bottom-2"
      required
    >
      <InjectedFormulaInput
        v-model="v$.values.url.$model"
        :placeholder="$t('iframeElementForm.urlPlaceholder')"
      />
      <template #helper>{{ $t('iframeElementForm.urlHelp') }}</template>
    </FormGroup>

    <FormGroup
      v-if="v$.values.source_type.$model === IFRAME_SOURCE_TYPES.EMBED"
      key="embed"
      :label="$t('iframeElementForm.embedLabel')"
      small-label
      class="margin-bottom-2"
      required
    >
      <InjectedFormulaInput
        v-model="v$.values.embed.$model"
        :placeholder="$t('iframeElementForm.embedPlaceholder')"
      />
    </FormGroup>
    <FormGroup
      :label="$t('iframeElementForm.heightLabel')"
      small-label
      required
      :error-message="getFirstErrorMessage('height')"
    >
      <FormInput
        v-model="v$.values.height.$model"
        type="number"
        :placeholder="$t('iframeElementForm.heightPlaceholder')"
        :to-value="(value) => parseInt(value)"
      />
    </FormGroup>
  </form>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import elementForm from '@baserow/modules/builder/mixins/elementForm'
import { IFRAME_SOURCE_TYPES } from '@baserow/modules/builder/enums'
import InjectedFormulaInput from '@baserow/modules/core/components/formula/InjectedFormulaInput.vue'
import {
  required,
  integer,
  minValue,
  maxValue,
  helpers,
} from '@vuelidate/validators'

export default {
  name: 'IFrameElementForm',
  components: { InjectedFormulaInput },
  mixins: [elementForm],
  setup() {
    return { v$: useVuelidate() }
  },
  data() {
    return {
      allowedValues: ['source_type', 'url', 'embed', 'height', 'styles'],
      values: {
        source_type: IFRAME_SOURCE_TYPES.URL,
        url: {},
        embed: {},
        height: 300,
        styles: {},
      },
    }
  },
  computed: {
    IFRAME_SOURCE_TYPES() {
      return IFRAME_SOURCE_TYPES
    },
    iframeSourceTypeOptions() {
      return [
        {
          label: this.$t('iframeElementForm.urlLabel'),
          value: IFRAME_SOURCE_TYPES.URL,
        },
        {
          label: this.$t('iframeElementForm.embedLabel'),
          value: IFRAME_SOURCE_TYPES.EMBED,
        },
      ]
    },
  },
  validations() {
    return {
      values: {
        height: {
          required: helpers.withMessage(
            this.$t('error.requiredField'),
            required
          ),
          integer: helpers.withMessage(this.$t('error.integerField'), integer),
          minValue: helpers.withMessage(
            this.$t('error.minValueField', { min: 1 }),
            minValue(1)
          ),
          maxValue: helpers.withMessage(
            this.$t('error.maxValueField', { max: 2000 }),
            maxValue(2000)
          ),
        },
        source_type: {},
        url: {},
        embed: {},
      },
    }
  },
}
</script>
