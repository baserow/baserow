<template>
  <form @submit.prevent @keydown.enter.prevent>
    <CustomStyle
      v-model="values.styles"
      style-key="input"
      :config-block-types="['input']"
      :theme="builder.theme"
    />
    <FormGroup
      :label="$t('generalForm.labelTitle')"
      class="margin-bottom-2"
      required
      small-label
    >
      <InjectedFormulaInput
        v-model="values.label"
        :placeholder="$t('generalForm.labelPlaceholder')"
      />
    </FormGroup>
    <FormGroup
      :label="$t('generalForm.valueTitle')"
      class="margin-bottom-2"
      required
      small-label
    >
      <InjectedFormulaInput
        v-model="values.default_value"
        :placeholder="$t('generalForm.valuePlaceholder')"
      />
    </FormGroup>
    <FormGroup
      :label="$t('generalForm.placeholderTitle')"
      class="margin-bottom-2"
      required
      small-label
    >
      <InjectedFormulaInput
        v-model="values.placeholder"
        :placeholder="$t('generalForm.placeholderPlaceholder')"
      />
    </FormGroup>
    <FormGroup
      :label="$t('generalForm.requiredTitle')"
      small-label
      required
      class="margin-bottom-2"
    >
      <Checkbox v-model="values.required"></Checkbox>
    </FormGroup>

    <FormGroup
      :label="$t('generalForm.validationTitle')"
      small-label
      required
      class="margin-bottom-2"
    >
      <Dropdown v-model="values.validation_type" :show-search="true">
        <DropdownItem
          v-for="validationType in validationTypes"
          :key="validationType.name"
          :name="validationType.label"
          :value="validationType.name"
          :description="validationType.description"
        >
        </DropdownItem>
      </Dropdown>
    </FormGroup>

    <FormGroup
      :label="$t('inputTextElementForm.multilineTitle')"
      small-label
      required
      class="margin-bottom-2"
    >
      <Checkbox v-model="values.is_multiline"></Checkbox>
    </FormGroup>

    <FormGroup
      v-if="values.is_multiline"
      small-label
      required
      class="margin-bottom-2"
      :error-message="
        $v.values.rows.$dirty && !$v.values.rows.required
          ? $t('error.requiredField')
          : !$v.values.rows.integer
          ? $t('error.integerField')
          : !$v.values.rows.minValue
          ? $t('error.minValueField', { min: 1 })
          : !$v.values.rows.maxValue
          ? $t('error.maxValueField', { max: 100 })
          : ''
      "
    >
      <FormInput
        v-model="values.rows"
        type="number"
        :label="$t('inputTextElementForm.rowsTitle')"
        :placeholder="$t('inputTextElementForm.rowsPlaceholder')"
        :to-value="(value) => parseInt(value)"
      ></FormInput>
    </FormGroup>

    <FormGroup
      v-else
      :label="$t('inputTextElementForm.inputType')"
      :helper-text="
        values.input_type === 'password'
          ? $t('inputTextElementForm.passwordTypeWarning')
          : null
      "
      small-label
      required
      class="margin-bottom-2"
    >
      <Dropdown v-model="values.input_type" :show-search="false">
        <DropdownItem
          v-for="inputType in inputTypes"
          :key="inputType.name"
          :name="inputType.label"
          :value="inputType.name"
          :description="inputType.description"
        >
        </DropdownItem>
      </Dropdown>
    </FormGroup>
  </form>
</template>

<script>
import form from '@baserow/modules/core/mixins/form'
import InjectedFormulaInput from '@baserow/modules/core/components/formula/InjectedFormulaInput.vue'
import formElementForm from '@baserow/modules/builder/mixins/formElementForm'
import CustomStyle from '@baserow/modules/builder/components/elements/components/forms/style/CustomStyle'
import { required, integer, minValue, maxValue } from 'vuelidate/lib/validators'

export default {
  name: 'InputTextElementForm',
  components: { InjectedFormulaInput, CustomStyle },
  mixins: [formElementForm],
  data() {
    return {
      values: {
        label: '',
        default_value: '',
        required: false,
        validation_type: 'any',
        placeholder: '',
        is_multiline: false,
        rows: 3,
        type: 'text',
      },
    }
  },
  computed: {
    validationTypes() {
      return [
        {
          name: 'any',
          label: this.$t('inputTextElementForm.validationTypeAnyLabel'),
          description: this.$t(
            'inputTextElementForm.validationTypeAnyDescription'
          ),
        },
        {
          name: 'integer',
          label: this.$t('inputTextElementForm.validationTypeIntegerLabel'),
          description: this.$t(
            'inputTextElementForm.validationTypeIntegerDescription'
          ),
        },
        {
          name: 'email',
          label: this.$t('inputTextElementForm.validationTypeEmailLabel'),
          description: this.$t(
            'inputTextElementForm.validationTypeEmailDescription'
          ),
        },
      ]
    },
    inputTypes() {
      return [
        {
          name: 'text',
          label: this.$t('inputTextElementForm.inputTypeTextLabel'),
        },
        {
          name: 'password',
          label: this.$t('inputTextElementForm.inputTypePasswordLabel'),
        },
      ]
    },
  },
  methods: {
    emitChange(newValues) {
      if (this.isFormValid()) {
        form.methods.emitChange.bind(this)(newValues)
      }
    },
  },
  validations() {
    return {
      values: {
        rows: {
          required,
          integer,
          minValue: minValue(1),
          maxValue: maxValue(100),
        },
      },
    }
  },
}
</script>
