<template>
  <form>
    <LocalBaserowTableSelector
      v-model="computedTableId"
      class="local-baserow-user-source-form__table-selector"
      :service-type="userSourceType"
      :databases="integration.context_data.databases"
      :display-view-dropdown="false"
      dropdown-size="large"
    />

    <p>{{ $t('localBaserowUserSourceForm.description') }}</p>
    <FormRow class="margin-bottom-2">
      <FormGroup
        :label="$t('localBaserowUserSourceForm.emailFieldLabel')"
        small-label
        required
      >
        <Dropdown
          v-model="values.email_field_id"
          fixed-items
          :disabled="!selectedTable || fieldsLoading"
          :placeholder="
            $t('localBaserowUserSourceForm.emailFieldLabelPlaceholder')
          "
          size="large"
        >
          <DropdownItem
            v-for="field in emailFields"
            :key="field.id"
            :name="field.name"
            :value="field.id"
            :icon="getIconForType(field.type)"
          />
          <template #emptyState>
            {{ $t('localBaserowUserSourceForm.noFields') }}
          </template>
        </Dropdown>
      </FormGroup>

      <FormGroup
        :label="$t('localBaserowUserSourceForm.nameFieldLabel')"
        small-label
        required
      >
        <Dropdown
          v-model="values.name_field_id"
          fixed-items
          :disabled="!selectedTable || fieldsLoading"
          :placeholder="$t('localBaserowUserSourceForm.nameFieldPlaceholder')"
          size="large"
        >
          <DropdownItem
            v-for="field in nameFields"
            :key="field.id"
            :name="field.name"
            :value="field.id"
            :icon="getIconForType(field.type)"
          />
          <template #emptyState>
            {{ $t('localBaserowUserSourceForm.noFields') }}
          </template>
        </Dropdown>
      </FormGroup>

      <FormGroup
        :label="$t('localBaserowUserSourceForm.roleFieldLabel')"
        small-label
        required
      >
        <Dropdown
          v-model="values.role_field_id"
          fixed-items
          :disabled="!selectedTable || fieldsLoading"
          :placeholder="$t('localBaserowUserSourceForm.roleFieldPlaceholder')"
          size="large"
        >
          <DropdownItem
            key="use-default-role"
            name="Use Default Role"
            :value="null"
            icon="iconoir-user"
          />
          <DropdownItem
            v-for="field in roleFields"
            :key="field.id"
            :name="field.name"
            :value="field.id"
            :icon="getIconForType(field.type)"
          />
          <template #emptyState>
            {{ $t('localBaserowUserSourceForm.noFields') }}
          </template>
        </Dropdown>
      </FormGroup>
    </FormRow>
  </form>
</template>

<script>
import form from '@baserow/modules/core/mixins/form'
import LocalBaserowTableSelector from '@baserow/modules/integrations/localBaserow/components/services/LocalBaserowTableSelector'
import tableFields from '@baserow/modules/database/mixins/tableFields'

export default {
  components: {
    LocalBaserowTableSelector,
  },
  mixins: [form, tableFields],
  props: {
    application: {
      type: Object,
      required: true,
    },
    integration: {
      type: Object,
      required: true,
    },
  },
  data() {
    return {
      values: {
        table_id: null,
        email_field_id: null,
        name_field_id: null,
        role_field_id: null,
      },
      allowedValues: [
        'table_id',
        'email_field_id',
        'name_field_id',
        'role_field_id',
      ],
    }
  },
  computed: {
    userSourceType() {
      return this.$registry.get('userSource', 'local_baserow')
    },
    databases() {
      return this.integration.context_data.databases
    },
    fieldTypes() {
      return this.$registry.getAll('field')
    },
    computedTableId: {
      get() {
        return this.values.table_id
      },
      set(newValue) {
        // If we currently have a `table_id` selected, and the `newValue`
        // is different to the current `table_id`, then reset the `fields`
        // to null.
        if (this.values.table_id && this.values.table_id !== newValue) {
          this.values.email_field_id = null
          this.values.name_field_id = null
          this.values.role_field_id = null
        }
        this.values.table_id = newValue
      },
    },
    selectedTable() {
      if (!this.values.table_id) {
        return null
      }
      for (const database of this.databases) {
        for (const table of database.tables) {
          if (table.id === this.values.table_id) {
            return table
          }
        }
      }
      return null
    },
    emailFields() {
      return this.tableFields.filter(({ type }) =>
        this.userSourceType.allowedEmailFieldTypes.includes(type)
      )
    },
    nameFields() {
      return this.tableFields.filter(({ type }) =>
        this.userSourceType.allowedNameFieldTypes.includes(type)
      )
    },
    roleFields() {
      return this.tableFields.filter(({ type }) =>
        this.userSourceType.allowedRoleFieldTypes.includes(type)
      )
    },
  },
  methods: {
    /* Overrides the method in the tableFields mixin */
    getTableId() {
      return this.values.table_id
    },
    getIconForType(type) {
      return this.fieldTypes[type].getIconClass()
    },
  },
}
</script>
