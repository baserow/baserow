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
      :error="v$.through_field_id.$error"
    >
      <Dropdown
        v-model="v$.through_field_id.$model"
        :error="v$.through_field_id.$error"
        :fixed-items="true"
        @hide="v$.through_field_id.$touch"
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

      <template #error>{{ $t('error.requiredField') }}</template>
    </FormGroup>
  </div>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import { reactive, computed } from 'vue'
import { required } from '@vuelidate/validators'

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
  data() {
    return {
      allowedValues: ['through_field_id'],
      values: null,
      v$: null,
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
    const values = reactive({
      through_field_id: null,
    })

    const rules = computed(() => ({
      through_field_id: { required },
    }))

    this.v$ = useVuelidate(rules, values, { $lazy: true })
    this.values = values
    this.throughFieldChanged(this.defaultValues.through_field_id)
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
