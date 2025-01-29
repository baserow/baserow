<template>
  <div
    v-if="
      loading || (fieldsInThroughTable.length > 0 && isSelectedFieldAccessible)
    "
  >
    <div v-if="loading" class="context--loading">
      <div class="loading"></div>
    </div>

    <FormGroup
      v-else-if="fieldsInThroughTable.length > 0 && isSelectedFieldAccessible"
      :label="label"
      small-label
      required
      :error="fieldHasErrors('target_field_id')"
    >
      <Dropdown
        v-model="v$.values.target_field_id.$model"
        :error="fieldHasErrors('target_field_id')"
        :fixed-items="true"
        @hide="v$.values.target_field_id.$touch"
        @input="targetFieldChanged($event)"
      >
        <DropdownItem
          v-for="field in fieldsInThroughTable"
          :key="field.id"
          :name="field.name"
          :value="field.id"
          :icon="field.icon"
        ></DropdownItem>
      </Dropdown>

      <template #error>
        {{ v$.values.target_field_id.$errors[0]?.$message }}</template
      >
    </FormGroup>
  </div>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import { required, helpers } from '@vuelidate/validators'

import form from '@baserow/modules/core/mixins/form'
import FieldService from '@baserow/modules/database/services/field'
import { notifyIf } from '@baserow/modules/core/utils/error'

export default {
  name: 'FieldSelectTargetFieldSubForm',
  mixins: [form],
  props: {
    database: {
      type: Object,
      required: true,
    },
    table: {
      type: Object,
      required: true,
    },
    throughField: {
      validator: (prop) => typeof prop === 'object' || prop === null,
      required: false,
      default: null,
    },
    label: {
      type: String,
      required: true,
    },
  },
  setup() {
    return { v$: useVuelidate({ $lazy: true }) }
  },
  data() {
    return {
      allowedValues: ['target_field_id'],
      values: {
        target_field_id: null,
      },
      loading: false,
      fieldsInThroughTable: [],
    }
  },
  computed: {
    linkedToTable() {
      return this.database.tables.find(
        (table) => table.id === this.throughField?.link_row_table_id
      )
    },
    isSelectedFieldAccessible() {
      return (
        this.linkedToTable &&
        this.$hasPermission(
          'database.table.create_field',
          this.linkedToTable,
          this.database.workspace.id
        )
      )
    },
  },
  watch: {
    throughField(value) {
      this.throughFieldChanged(value)
    },
  },
  methods: {
    async fetchFields() {
      this.loading = true

      try {
        const { data } = await FieldService(this.$client).fetchAll(
          this.throughField.link_row_table_id
        )
        this.fieldsInThroughTable = data
          .filter((f) => {
            // Filter out any links back to this table as it is a lookup back to
            // ourselve and hence would always cause a circular reference.
            return this.table.id !== f.link_row_table_id
          })
          .filter((f) => {
            return this.$registry
              .get('field', f.type)
              .canBeReferencedByFormulaField(f)
          })
          .filter((f) => {
            return this.$hasPermission(
              'database.table.field.update',
              f,
              this.database.workspace.id
            )
          })
          .map((f) => {
            const fieldType = this.$registry.get('field', f.type)
            f.icon = fieldType.getIconClass()
            return f
          })
      } catch (error) {
        notifyIf(error, 'view')
      }

      this.loading = false
    },
    async throughFieldChanged(value) {
      this.fieldsInThroughTable = []

      if (value === null) {
        this.values.target_field_id = null
        this.loading = false
        return
      }

      await this.fetchFields()
      this.targetFieldChanged(this.values.target_field_id)
    },
    targetFieldChanged(fieldId) {
      const field = this.fieldsInThroughTable.find((f) => f.id === fieldId)
      if (field === undefined) {
        this.values.target_field_id = null
        this.$emit('input', null)
      } else {
        this.$emit('input', field)
      }
    },
  },
  validations() {
    return {
      values: {
        target_field_id: {
          required: helpers.withMessage(
            this.$t('error.requiredField'),
            required
          ),
        },
      },
    }
  },
}
</script>
