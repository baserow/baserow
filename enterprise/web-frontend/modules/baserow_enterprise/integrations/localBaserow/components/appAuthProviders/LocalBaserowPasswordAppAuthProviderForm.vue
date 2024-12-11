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
        :disabled="!selectedTable"
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

export default {
  mixins: [authProviderForm],
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
    fields() {
      if (!this.selectedTable) {
        return []
      } else {
        return this.selectedTable.fields
      }
    },
    passwordFields() {
      return this.fields.filter(({ type }) =>
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
    getIconForType(type) {
      return this.fieldTypes[type].getIconClass()
    },
  },
}
</script>
