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
      small-labelt
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
        @blur="$v.values.value.$touch()"
      />
    </FormGroup>

    <RatingFormFields :values="values" />
  </form>
</template>

<script>
import elementForm from '@baserow/modules/builder/mixins/elementForm'
import InjectedFormulaInput from '@baserow/modules/core/components/formula/InjectedFormulaInput'
import Checkbox from '@baserow/modules/core/components/Checkbox'
import RatingFormFields from '../RatingFormFields.vue'

export default {
  name: 'RatingInputElementForm',
  components: {
    InjectedFormulaInput,
    Checkbox,
    RatingFormFields,
  },
  mixins: [elementForm],
  validations() {
    return {
      values: {
        value: {},
      },
    }
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
        style: 'star',
      },
    }
  },
  computed: {
    valueErrorMessage() {
      if (!this.$v.values.value.$error) {
        return ''
      }
      return this.$t('error.requiredField')
    },
  },
}
</script>
