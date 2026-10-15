<template>
  <form :class="{ 'service-form--small': small }" @submit.prevent>
    <LocalBaserowServiceForm
      :application="application"
      :service-type="serviceType"
      :default-values="defaultValues"
      :databases="databases"
      @values-changed="values = { ...values, ...$event }"
      @table-changed="onTableChanged"
    ></LocalBaserowServiceForm>

    <template v-if="values.table_id && !fieldsLoading">
      <ServiceRefinementForms
        :small="small"
        :values="values"
        :table-fields="tableFields"
        show-filter
        class="margin-bottom-2"
      />
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
          :model-value="values.search_field_ids"
          :disabled="searchFieldOptions.length === 0"
          :placeholder="$t('localBaserowSemanticSearchForm.fieldsPlaceholder')"
          multiple
          @update:model-value="
            chooseFields('search_field_ids', 'search_all_fields', $event)
          "
        >
          <DropdownItem
            v-for="field in searchFieldOptions"
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
        :error-message="
          includedFieldsGone
            ? $t('localBaserowSemanticSearchForm.includedFieldsGone')
            : null
        "
        class="margin-bottom-2"
      >
        <Dropdown
          :model-value="values.included_field_ids"
          :placeholder="
            $t('localBaserowSemanticSearchForm.includedFieldsPlaceholder')
          "
          multiple
          @update:model-value="
            chooseFields('included_field_ids', 'include_all_fields', $event)
          "
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
    </template>
    <div v-if="fieldsLoading" class="skeleton">
      <div
        v-for="labelWidth in ['120px', '90px', '110px', '160px', '130px']"
        :key="labelWidth"
        class="margin-bottom-2"
      >
        <SkeletonBlock :width="labelWidth" height="10px" />
        <SkeletonBlock class="margin-top-1" height="36px" />
      </div>
    </div>
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
        'search_all_fields',
        'search_field_ids',
        'search_query',
        'include_all_fields',
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
        search_all_fields: true,
        search_field_ids: [],
        search_query: {},
        include_all_fields: true,
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
    maxResults() {
      return this.$store.getters['settings/get'].semantic_search?.max_results
    },
    semanticSearchFields() {
      return this.tableFields.filter((field) => field.semantic_search_enabled)
    },
    // A chosen field of which semantic search was disabled stays chosen, so it can
    // be deselected.
    searchFieldOptions() {
      return this.tableFields.filter(
        (field) =>
          field.semantic_search_enabled ||
          this.values.search_field_ids.includes(field.id)
      )
    },
    // The search fails, instead of searching the fields that were left out.
    searchFieldsGone() {
      return (
        this.values.search_all_fields === false &&
        !this.values.search_field_ids.some((id) =>
          this.semanticSearchFields.some((field) => field.id === id)
        )
      )
    },
    // No values are returned, instead of the values of the fields that were left
    // out.
    includedFieldsGone() {
      return (
        this.values.include_all_fields === false &&
        !this.values.included_field_ids.some((id) =>
          this.tableFields.some((field) => field.id === id)
        )
      )
    },
  },
  methods: {
    /**
     * The fields belong to the previous table. This is only done when the user
     * picks a table, because resetting the form to restored values, like after an
     * undo, must keep their fields.
     */
    onTableChanged(tableId) {
      if (tableId !== this.values.table_id) {
        this.chooseFields('search_field_ids', 'search_all_fields', [])
        this.chooseFields('included_field_ids', 'include_all_fields', [])
      }
    },
    /**
     * Sets the flag that the server derives from the chosen fields together with
     * them, because the node shows the sent values before the server responds.
     * Clearing the choice means that all fields are used.
     */
    chooseFields(fieldIdsName, allFieldsName, fieldIds) {
      this.values[fieldIdsName] = fieldIds || []
      this.values[allFieldsName] = this.values[fieldIdsName].length === 0
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
          // Unknown when the server doesn't send it yet, then the server checks it.
          ...(this.maxResults
            ? {
                maxValue: helpers.withMessage(
                  this.$t('error.maxValueField', { max: this.maxResults }),
                  maxValue(this.maxResults)
                ),
              }
            : {}),
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
