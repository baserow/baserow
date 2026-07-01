<template>
  <form @submit.prevent>
    <LocalBaserowServiceForm
      :service-type="serviceType"
      :application="application"
      :enable-view-picker="false"
      :default-values="defaultValues"
      @table-changed="handleTableChange"
      @values-changed="emitServiceChange($event)"
    ></LocalBaserowServiceForm>
    <FormGroup
      small-label
      :label="$t(`${translationPrefix}.rowsLabel`)"
      :helper-text="
        $t(`${translationPrefix}.rowsHelper`, {
          limit: batchOperationSizeLimit,
        })
      "
      class="margin-bottom-2"
      required
    >
      <InjectedFormulaInput
        v-model="values.rows"
        :disabled="!selectedTableId"
        allow-node-selection="array"
        :placeholder="$t(`${translationPrefix}.rowsPlaceholder`)"
      />
    </FormGroup>
    <div v-if="tableLoading" class="loading-spinner margin-bottom-1"></div>
    <p v-if="selectedIntegrationId && !selectedTableId">
      {{ $t('localBaserowUpsertRowServiceForm.noTableSelectedMessage') }}
    </p>
  </form>
</template>

<script>
import _ from 'lodash'
import form from '@baserow/modules/core/mixins/form'
import InjectedFormulaInput from '@baserow/modules/core/components/formula/InjectedFormulaInput'
import LocalBaserowServiceForm from '@baserow/modules/integrations/localBaserow/components/services/LocalBaserowServiceForm'

export default {
  name: 'LocalBaserowCreateRowsServiceForm',
  components: {
    InjectedFormulaInput,
    LocalBaserowServiceForm,
  },
  mixins: [form],
  props: {
    application: {
      type: Object,
      required: true,
    },
    loading: {
      type: Boolean,
      required: false,
      default: false,
    },
    service: {
      type: Object,
      required: false,
      default: () => ({}),
    },
    serviceType: {
      type: Object,
      required: false,
      default: () => ({}),
    },
  },
  emits: ['values-changed'],
  data() {
    return {
      allowedValues: ['rows'],
      values: {
        rows: {},
      },
      state: null,
      tableLoading: false,
    }
  },
  computed: {
    translationPrefix() {
      return this.serviceType?.type === 'local_baserow_update_rows'
        ? 'localBaserowUpdateRowsServiceForm'
        : 'localBaserowCreateRowsServiceForm'
    },
    batchOperationSizeLimit() {
      return this.$config.public.integrationLocalBaserowBatchOperationSizeLimit
    },
    selectedIntegrationId() {
      return this.values.integration_id || this.service?.integration_id || null
    },
    selectedTableId() {
      return this.values.table_id || this.service?.table_id || null
    },
  },
  watch: {
    loading: {
      handler(value) {
        if (!value) {
          this.tableLoading = false
        }
      },
    },
  },
  methods: {
    handleTableChange() {
      this.tableLoading = true
    },
    emitServiceChange(newValues) {
      if (this.isFormValid()) {
        const differences = Object.fromEntries(
          Object.entries(newValues).filter(
            ([key, value]) => !_.isEqual(value, this.defaultValues[key])
          )
        )
        if (Object.keys(differences).length > 0) {
          this.$emit('values-changed', differences)
        }
      }
    },
  },
}
</script>
