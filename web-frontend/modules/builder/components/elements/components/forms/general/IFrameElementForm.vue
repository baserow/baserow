<template>
  <form @submit.prevent @keydown.enter.prevent>
    <FormGroup
      :label="$t('iframeElementForm.sourceTypeLabel')"
      small-label
      required
      class="margin-bottom-2"
    >
      <RadioGroup
        v-model="v$.source_type.$model"
        :options="iframeSourceTypeOptions"
        type="button"
      >
      </RadioGroup>
    </FormGroup>

    <FormGroup
      v-if="v$.source_type.$model === IFRAME_SOURCE_TYPES.URL"
      key="url"
      small-label
      :label="$t('iframeElementForm.urlLabel')"
      class="margin-bottom-2"
      required
    >
      <InjectedFormulaInput
        v-model="v$.url.$model"
        :placeholder="$t('iframeElementForm.urlPlaceholder')"
      />
      <template #helper>{{ $t('iframeElementForm.urlHelp') }}</template>
    </FormGroup>

    <FormGroup
      v-if="v$.source_type.$model === IFRAME_SOURCE_TYPES.EMBED"
      key="embed"
      :label="$t('iframeElementForm.embedLabel')"
      small-label
      class="margin-bottom-2"
      required
    >
      <InjectedFormulaInput
        v-model="v$.embed.$model"
        :placeholder="$t('iframeElementForm.embedPlaceholder')"
      />
    </FormGroup>
    <FormGroup
      :label="$t('iframeElementForm.heightLabel')"
      small-label
      required
      :error="v$.height.$error"
    >
      <FormInput
        v-model="v$.height.$model"
        type="number"
        :placeholder="$t('iframeElementForm.heightPlaceholder')"
        :to-value="(value) => parseInt(value)"
      ></FormInput>

      <template #error>
        <span v-if="v$.height.required.$invalid">
          {{ $t('error.requiredField') }}
        </span>
        <span v-else-if="v$.height.integer.$invalid">
          {{ $t('error.integerField') }}
        </span>
        <span v-else-if="v$.height.minValue.$invalid">
          {{ $t('error.minValueField', { min: 1 }) }}
        </span>
        <span v-else-if="v$.height.maxValue.$invalid">
          {{ $t('error.maxValueField', { max: 2000 }) }}
        </span>
      </template>
    </FormGroup>
  </form>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import { reactive, computed } from 'vue'
import elementForm from '@baserow/modules/builder/mixins/elementForm'
import { IFRAME_SOURCE_TYPES } from '@baserow/modules/builder/enums'
import InjectedFormulaInput from '@baserow/modules/core/components/formula/InjectedFormulaInput.vue'
import { required, integer, minValue, maxValue } from '@vuelidate/validators'

export default {
  name: 'IFrameElementForm',
  components: { InjectedFormulaInput },
  mixins: [elementForm],
  data() {
    return {
      values: null,
      v$: null,
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
  created() {
    const values = reactive({
      height: 300,
      source_type: IFRAME_SOURCE_TYPES.URL,
      url: '',
      embed: '',
    })

    const rules = computed(() => ({
      height: {
        required,
        integer,
        minValue: minValue(1),
        maxValue: maxValue(2000),
      },
      source_type: {},
      url: {},
      embed: {},
    }))

    this.v$ = useVuelidate(rules, values, { $lazy: true })
    this.values = values
  },
}
</script>
