<template>
  <form>
    <FormGroup
      :label="$t('localBaserowPasswordAppAuthProviderForm.passwordFieldLabel')"
      small-label
      horizontal
      horizontal-variable
      required
    >
      <Dropdown
        v-model="values.password_field_id"
        fixed-items
        :disabled="!selectedTable || fieldsLoading"
        :placeholder="
          $t('localBaserowPasswordAppAuthProviderForm.passwordFieldLabel')
        "
      >
        <DropdownItem
          v-for="field in passwordFields"
          :key="field.id"
          :name="field.name"
          :value="field.id"
          :icon="getIconForType(field.type)"
        />
        <template #emptyState>
          {{ $t('localBaserowPasswordAppAuthProviderForm.noFields') }}
        </template>
      </Dropdown>
    </FormGroup>
  </form>
</template>

<script>
import authProviderForm from '@baserow/modules/core/mixins/authProviderForm'
import tableFields from '@baserow/modules/database/mixins/tableFields'

export default {
  mixins: [authProviderForm, tableFields],
  props: {
    integration: {
      type: Object,
      required: true,
    },
    userSource: {
      type: Object,
      required: true,
    },
  },
  data() {
    return {
      values: {
        password_field_id: null,
      },
      allowedValues: ['password_field_id'],
    }
  },
  computed: {
    databases() {
      return this.integration.context_data.databases
    },
    fieldTypes() {
      return this.$registry.getAll('field')
    },
    selectedTable() {
      if (!this.userSource.table_id) {
        return null
      }
      for (const database of this.databases) {
        for (const table of database.tables) {
          if (table.id === this.userSource.table_id) {
            return table
          }
        }
      }
      return null
    },
    passwordFields() {
      return this.tableFields.filter(({ type }) =>
        this.authProviderType.allowedPasswordFieldTypes.includes(type)
      )
    },
  },
  watch: {
    'userSource.table_id'() {
      this.values.password_field_id = null
    },
  },
  methods: {
    /* Overrides the method in the tableFields mixin */
    getTableId() {
      return this.userSource.table_id
    },
    getIconForType(type) {
      return this.fieldTypes[type].getIconClass()
    },
  },
}
</script>
