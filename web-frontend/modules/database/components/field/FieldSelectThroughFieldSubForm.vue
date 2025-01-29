<template>
  <div class="context__form-container">
    <Alert v-if="linkRowFieldsInThisTable.length === 0" type="error">
      <p>{{ $t('fieldSelectThroughFieldSubForm.noTable') }}</p>
    </Alert>

    <FormGroup
      v-if="linkRowFieldsInThisTable.length > 0"
      small-label
      :label="$t('fieldSelectThroughFieldSubForm.selectThroughFieldLabel')"
      required
      :error="fieldHasErrors('through_field_id')"
    >
      <Dropdown
        v-model="v$.values.through_field_id.$model"
        :error="fieldHasErrors('through_field_id')"
        :fixed-items="true"
        @hide="v$.values.through_field_id.$touch"
        @input="throughFieldChanged($event)"
      >
        <DropdownItem
          v-for="field in linkRowFieldsInThisTable"
          :key="field.id"
          :disabled="field.disabled"
          :name="field.name"
          :value="field.id"
          :icon="field.icon"
        ></DropdownItem>
      </Dropdown>

      <template #error>{{
        v$.values.through_field_id.$errors[0]?.$message
      }}</template>
    </FormGroup>
  </div>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import { required, helpers } from '@vuelidate/validators'

import form from '@baserow/modules/core/mixins/form'
import { LinkRowFieldType } from '@baserow/modules/database/fieldTypes'
import { DatabaseApplicationType } from '@baserow/modules/database/applicationTypes'

export default {
  name: 'FieldSelectThroughFieldSubForm',
  mixins: [form],
  props: {
    database: {
      type: Object,
      required: true,
    },
    fields: {
      type: Array,
      required: true,
    },
  },
  setup() {
    return { v$: useVuelidate({ $lazy: true }) }
  },
  data() {
    return {
      allowedValues: ['through_field_id'],
      values: {
        through_field_id: null,
      },
    }
  },
  computed: {
    linkRowFieldsInThisTable() {
      return this.fields
        .filter((f) => f.type === LinkRowFieldType.getType())
        .map((f) => {
          const fieldType = this.$registry.get('field', f.type)
          f.icon = fieldType.getIconClass()
          f.disabled = !this.tableIdsAccessible.includes(f.link_row_table_id)
          return f
        })
    },
    allTables() {
      const databaseType = DatabaseApplicationType.getType()
      return this.$store.getters['application/getAll'].reduce(
        (tables, application) => {
          if (application.type === databaseType) {
            const tablesWithCreateFieldAccess = (
              application.tables || []
            ).filter((table) =>
              this.$hasPermission(
                'database.table.create_field',
                table,
                this.database.workspace.id
              )
            )
            return tables.concat(tablesWithCreateFieldAccess)
          }
          return tables
        },
        []
      )
    },
    tableIdsAccessible() {
      return this.allTables.map((table) => table.id)
    },
  },
  watch: {
    'defaultValues.through_field_id'(value) {
      this.throughFieldChanged(value)
    },
  },
  created() {
    this.throughFieldChanged(this.defaultValues.through_field_id)
  },
  validations() {
    return {
      values: {
        through_field_id: {
          required: helpers.withMessage(
            this.$t('error.requiredField'),
            required
          ),
        },
      },
    }
  },
  methods: {
    isFormValid() {
      return (
        form.methods.isFormValid.call(this) &&
        this.linkRowFieldsInThisTable.length > 0
      )
    },
    throughFieldChanged(fieldId) {
      const field = this.linkRowFieldsInThisTable.find((f) => f.id === fieldId)
      this.$emit('input', field)
    },
  },
}
</script>
