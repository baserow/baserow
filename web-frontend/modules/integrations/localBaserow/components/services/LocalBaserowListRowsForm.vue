<template>
  <form :class="{ 'service-form--small': small }" @submit.prevent>
    <div class="row">
      <div class="col col-12">
        <LocalBaserowServiceForm
          :application="application"
          :default-values="defaultValues"
          :enable-integration-picker="enableIntegrationPicker"
          @values-changed="values = { ...values, ...$event }"
        ></LocalBaserowServiceForm>
      </div>
    </div>
    <div v-if="!small && !fieldsLoading" class="row">
      <div class="col col-12">
        <Tabs>
          <Tab
            :title="$t('localBaserowListRowsForm.filterTabTitle')"
            class="service-form__condition-form-tab"
          >
            <LocalBaserowTableServiceConditionalForm
              v-if="values.table_id"
              v-model="values.filters"
              :fields="tableFields"
              :filter-type.sync="values.filter_type"
            >
            </LocalBaserowTableServiceConditionalForm>
            <p v-if="!values.table_id">
              {{ $t('localBaserowListRowsForm.noTableChosenForFiltering') }}
            </p>
          </Tab>
          <Tab
            :title="$t('localBaserowListRowsForm.sortTabTitle')"
            class="service-form__sort-form-tab"
          >
            <LocalBaserowTableServiceSortForm
              v-if="values.table_id"
              v-model="values.sortings"
              :fields="tableFields"
            ></LocalBaserowTableServiceSortForm>
            <p v-if="!values.table_id">
              {{ $t('localBaserowListRowsForm.noTableChosenForSorting') }}
            </p>
          </Tab>
          <Tab
            :title="$t('localBaserowListRowsForm.searchTabTitle')"
            class="service-form__search-form-tab"
          >
            <InjectedFormulaInput
              v-model="values.search_query"
              small
              :placeholder="
                $t('localBaserowListRowsForm.searchFieldPlaceHolder')
              "
            />
          </Tab>
          <Tab
            :title="$t('localBaserowListRowsForm.advancedConfig')"
            class="service-form__search-form-tab"
          >
            <FormGroup
              class="margin-bottom-2"
              small-label
              :label="$t('localBaserowListRowsForm.defaultResultCount')"
              :helper-text="
                $t('localBaserowListRowsForm.defaultResultCountHelp')
              "
              required
              :error-message="getFirstErrorMessage('default_result_count')"
            >
              <FormInput
                v-model="v$.values.default_result_count.$model"
                class="service-form__result-count-input"
                :placeholder="
                  $t('localBaserowListRowsForm.defaultResultCountPlaceholder')
                "
                :to-value="(value) => parseFloat(value)"
                type="number"
              />
            </FormGroup>
          </Tab>
        </Tabs>
      </div>
    </div>
    <div v-if="fieldsLoading" class="loading-spinner"></div>
  </form>
</template>

<script>
import form from '@baserow/modules/core/mixins/form'
import LocalBaserowTableServiceConditionalForm from '@baserow/modules/integrations/localBaserow/components/services/LocalBaserowTableServiceConditionalForm'
import LocalBaserowTableServiceSortForm from '@baserow/modules/integrations/localBaserow/components/services/LocalBaserowTableServiceSortForm'
import InjectedFormulaInput from '@baserow/modules/core/components/formula/InjectedFormulaInput'
import localBaserowService from '@baserow/modules/integrations/localBaserow/mixins/localBaserowService'
import {
  required,
  minValue,
  maxValue,
  helpers,
  integer,
} from '@vuelidate/validators'
import { useVuelidate } from '@vuelidate/core'
import LocalBaserowServiceForm from '@baserow/modules/integrations/localBaserow/components/services/LocalBaserowServiceForm'

export default {
  components: {
    LocalBaserowServiceForm,
    InjectedFormulaInput,
    LocalBaserowTableServiceSortForm,
    LocalBaserowTableServiceConditionalForm,
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
        'search_query',
        'filters',
        'filter_type',
        'sortings',
        'default_result_count',
      ],
      values: {
        table_id: null,
        view_id: null,
        search_query: '',
        filters: [],
        sortings: [],
        filter_type: 'AND',
        default_result_count: null,
      },
    }
  },
  computed: {
    maxResultLimit() {
      return this.service
        ? this.$registry
            .get('service', this.service.type)
            .getMaxResultLimit(this.service)
        : null
    },
  },
  validations() {
    return {
      values: {
        default_result_count: {
          required: helpers.withMessage(
            this.$t('error.requiredField'),
            required
          ),
          integer: helpers.withMessage(this.$t('error.integerField'), integer),
          minValue: helpers.withMessage(
            this.$t('error.minValueField', { min: 0 }),
            minValue(0)
          ),
          maxValue: helpers.withMessage(
            this.$t('error.maxValueField', { max: this.maxResultLimit }),
            maxValue(this.maxResultLimit)
          ),
        },
      },
    }
  },
}
</script>
