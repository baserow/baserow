<template>
  <form @submit.prevent @keydown.enter.prevent>
    <FormGroup
      small-label
      :label="$t('generalForm.labelTitle')"
      class="margin-bottom-2"
      horizontal
      required
    >
      <InjectedFormulaInput
        v-model="values.label"
        :placeholder="$t('buttonFieldForm.labelPlaceholder')"
      />
    </FormGroup>
    <Alert>
      {{ $t('buttonFieldForm.infoMessage') }}
    </Alert>
  </form>
</template>

<script>
import collectionFieldForm from '@baserow/modules/builder/mixins/collectionFieldForm'
import InjectedFormulaInput from '@baserow/modules/core/components/formula/InjectedFormulaInput'

export default {
  name: 'ButtonFieldForm',
  components: { InjectedFormulaInput },
  mixins: [collectionFieldForm],
  data() {
    return {
      allowedValues: ['label', 'styles'],
      values: {
        label: {},
        styles: {},
      },
    }
  },
}
</script>
