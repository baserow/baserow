<template>
  <form @submit.prevent="submit">
    <ul class="row-modal__field-list margin-bottom-0">
      <li
        v-for="field in fields"
        :key="'row-edit-field-' + field.id"
        class="row-modal__field-item"
      >
        <RowEditModalField
          :ref="'field-' + field.id"
          :field="field"
          :can-be-hidden="false"
          :hidden="false"
          :read-only="readOnly"
          :row="values"
          :view="view"
          :table="table"
          :database="database"
          :sortable="false"
          :can-modify-fields="false"
          :all-fields-in-table="allFieldsInTable"
          @update="updateField($event)"
        />
      </li>
    </ul>
    <slot></slot>
  </form>
</template>

<script>
import form from '@baserow/modules/core/mixins/form'
import RowEditModalField from '@baserow/modules/database/components/row/RowEditModalField'

export default {
  name: 'DefaultRowValuesForm',
  components: {
    RowEditModalField,
  },
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
    view: {
      type: [Object, null],
      required: false,
      default: null,
    },
    fields: {
      type: Array,
      required: true,
    },
    allFieldsInTable: {
      type: Array,
      required: true,
    },
    readOnly: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  data() {
    return {
      allowedValues: null,
      values: {},
    }
  },
  methods: {
    updateField({ field, value }) {
      this.values[`field_${field.id}`] = value
    },
  },
}
</script>
