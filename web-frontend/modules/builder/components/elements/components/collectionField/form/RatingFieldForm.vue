<template>
  <form @submit.prevent @keydown.enter.prevent>
    <FormGroup
      small-label
      :label="$t('ratingElementForm.value')"
      class="margin-bottom-2"
      horizontal
      required
    >
      <InjectedFormulaInput v-model="values.value" />
    </FormGroup>
    <RatingFormFields :values="values" />
  </form>
</template>

<script>
import collectionFieldForm from '@baserow/modules/builder/mixins/collectionFieldForm'
import InjectedFormulaInput from '@baserow/modules/core/components/formula/InjectedFormulaInput'
import RatingFormFields from '../../forms/RatingFormFields.vue'

export default {
  name: 'RatingFieldForm',
  components: {
    InjectedFormulaInput,
    RatingFormFields,
  },
  mixins: [collectionFieldForm],
  data() {
    return {
      allowedValues: ['max_value', 'color', 'rating_style', 'value'],
      values: {
        max_value: 5,
        color: '#fcbb03',
        rating_style: 'star',
        value: '',
      },
    }
  },
}
</script>
