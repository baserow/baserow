<template>
  <form @submit.prevent>
    <FormGroup :label="$t('htmlElement.source')" small-label required>
      <InjectedFormulaInput v-model="values.html" />
      <template #helper>{{ $t('htmlElement.sourceHelp') }}</template>
    </FormGroup>
  </form>
</template>

<script>
import elementForm from '@baserow/modules/builder/mixins/elementForm'
import InjectedFormulaInput from '@baserow/modules/core/components/formula/InjectedFormulaInput.vue'

export default {
  name: 'BuilderHTMLElementForm',
  components: { InjectedFormulaInput },
  mixins: [elementForm],
  data() {
    return { values: { html: {} }, allowedValues: ['html'] }
  },
}
</script>
