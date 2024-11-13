<template>
  <form @submit.prevent @keydown.enter.prevent>
    <CustomStyle
      v-model="v$.styles.$model"
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
        v-model="v$.label.$model"
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
        v-model="v$.default_value.$model"
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
        v-model="v$.placeholder.$model"
        :placeholder="$t('generalForm.placeholderPlaceholder')"
      />
    </FormGroup>
    <FormGroup
      :label="$t('generalForm.requiredTitle')"
      small-label
      required
      class="margin-bottom-2"
    >
      <Checkbox v-model="v$.required.$model"></Checkbox>
    </FormGroup>

    <FormGroup
      :label="$t('generalForm.validationTitle')"
      small-label
      required
      class="margin-bottom-2"
    >
      <Dropdown v-model="v$.validation_type.$model" :show-search="true">
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
      <Checkbox v-model="v$.is_multiline.$model"></Checkbox>
    </FormGroup>

    <FormGroup
      v-if="v$.is_multiline.$model"
      small-label
      required
      class="margin-bottom-2"
      :error="v$.rows.$error"
    >
      <FormInput
        v-model="v$.rows.$model"
        type="number"
        :label="$t('inputTextElementForm.rowsTitle')"
        :placeholder="$t('inputTextElementForm.rowsPlaceholder')"
        :to-value="(value) => parseInt(value)"
      ></FormInput>

      <template #error>
        <span v-if="v$.rows.required.$invalid">
          {{ $t('error.requiredField') }}
        </span>
        <span v-else-if="v$.rows.integer.$invalid">
          {{ $t('error.integerField') }}
        </span>
        <span v-else-if="v$.rows.minValue.$invalid">
          {{ $t('error.minValueField', { min: 1 }) }}
        </span>
        <span v-else-if="v$.rows.maxValue.$invalid">
          {{ $t('error.maxValueField', { max: 100 }) }}
        </span>
      </template>
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
import { reactive, computed } from 'vue'
import form from '@baserow/modules/core/mixins/form'
import InjectedFormulaInput from '@baserow/modules/core/components/formula/InjectedFormulaInput.vue'
import formElementForm from '@baserow/modules/builder/mixins/formElementForm'
import CustomStyle from '@baserow/modules/builder/components/elements/components/forms/style/CustomStyle'
import { required, integer, minValue, maxValue } from '@vuelidate/validators'

export default {
  name: 'InputTextElementForm',
  components: { InjectedFormulaInput, CustomStyle },
  mixins: [formElementForm],
  data() {
    return {
      values: null,
      v$: null,
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
  created() {
    const values = reactive({
      label: '',
      default_value: '',
      required: false,
      validation_type: 'any',
      placeholder: '',
      is_multiline: false,
      rows: 3,
      type: 'text',
      styles: {},
    })

    const rules = computed(() => ({
      rows: {
        required,
        integer,
        minValue: minValue(1),
        maxValue: maxValue(100),
      },
      label: {},
      default_value: {},
      required: {},
      validation_type: {},
      placeholder: {},
      is_multiline: {},
      type: {},
      styles: {},
    }))

    this.v$ = useVuelidate(rules, values, { $lazy: true })
    this.values = values
  },
  methods: {
    emitChange(newValues) {
      if (this.isFormValid()) {
        form.methods.emitChange.bind(this)(newValues)
      }
    },
  },
}
</script>
