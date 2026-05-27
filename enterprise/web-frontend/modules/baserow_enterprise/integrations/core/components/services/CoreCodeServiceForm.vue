<template>
  <form @submit.prevent>
    <FormGroup
      small-label
      :label="$t('coreCodeServiceForm.codeLabel')"
      required
      class="margin-bottom-2"
    >
      <InjectedFormulaInput
        v-model="values.code"
        :placeholder="$t('coreCodeServiceForm.codePlaceholder')"
        textarea
      />
    </FormGroup>
  </form>
</template>

<script>
import form from '@baserow/modules/core/mixins/form'
import InjectedFormulaInput from '@baserow/modules/core/components/formula/InjectedFormulaInput'

export default {
  name: 'CoreCodeServiceForm',
  components: {
    InjectedFormulaInput,
  },
  mixins: [form],
  data() {
    return {
      allowedValues: ['code'],
      values: {
        code: {},
      },
    }
  },
}
</script>
