<template>
  <div class="control">
    <label class="control__label control__label--small">
      <i :class="field._.type.iconClass"></i>
      {{ field.name }}
      <span v-if="field.description" class="margin-left-1">
        <HelpIcon
          :tooltip="field.description || ''"
          :tooltip-content-type="'plain'"
          :tooltip-content-classes="[
            'tooltip__content--expandable',
            'tooltip__content--expandable-plain-text',
          ]"
          :icon="'info-empty'"
          :tooltip-duration="0.2"
        />
      </span>
    </label>
    <component
      :is="getFieldComponent(field.type)"
      v-if="hasDefaultValueSet"
      ref="field"
      :workspace-id="database.workspace.id"
      :field="field"
      :value="row['field_' + field.id]"
      :read-only="readOnly"
      :row-is-created="false"
      :row="row"
      :all-fields-in-table="allFieldsInTable"
      @update="update"
    />
  </div>
</template>

<script>
import FieldContext from '@baserow/modules/database/components/field/FieldContext'

export default {
  name: 'RowEditModalField',
  components: { FieldContext },
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
    field: {
      type: Object,
      required: true,
    },
    hidden: {
      type: Boolean,
      required: false,
      default: false,
    },
    row: {
      type: Object,
      required: true,
    },
    readOnly: {
      type: Boolean,
      required: true,
    },
    allFieldsInTable: {
      type: Array,
      required: true,
    },
    viewDefaultValues: {
      type: Object,
      required: true,
    },
  },
  emits: [
    'update',
  ],
  computed: {
    hasDefaultValueSet() {
      return !!Object.hasOwn(this.viewDefaultValues, this.field.id)
    },
  },
  methods: {
    getFieldComponent(type) {
      return this.$registry
        .get('field', type)
        .getRowEditFieldComponent(this.field)
    },
    update(value, oldValue) {
      this.$emit('update', {
        row: this.row,
        field: this.field,
        value,
        oldValue,
      })
    },
  },
}
</script>
