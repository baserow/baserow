<template>
  <!--
    The :key property must be set here because it makes sure that the child components
    are not re-rendered when functional component changes position in the DOM.
  -->
  <div
    :key="cellKey"
    ref="wrapper"
    class="grid-view__column"
    :class="columnClass"
    v-bind="$attrs"
    @click.exact="select($event, field.id)"
    @mousedown.left="cellMouseDownLeft($event)"
    @mouseover="cellMouseover($event)"
    @mouseup.left="cellMouseUpLeft($event)"
    @click.shift.exact="cellShiftClick($event)"
  >
    <component
      :is="getFunctionalComponent()"
      v-if="!isSelected && !isAlive"
      ref="unselectedField"
      :workspace-id="workspaceId"
      :row="row"
      :field="field"
      :value="fieldValue"
      :state="state"
      :read-only="readOnly"
      :store-prefix="storePrefix"
    />
    <component
      :is="getComponent()"
      v-else
      ref="selectedField"
      :workspace-id="workspaceId"
      :field="field"
      :value="fieldValue"
      :selected="isSelected"
      :store-prefix="storePrefix"
      :read-only="readOnly"
      :row="row"
      :all-fields-in-table="allFieldsInTable"
      @update="update"
      @paste="paste"
      @edit="edit"
      @refresh-row="refreshRow"
      @unselect="unselect"
      @selected="selected"
      @unselected="unselected"
      @select-previous="() => selectNext('previous')"
      @select-next="() => selectNext('next')"
      @select-above="() => selectNext('above')"
      @select-below="() => selectNext('below')"
      @add-row-after="addRowAfter"
      @add-keep-alive="addKeepAlive"
      @remove-keep-alive="removeKeepAlive"
      @edit-modal="editModal"
    />
  </div>
</template>

<script>
export default {
  inheritAttrs: false,
  props: {
    workspaceId: {
      type: null,
      required: true,
    },
    row: {
      type: Object,
      required: true,
    },
    field: {
      type: Object,
      required: true,
    },
    state: {
      type: Object,
      required: true,
    },
    readOnly: {
      type: Boolean,
      default: false,
    },
    storePrefix: {
      type: String,
      default: '',
    },
    multiSelectPosition: {
      type: Object,
      required: true,
    },
    groupEnd: {
      type: Boolean,
      default: false,
    },
    allFieldsInTable: {
      type: Array,
      required: true,
    },
    isSelected: {
      type: Boolean,
      required: false,
      default: false,
    },
    isAlive: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  emits: [
    'update',
    'paste',
    'edit',
    'cell-mousedown-left',
    'cell-mouseover',
    'cell-mouseup-left',
    'cell-shift-click',
    'selected',
    'unselected',
    'select-cell',
    'select-next',
    'add-row-after',
    'edit-modal',
    'refresh-row',
  ],
  computed: {
    cellKey() {
      return `row-field-cell-${this.row._.persistentId}-${this.field.id}`
    },
    columnClass() {
      return {
        'grid-view__column--matches-search':
          this.row._.matchSearch &&
          this.row._.fieldSearchMatches.includes(this.field.id.toString()),
        'grid-view__column--multi-select': this.multiSelectPosition.selected,
        'grid-view__column--multi-select-top': this.multiSelectPosition.top,
        'grid-view__column--multi-select-right': this.multiSelectPosition.right,
        'grid-view__column--multi-select-left': this.multiSelectPosition.left,
        'grid-view__column--multi-select-bottom':
          this.multiSelectPosition.bottom,
        'grid-view__column--group-end': this.groupEnd,
      }
    },
    fieldValue() {
      return this.row[`field_${this.field.id}`]
    },
  },
  methods: {
    getFunctionalComponent() {
      return this.$registry
        .get('field', this.field.type)
        .getFunctionalGridViewFieldComponent(this.field)
    },
    getComponent() {
      return this.$registry
        .get('field', this.field.type)
        .getGridViewFieldComponent(this.field)
    },
    update(value, oldValue) {
      this.$emit('update', {
        row: this.row,
        field: this.field,
        value,
        oldValue,
      })
    },
    paste(event) {
      this.$emit('paste', {
        data: event,
        row: this.row,
        field: this.field,
      })
    },
    edit(value, oldValue) {
      this.$emit('edit', {
        row: this.row,
        field: this.field,
        value,
        oldValue,
      })
    },
    select(event, fieldId) {
      event.preventFieldCellUnselect = true
      this.$emit('select-cell', fieldId)
    },
    cellMouseDownLeft(event) {
      if (!event.shiftKey) {
        this.$emit('cell-mousedown-left')
      }
    },
    cellMouseover() {
      this.$emit('cell-mouseover')
    },
    cellMouseUpLeft() {
      this.$emit('cell-mouseup-left')
    },
    cellShiftClick() {
      this.$emit('cell-shift-click')
    },
    unselect() {
      if (this.isSelected) {
        this.$emit('select-cell', -1, -1)
      }
    },
    selected(event) {
      const payload = event ? { ...event } : {}
      this.$emit('selected', { ...payload, row: this.row, field: this.field })
    },
    unselected(event) {
      const payload = event ? { ...event } : {}
      this.$emit('unselected', {
        ...payload,
        row: this.row,
        field: this.field,
      })
    },
    selectNext(direction) {
      this.$emit('select-next', {
        row: this.row,
        field: this.field,
        direction,
      })
    },
    addRowAfter() {
      this.$emit('add-row-after', this.row)
    },
    editModal() {
      this.$emit('edit-modal')
    },
    refreshRow() {
      this.$emit('refresh-row', this.row)
    },
    addKeepAlive() {
      this.addKeepAlive(this.field.id)
      /*if (this.parent) {
        this.parent.addKeepAlive(this.field.id)
      }*/
    },
    removeKeepAlive() {
      this.removeKeepAlive(this.field.id)
      /*if (this.parent) {
        this.parent.removeKeepAlive(this.field.id)
      }*/
    },
  },
}
</script>
