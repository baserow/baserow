<template>
  <form :class="{ 'service-form--small': small }" @submit.prevent>
    <LocalBaserowServiceForm
      :application="application"
      :service-type="serviceType"
      :default-values="defaultValues"
      :databases="databases"
      @values-changed="values = { ...values, ...$event }"
    ></LocalBaserowServiceForm>

    <template v-if="values.table_id && !fieldsLoading">
      <FormGroup
        small-label
        :label="$t('localBaserowSemanticSearchForm.fields')"
        :error-message="
          searchFieldsGone
            ? $t('localBaserowSemanticSearchForm.searchFieldsGone')
            : null
        "
        class="margin-bottom-2"
      >
        <Dropdown
          v-model="values.search_field_ids"
          :disabled="semanticSearchFields.length === 0"
          :placeholder="$t('localBaserowSemanticSearchForm.fieldsPlaceholder')"
          multiple
        >
          <DropdownItem
            v-for="field in semanticSearchFields"
            :key="field.id"
            :name="field.name"
            :value="field.id"
          ></DropdownItem>
        </Dropdown>
        <template #helper>
          {{
            semanticSearchFields.length === 0
              ? $t('localBaserowSemanticSearchForm.noFields')
              : $t('localBaserowSemanticSearchForm.fieldsHelper')
          }}
        </template>
      </FormGroup>

      <FormGroup
        small-label
        :label="$t('localBaserowSemanticSearchForm.searchQuery')"
        :helper-text="$t('localBaserowSemanticSearchForm.searchQueryHelper')"
        required
        class="margin-bottom-2"
      >
        <InjectedFormulaInput
          v-model="values.search_query"
          :placeholder="
            $t('localBaserowSemanticSearchForm.searchQueryPlaceholder')
          "
        />
      </FormGroup>

      <FormGroup
        small-label
        :label="$t('localBaserowSemanticSearchForm.includedFields')"
        :helper-text="$t('localBaserowSemanticSearchForm.includedFieldsHelper')"
        class="margin-bottom-2"
      >
        <Dropdown
          v-model="values.included_field_ids"
          :placeholder="
            $t('localBaserowSemanticSearchForm.includedFieldsPlaceholder')
          "
          multiple
        >
          <DropdownItem
            v-for="field in tableFields"
            :key="field.id"
            :name="field.name"
            :value="field.id"
          ></DropdownItem>
        </Dropdown>
      </FormGroup>

      <FormGroup
        small-label
        :label="$t('localBaserowSemanticSearchForm.maxResults')"
        required
        :error-message="getFirstErrorMessage('max_results')"
        class="margin-bottom-2"
      >
        <FormInput
          v-model="v$.values.max_results.$model"
          type="number"
          :to-value="(value) => parseInt(value)"
        />
      </FormGroup>

      <FormGroup
        small-label
        :label="$t('localBaserowSemanticSearchForm.minSimilarity')"
        :helper-text="$t('localBaserowSemanticSearchForm.minSimilarityHelper')"
        :error-message="getFirstErrorMessage('min_similarity')"
        class="margin-bottom-2"
      >
        <FormInput
          v-model="v$.values.min_similarity.$model"
          type="number"
          :placeholder="
            $t('localBaserowSemanticSearchForm.minSimilarityPlaceholder')
          "
          :to-value="(value) => (value === '' ? null : parseFloat(value))"
        />
      </FormGroup>

      <ServiceRefinementForms
        :small="small"
        :values="values"
        :table-fields="tableFields"
        show-filter
      />
    </template>
    <div v-if="fieldsLoading" class="loading-spinner"></div>
  </form>
</template>

<script>
import {
  helpers,
  integer,
  minValue,
  maxValue,
  required,
} from '@vuelidate/validators'
import { useVuelidate } from '@vuelidate/core'
import form from '@baserow/modules/core/mixins/form'
import localBaserowService from '@baserow/modules/integrations/localBaserow/mixins/localBaserowService'
import LocalBaserowServiceForm from '@baserow/modules/integrations/localBaserow/components/services/LocalBaserowServiceForm'
import ServiceRefinementForms from '@baserow/modules/integrations/localBaserow/components/services/ServiceRefinementForms'
import InjectedFormulaInput from '@baserow/modules/core/components/formula/InjectedFormulaInput'

export default {
  name: 'LocalBaserowSemanticSearchServiceForm',
  components: {
    LocalBaserowServiceForm,
    ServiceRefinementForms,
    InjectedFormulaInput,
  },
  mixins: [form, localBaserowService],
  setup() {
    return { v$: useVuelidate({ $lazy: true }) }
  },
  data() {
    return {
      allowedValues: [
        'table_id',
        'view_id',
        'search_field_ids',
        'search_query',
        'included_field_ids',
        'max_results',
        'min_similarity',
        'filters',
        'filter_groups',
        'filter_type',
      ],
      values: {
        table_id: null,
        view_id: null,
        search_field_ids: [],
        search_query: {},
        included_field_ids: [],
        max_results: 10,
        min_similarity: null,
        filters: [],
        filter_groups: [],
        filter_type: 'AND',
      },
    }
  },
  computed: {
    semanticSearchFields() {
      return this.tableFields.filter((field) => field.semantic_search_enabled)
    },
    // The search fails, instead of searching the fields that were left out.
    searchFieldsGone() {
      return (
        this.defaultValues.search_all_fields === false &&
        !this.values.search_field_ids.some((id) =>
          this.semanticSearchFields.some((field) => field.id === id)
        )
      )
    },
  },
  watch: {
    'values.table_id'(newTableId, oldTableId) {
      // The fields belong to the previous table. The initial load is skipped,
      // because it would clear the saved fields.
      if (
        oldTableId !== null &&
        oldTableId !== undefined &&
        newTableId !== oldTableId
      ) {
        this.values.search_field_ids = []
        this.values.included_field_ids = []
      }
    },
  },
  validations() {
    return {
      values: {
        max_results: {
          required: helpers.withMessage(
            this.$t('error.requiredField'),
            required
          ),
          integer: helpers.withMessage(this.$t('error.integerField'), integer),
          minValue: helpers.withMessage(
            this.$t('error.minValueField', { min: 1 }),
            minValue(1)
          ),
        },
        min_similarity: {
          minValue: helpers.withMessage(
            this.$t('error.minValueField', { min: 0 }),
            minValue(0)
          ),
          maxValue: helpers.withMessage(
            this.$t('error.maxValueField', { max: 1 }),
            maxValue(1)
          ),
        },
      },
    }
  },
}
</script>
