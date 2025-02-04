<template>
  <form @submit.prevent @keydown.enter.prevent>
    <div class="control">
      <label class="control__label">{{ $t('ratingFieldForm.value') }}</label>
      <div class="control__elements">
        <InjectedFormulaInput v-model="values.value" />
      </div>
    </div>
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
      allowedValues: ['max_value', 'color', 'style', 'value'],
      values: {
        max_value: 5,
        color: '#fcbb03',
        style: 'star',
        value: '',
      },
    }
  },
}
</script>
