<template>
  <form @submit.prevent @keydown.enter.prevent>
    <FormGroup
      small-label
      :label="$t('generalForm.valueTitle')"
      class="margin-bottom-2"
      :required="true"
      :error-message="valueErrorMessage"
    >
      <InjectedFormulaInput
        v-model="values.value"
        :placeholder="$t('generalForm.valueRequiredPlaceholder')"
        @input="emitChange"
        @blur="$v.values.value.$touch()"
      />
    </FormGroup>
    <RatingFormFields :values="values" />
  </form>
</template>

<script>
import elementForm from '@baserow/modules/builder/mixins/elementForm'
import InjectedFormulaInput from '@baserow/modules/core/components/formula/InjectedFormulaInput'
import FormGroup from '@baserow/modules/core/components/FormGroup'
import RatingFormFields from '../RatingFormFields.vue'

export default {
  name: 'RatingElementForm',
  components: {
    InjectedFormulaInput,
    FormGroup,
    RatingFormFields,
  },
  mixins: [elementForm],
  validations: {
    values: {
      value: {
        required: true,
      },
    },
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
    valueErrorMessage() {
      if (!this.$v.values.value.$error) {
        return ''
      }
      return this.$t('error.requiredField')
    },
  },
}
</script>
