<template>
  <div class="control">
    <label class="control__label control__label--small">
      <a
        :class="{ 'row-modal__field-item-handle': sortable }"
        data-field-handle
      ></a>
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
      <i
        v-if="!readOnly && canModifyFields"
        ref="contextLink"
        class="control__context baserow-icon-more-vertical"
        @click="$refs.context.toggle($refs.contextLink, 'bottom', 'left', 0)"
      ></i>
    </label>
    <FieldContext
      ref="context"
      :database="database"
      :table="table"
      :view="view"
      :field="field"
      :all-fields-in-table="allFieldsInTable"
      @update="$emit('field-updated', $event)"
      @delete="$emit('field-deleted')"
    >
      <li v-if="canBeHidden" class="context__menu-item">
        <a
          class="context__menu-item-link"
          @click="$emit('toggle-field-visibility', { field })"
        >
          <i
            class="context__menu-item-icon"
            :class="[hidden ? 'iconoir-eye-empty' : 'iconoir-eye-off']"
          ></i>
          {{ $t(hidden ? 'fieldContext.showField' : 'fieldContext.hideField') }}
        </a>
      </li>
    </FieldContext>
    <component
      :is="getFieldComponent(field.type)"
      ref="field"
      :workspace-id="database.workspace.id"
      :field="field"
      :value="row['field_' + field.id]"
      :read-only="readOnly || isReadOnlyField(field)"
      :row-is-created="!!row.id"
      :row="row"
      :all-fields-in-table="allFieldsInTable"
      @update="update"
      @refresh-row="$emit('refresh-row', row)"
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
    sortable: {
      type: Boolean,
      default: false,
    },
    canModifyFields: {
      type: Boolean,
      required: false,
      default: true,
    },
    canBeHidden: {
      type: Boolean,
      required: false,
      default: true,
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
    rowIsCreated: {
      type: Boolean,
      required: false,
      default: () => true,
    },
  },
  methods: {
    isReadOnlyField(field) {
      return !this.$registry.get('field', field.type).canWriteFieldValues(field)
    },
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
