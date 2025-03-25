<template>
  <form @submit.prevent>
    <FormGroup
      :label="$t('localBaserowServiceForm.integrationDropdownLabel')"
      small-label
      required
      class="margin-bottom-2"
    >
      <IntegrationDropdown
        v-model="values.integration_id"
        :application="builder"
        :integrations="integrations"
        :integration-type="integrationType"
      />
    </FormGroup>
    <LocalBaserowTableSelector
      v-if="selectedIntegration"
      v-model="fakeTableId"
      disallow-data-synced-tables
      :databases="databases"
      :display-view-dropdown="false"
    />
    <FormGroup
      v-if="enableRowId && values.integration_id"
      small-label
      :label="$t('localBaserowServiceForm.rowIdLabel')"
      class="margin-bottom-2"
      required
    >
      <InjectedFormulaInput
        v-model="values.row_id"
        :disabled="values.table_id === null"
        :placeholder="$t('localBaserowServiceForm.rowIdPlaceholder')"
      />
    </FormGroup>
  </form>
</template>

<script>
import LocalBaserowTableSelector from '@baserow/modules/integrations/localBaserow/components/services/LocalBaserowTableSelector'
import { LocalBaserowIntegrationType } from '@baserow/modules/integrations/integrationTypes'
import InjectedFormulaInput from '@baserow/modules/core/components/formula/InjectedFormulaInput'
import IntegrationDropdown from '@baserow/modules/core/components/integrations/IntegrationDropdown'
import form from '@baserow/modules/core/mixins/form'

/**
 * The purpose of this component is to reuse the concept of a "Local Baserow service form"
 * across our Local Baserow workflow action forms. Upsert (used by Create and Update)
 * and Delete need to be able to manage the integration, table, and optional row ID.
 * Rather than duplicate the form a few times, this component keeps things tidier.
 */
export default {
  name: 'LocalBaserowServiceForm',
  components: {
    IntegrationDropdown,
    LocalBaserowTableSelector,
    InjectedFormulaInput,
  },
  mixins: [form],
  inject: ['builder'],
  props: {
    enableRowId: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  data() {
    return {
      allowedValues: ['row_id', 'table_id', 'integration_id'],
      values: {
        row_id: '',
        table_id: null,
        integration_id: null,
      },
    }
  },
  computed: {
    integrations() {
      return this.$store.getters['integration/getIntegrations'](this.builder)
    },
    fakeTableId: {
      get() {
        return this.values.table_id
      },
      set(newValue) {
        this.values.table_id = newValue
        // Emit that the table changed so that the parent
        // component can optionally do something with it,
        // e.g. showing a loading spinner.
        this.$emit('table-changed', newValue)
      },
    },
    integrationType() {
      return this.$registry.get(
        'integration',
        LocalBaserowIntegrationType.getType()
      )
    },
    selectedIntegration() {
      return this.$store.getters['integration/getIntegrationById'](
        this.builder,
        this.values.integration_id
      )
    },
    databases() {
      return this.selectedIntegration?.context_data.databases || []
    },
  },
  watch: {
    'values.table_id': {
      handler(newValue, oldValue) {
        if (oldValue && newValue !== oldValue) {
          this.values.row_id = ''
        }
      },
    },
  },
}
</script>
