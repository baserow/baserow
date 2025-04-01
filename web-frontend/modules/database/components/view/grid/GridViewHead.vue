<template>
  <div class="grid-view__head">
    <div
      v-for="groupBy in includeGroupBy ? activeGroupBys : []"
      :key="'field-group-' + groupBy.field"
      class="grid-view__head-group"
      :style="{ width: groupBy.width + 'px' }"
      :set="(field = $options.methods.getField(allFieldsInTable, groupBy))"
    >
      <div class="grid-view__group-cell">
        <div class="grid-view__group-name">
          {{ field.name }}
        </div>
      </div>
    </div>
    <div
      v-if="includeRowDetails"
      class="grid-view__column grid-view__column--no-border-right"
      :style="{ width: gridViewRowDetailsWidth + 'px' }"
    >
      <GridViewRowIdentifierDropdown
        v-if="
          !readOnly &&
          $hasPermission(
            'database.table.view.update',
            view,
            database.workspace.id
          )
        "
        :row-identifier-type-selected="view.row_identifier_type"
        @change="onChangeIdentifierDropdown"
      ></GridViewRowIdentifierDropdown>
    </div>
    <GridViewFieldType
      v-for="field in visibleFields"
      :key="'field-type-' + field.id"
      :database="database"
      :table="table"
      :view="view"
      :field="field"
      :all-fields-in-table="allFieldsInTable"
      :filters="view.filters"
      :include-field-width-handles="includeFieldWidthHandles"
      :read-only="readOnly"
      :store-prefix="storePrefix"
      @refresh="$emit('refresh', $event)"
      @dragging="$emit('dragging', $event)"
      @field-created="$emit('field-created', $event)"
      @move-field="moveField"
    ></GridViewFieldType>
    <div
      v-if="
        includeAddField &&
        !readOnly &&
        $hasPermission(
          'database.table.create_field',
          table,
          database.workspace.id
        )
      "
      class="grid-view__column"
      :style="{ width: 100 + 'px' }"
    >
      <a
        ref="createFieldContextLink"
        class="grid-view__add-column"
        data-highlight="add-field"
        @click="$refs.createFieldContext.toggle($refs.createFieldContextLink)"
      >
        <i class="grid-view__add-column-icon iconoir-plus"></i>
      </a>
      <CreateFieldContext
        ref="createFieldContext"
        :table="table"
        :view="view"
        :all-fields-in-table="allFieldsInTable"
        :database="database"
        @field-created="$emit('field-created', $event)"
        @field-created-callback-done="afterFieldCreatedUpdateFieldOptions"
        @shown="onShownCreateFieldContext"
      ></CreateFieldContext>
    </div>
  </div>
</template>

<script>
import { notifyIf } from '@baserow/modules/core/utils/error'
import CreateFieldContext from '@baserow/modules/database/components/field/CreateFieldContext'
import GridViewFieldType from '@baserow/modules/database/components/view/grid/GridViewFieldType'
import gridViewHelpers from '@baserow/modules/database/mixins/gridViewHelpers'
import viewHelpers from '@baserow/modules/database/mixins/viewHelpers'
import GridViewRowIdentifierDropdown from '@baserow/modules/database/components/view/grid/GridViewRowIdentifierDropdown'

export default {
  name: 'GridViewHead',
  components: {
    GridViewRowIdentifierDropdown,
    GridViewFieldType,
    CreateFieldContext,
  },
  mixins: [gridViewHelpers, viewHelpers],
  props: {
    visibleFields: {
      type: Array,
      required: true,
    },
    database: {
      type: Object,
      required: true,
    },
    table: {
      type: Object,
      required: true,
    },
    view: {
      type: Object,
      required: true,
    },
    allFieldsInTable: {
      type: Array,
      required: true,
    },
    includeFieldWidthHandles: {
      type: Boolean,
      required: false,
      default: () => false,
    },
    includeRowDetails: {
      type: Boolean,
      required: false,
      default: () => false,
    },
    includeGroupBy: {
      type: Boolean,
      required: false,
      default: () => false,
    },
    includeAddField: {
      type: Boolean,
      required: false,
      default: () => false,
    },
    includeGridViewIdentifierDropdown: {
      type: Boolean,
      required: false,
      default: () => false,
    },
    readOnly: {
      type: Boolean,
      required: true,
    },
  },
  methods: {
    /**
     * After newField is created pressing "insert left" or "insert right" button,
     * we need to move the newField into the correct order position.
     * Also necessary when we duplicate a field.
     * This function move the field thanks to the store.
     **/
    async moveField({
      position,
      newField,
      fromField,
      undoRedoActionGroupId = null,
    }) {
      try {
        await this.$store.dispatch(
          `${this.storePrefix}view/grid/updateSingleFieldOptionOrder`,
          {
            fieldToMove: newField,
            position,
            fromField,
            undoRedoActionGroupId,
            readOnly: this.readOnly,
          }
        )
      } catch (error) {
        notifyIf(error, 'view')
      }
    },
    async onChangeIdentifierDropdown(rowIdentifierType) {
      try {
        await this.$store.dispatch('view/update', {
          view: this.view,
          values: { row_identifier_type: rowIdentifierType },
        })
      } catch (error) {
        notifyIf(error, 'view')
      }
    },
    onShownCreateFieldContext() {
      this.$refs.createFieldContext.showFieldTypesDropdown(this.$el)
    },
    getField(allFieldsInTable, groupBy) {
      const field = allFieldsInTable.find((f) => f.id === groupBy.field)
      return field
    },
  },
}
</script>
