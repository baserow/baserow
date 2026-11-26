<template>
  <form @submit.prevent @keydown.enter.prevent>
    <FormGroup
      small-label
      :label="$t('textFieldForm.fieldValueLabel')"
      required
      horizontal
      class="margin-bottom-2"
    >
      <InjectedFormulaInput
        v-model="values.value"
        :placeholder="$t('textFieldForm.fieldValuePlaceholder')"
      />
    </FormGroup>
  </form>
</template>

<script>
import collectionFieldForm from '@baserow/modules/builder/mixins/collectionFieldForm'
import InjectedFormulaInput from '@baserow/modules/core/components/formula/InjectedFormulaInput'

export default {
  name: 'BooleanFieldForm',
  components: { InjectedFormulaInput },
  mixins: [collectionFieldForm],
  data() {
    return {
      allowedValues: ['value', 'styles'],
      values: {
        value: {},
        styles: {},
      },
    }
  },
}
</script>
