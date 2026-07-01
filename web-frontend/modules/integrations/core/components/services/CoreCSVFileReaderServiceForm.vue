<template>
  <form @submit.prevent>
    <FormGroup
      class="margin-bottom-2"
      :label="$t('coreCSVFileReaderServiceForm.inputType')"
      required
      small-label
    >
      <RadioGroup
        v-model="values.input_type"
        :options="inputTypes"
        type="button"
      />
    </FormGroup>
    <FormGroup
      v-if="values.input_type === 'file'"
      class="margin-bottom-2"
      :label="$t('coreCSVFileReaderServiceForm.file')"
      required
      small-label
    >
      <InjectedFormulaInput
        v-model="values.file"
        allow-node-selection="object"
        :placeholder="$t('coreCSVFileReaderServiceForm.filePlaceholder')"
      />
    </FormGroup>
    <FormGroup
      v-else
      class="margin-bottom-2"
      :label="$t('coreCSVFileReaderServiceForm.csv')"
      required
      small-label
    >
      <InjectedFormulaInput
        v-model="values.csv"
        :placeholder="$t('coreCSVFileReaderServiceForm.csvPlaceholder')"
        textarea
      />
    </FormGroup>
    <FormGroup
      small-label
      :label="$t('coreCSVFileReaderServiceForm.separator')"
      required
      class="margin-bottom-2"
    >
      <Dropdown v-model="values.separator">
        <DropdownItem
          v-for="separator in separators"
          :key="separator.value"
          :name="separator.name"
          :value="separator.value"
        />
      </Dropdown>
    </FormGroup>
    <FormGroup
      small-label
      :label="$t('coreCSVFileReaderServiceForm.encoding')"
      required
      class="margin-bottom-2"
    >
      <Dropdown v-model="values.encoding">
        <DropdownItem
          v-for="encoding in encodings"
          :key="encoding.value"
          :name="encoding.name"
          :value="encoding.value"
        />
      </Dropdown>
    </FormGroup>
    <FormGroup class="margin-bottom-2">
      <Checkbox v-model="values.first_line_is_header">
        {{ $t('coreCSVFileReaderServiceForm.firstLineIsHeader') }}
      </Checkbox>
    </FormGroup>
  </form>
</template>

<script>
import form from '@baserow/modules/core/mixins/form'
import InjectedFormulaInput from '@baserow/modules/core/components/formula/InjectedFormulaInput'
import Checkbox from '@baserow/modules/core/components/Checkbox'
import RadioGroup from '@baserow/modules/core/components/RadioGroup'
import { useVuelidate } from '@vuelidate/core'

export default {
  name: 'CoreCSVFileReaderServiceForm',
  components: { Checkbox, InjectedFormulaInput, RadioGroup },
  mixins: [form],
  setup() {
    return { v$: useVuelidate() }
  },
  data() {
    return {
      allowedValues: [
        'file',
        'csv',
        'input_type',
        'separator',
        'encoding',
        'first_line_is_header',
      ],
      values: {
        file: {},
        csv: {},
        input_type: 'file',
        separator: ',',
        encoding: 'utf-8',
        first_line_is_header: true,
      },
      inputTypes: [
        {
          label: this.$t('coreCSVFileReaderServiceForm.inputTypeFile'),
          value: 'file',
        },
        {
          label: this.$t('coreCSVFileReaderServiceForm.inputTypeContent'),
          value: 'content',
        },
      ],
      separators: [
        { name: this.$t('coreCSVFileReaderServiceForm.comma'), value: ',' },
        { name: this.$t('coreCSVFileReaderServiceForm.semicolon'), value: ';' },
        { name: this.$t('coreCSVFileReaderServiceForm.tab'), value: '\t' },
        { name: this.$t('coreCSVFileReaderServiceForm.pipe'), value: '|' },
      ],
      encodings: [
        { name: this.$t('coreCSVFileReaderServiceForm.utf8'), value: 'utf-8' },
        {
          name: this.$t('coreCSVFileReaderServiceForm.utf8Bom'),
          value: 'utf-8-sig',
        },
        {
          name: this.$t('coreCSVFileReaderServiceForm.latin1'),
          value: 'latin-1',
        },
      ],
    }
  },
  validations() {
    return {
      values: {
        file: {},
        csv: {},
        input_type: {},
        separator: {},
        encoding: {},
        first_line_is_header: {},
      },
    }
  },
}
</script>
