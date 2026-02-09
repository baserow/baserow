<template>
  <form :class="{ 'service-form--small': small }" @submit.prevent>
    <div class="row">
      <div class="col col-12">
        <LocalBaserowServiceForm
          :application="application"
          :service-type="serviceType"
          :default-values="defaultValues"
          :enable-integration-picker="enableIntegrationPicker"
          @values-changed="values = { ...values, ...$event }"
        ></LocalBaserowServiceForm>
      </div>
    </div>
    <div class="row margin-bottom-2">
      <div class="col col-6">
        <FormGroup
          small-label
          :label="$t('localBaserowAggregateRowsForm.aggregationFieldLabel')"
          required
        >
          <Dropdown
            v-model="values.field_id"
            :disabled="tableFields.length === 0 || fieldsLoading"
          >
            <DropdownItem
              v-for="field in tableFields"
              :key="field.id"
              :name="field.name"
              :value="field.id"
            >
            </DropdownItem>
          </Dropdown>
        </FormGroup>
      </div>
      <div class="col col-6">
        <FormGroup
          small-label
          :label="$t('localBaserowAggregateRowsForm.aggregationTypeLabel')"
          required
        >
          <Dropdown
            v-model="values.aggregation_type"
            :disabled="!values.field_id || fieldsLoading"
          >
            <DropdownItem
              v-for="viewAggregation in viewAggregationTypes"
              :key="viewAggregation.getType()"
              :name="viewAggregation.getName()"
              :value="viewAggregation.getType()"
              :disabled="
                unsupportedAggregationTypes.includes(viewAggregation.getType())
              "
            >
            </DropdownItem>
          </Dropdown>
        </FormGroup>
      </div>
    </div>
    <ServiceRefinementForms
      v-if="!fieldsLoading && values.table_id"
      :small="small"
      :values="values"
      :table-fields="tableFields"
      show-filter
      show-search
    />
    <div v-if="fieldsLoading" class="loading-spinner"></div>
  </form>
</template>

<script>
import form from '@baserow/modules/core/mixins/form'
import LocalBaserowServiceForm from '@baserow/modules/integrations/localBaserow/components/services/LocalBaserowServiceForm.vue'
import localBaserowService from '@baserow/modules/integrations/localBaserow/mixins/localBaserowService'
import ServiceRefinementForms from '@baserow/modules/integrations/localBaserow/components/services/ServiceRefinementForms'

export default {
  components: {
    LocalBaserowServiceForm,
    ServiceRefinementForms,
  },
  mixins: [form, localBaserowService],
  data() {
    return {
      allowedValues: [
        'table_id',
        'view_id',
        'field_id',
        'search_query',
        'filters',
        'filter_type',
        'aggregation_type',
      ],
      values: {
        table_id: null,
        view_id: null,
        field_id: null,
        search_query: {},
        filters: [],
        filter_type: 'AND',
        aggregation_type: 'sum',
      },
    }
  },
  computed: {
    unsupportedAggregationTypes() {
      return this.$registry.get('service', 'local_baserow_aggregate_rows')
        .unsupportedAggregationTypes
    },
    viewAggregationTypes() {
      const selectedField = this.tableFields.find(
        (field) => field.id === this.values.field_id
      )
      if (!selectedField) return []
      return this.$registry
        .getOrderedList('viewAggregation')
        .filter((agg) => agg.fieldIsCompatible(selectedField))
    },
  },
}
</script>
