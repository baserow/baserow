<template>
  <form @submit.prevent @keydown.enter.prevent>
    <FormGroup
      small-label
      :label="$t('generalForm.valueTitle')"
      class="margin-bottom-2"
      :required="true"
      :error-message="v$.values.value.$error ? $t('error.requiredField') : ''"
    >
      <InjectedFormulaInput
        v-model="values.value"
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
import FormGroup from '@baserow/modules/core/components/FormGroup'
import RatingFormFields from '@baserow/modules/builder/components/elements/components/forms/RatingFormFields.vue'
import { useVuelidate } from '@vuelidate/core'
import { required } from '@vuelidate/validators'

export default {
  name: 'RatingElementForm',
  components: {
    InjectedFormulaInput,
    FormGroup,
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
        max_value: 5,
        color: '#fcbb03',
        style: 'star',
      },
    }
  },
  computed: {
    rules() {
      return {
        values: {
          value: { required },
        },
      }
    },
  },
  validations() {
    return this.rules
  },
}
</script>
