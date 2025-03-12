<template>
  <form @submit.prevent @keydown.enter.prevent>
    <FormGroup
      small-label
      :label="$t('generalForm.labelTitle')"
      class="margin-bottom-2"
    >
      <InjectedFormulaInput
        v-model="values.label"
        :placeholder="$t('generalForm.labelPlaceholder')"
      />
    </FormGroup>

    <FormGroup
      :label="$t('generalForm.requiredTitle')"
      class="margin-bottom-2"
      small-label
    >
      <Checkbox v-model="values.required" />
    </FormGroup>

    <FormGroup
      small-label
      :label="$t('generalForm.valueTitle')"
      class="margin-bottom-2"
      :error-message="valueErrorMessage"
    >
      <InjectedFormulaInput
        v-model="values.value"
        data-test-id="rating-form-value"
        :placeholder="$t('generalForm.valuePlaceholder')"
        @blur="v$.values.value.$touch()"
      />
    </FormGroup>

    <RatingFormFields :values="values" />
  </form>
</template>

<script>
import elementForm from '@baserow/modules/builder/mixins/elementForm'
import InjectedFormulaInput from '@baserow/modules/core/components/formula/InjectedFormulaInput'
import Checkbox from '@baserow/modules/core/components/Checkbox'
import RatingFormFields from '@baserow/modules/builder/components/elements/components/forms/RatingFormFields.vue'
import { useVuelidate } from '@vuelidate/core'
import { required } from '@vuelidate/validators'

export default {
  name: 'RatingInputElementForm',
  components: {
    InjectedFormulaInput,
    Checkbox,
    RatingFormFields,
  },
  mixins: [elementForm],
  setup() {
    return { v$: useVuelidate() }
  },
  data() {
    return {
      values: {
        value: '',
        required: false,
        label: '',
        editing: true,
        max_value: 5,
        color: '#fcbb03',
        rating_style: 'star',
      },
    }
  },
  computed: {
    valueErrorMessage() {
      if (!this.v$.values.value.$error) {
        return ''
      }
      return this.$t('error.requiredField')
    },
  },
  validations() {
    return {
      values: {
        value: { required },
      },
    }
  },
}
</script>
