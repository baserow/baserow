<template>
  <form :class="{ 'service-form--small': small }" @submit.prevent>
    <LocalBaserowServiceForm
      :application="application"
      :service-type="serviceType"
      :default-values="defaultValues"
      :databases="databases"
      :enable-view-picker="false"
      @values-changed="values = { ...values, ...$event }"
    ></LocalBaserowServiceForm>
    <FormGroup
      small-label
      :label="$t('localBaserowFieldsUpdatedForm.fieldLabel')"
      :helper-text="$t('localBaserowFieldsUpdatedForm.fieldHelper')"
      required
    >
      <Dropdown
        v-model="values.field_ids"
        multiple
        :disabled="selectableFields.length === 0 || fieldsLoading"
      >
        <DropdownItem
          v-for="field in selectableFields"
          :key="field.id"
          :name="field.name"
          :value="field.id"
        >
        </DropdownItem>
      </Dropdown>
    </FormGroup>
    <div v-if="fieldsLoading" class="loading-spinner"></div>
  </form>
</template>

<script>
import form from '@baserow/modules/core/mixins/form'
import LocalBaserowServiceForm from '@baserow/modules/integrations/localBaserow/components/services/LocalBaserowServiceForm.vue'
import localBaserowService from '@baserow/modules/integrations/localBaserow/mixins/localBaserowService'

export default {
  name: 'LocalBaserowFieldsUpdatedTriggerServiceForm',
  components: { LocalBaserowServiceForm },
  mixins: [form, localBaserowService],
  data() {
    return {
      allowedValues: ['table_id', 'integration_id', 'field_ids'],
      values: {
        table_id: null,
        integration_id: null,
        field_ids: [],
      },
    }
  },
  computed: {
    /**
     * Only fields the user can directly set are eligible. Read-only field types
     * (formula, lookup, created/last modified, autonumber, etc.) can never be
     * targeted, since their value isn't changed by a user editing the row.
     */
    selectableFields() {
      return this.tableFields.filter(
        (field) =>
          !this.$registry.get('field', field.type).isReadOnlyField(field)
      )
    },
  },
  watch: {
    'values.table_id'(newTableId, oldTableId) {
      // Clear the selected fields when the user switches to a different table,
      // since they belong to the previous table. We guard on `oldTableId` so
      // this does not fire on initial load (null -> persisted table), which
      // would wipe saved fields before its table's fields have loaded.
      if (
        oldTableId !== null &&
        oldTableId !== undefined &&
        newTableId !== oldTableId
      ) {
        this.values.field_ids = []
      }
    },
  },
}
</script>
