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
      >
        <template #leading-tabs>
          <Tab
            :title="$t('serviceRefinementForms.searchTabTitle', { count: 0 })"
            class="padding-left-0 padding-right-0"
          >
            <LocalBaserowSemanticSearchSettings
              v-bind="settingsProps"
              @choose-fields="chooseFields"
            />
          </Tab>
        </template>
      </ServiceRefinementForms>
      <LocalBaserowSemanticSearchSettings
        v-if="small"
        v-bind="settingsProps"
        @choose-fields="chooseFields"
      />
    </template>
    <div v-if="fieldsLoading" class="skeleton">
      <div
        v-for="labelWidth in ['90px', '120px', '110px', '130px']"
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
import Tab from '@baserow/modules/core/components/Tab'
import LocalBaserowSemanticSearchSettings from '@baserow_enterprise/integrations/localBaserow/components/services/LocalBaserowSemanticSearchSettings'

export default {
  name: 'LocalBaserowSemanticSearchServiceForm',
  components: {
    LocalBaserowServiceForm,
    ServiceRefinementForms,
    Tab,
    LocalBaserowSemanticSearchSettings,
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
    settingsProps() {
      return {
        values: this.values,
        tableFields: this.tableFields,
        v$: this.v$,
        maxResults: this.maxResults || null,
        maxResultsError: this.getFirstErrorMessage('max_results') || null,
        minSimilarityError: this.getFirstErrorMessage('min_similarity') || null,
      }
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
