<template>
  <RecursiveWrapper
    :components="
      wrapperDecorations.map((comp) => ({
        ...comp,
        props: comp.propsFn(row),
      }))
    "
    first-component-class="grid-view__row-background-wrapper"
  >
    <div
      class="grid-view__row"
      :class="{
        'grid-view__row--selected': isRowHighlighted(row),
        'grid-view__row--loading': row._.loading,
        'grid-view__row--hover': row._.hover,
        'grid-view__row--warning':
          !row._.matchFilters || !row._.matchSortings || !row._.matchSearch,
      }"
      @mouseover="$emit('row-hover', { row, value: true })"
      @mouseleave="$emit('row-hover', { row, value: false })"
      @contextmenu.prevent="$emit('row-context', { row, event: $event })"
    >
      <template v-if="includeRowDetails">
        <div
          v-if="
            !row._.matchFilters || !row._.matchSortings || !row._.matchSearch
          "
          class="grid-view__row-warning"
        >
          <template v-if="!row._.matchFilters">
            {{ $t('gridViewRow.rowNotMatchingFilters') }}
          </template>
          <template v-else-if="!row._.matchSearch">
            {{ $t('gridViewRow.rowNotMatchingSearch') }}
          </template>
          <template v-else-if="!row._.matchSortings">{{
            $t('gridViewRow.rowHasMoved')
          }}</template>
        </div>
        <div
          class="grid-view__column grid-view__column--no-border-right"
          :class="{ 'grid-view__column--group-end': groupEnd }"
          :style="{ width: gridViewRowDetailsWidth + 'px' }"
        >
          <div
            class="grid-view__row-info"
            :class="{
              'grid-view__row-info--matches-search':
                row._.matchSearch &&
                row._.fieldSearchMatches.includes('row_id'),
            }"
          >
            <div
              v-if="isCheckboxSelected(row.id) || row._.hover"
              class="grid-view__row-checkbox"
            >
              <Checkbox
                :checked="isCheckboxSelected(row.id)"
                :disabled="isCheckboxDisabled(row.id)"
                :size="'small'"
                @input="toggleRowCheckbox"
              ></Checkbox>
            </div>
            <div
              v-else
              class="grid-view__row-count"
              :class="{
                'grid-view__row-count--small': rowIdentifier > 9999,
                'grid-view__row-count--hide-on-hover': canDrag,
              }"
              :title="rowIdentifier"
            >
              <div class="grid-view__row-count-content">
                {{ rowIdentifier }}
              </div>
            </div>
            <div
              v-if="!readOnly && canDrag"
              class="grid-view__row-drag"
              @mousedown="startDragging($event, row)"
            ></div>
            <component
              :is="rowExpandButton"
              v-if="!row._.loading"
              :row="row"
              :workspace-id="workspaceId"
              :table="view.table"
              @edit-modal="$emit('edit-modal', row)"
            ></component>
            <component
              :is="dec.component"
              v-for="dec in firstCellDecorations"
              :key="dec.decoration.id"
              v-bind="dec.propsFn(row)"
            />
          </div>
        </div>
      </template>
      <!--
      Somehow re-declaring all the events instead of using v-on="$listeners" speeds
      everything up because the rows don't need to be updated everytime a new one is
      rendered, which happens a lot when scrolling.
      -->
      <GridViewCell
        v-for="field in fieldsToRender"
        :key="'row-field-' + row._.persistentId + '-' + field.id.toString()"
        :workspace-id="workspaceId"
        :field="field"
        :row="row"
        :all-fields-in-table="allFieldsInTable"
        :state="state"
        :multi-select-position="getMultiSelectPosition(row.id, field)"
        :read-only="readOnly || !canWriteFieldValues(field)"
        :store-prefix="storePrefix"
        :group-end="groupEnd"
        :style="{
          width: fieldWidths[field.id] + 'px',
          ...getSelectedCellStyle(field),
        }"
        @update="$emit('update', $event)"
        @paste="$emit('paste', $event)"
        @edit="$emit('edit', $event)"
        @select="$emit('select', $event)"
        @unselect="$emit('unselect', $event)"
        @selected="$emit('selected', $event)"
        @unselected="$emit('unselected', $event)"
        @select-next="$emit('select-next', $event)"
        @refresh-row="$emit('refresh-row', $event)"
        @cell-mousedown-left="$emit('cell-mousedown-left', { row, field })"
        @cell-mouseover="$emit('cell-mouseover', { row, field })"
        @cell-mouseup-left="$emit('cell-mouseup-left', { row, field })"
        @cell-shift-click="$emit('cell-shift-click', { row, field })"
        @add-row-after="$emit('add-row-after', $event)"
        @edit-modal="$emit('edit-modal', row)"
      ></GridViewCell>
    </div>
  </RecursiveWrapper>
</template>

<script>
import GridViewCell from '@baserow/modules/database/components/view/grid/GridViewCell'
import gridViewHelpers from '@baserow/modules/database/mixins/gridViewHelpers'
import GridViewRowExpandButton from '@baserow/modules/database/components/view/grid/GridViewRowExpandButton'
import RecursiveWrapper from '@baserow/modules/core/components/RecursiveWrapper'
import { GRID_VIEW_MULTI_SELECT_AREA } from '@baserow/modules/database/constants'

export default {
  name: 'GridViewRow',
  components: {
    GridViewRowExpandButton,
    GridViewCell,
    RecursiveWrapper,
  },
  mixins: [gridViewHelpers],
  provide() {
    return {
      $hasPermission: this.$hasPermission,
    }
  },
  props: {
    view: {
      type: Object,
      required: true,
    },
    workspaceId: {
      type: Number,
      required: true,
    },
    row: {
      type: Object,
      required: true,
    },
    groupEnd: {
      type: Boolean,
      required: false,
      default: () => false,
    },
    renderedFields: {
      type: Array,
      required: true,
    },
    decorationsByPlace: {
      type: Object,
      required: true,
    },
    visibleFields: {
      type: Array,
      required: true,
    },
    allFieldsInTable: {
      type: Array,
      required: true,
    },
    fieldWidths: {
      type: Object,
      required: true,
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
    readOnly: {
      type: Boolean,
      required: true,
    },
    canDrag: {
      type: Boolean,
      required: true,
    },
    rowIdentifierType: {
      type: String,
      required: true,
      default: 'count',
    },
    count: {
      type: Number,
      required: true,
    },
    primaryFieldIsSticky: {
      type: Boolean,
      required: false,
      default: () => true,
    },
  },
  data() {
    return {
      // The state can be used by functional components to make changes to the dom.
      // This is for example used by the functional file field component to enable the
      // drop effect without having the cell selected.
      state: {},
      // A list containing field id's of field cells that must not be converted to the
      // functional component even though the user has selected another cell. This is
      // for example used by the file field to finish the uploading task if the user
      // has selected another cell while uploading.
      alive: [],
      rowExpandButton: this.$registry
        .get('application', 'database')
        .getRowExpandButtonComponent(),
    }
  },
  computed: {
    /**
     * This component already accepts a `renderedFields` property containing the fields
     * that must be rendered based on the viewport width and horizontal scroll offset,
     * meaning it only renders the fields that are in the viewport. Because a selected
     * field must always be rendered, this computed property checks if there is a
     * selected field and if so, it's added to the array. This doesn't influence the
     * position of the other cells because the position will be absolute. The selected
     * field must always be rendered, otherwise the arrow keys and other functionality
     * won't work.
     */
    fieldsToRender() {
      // If the row doesn't have a selected field, we can safely return the fields
      // because we just want to render the fields inside of the view port.
      if (!this.row._.selected) {
        return this.renderedFields
      }

      // Check if the selected field exists in the all fields array, so not just the to
      // be rendered ones.
      const selectedField = this.visibleFields.find(
        (field) => field.id === this.row._.selectedFieldId
      )

      // If it doesn't exist or if it's already in the fields array, we don't have to
      // add it because it's already rendered.
      if (
        selectedField === undefined ||
        this.renderedFields.find((field) => field.id === selectedField.id) !==
          undefined
      ) {
        return this.renderedFields
      }

      // If the selected field exists in all fields, but not in fields it must be added
      // to the fields array because we want to render it. It won't influence the other
      // cells because it's positioned absolute.
      const fields = this.renderedFields.slice()
      fields.unshift(selectedField)
      return fields
    },
    firstCellDecorations() {
      return this.decorationsByPlace?.first_cell || []
    },
    wrapperDecorations() {
      return this.decorationsByPlace?.wrapper || []
    },
    rowIdentifier() {
      switch (this.rowIdentifierType) {
        case 'count':
          return this.count
        default:
          return this.row.id
      }
    },
  },
  methods: {
    isCheckboxDisabled(rowId) {
      const checkboxSelectedRows =
        this.$store.state[this.storePrefix + 'view/grid'].checkboxSelectedRows
      return (
        checkboxSelectedRows.length >=
          this.$config.BASEROW_ROW_PAGE_SIZE_LIMIT &&
        !checkboxSelectedRows.includes(rowId)
      )
    },
    isCheckboxSelected(rowId) {
      return this.$store.state[
        this.storePrefix + 'view/grid'
      ].checkboxSelectedRows.includes(rowId)
    },
    isRowHighlighted(row) {
      // const selectionType =
      //   this.$store.getters[this.storePrefix + 'view/grid/getSelectionType']
      return (
        // selectionType === GRID_VIEW_MULTI_SELECT_AREA &&
        row._.selectedBy.length > 0
      )
    },
    isCellSelected(fieldId) {
      return this.row._.selected && this.row._.selectedFieldId === fieldId
    },
    selectCell(fieldId, rowId = this.row.id) {
      this.$emit('cell-selected', { fieldId, rowId })
    },
    // Return an object that represents if a cell is selected,
    // and it's current position in the selection grid
    getMultiSelectPosition(rowId, field) {
      const position = {
        selected: false,
        top: false,
        right: false,
        bottom: false,
        left: false,
      }
      const selectionType =
        this.$store.getters[this.storePrefix + 'view/grid/getSelectionType']
      if (selectionType !== GRID_VIEW_MULTI_SELECT_AREA) {
        if (this.isCheckboxSelected(rowId)) {
          position.selected = true
        }
        return position
      }

      if (
        this.$store.getters[this.storePrefix + 'view/grid/isMultiSelectActive']
      ) {
        const rowIndex =
          this.$store.getters[this.storePrefix + 'view/grid/getRowIndexById'](
            rowId
          )

        const allFieldIds = this.visibleFields.map((field) => field.id)
        let fieldIndex = allFieldIds.findIndex((id) => field.id === id)
        fieldIndex += !field.primary && this.primaryFieldIsSticky ? 1 : 0

        const [minRow, maxRow] =
          this.$store.getters[
            this.storePrefix + 'view/grid/getMultiSelectRowIndexSorted'
          ]
        const [minField, maxField] =
          this.$store.getters[
            this.storePrefix + 'view/grid/getMultiSelectFieldIndexSorted'
          ]

        if (rowIndex >= minRow && rowIndex <= maxRow) {
          if (fieldIndex >= minField && fieldIndex <= maxField) {
            position.selected = true
            if (rowIndex === minRow) {
              position.top = true
            }
            if (rowIndex === maxRow) {
              position.bottom = true
            }
            if (fieldIndex === minField) {
              position.left = true
            }
            if (fieldIndex === maxField) {
              position.right = true
            }
          }
        }
      }
      return position
    },
    setState(value) {
      this.state = value
    },
    addKeepAlive(fieldId) {
      if (!this.alive.includes(fieldId)) {
        this.alive.push(fieldId)
      }
    },
    removeKeepAlive(fieldId) {
      const index = this.alive.findIndex((id) => id === fieldId)
      if (index > -1) {
        this.alive.splice(index, 1)
      }
    },
    startDragging(event, row) {
      if (this.readOnly) {
        return
      }

      event.preventDefault()
      this.$emit('row-dragging', { row, event })
    },
    /**
     * Returns an object with additional styling if the field is selected and outside
     * of the viewport. This is because selected fields must always be rendered because
     * otherwise certain functionality won't work.
     */
    getSelectedCellStyle(field) {
      const exists =
        this.renderedFields.find((f) => f.id === field.id) !== undefined

      // If the field already exists in the field list it means that it's already
      // rendered. In that case we don't have to provide any other styling because it's
      // already in the position it's supposed to be in.
      if (exists) {
        return {}
      }

      // If the field doesn't exist in the fields array, it's being rendered because
      // it's selected. In that case, the element must be positioned without influencing
      // the other cells.
      const styling = { position: 'absolute' }

      const selectedFieldIndex = this.visibleFields.findIndex(
        (field) => field.id === this.row._.selectedFieldId
      )
      const firstVisibleFieldIndex = this.visibleFields.findIndex(
        (field) => field.id === this.renderedFields[0].id
      )
      const lastVisibleFieldIndex = this.visibleFields.findIndex(
        (field) =>
          field.id === this.renderedFields[this.renderedFields.length - 1].id
      )

      // Positions the selected field cell on the right position without influencing the
      // position of the rendered cells. This is needed because other components depend
      // on the cell to be in the right position, for example when using the arrow key
      // navigation.
      if (selectedFieldIndex < firstVisibleFieldIndex) {
        // If the selected field must be positioned before the other fields
        let spaceBetween = 0
        for (let i = selectedFieldIndex; i < firstVisibleFieldIndex; i++) {
          spaceBetween += this.fieldWidths[this.visibleFields[i].id]
        }
        styling.left = -spaceBetween + 'px'
      } else if (selectedFieldIndex > lastVisibleFieldIndex) {
        // If the selected field must be positioned after the other fields.
        let spaceBetween = 0
        for (let i = lastVisibleFieldIndex; i < selectedFieldIndex; i++) {
          spaceBetween += this.fieldWidths[this.visibleFields[i].id]
        }
        styling.right = -spaceBetween + 'px'
      }

      return styling
    },
    canWriteFieldValues(field) {
      return this.$registry.get('field', field.type).canWriteFieldValues(field)
    },
    toggleRowCheckbox() {
      this.$store.dispatch(
        this.storePrefix + 'view/grid/toggleCheckboxRowSelection',
        { row: this.row }
      )
    },
  },
}
</script>
