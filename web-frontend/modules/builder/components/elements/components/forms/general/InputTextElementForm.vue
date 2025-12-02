<template>
  <form @submit.prevent @keydown.enter.prevent>
    <CustomStyleButton
      v-model="v$.values.styles.$model"
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
        v-model="v$.values.label.$model"
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
        v-model="v$.values.default_value.$model"
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
        v-model="v$.values.placeholder.$model"
        :placeholder="$t('generalForm.placeholderPlaceholder')"
      />
    </FormGroup>
    <FormGroup
      :label="$t('generalForm.requiredTitle')"
      small-label
      required
      class="margin-bottom-2"
    >
      <Checkbox v-model="v$.values.required.$model"></Checkbox>
    </FormGroup>

    <FormGroup
      :label="$t('generalForm.validationTitle')"
      small-label
      required
      class="margin-bottom-2"
    >
      <Dropdown v-model="v$.values.validation_type.$model" :show-search="true">
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
      <Checkbox v-model="v$.values.is_multiline.$model"></Checkbox>
    </FormGroup>

    <FormGroup
      v-if="v$.values.is_multiline.$model"
      small-label
      required
      class="margin-bottom-2"
      :error-message="getFirstErrorMessage('rows')"
    >
      <FormInput
        v-model="v$.values.rows.$model"
        type="number"
        :label="$t('inputTextElementForm.rowsTitle')"
        :placeholder="$t('inputTextElementForm.rowsPlaceholder')"
        :to-value="(value) => parseInt(value)"
      />
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
import { useVuelidate } from '@vuelidate/core'
import form from '@baserow/modules/core/mixins/form'
import InjectedFormulaInput from '@baserow/modules/core/components/formula/InjectedFormulaInput.vue'
import formElementForm from '@baserow/modules/builder/mixins/formElementForm'
import CustomStyleButton from '@baserow/modules/builder/components/elements/components/forms/style/CustomStyleButton'
import {
  required,
  integer,
  minValue,
  maxValue,
  helpers,
} from '@vuelidate/validators'

export default {
  name: 'InputTextElementForm',
  components: { InjectedFormulaInput, CustomStyleButton },
  mixins: [formElementForm],
  setup() {
    return { v$: useVuelidate() }
  },
  data() {
    return {
      allowedValues: [
        'label',
        'default_value',
        'required',
        'validation_type',
        'placeholder',
        'is_multiline',
        'rows',
        'type',
        'styles',
        'input_type',
      ],
      values: {
        label: {},
        default_value: {},
        required: false,
        validation_type: 'any',
        placeholder: {},
        is_multiline: false,
        input_type: 'text',
        rows: 3,
        type: 'text',
        styles: {},
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
          required: helpers.withMessage(
            this.$t('error.requiredField'),
            required
          ),
          integer: helpers.withMessage(this.$t('error.integerField'), integer),
          minValue: helpers.withMessage(
            this.$t('error.minValueField', { min: 1 }),
            minValue(1)
          ),
          maxValue: helpers.withMessage(
            this.$t('error.maxValueField', { max: 100 }),
            maxValue(100)
          ),
        },
        label: {},
        default_value: {},
        required: {},
        validation_type: {},
        placeholder: {},
        is_multiline: {},
        type: {},
        styles: {},
      },
    }
  },
}
</script>
