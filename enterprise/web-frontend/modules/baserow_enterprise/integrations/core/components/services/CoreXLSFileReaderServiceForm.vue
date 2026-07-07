<template>
  <form @submit.prevent>
    <FormGroup
      class="margin-bottom-2"
      :label="$t('coreXLSFileReaderServiceForm.file')"
      required
      small-label
    >
      <InjectedFormulaInput
        v-model="values.file"
        allow-node-selection="object"
        :placeholder="$t('coreXLSFileReaderServiceForm.filePlaceholder')"
      />
    </FormGroup>
    <FormGroup
      class="margin-bottom-2"
      :label="$t('coreXLSFileReaderServiceForm.sheetName')"
      small-label
    >
      <InjectedFormulaInput
        v-model="values.sheet_name"
        :placeholder="$t('coreXLSFileReaderServiceForm.sheetNamePlaceholder')"
      />
    </FormGroup>
    <FormGroup class="margin-bottom-2">
      <Checkbox v-model="values.first_line_is_header">
        {{ $t('coreXLSFileReaderServiceForm.firstLineIsHeader') }}
      </Checkbox>
    </FormGroup>
  </form>
</template>

<script>
import form from '@baserow/modules/core/mixins/form'
import InjectedFormulaInput from '@baserow/modules/core/components/formula/InjectedFormulaInput'
import Checkbox from '@baserow/modules/core/components/Checkbox'
import { useVuelidate } from '@vuelidate/core'

export default {
  name: 'CoreXLSFileReaderServiceForm',
  components: { Checkbox, InjectedFormulaInput },
  mixins: [form],
  setup() {
    return { v$: useVuelidate() }
  },
  data() {
    return {
      allowedValues: ['file', 'sheet_name', 'first_line_is_header'],
      values: {
        file: {},
        sheet_name: {},
        first_line_is_header: true,
      },
    }
  },
  validations() {
    return {
      values: {
        file: {},
        sheet_name: {},
        first_line_is_header: {},
      },
    }
  },
}
</script>
