<template>
  <form @submit.prevent @keydown.enter.prevent>
    <CustomStyle
      v-model="values.styles"
      style-key="input"
      :config-block-types="['input']"
      :theme="builder.theme"
    />
    <FormGroup
      small-label
      :label="$t('generalForm.labelTitle')"
      class="margin-bottom-2"
      required
    >
      <InjectedFormulaInput
        v-model="values.label"
        :placeholder="$t('generalForm.labelPlaceholder')"
      />
    </FormGroup>
    <FormGroup
      small-label
      :label="$t('generalForm.valueTitle')"
      class="margin-bottom-2"
      required
    >
      <InjectedFormulaInput
        v-model="values.default_value"
        :placeholder="$t('generalForm.valuePlaceholder')"
      />
    </FormGroup>
    <FormGroup
      small-label
      :label="$t('generalForm.requiredTitle')"
      class="margin-bottom-2"
      required
    >
      <Checkbox v-model="values.required"></Checkbox>
    </FormGroup>
    <FormGroup
      small-label
      :label="$t('common.dateFormatTitle')"
      class="margin-bottom-2"
      required
    >
      <Dropdown v-model="values.date_format" :fixed-items="true">
        <DropdownItem
          v-for="([value, { name, example }], index) in Object.entries(
            DATE_FORMATS
          )"
          :key="`${index} - ${value}`"
          :name="`${$t(name)} (${example})`"
          :value="value"
        />
      </Dropdown>
    </FormGroup>
    <FormGroup
      small-label
      :label="$t('dateTimePickerElementForm.includeTime')"
      class="margin-bottom-2"
      required
    >
      <Checkbox v-model="values.include_time"></Checkbox>
    </FormGroup>
    <FormGroup
      v-if="values.include_time"
      small-label
      :label="$t('common.timeFormatTitle')"
      class="margin-bottom-2"
      required
    >
      <Dropdown v-model="values.time_format" :fixed-items="true">
        <DropdownItem
          v-for="([value, { name, example }], index) in Object.entries(
            TIME_FORMATS
          )"
          :key="`${index} - ${value}`"
          :name="`${$t(name)} (${example})`"
          :value="value"
        />
      </Dropdown>
    </FormGroup>
  </form>
</template>

<script>
import formElementForm from '@baserow/modules/builder/mixins/formElementForm'
import InjectedFormulaInput from '@baserow/modules/core/components/formula/InjectedFormulaInput.vue'
import CustomStyle from '@baserow/modules/builder/components/elements/components/forms/style/CustomStyle'
import { DATE_FORMATS, TIME_FORMATS } from '@baserow/modules/builder/enums'

export default {
  name: 'DateTimePickerElementForm',
  components: { InjectedFormulaInput, CustomStyle },
  mixins: [formElementForm],
  data() {
    return {
      values: {
        label: '',
        default_value: '',
        required: false,
        date_format: '',
        include_time: false,
        time_format: '',
      },
    }
  },
  computed: {
    TIME_FORMATS() {
      return TIME_FORMATS
    },
    DATE_FORMATS() {
      return DATE_FORMATS
    },
  },
}
</script>
