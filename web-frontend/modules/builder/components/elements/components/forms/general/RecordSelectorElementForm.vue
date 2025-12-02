<template>
  <form @submit.prevent @keydown.enter.prevent>
    <CustomStyleButton
      v-model="values.styles"
      style-key="input"
      :config-block-types="['input']"
      :theme="builder.theme"
    />
    <FormGroup
      class="margin-bottom-2"
      small-label
      required
      :label="$t('recordSelectorElementForm.selectRecordsFrom')"
    >
      <DataSourceDropdown
        v-model="values.data_source_id"
        small
        :shared-data-sources="listSharedDataSources"
        :local-data-sources="listLocalDataSources"
      >
        <template #chooseValueState>
          {{ $t('recordSelectorElementForm.noDataSourceMessage') }}
        </template>
      </DataSourceDropdown>
    </FormGroup>
    <FormGroup
      class="margin-bottom-2"
      small-label
      :label="$t('recordSelectorElementForm.itemsPerPage')"
      :error-message="getFirstErrorMessage('items_per_page')"
    >
      <FormInput
        v-model="v$.values.items_per_page.$model"
        type="number"
        :to-value="(value) => parseInt(value)"
        :placeholder="$t('recordSelectorElementForm.itemsPerPagePlaceholder')"
        @blur="v$.values.items_per_page.$touch()"
      />
    </FormGroup>
    <!--
    We use a key here otherwise Vuejs reuse the components of the following
    formula input with the old application context when the v-if becomes true.
    Therefore the "allowSameElement" value is wrong showing invalid formula when they
    are valid. We could also solve this by using a v-show instead of a v-if.
    -->
    <FormGroup
      v-if="values.data_source_id"
      key="optionNameSuffix"
      class="margin-bottom-2"
      small-label
      :label="$t('recordSelectorElementForm.optionNameSuffix')"
      :helper-text="$t('recordSelectorElementForm.optionNameSuffixHelper')"
      required
    >
      <InjectedFormulaInput
        v-model="values.option_name_suffix"
        :placeholder="
          $t('recordSelectorElementForm.optionNameSuffixPlaceholder')
        "
        :application-context-additions="{
          allowSameElement: true,
        }"
      />
    </FormGroup>
    <FormGroup
      small-label
      class="margin-bottom-2"
      :label="$t('generalForm.labelTitle')"
      required
    >
      <InjectedFormulaInput
        v-model="values.label"
        :placeholder="$t('generalForm.labelPlaceholder')"
      />
    </FormGroup>
    <FormGroup
      v-if="values.data_source_id"
      small-label
      class="margin-bottom-2"
      :label="$t('generalForm.valueTitle')"
      required
    >
      <InjectedFormulaInput
        v-model="values.default_value"
        :placeholder="$t('generalForm.valuePlaceholder')"
      />
    </FormGroup>
    <FormGroup
      small-label
      class="margin-bottom-2"
      :label="$t('generalForm.placeholderTitle')"
      required
    >
      <InjectedFormulaInput
        v-model="values.placeholder"
        :placeholder="$t('generalForm.placeholderPlaceholder')"
      />
    </FormGroup>
    <FormGroup
      small-label
      class="margin-bottom-2"
      required
      :label="$t('recordSelectorElementForm.multipleLabel')"
    >
      <Checkbox v-model="values.multiple"></Checkbox>
    </FormGroup>
    <FormGroup
      small-label
      class="margin-bottom-2"
      required
      :label="$t('generalForm.requiredTitle')"
    >
      <Checkbox v-model="values.required"></Checkbox>
    </FormGroup>
    <FormGroup
      v-if="propertyOptionsAvailable"
      small-label
      class="margin-bottom-2"
      :label="$t('collectionElementForm.propertyOptionLabel')"
    >
      <PropertyOptionForm
        :default-values="element"
        :is-filterable="element.is_publicly_filterable"
        :is-sortable="element.is_publicly_sortable"
        :is-searchable="element.is_publicly_searchable"
        :data-source="selectedDataSource"
        @values-changed="$emit('values-changed', $event)"
      ></PropertyOptionForm>
    </FormGroup>
  </form>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import collectionElementForm from '@baserow/modules/builder/mixins/collectionElementForm'
import InjectedFormulaInput from '@baserow/modules/core/components/formula/InjectedFormulaInput.vue'
import formElementForm from '@baserow/modules/builder/mixins/formElementForm'
import CustomStyleButton from '@baserow/modules/builder/components/elements/components/forms/style/CustomStyleButton'
import {
  integer,
  maxValue,
  minValue,
  required,
  helpers,
} from '@vuelidate/validators'
import DataSourceDropdown from '@baserow/modules/builder/components/dataSource/DataSourceDropdown.vue'
import PropertyOptionForm from '@baserow/modules/builder/components/elements/components/forms/general/settings/PropertyOptionForm'

export default {
  name: 'RecordSelectorElementForm',
  components: {
    PropertyOptionForm,
    DataSourceDropdown,
    CustomStyleButton,
    InjectedFormulaInput,
  },
  mixins: [formElementForm, collectionElementForm],
  setup() {
    return { v$: useVuelidate() }
  },
  data() {
    return {
      allowedValues: [
        'required',
        'data_source_id',
        'items_per_page',
        'label',
        'default_value',
        'placeholder',
        'multiple',
        'option_name_suffix',
        'styles',
      ],
      values: {
        required: false,
        data_source_id: null,
        items_per_page: null,
        label: {},
        default_value: {},
        placeholder: {},
        multiple: false,
        option_name_suffix: {},
        styles: {},
      },
    }
  },
  computed: {
    // For now, RecordSelector only supports data sources that return arrays
    listLocalDataSources() {
      if (this.localDataSources === null) {
        return null
      }
      return this.localDataSources.filter(
        (dataSource) =>
          this.$registry.get('service', dataSource.type).returnsList
      )
    },
    listSharedDataSources() {
      return this.sharedDataSources.filter(
        (dataSource) =>
          this.$registry.get('service', dataSource.type).returnsList
      )
    },
  },
  watch: {
    'values.data_source_id': {
      handler(value) {
        this.values.data_source_id = value

        // If the data source was removed we should also delete the name formula
        if (value === null) {
          this.values.option_name_suffix = ''
        }
      },
      immediate: true,
    },
  },
  validations() {
    return {
      values: {
        items_per_page: {
          required: helpers.withMessage(
            this.$t('error.requiredField'),
            required
          ),
          integer: helpers.withMessage(this.$t('error.integerField'), integer),
          // We need at least 5 items to trigger the
          // infinite scroll
          minValue: helpers.withMessage(
            this.$t('error.minValueField', { min: 5 }),
            minValue(5)
          ),
          maxValue: helpers.withMessage(
            this.$t('error.maxValueField', { max: this.maxItemPerPage }),
            maxValue(this.maxItemPerPage)
          ),
        },
      },
    }
  },
}
</script>
