<template>
  <form @submit.prevent="submit">
    <ul class="row-modal__field-list margin-bottom-0">
      <li
        v-for="field in fields"
        :key="'row-edit-field-' + field.id"
        class="row-modal__field-item"
      >
        <DefaultRowValueField
          :ref="'field-' + field.id"
          :field="field"
          :hidden="false"
          :read-only="readOnly"
          :row="row"
          :view="view"
          :table="table"
          :database="database"
          :all-fields-in-table="allFieldsInTable"
          :view-default-values="viewDefaultValues"
          @update="updateField($event)"
        />
      </li>
    </ul>
    <slot></slot>
  </form>
</template>

<script>
import form from '@baserow/modules/core/mixins/form'
import DefaultRowValueField from '@baserow/modules/database/components/view/DefaultRowValueField'

export default {
  name: 'DefaultRowValuesForm',
  components: {
    DefaultRowValueField,
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
    row: {
      type: Object,
      required: true,
    },
    viewDefaultValues: {
      type: Object,
      required: true,
    },
  },
  data() {
    return {
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
