<template>
  <div
    v-scroll="scroll"
    class="grid-view"
    :class="[
      {
        'grid-view--disable-selection': isMultiSelectActive,
      },
      'grid-view--row-height-' + view.row_height_size,
    ]"
  >
    <Scrollbars
      ref="scrollbars"
      horizontal="getHorizontalScrollbarElement"
      vertical="getVerticalScrollbarElement"
      :style="{ left: leftWidth + 'px' }"
      @vertical="verticalScroll"
      @horizontal="horizontalScroll"
    ></Scrollbars>
    <GridViewSection
      ref="left"
      class="grid-view__left"
      :visible-fields="leftFields"
      :all-fields-in-table="fields"
      :decorations-by-place="decorationsByPlace"
      :database="database"
      :table="table"
      :view="view"
      :include-field-width-handles="false"
      :include-row-details="!viewHasGroupBys"
      :include-grid-view-identifier-dropdown="!viewHasGroupBys"
      :include-group-by="true"
      :read-only="
        readOnly ||
        (!$hasPermission(
          'database.table.update_row',
          table,
          database.workspace.id
        ) &&
          !$hasPermission(
            'database.table.view.update_row',
            view,
            database.workspace.id
          ))
      "
      :store-prefix="storePrefix"
      :style="{ width: leftWidth + 'px' }"
      @refresh="$emit('refresh', $event)"
      @field-created="fieldCreated"
      @row-hover="setRowHover($event.row, $event.value)"
      @row-context="showRowContext($event.event, $event.row)"
      @row-dragging="rowDragStart"
      @row-select="handleRowSelect"
      @cell-mousedown-left="multiSelectStart"
      @cell-mouseover="multiSelectHold"
      @cell-mouseup-left="multiSelectStop"
      @cell-shift-click="multiSelectShiftClick"
      @add-row="addRow()"
      @add-rows="$refs.rowsAddContext.toggleNextToMouse($event)"
      @add-row-after="addRowAfter($event)"
      @update="updateValue"
      @paste="multiplePasteFromCell"
      @edit="editValue"
      @selected="selectedCell"
      @unselected="unselectedCell"
      @select-next="selectNextCell"
      @edit-modal="openRowEditModal($event)"
      @refresh-row="refreshRow"
      @scroll="scroll($event.pixelY, 0)"
      @cell-selected="cellSelected"
    ></GridViewSection>
    <GridViewRowsAddContext ref="rowsAddContext" @add-rows="addRows" />
    <div
      ref="divider"
      class="grid-view__divider"
      :style="{ left: leftWidth + 'px' }"
    ></div>
    <HorizontalResize
      v-if="primaryFieldIsSticky"
      class="grid-view__divider-width"
      :style="{ left: leftWidth + 'px' }"
      :width="leftFieldsWidth"
      :min="GRID_VIEW_MIN_FIELD_WIDTH"
      @move="moveFieldWidth(leftFields[0], $event)"
      @update="
        updateFieldWidth(leftFields[0], view, database, readOnly, $event)
      "
    ></HorizontalResize>
    <HorizontalResize
      v-else-if="viewHasGroupBys && leftFields.length === 0"
      class="grid-view__divider-width"
      :style="{ left: leftWidth + 'px' }"
      :width="activeGroupBys[activeGroupBys.length - 1].width"
      :min="GRID_VIEW_MIN_FIELD_WIDTH"
      @move="
        moveGroupWidth(activeGroupBys[activeGroupBys.length - 1], view, $event)
      "
      @update="
        updateGroupWidth(
          activeGroupBys[activeGroupBys.length - 1],
          view,
          database,
          readOnly,
          $event
        )
      "
    ></HorizontalResize>
    <GridViewSection
      ref="right"
      class="grid-view__right"
      :visible-fields="rightVisibleFields"
      :all-fields-in-table="fields"
      :decorations-by-place="decorationsByPlace"
      :database="database"
      :primary-field-is-sticky="primaryFieldIsSticky"
      :table="table"
      :view="view"
      :include-row-details="viewHasGroupBys"
      :include-grid-view-identifier-dropdown="viewHasGroupBys"
      :include-add-field="true"
      :can-order-fields="true"
      :read-only="
        readOnly ||
        (!$hasPermission(
          'database.table.update_row',
          table,
          database.workspace.id
        ) &&
          !$hasPermission(
            'database.table.view.update_row',
            view,
            database.workspace.id
          ))
      "
      :store-prefix="storePrefix"
      :style="{ left: leftWidth + 'px' }"
      @refresh="$emit('refresh', $event)"
      @field-created="fieldCreated"
      @row-hover="setRowHover($event.row, $event.value)"
      @row-context="showRowContext($event.event, $event.row)"
      @add-row="addRow()"
      @add-rows="$refs.rowsAddContext.toggleNextToMouse($event)"
      @add-row-after="addRowAfter($event)"
      @update="updateValue"
      @paste="multiplePasteFromCell"
      @edit="editValue"
      @row-dragging="rowDragStart"
      @cell-mousedown-left="multiSelectStart"
      @cell-mouseover="multiSelectHold"
      @cell-mouseup-left="multiSelectStop"
      @cell-shift-click="multiSelectShiftClick"
      @selected="selectedCell"
      @unselected="unselectedCell"
      @select-next="selectNextCell"
      @edit-modal="openRowEditModal($event)"
      @refresh-row="refreshRow"
      @scroll="scroll($event.pixelY, $event.pixelX)"
      @cell-selected="cellSelected"
    ></GridViewSection>
    <GridViewRowDragging
      ref="rowDragging"
      :table="table"
      :view="view"
      :all-visible-fields="allVisibleFields"
      :all-fields-in-table="fields"
      :store-prefix="storePrefix"
      :offset="activeGroupByWidth"
      vertical="getVerticalScrollbarElement"
      @scroll="scroll($event.pixelY, $event.pixelX)"
    ></GridViewRowDragging>
    <Context ref="rowContext" overflow-scroll max-height-if-outside-viewport>
      <ul v-show="isMultiSelectActive" class="context__menu">
        <component
          :is="contextItemComponent"
          v-for="(contextItemComponent, index) in getMultiSelectContextItems()"
          :key="index"
          :field="getSelectedField()"
          :get-rows="getSelectedRowsFunction"
          :store-prefix="storePrefix"
          :database="database"
          @click=";[$refs.rowContext.hide()]"
        ></component>
        <li class="context__menu-item">
          <a
            class="context__menu-item-link"
            @click=";[copySelection($event, false), $refs.rowContext.hide()]"
          >
            <i class="context__menu-item-icon iconoir-copy"></i>
            {{ $t('gridView.copyCells') }}
          </a>
        </li>
        <li class="context__menu-item">
          <a
            class="context__menu-item-link"
            @click=";[copySelection($event, true), $refs.rowContext.hide()]"
          >
            <i class="context__menu-item-icon iconoir-copy"></i>
            {{ $t('gridView.copyCellsWithHeader') }}
          </a>
        </li>
        <li
          v-if="
            !readOnly &&
            (!table.data_sync || table.data_sync.two_way_sync) &&
            ($hasPermission(
              'database.table.delete_row',
              table,
              database.workspace.id
            ) ||
              $hasPermission(
                'database.table.view.delete_row',
                view,
                database.workspace.id
              ))
          "
          class="context__menu-item"
        >
          <a
            class="context__menu-item-link"
            :class="{ 'context__menu-item-link--loading': deletingRow }"
            @click.stop="deleteRowsFromMultipleCellSelection()"
          >
            <i class="context__menu-item-icon iconoir-bin"></i>
            {{ $t('gridView.deleteRows') }}
          </a>
        </li>
      </ul>
      <ul v-show="!isMultiSelectActive" class="context__menu">
        <li class="context__menu-item">
          <a
            class="context__menu-item-link"
            @click=";[selectRow($event, selectedRow), $refs.rowContext.hide()]"
          >
            <i class="context__menu-item-icon iconoir-check-circle"></i>
            {{ $t('gridView.selectRow') }}
          </a>
        </li>
        <li
          v-if="
            !readOnly &&
            (!table.data_sync || table.data_sync.two_way_sync) &&
            ($hasPermission(
              'database.table.create_row',
              table,
              database.workspace.id
            ) ||
              $hasPermission(
                'database.table.view.create_row',
                view,
                database.workspace.id
              ))
          "
          class="context__menu-item"
        >
          <a
            class="context__menu-item-link"
            @click="addRowAboveSelectedRow($event, selectedRow)"
          >
            <i class="context__menu-item-icon iconoir-arrow-up"></i>
            {{ $t('gridView.insertRowAbove') }}
          </a>
        </li>
        <li
          v-if="
            !readOnly &&
            (!table.data_sync || table.data_sync.two_way_sync) &&
            ($hasPermission(
              'database.table.create_row',
              table,
              database.workspace.id
            ) ||
              $hasPermission(
                'database.table.view.create_row',
                view,
                database.workspace.id
              ))
          "
          class="context__menu-item"
        >
          <a
            class="context__menu-item-link"
            @click="addRowBelowSelectedRow($event, selectedRow)"
          >
            <i class="context__menu-item-icon iconoir-arrow-down"></i>
            {{ $t('gridView.insertRowBelow') }}
          </a>
        </li>
        <li
          v-if="
            !readOnly &&
            (!table.data_sync || table.data_sync.two_way_sync) &&
            ($hasPermission(
              'database.table.create_row',
              table,
              database.workspace.id
            ) ||
              $hasPermission(
                'database.table.view.create_row',
                view,
                database.workspace.id
              ))
          "
          class="context__menu-item"
        >
          <a
            class="context__menu-item-link"
            @click="duplicateSelectedRow($event, selectedRow)"
          >
            <i class="context__menu-item-icon iconoir-copy"></i>
            {{ $t('gridView.duplicateRow') }}
          </a>
        </li>
        <li v-if="!readOnly" class="context__menu-item">
          <a
            class="context__menu-item-link"
            @click="copyLinkToSelectedRow($event, selectedRow)"
          >
            <i class="context__menu-item-icon iconoir-link"></i>
            {{ $t('gridView.copyRowURL') }}
          </a>
        </li>
        <li
          v-if="selectedRow !== null && !selectedRow._.loading"
          class="context__menu-item"
        >
          <a
            class="context__menu-item-link"
            @click=";[openRowEditModal(selectedRow), $refs.rowContext.hide()]"
          >
            <i class="context__menu-item-icon iconoir-expand"></i>
            {{ $t('gridView.enlargeRow') }}
          </a>
        </li>
        <li
          v-if="
            !readOnly &&
            (!table.data_sync || table.data_sync.two_way_sync) &&
            ($hasPermission(
              'database.table.delete_row',
              table,
              database.workspace.id
            ) ||
              $hasPermission(
                'database.table.view.delete_row',
                view,
                database.workspace.id
              ))
          "
          class="context__menu-item context__menu-item--with-separator"
        >
          <a class="context__menu-item-link" @click="deleteRow(selectedRow)">
            <i class="context__menu-item-icon iconoir-bin"></i>
            {{ $t('gridView.deleteRow') }}
          </a>
        </li>
      </ul>
    </Context>
    <RowEditModal
      ref="rowEditModal"
      :database="database"
      :table="table"
      :view="view"
      :all-fields-in-table="fields"
      :visible-fields="allVisibleFields"
      :hidden-fields="hiddenFields"
      :rows="allRows"
      :sortable="true"
      :can-modify-fields="true"
      :read-only="
        readOnly ||
        (!$hasPermission(
          'database.table.update_row',
          table,
          database.workspace.id
        ) &&
          !$hasPermission(
            'database.table.view.update_row',
            view,
            database.workspace.id
          ))
      "
      :enable-navigation="
        !readOnly &&
        ($hasPermission(
          'database.table.update_row',
          table,
          database.workspace.id
        ) ||
          $hasPermission(
            'database.table.view.update_row',
            view,
            database.workspace.id
          ))
      "
      :show-hidden-fields="showHiddenFieldsInRowModal"
      @toggle-hidden-fields-visibility="
        showHiddenFieldsInRowModal = !showHiddenFieldsInRowModal
      "
      @update="updateValue"
      @toggle-field-visibility="toggleFieldVisibility"
      @order-fields="orderFields"
      @hidden="rowEditModalHidden"
      @field-updated="$emit('refresh', $event)"
      @field-deleted="$emit('refresh')"
      @field-created="fieldCreated"
      @field-created-callback-done="afterFieldCreatedUpdateFieldOptions"
      @navigate-previous="$emit('navigate-previous', $event, activeSearchTerm)"
      @navigate-next="$emit('navigate-next', $event, activeSearchTerm)"
      @refresh-row="refreshRow"
    ></RowEditModal>
  </div>
</template>

<script>
import { mapGetters } from 'vuex'
import ResizeObserver from 'resize-observer-polyfill'

import { notifyIf } from '@baserow/modules/core/utils/error'
import GridViewSection from '@baserow/modules/database/components/view/grid/GridViewSection'
import HorizontalResize from '@baserow/modules/core/components/HorizontalResize'
import GridViewRowDragging from '@baserow/modules/database/components/view/grid/GridViewRowDragging'
import RowEditModal from '@baserow/modules/database/components/row/RowEditModal'
import gridViewHelpers from '@baserow/modules/database/mixins/gridViewHelpers'
import {
  filterHiddenFieldsFunction,
  filterVisibleFieldsFunction,
  sortFieldsByOrderAndIdFunction,
} from '@baserow/modules/database/utils/view'
import viewHelpers from '@baserow/modules/database/mixins/viewHelpers'
import { isElement } from '@baserow/modules/core/utils/dom'
import viewDecoration from '@baserow/modules/database/mixins/viewDecoration'
import { populateRow } from '@baserow/modules/database/store/view/grid'
import { clone } from '@baserow/modules/core/utils/object'
import copyPasteHelper from '@baserow/modules/database/mixins/copyPasteHelper'
import GridViewRowsAddContext from '@baserow/modules/database/components/view/grid/fields/GridViewRowsAddContext'
import { copyToClipboard } from '@baserow/modules/database/utils/clipboard'
import {
  GRID_VIEW_SIZE_TO_ROW_HEIGHT_MAPPING,
  GRID_VIEW_MULTI_SELECT_CHECKBOX,
  GRID_VIEW_MULTI_SELECT_AREA,
} from '@baserow/modules/database/constants'

export default {
  name: 'GridView',
  components: {
    HorizontalResize,
    GridViewRowsAddContext,
    GridViewSection,
    GridViewRowDragging,
    RowEditModal,
  },
  mixins: [viewHelpers, gridViewHelpers, viewDecoration, copyPasteHelper],
  props: {
    fields: {
      type: Array,
      required: true,
    },
    view: {
      type: Object,
      required: true,
    },
    table: {
      type: Object,
      required: true,
    },
    database: {
      type: Object,
      required: true,
    },
    readOnly: {
      type: Boolean,
      required: true,
    },
  },
  data() {
    return {
      lastHoveredRow: null,
      selectedRow: null,
      deletingRow: false,
      showHiddenFieldsInRowModal: false,
      // Indicates whether the first two columns have enough space to be usable. If
      // not, the primary field is not sticky, so it's easier to view all data on for
      // example a smartphone.
      canFitInTwoColumns: true,
      // When a cell is selected, the component will be propagated and stored into this
      // array until it's unselected. Having these components here can be useful if a
      // global keyboard shortcut must be blocked if a single line text field cell is
      // in an editing state for example.
      selectedCellComponents: [],
      // Set to true when the row is being refreshed to avoid multiple fields
      // submitting multiple refresh requests at the same time.
      refreshingRow: false,
    }
  },
  computed: {
    ...mapGetters({
      row: 'rowModalNavigation/getRow',
    }),
    /**
     * Returns all visible fields no matter in what section they
     * belong.
     */
    allVisibleFields() {
      return this.leftFields.concat(this.rightVisibleFields)
    },
    /**
     * Returns only the visible fields in the correct order that are in
     * the right section of the grid. Primary must always be
     * first if in that list.
     */
    rightVisibleFields() {
      const fieldOptions = this.fieldOptions
      return this.rightFields
        .filter(filterVisibleFieldsFunction(fieldOptions))
        .sort(sortFieldsByOrderAndIdFunction(fieldOptions, true))
    },
    /**
     * Returns only the hidden fields in the correct order.
     */
    hiddenFields() {
      const fieldOptions = this.fieldOptions
      return this.rightFields
        .filter(filterHiddenFieldsFunction(fieldOptions))
        .sort(sortFieldsByOrderAndIdFunction(fieldOptions))
    },
    viewHasGroupBys() {
      return this.activeGroupBys.length > 0
    },
    primaryFieldIsSticky() {
      return this.canFitInTwoColumns && !this.viewHasGroupBys
    },
    leftFields() {
      if (this.primaryFieldIsSticky) {
        return this.fields.filter((field) => field.primary)
      } else {
        return []
      }
    },
    rightFields() {
      if (this.primaryFieldIsSticky) {
        return this.fields.filter((field) => !field.primary)
      } else {
        return this.fields
      }
    },
    leftFieldsWidth() {
      return this.leftFields.reduce(
        (value, field) => this.getFieldWidth(field) + value,
        0
      )
    },
    leftWidth() {
      return (
        this.leftFieldsWidth +
        (this.viewHasGroupBys ? 0 : this.gridViewRowDetailsWidth) +
        // 100 must be replaced with the dynamic width
        this.activeGroupByWidth
      )
    },
    activeSearchTerm() {
      return this.$store.getters[
        `${this.storePrefix}view/grid/getActiveSearchTerm`
      ]
    },
  },
  watch: {
    fieldOptions: {
      deep: true,
      handler() {
        // When the field options have changed, it could be that the width of the
        // fields have changed and in that case we want to update the scrollbars.
        this.fieldsUpdated()
      },
    },
    fields() {
      // When a field is added or removed, we want to update the scrollbars.
      this.fieldsUpdated()
    },
    row: {
      deep: true,
      handler(newRow, prevRow) {
        if (this.$refs.rowEditModal) {
          if (
            (prevRow === null && newRow !== null) ||
            (prevRow && newRow && prevRow.id !== newRow.id)
          ) {
            this.populateAndEditRow(newRow)
          } else if (prevRow !== null && newRow === null) {
            // Pass emit=false as argument into the hide function because that will
            // prevent emitting another `hidden` event of the `RowEditModal` which can
            // result in the route changing twice.
            this.$refs.rowEditModal.hide(false)
          }
        }
        // `refreshRow` doesn't immediately hide a row not matching filters if a
        // user open the modal for that row to solve
        // https://gitlab.com/baserow/baserow/-/issues/1765. This handler ensure
        // the row is correctly refreshed if the user open another row using the
        // navigation buttons in the modal.
        const prevRowId = prevRow?.id
        if (prevRowId !== undefined && prevRowId !== newRow?.id) {
          this.$store.dispatch(this.storePrefix + 'view/grid/refreshRowById', {
            grid: this.view,
            fields: this.fields,
            rowId: prevRowId,
            getScrollTop: () => this.$refs.left.$refs.body.scrollTop,
          })
        }
      },
    },
    'view.row_height_size'(value, oldValue) {
      if (value === oldValue) {
        return
      }
      this.$store.dispatch(
        this.storePrefix + 'view/grid/setRowHeight',
        GRID_VIEW_SIZE_TO_ROW_HEIGHT_MAPPING[value]
      )
      this.onWindowResize()
      this.$emit('refresh')
    },
  },
  beforeCreate() {
    this.$options.computed = {
      ...(this.$options.computed || {}),
      ...mapGetters({
        allRows: this.$options.propsData.storePrefix + 'view/grid/getAllRows',
        isMultiSelectActive:
          this.$options.propsData.storePrefix + 'view/grid/isMultiSelectActive',
      }),
    }
  },
  created() {
    // When the grid view is created we want to update the scrollbars.
    this.fieldsUpdated()
  },
  beforeMount() {
    this.$bus.$on('field-deleted', this.fieldDeleted)
  },
  mounted() {
    this.$el.resizeObserver = new ResizeObserver(this.onWindowResize)
    this.$el.resizeObserver.observe(this.$el)
    window.addEventListener('keydown', this.keyDownEvent)
    window.addEventListener('copy', this.copySelection)
    window.addEventListener('paste', this.pasteFromMultipleCellSelection)
    window.addEventListener('click', this.cancelMultiSelectIfActive)
    window.addEventListener('mouseup', this.multiSelectStop)
    this.$refs.left.$el.addEventListener(
      'scroll',
      this.$el.horizontalScrollEvent
    )
    this.$store.dispatch(
      this.storePrefix + 'view/grid/fetchAllFieldAggregationData',
      { view: this.view }
    )
    this.onWindowResize()

    if (this.row !== null) {
      this.populateAndEditRow(this.row)
    }
  },
  beforeDestroy() {
    this.$el.resizeObserver.unobserve(this.$el)
    window.removeEventListener('keydown', this.keyDownEvent)
    window.removeEventListener('copy', this.copySelection)
    window.removeEventListener('paste', this.pasteFromMultipleCellSelection)
    window.removeEventListener('click', this.cancelMultiSelectIfActive)
    window.removeEventListener('mouseup', this.multiSelectStop)
    this.$bus.$off('field-deleted', this.fieldDeleted)

    this.$store.dispatch(
      this.storePrefix + 'view/grid/clearAndDisableMultiSelect'
    )
  },
  methods: {
    /**
     * Method to scroll viewport to a DOM element
     * Scroll direction can be limited to only one axis (both, vertical, horizontal)
     */
    scrollToCellElement(element, scrollDirection = 'both', field) {
      const verticalContainer = this.$refs.right.$refs.body
      const horizontalContainer = this.$refs.right.$el
      const verticalContainerRect = verticalContainer.getBoundingClientRect()
      const horizontalContainerRect =
        horizontalContainer.getBoundingClientRect()
      const elementRect = element.getBoundingClientRect()
      const elementTop = elementRect.top - verticalContainerRect.top
      const elementBottom = elementRect.bottom - verticalContainerRect.top
      const elementLeft = elementRect.left - horizontalContainerRect.left
      const elementRight = elementRect.right - horizontalContainerRect.left
      this.scrollToElementRect(
        { elementTop, elementBottom, elementLeft, elementRight },
        scrollDirection,
        field
      )
    },
    /**
     * Method to scroll viewport to a DOM element defined by its rectangle
     * Scroll direction can be limited to only one axis (both, vertical, horizontal)
     */
    scrollToElementRect(
      { elementTop, elementBottom, elementLeft, elementRight },
      scrollDirection = 'both',
      field
    ) {
      const verticalContainer = this.$refs.right.$refs.body
      const horizontalContainer = this.$refs.right.$el
      const verticalContainerHeight = verticalContainer.clientHeight
      const horizontalContainerWidth = horizontalContainer.clientWidth

      if (scrollDirection !== 'horizontal') {
        if (elementTop < 0) {
          // If the field isn't visible in the viewport we need to scroll up in order
          // to show it.
          this.verticalScroll(elementTop + verticalContainer.scrollTop - 20)
          this.$refs.scrollbars.updateVertical()
        } else if (elementBottom > verticalContainerHeight) {
          // If the field isn't visible in the viewport we need to scroll down in order
          // to show it.
          this.verticalScroll(
            elementBottom +
              verticalContainer.scrollTop -
              verticalContainer.clientHeight +
              20
          )
          this.$refs.scrollbars.updateVertical()
        }
      }

      if (scrollDirection !== 'vertical') {
        const fieldPrimary = field.primary
        if (elementLeft < 0 && (!this.primaryFieldIsSticky || !fieldPrimary)) {
          // If the field isn't visible in the viewport we need to scroll left in order
          // to show it.
          this.horizontalScroll(
            elementLeft + horizontalContainer.scrollLeft - 20
          )
          this.$refs.scrollbars.updateHorizontal()
        } else if (
          elementRight > horizontalContainerWidth &&
          (!this.primaryFieldIsSticky || !fieldPrimary)
        ) {
          // If the field isn't visible in the viewport we need to scroll right in order
          // to show it.
          this.horizontalScroll(
            elementRight +
              horizontalContainer.scrollLeft -
              horizontalContainer.clientWidth +
              20
          )
          this.$refs.scrollbars.updateHorizontal()
        }
      }
    },
    duplicateSelectedRow(event, selectedRow) {
      event.preventFieldCellUnselect = true
      const duplicatedRow = clone(selectedRow)
      this.fields.forEach((field) => {
        const fieldType = this.$registry.get('field', field.type)
        const fieldKey = `field_${field.id}`
        if (Object.prototype.hasOwnProperty.call(duplicatedRow, fieldKey)) {
          duplicatedRow[fieldKey] = fieldType.prepareValueForDuplicate(
            field,
            duplicatedRow[fieldKey]
          )
        }
      })
      this.addRowAfter(selectedRow, duplicatedRow)
      this.$refs.rowContext.hide()
    },
    copyLinkToSelectedRow(event, selectedRow) {
      const url =
        this.$config.BASEROW_EMBEDDED_SHARE_URL +
        this.$router.resolve({
          name: 'database-table-row',
          params: { ...this.$route.params, rowId: selectedRow.id },
        }).href
      copyToClipboard(url)
      this.$store.dispatch('toast/info', {
        title: this.$i18n.t('gridView.copiedRowURL'),
        message: this.$i18n.t('gridView.copiedRowURLMessage', {
          id: selectedRow.id,
        }),
      })
      this.$refs.rowContext.hide()
    },
    addRowAboveSelectedRow(event, selectedRow) {
      event.preventFieldCellUnselect = true
      this.addRow(selectedRow)
      this.$refs.rowContext.hide()
    },
    addRowBelowSelectedRow(event, selectedRow) {
      event.preventFieldCellUnselect = true
      this.addRowAfter(selectedRow)
      this.$refs.rowContext.hide()
    },
    /**
     * When a field is deleted we need to check if that field was related to any
     * filters or sortings. If that is the case then the view needs to be refreshed so
     * we can see fresh results.
     */
    fieldDeleted({ field }) {
      const filterIndex = this.view.filters.findIndex((filter) => {
        return filter.field === field.id
      })
      const groupIndex = this.view.group_bys.findIndex((group) => {
        return group.field === field.id
      })
      const sortIndex = this.view.sortings.findIndex((sort) => {
        return sort.field === field.id
      })
      if (filterIndex > -1 || groupIndex > -1 || sortIndex > -1) {
        this.$emit('refresh')
      }
    },
    /**
     * Is called when anything related to a field has changed and in that case we want
     * to update the scrollbars.
     */
    fieldsUpdated() {
      const scrollbars = this.$refs.scrollbars
      // Vue can sometimes trigger this via watch before the child component
      // scrollbars has been created, check it exists and has the expected method
      if (scrollbars && scrollbars.update) {
        scrollbars.update()
      }

      // When anything related to the fields has been updated, it could be that it
      // doesn't fit in two columns anymore. Calling this method checks that.
      this.checkCanFitInTwoColumns()
    },
    /**
     * Calls action in the store to refresh row directly from the backend - f. ex.
     * when editing row from a different table, when editing is complete, we need
     * to refresh the 'main' row that's 'under' the RowEdit modal.
     */
    refreshRow(row) {
      if (this.refreshingRow) {
        return
      }
      this.refreshingRow = true
      this.$nextTick(async () => {
        try {
          await this.$store.dispatch(
            this.storePrefix + 'view/grid/refreshRowFromBackend',
            { table: this.table, row }
          )
        } catch (error) {
          notifyIf(error, 'row')
        } finally {
          this.refreshingRow = false
        }
      })
    },
    /**
     * Called when a cell value has been updated. This can for example happen via the
     * row edit modal or when editing a cell directly in the grid.
     */
    async updateValue({ field, row, value, oldValue }) {
      try {
        await this.$store.dispatch(
          this.storePrefix + 'view/grid/updateRowValue',
          {
            table: this.table,
            view: this.view,
            fields: this.fields,
            row,
            field,
            value,
            oldValue,
            isRowOpenedInModal: this.isRowOpenedInModal,
          }
        )
      } catch (error) {
        notifyIf(error, 'field')
      }
    },
    /**
     * Called when a value is edited, but not yet saved. Here we can do a preliminary
     * check to see if the values matches the filters.
     */
    editValue({ field, row, value, oldValue }) {
      const overrides = {}
      overrides[`field_${field.id}`] = value
      this.$store.dispatch(this.storePrefix + 'view/grid/onRowChange', {
        view: this.view,
        row,
        fields: this.fields,
        overrides,
      })
    },
    /**
     * This method is called by the Scrollbars component and should return the element
     * that handles the horizontal scrolling.
     */
    getHorizontalScrollbarElement() {
      return this.$refs.right.$el
    },
    /**
     * This method is called by the Scrollbars component and should return the element
     * that handles the vertical scrolling.
     */
    getVerticalScrollbarElement() {
      return this.$refs.right.$refs.body
    },
    /**
     * Called when a user scrolls without using the scrollbar.
     */
    scroll(pixelY, pixelX) {
      const $rightBody = this.$refs.right.$refs.body
      const $right = this.$refs.right.$el

      const top = $rightBody.scrollTop + pixelY
      const left = $right.scrollLeft + pixelX

      this.verticalScroll(top)
      this.horizontalScroll(left)

      this.$refs.scrollbars.update()
    },
    /**
     * Called when the user scrolls vertically. The scroll offset of both the left and
     * right section must be updated and we want might need to fetch new rows which
     * is handled by the grid view store.
     */
    verticalScroll(top) {
      this.$refs.left.$refs.body.scrollTop = top
      this.$refs.right.$refs.body.scrollTop = top

      this.$store.dispatch(
        this.storePrefix + 'view/grid/fetchByScrollTopDelayed',
        {
          scrollTop: this.$refs.left.$refs.body.scrollTop,
          fields: this.fields,
        }
      )
    },
    /**
     * Called when the user scrolls horizontally. If the user scrolls we might want to
     * show a shadow next to the left section because that one has a fixed position.
     */
    horizontalScroll(left) {
      const $right = this.$refs.right.$el
      const $divider = this.$refs.divider
      const canScroll = $right.scrollWidth > $right.clientWidth

      $divider.classList.toggle('shadow', canScroll && left > 0)
      $right.scrollLeft = left
    },
    /**
     * Selects the entire row.
     */
    async selectRow(event, row) {
      event.stopPropagation()
      const rowIndex = this.$store.getters[
        this.storePrefix + 'view/grid/getRowIndexById'
      ](row.id)
      await this.$store.dispatch(
        this.storePrefix + 'view/grid/setMultipleSelect',
        {
          rowHeadIndex: rowIndex,
          rowTailIndex: rowIndex,
          fieldHeadIndex: 0,
          fieldTailIndex: this.allVisibleFields.length - 1,
        }
      )
    },
    async addRow(before = null, values = {}) {
      try {
        await this.$store.dispatch(
          this.storePrefix + 'view/grid/createNewRow',
          {
            view: this.view,
            table: this.table,
            // We need a list of all fields including the primary one here.
            fields: this.fields,
            values,
            before,
            selectPrimaryCell: true,
            isRowOpenedInModal: this.isRowOpenedInModal,
          }
        )
      } catch (error) {
        notifyIf(error, 'row')
      }
    },
    async addRows(rowsAmount) {
      this.$refs.rowsAddContext.hide()
      try {
        await this.$store.dispatch(
          this.storePrefix + 'view/grid/createNewRows',
          {
            view: this.view,
            table: this.table,
            // We need a list of all fields including the primary one here.
            fields: this.fields,
            rows: Array.from(Array(rowsAmount)).map(() => ({})),
            selectPrimaryCell: true,
            isRowOpenedInModal: this.isRowOpenedInModal,
          }
        )
      } catch (error) {
        notifyIf(error, 'row')
      }
    },
    /**
     * Because it is only possible to add a new row before another row, we have to
     * figure out which row is below the given row and insert before that one. If the
     * next row is not found, we can safely assume it is the last row and add it last.
     */
    addRowAfter(row, values = {}) {
      const rows =
        this.$store.getters[this.storePrefix + 'view/grid/getAllRows']
      const index = rows.findIndex((r) => r.id === row.id)
      let nextRow = null

      if (index !== -1 && rows.length > index + 1) {
        nextRow = rows[index + 1]
      }

      this.addRow(nextRow, values)
    },
    async deleteRow(row) {
      try {
        this.$refs.rowContext.hide()
        // We need a small helper function that calculates the current scrollTop because
        // the delete action will recalculate the visible scroll range and buffer.
        const getScrollTop = () => this.$refs.left.$refs.body.scrollTop
        await this.$store.dispatch(
          this.storePrefix + 'view/grid/deleteExistingRow',
          {
            table: this.table,
            view: this.view,
            fields: this.fields,
            row,
            getScrollTop,
          }
        )
        await this.$store.dispatch('toast/restore', {
          trash_item_type: 'row',
          parent_trash_item_id: this.table.id,
          trash_item_id: row.id,
        })
      } catch (error) {
        notifyIf(error, 'row')
      }
    },
    setRowHover(row, value) {
      // Sometimes the mouseleave is not triggered, but because you can hover only one
      // row at a time we can remember which was hovered last and set the hover state to
      // false if it differs.
      if (this.lastHoveredRow !== null && this.lastHoveredRow.id !== row.id) {
        this.$store.dispatch(this.storePrefix + 'view/grid/setRowHover', {
          row: this.lastHoveredRow,
          value: false,
        })
        this.lastHoveredRow = null
      }

      this.$store.dispatch(this.storePrefix + 'view/grid/setRowHover', {
        row,
        value,
      })
      this.lastHoveredRow = row
    },
    handleRowSelect({ row, value }) {
      if (
        this.$store.getters[this.storePrefix + 'view/grid/isMultiSelectActive']
      ) {
        this.$store.dispatch(
          this.storePrefix + 'view/grid/clearAndDisableMultiSelect'
        )
      }

      if (value) {
        this.$store.dispatch(this.storePrefix + 'view/grid/addRowSelectedBy', {
          row,
          field: this.fields[0],
        })
      } else {
        this.$store.dispatch(
          this.storePrefix + 'view/grid/removeRowSelectedBy',
          {
            grid: this.view,
            row,
            field: this.fields[0],
            fields: this.fields,
            getScrollTop: () => this.$refs.left.$refs.body.scrollTop,
          }
        )
      }
    },
    showRowContext(event, row) {
      this.selectedRow = row
      this.$refs.rowContext.toggleNextToMouse(event)
    },
    /**
     * Called when the user starts dragging the row. This will initiate the dragging
     * effect and allows the user to move it to another position.
     */
    rowDragStart({ event, row }) {
      this.$refs.rowDragging.start(row, event)
    },
    /**
     * When the modal hides and the related row does not match the filters anymore it
     * must be deleted.
     */
    rowEditModalHidden({ row }) {
      this.$emit('selected-row', undefined)

      // It could be that the row is not in the buffer anymore and in that case we also
      // don't need to refresh the row.
      if (
        row === undefined ||
        !Object.prototype.hasOwnProperty.call(row, 'id')
      ) {
        return
      }

      this.$store.dispatch(this.storePrefix + 'view/grid/refreshRowById', {
        grid: this.view,
        fields: this.fields,
        rowId: row.id,
        getScrollTop: () => this.$refs.left.$refs.body.scrollTop,
      })
    },
    /**
     * When the row edit modal is opened we notify
     * the Table component that a new row has been selected,
     * such that we can update the path to include the row id.
     */
    openRowEditModal(row) {
      // The row edit modal doesn't support a row that doesn't yet have a row ID, so we
      // don't do anything in that case.
      if (row._.loading) {
        return
      }

      this.$refs.rowEditModal.show(row.id)
      this.$emit('selected-row', row)
    },
    /**
     * Populates a new row and opens the row edit modal
     * to edit the row.
     */
    populateAndEditRow(row) {
      const rowClone = populateRow(clone(row))
      this.$refs.rowEditModal.show(row.id, rowClone)
    },
    /**
     * When a cell is selected we want to make sure it is visible in the viewport, so
     * we might need to scroll a little bit.
     */
    selectedCell({ component, row, field }) {
      // Put the selected cell component in an array, so that we can check whether it's
      // allowed to hit keyboard shortcuts, click outside, etc when a global keyboard
      // short is called.
      if (!this.selectedCellComponents.includes(component)) {
        this.selectedCellComponents.push(component)
      }

      const element = component.$el
      this.scrollToCellElement(element, 'both', field)
      this.$store.dispatch(this.storePrefix + 'view/grid/addRowSelectedBy', {
        row,
        field,
      })
    },
    /**
     * This function helps the store determine whether it is safe to hide a row. Since
     * some filters or groups may depend on values computed in the backend, the store
     * needs to know if a row that does not meet the filters can be safely hidden when
     * the values become available or if it should remain visible until the modal is
     * closed.
     */
    isRowOpenedInModal(row) {
      return this.$store.getters['rowModalNavigation/getRow']?.id === row.id
    },
    /**
     * When a cell is unselected need to change the selected state of the row.
     */
    unselectedCell({ component, row, field }) {
      // Remove the selected cell component in an array because we don't have to check
      // if keyboard shortcuts are allowed, click outside, etc is allowed anymore.
      if (this.selectedCellComponents.includes(component)) {
        const index = this.selectedCellComponents.indexOf(component)
        this.selectedCellComponents.splice(index, 1)
      }

      // We want to change selected state of the row on the next tick because if another
      // cell within a row is selected, we want to wait for that selected state tot
      // change. This will make sure that the row is stays selected.
      this.$nextTick(() => {
        // The getScrollTop function tries to find the vertically scrollable element
        // and returns the scrollTop value. The unselectCell method could in some cases
        // be called when the grid view component has already been destroyed. For
        // example when a cell is selected in the template modal and the user presses
        // the escape key which destroys the modal. We need to make sure, the lookup
        // doesn't fail hard when that happens, so we can return the last scroll top
        // value stored in the grid view store.
        let getScrollTop = () => this.$refs.left.$refs.body.scrollTop
        if (!this.$refs.left) {
          getScrollTop = () =>
            this.$store.getters[this.storePrefix + 'view/grid/getScrollTop']
        }

        this.$store.dispatch(
          this.storePrefix + 'view/grid/removeRowSelectedBy',
          {
            grid: this.view,
            fields: this.fields,
            row,
            field,
            getScrollTop,
            isRowOpenedInModal: this.isRowOpenedInModal,
          }
        )
      })
    },
    /**
     * This method is called when the next cell must be selected. This can for example
     * happen when the tab key is pressed. It tries to find the next field based on the
     * direction and will select that one.
     */
    selectNextCell({ row, field, direction = 'next' }) {
      const fields = this.allVisibleFields
      let nextFieldId = -1
      let nextRowId = -1

      if (direction === 'next' || direction === 'previous') {
        nextRowId = row.id

        // First we need to know which index the currently selected field has in the
        // fields list.
        const index = fields.findIndex((f) => f.id === field.id)
        if (direction === 'next' && fields.length > index + 1) {
          // If we want to select the next field we can just check if the next index
          // exists and read the id from there.
          nextFieldId = fields[index + 1].id
        } else if (direction === 'previous' && index > 0) {
          // If we want to select the previous field we can just check if aren't
          // already the first and read the id from the previous.
          nextFieldId = fields[index - 1].id
        }
      }

      if (direction === 'below' || direction === 'above') {
        nextFieldId = field.id
        const rows =
          this.$store.getters[this.storePrefix + 'view/grid/getAllRows']
        const index = rows.findIndex((r) => r.id === row.id)

        if (index !== -1 && direction === 'below' && rows.length > index + 1) {
          // If the next row index exists we can select the same field in the next row.
          nextRowId = rows[index + 1].id
        } else if (index !== -1 && direction === 'above' && index > 0) {
          // If the previous row index exists we can select the same field in the
          // previous row.
          nextRowId = rows[index - 1].id
        }
      }

      if (nextFieldId === -1 || nextRowId === -1) {
        return
      }

      this.$store.dispatch(
        this.storePrefix + 'view/grid/clearAndDisableMultiSelect'
      )

      this.$store.dispatch(this.storePrefix + 'view/grid/setSelectedCell', {
        rowId: nextRowId,
        fieldId: nextFieldId,
        fields: this.fields,
      })
    },
    cellSelected({ fieldId, rowId }) {
      this.$store.dispatch(this.storePrefix + 'view/grid/setSelectedCell', {
        rowId,
        fieldId,
        fields: this.fields,
      })
    },
    /**
     * This method is called from the parent component when the data in the view has
     * been reset. This can for example happen when a user creates or updates a filter
     * or wants to sort on a field.
     */
    async refresh() {
      await this.$store.dispatch(
        this.storePrefix + 'view/grid/visibleByScrollTop',
        this.$refs.right.$refs.body.scrollTop
      )
      // The grid view store keeps a copy of the group bys that must only be updated
      // after the refresh of the page. This is because the group by depends on the rows
      // being sorted, and this will only be the case after a refresh.
      await this.$store.dispatch(
        this.storePrefix + 'view/grid/updateActiveGroupBys',
        clone(this.view.group_bys)
      )
      this.$nextTick(() => {
        this.fieldsUpdated()
      })
    },
    multiSelectShiftClick({ event, row, field }) {
      this.$store.dispatch(
        this.storePrefix + 'view/grid/multiSelectShiftClick',
        {
          rowId: row.id,
          fieldIndex: this.allVisibleFields.findIndex((f) => f.id === field.id),
        }
      )
    },
    /**
     * Called when mouse is clicked and held on a GridViewCell component.
     * Starts multi-select by setting the head and tail index to the currently
     * selected cell.
     */
    multiSelectStart({ event, row, field }) {
      const fieldIndex = this.allVisibleFields.findIndex(
        (f) => f.id === field.id
      )

      this.$store.dispatch(this.storePrefix + 'view/grid/multiSelectStart', {
        rowId: row.id,
        fieldIndex,
      })
      this.$refs.rowContext.hide()
    },
    /**
     * Called when mouse hovers over a GridViewCell component.
     * Updates the current multi-select grid by updating the tail index
     * with the last cell hovered over.
     */
    multiSelectHold({ event, row, field }) {
      const fieldIndex = this.allVisibleFields.findIndex(
        (f) => f.id === field.id
      )

      this.$store.dispatch(this.storePrefix + 'view/grid/multiSelectHold', {
        rowId: row.id,
        fieldIndex,
      })
    },
    /**
     * Called when the mouse is unpressed over a GridViewCell component.
     * Stop multi-select.
     */
    multiSelectStop({ event, row, field }) {
      const selectionType =
        this.$store.getters[this.storePrefix + 'view/grid/getSelectionType']
      if (selectionType === GRID_VIEW_MULTI_SELECT_CHECKBOX) {
        return
      }
      this.$store.dispatch(
        this.storePrefix + 'view/grid/setMultiSelectHolding',
        false
      )
    },
    /**
     * Cancels multi-select if it's currently active.
     * This function checks if a mouse click event is triggered
     * outside of GridViewRows.
     */
    cancelMultiSelectIfActive(event) {
      const selectionType =
        this.$store.getters[this.storePrefix + 'view/grid/getSelectionType']

      if (selectionType !== GRID_VIEW_MULTI_SELECT_AREA) {
        return
      }

      if (
        this.$store.getters[
          this.storePrefix + 'view/grid/isMultiSelectActive'
        ] &&
        !event.shiftKey &&
        (!isElement(this.$el, event.target) ||
          !['grid-view__row', 'grid-view__rows', 'grid-view'].includes(
            event.target.classList[0]
          ))
      ) {
        this.$store.dispatch(
          this.storePrefix + 'view/grid/clearAndDisableMultiSelect'
        )
      }
    },
    async keyDownEvent(event) {
      const arrowKeys = ['ArrowRight', 'ArrowLeft', 'ArrowUp', 'ArrowDown']
      const arrowShiftKeysMapping = {
        ArrowLeft: 'previous',
        ArrowRight: 'next',
        ArrowUp: 'above',
        ArrowDown: 'below',
      }
      const { key, shiftKey } = event
      if (
        arrowKeys.includes(key) &&
        shiftKey &&
        // Only allow this event if there is an active single cell selection, or
        // multiple selection.
        (this.$store.getters[this.storePrefix + 'view/grid/hasSelectedCell'] ||
          this.$store.getters[
            this.storePrefix + 'view/grid/isMultiSelectActive'
          ]) &&
        // And there is no selected cell component blocking the select next events. A
        // single line text field can for example block this while it's in an editing
        // state.
        this.selectedCellComponents.every((component) => {
          return component.canSelectNext(event)
        })
      ) {
        event.preventDefault()

        const { position, fieldIndex, rowIndex } = await this.$store.dispatch(
          this.storePrefix + 'view/grid/multiSelectShiftChange',
          {
            direction: arrowShiftKeysMapping[key],
          }
        )

        if (position === null) {
          return
        }

        let scrollDirection = 'both'
        if (position === 'head' && key === 'ArrowLeft') {
          scrollDirection = 'horizontal'
        }
        if (position === 'head' && key === 'ArrowUp') {
          scrollDirection = 'vertical'
        }
        if (position === 'tail' && key === 'ArrowRight') {
          scrollDirection = 'horizontal'
        }
        if (position === 'tail' && key === 'ArrowDown') {
          scrollDirection = 'vertical'
        }

        const fieldId = this.$store.getters[
          this.storePrefix + 'view/grid/getFieldIdByIndex'
        ](fieldIndex, this.fields)
        if (fieldId === -1) {
          return
        }
        const field = this.$store.getters['field/get'](fieldId)
        const verticalContainer = this.$refs.right.$refs.body
        const horizontalContainer = this.$refs.right.$el
        const visibleFieldOptions = this.$store.getters[
          this.storePrefix + 'view/grid/getOrderedVisibleFieldOptions'
        ](this.fields)
        let elementRight = -horizontalContainer.scrollLeft
        for (let i = 0; i < visibleFieldOptions.length; i++) {
          const fieldOption = visibleFieldOptions[i]
          if (i === 0) {
            if (fieldOption[0] === fieldId) {
              elementRight = 0
              break
            }
            continue
          }

          const matchedField = this.fields.find(
            (field) => field.id === fieldOption[0]
          )
          elementRight += this.getFieldWidth(matchedField)
          if (fieldOption[0] === fieldId) {
            break
          }
        }
        const rowHeight =
          this.$store.getters[this.storePrefix + 'view/grid/getRowHeight']
        const elementLeft = elementRight - this.getFieldWidth(field)
        const elementBottom =
          -verticalContainer.scrollTop + rowHeight + rowIndex * rowHeight
        const elementTop = elementBottom - rowHeight
        this.scrollToElementRect(
          { elementTop, elementBottom, elementLeft, elementRight },
          scrollDirection,
          field
        )

        return
      }

      if (
        this.$store.getters[this.storePrefix + 'view/grid/isMultiSelectActive']
      ) {
        if (arrowKeys.includes(key) && !shiftKey) {
          this.$store.dispatch(
            this.storePrefix + 'view/grid/setSelectedCellCancelledMultiSelect',
            {
              direction: arrowShiftKeysMapping[key],
              fields: this.fields,
            }
          )
        }

        if (event.key === 'Backspace' || event.key === 'Delete') {
          this.clearValuesFromMultipleCellSelection()
        }
      }
    },
    /**
     * Prepare and copy the multi-select cells into the clipboard,
     * formatted as TSV
     */
    copySelection(event, includeHeader = false) {
      const gridStore = this.storePrefix + 'view/grid'
      if (!this.$store.getters[`${gridStore}/isMultiSelectActive`]) {
        return
      }

      this.copySelectionToClipboard(
        this.$store.dispatch(`${gridStore}/getCurrentSelection`, {
          fields: this.allVisibleFields,
        }),
        includeHeader
      )

      // prevent Safari from beeping since window.getSelection() is empty
      event.preventDefault()
    },
    /**
     * Called when the @paste event is triggered from the `GridViewSection` component.
     * This happens when the individual cell doesn't understand the pasted data and
     * needs to emit it up. This typically happens when multiple cell values are pasted.
     */
    async multiplePasteFromCell({ data: { textData, jsonData }, field, row }) {
      const rowIndex = this.$store.getters[
        this.storePrefix + 'view/grid/getRowIndexById'
      ](row.id)
      const fieldIndex = this.allVisibleFields.findIndex(
        (f) => f.id === field.id
      )
      await this.pasteData(textData, jsonData, rowIndex, fieldIndex)
    },
    /**
     * Called when the user pastes data without having an individual cell selected. It
     * only works when a multiple selection is active because then we know in which
     * cells we can paste the data.
     */
    async pasteFromMultipleCellSelection(event) {
      if (!this.isMultiSelectActive) {
        return
      }

      const [textData, jsonData] = await this.extractClipboardData(event)

      await this.pasteData(textData, jsonData)
    },
    /**
     * Called when data must be pasted into the grid view. It basically forwards the
     * request to a store action which handles the actual updating of rows. It also
     * shows a loading animation while busy, so the user knows something is while the
     * update is in progress.
     */
    async pasteData(textData, jsonData, rowIndex, fieldIndex) {
      // If the data is an empty array, we don't have to do anything because there is
      // nothing to update. If the view is in read only mode or if we don't have the
      // permission, we can't paste so not doing anything.
      if (
        textData.length === 0 ||
        textData[0].length === 0 ||
        this.readOnly ||
        (!this.$hasPermission(
          'database.table.update_row',
          this.table,
          this.database.workspace.id
        ) &&
          !this.$hasPermission(
            'database.table.view.update_row',
            this.view,
            this.database.workspace.id
          ))
      ) {
        return
      }

      // The backend will fail hard if it tries to update more rows than the limit, so
      // we're slicing the data here.
      const pageSizeLimit = this.$config.BASEROW_ROW_PAGE_SIZE_LIMIT
      if (textData.length > pageSizeLimit) {
        this.$store.dispatch('toast/info', {
          title: this.$t('gridView.tooManyItemsTitle'),
          message: this.$t('gridView.tooManyItemsDescription', {
            limit: pageSizeLimit,
          }),
        })
        textData = textData.slice(0, pageSizeLimit)
      }

      this.$store.dispatch('toast/setPasting', true)
      try {
        await this.$store.dispatch(
          this.storePrefix + 'view/grid/updateDataIntoCells',
          {
            table: this.table,
            view: this.view,
            allVisibleFields: this.allVisibleFields,
            allFieldsInTable: this.fields,
            getScrollTop: () => this.$refs.left.$refs.body.scrollTop,
            textData,
            jsonData,
            rowIndex,
            fieldIndex,
          }
        )
      } catch (error) {
        notifyIf(error)
      }

      this.$store.dispatch('toast/setPasting', false)
      return true
    },
    /**
     * Called when the delete option is selected in
     * the context menu. Attempts to delete all the
     * selected rows and scrolls the view accordingly.
     */
    async deleteRowsFromMultipleCellSelection() {
      this.deletingRow = true
      try {
        await this.$store.dispatch(
          this.storePrefix + 'view/grid/deleteSelectedRows',
          {
            table: this.table,
            view: this.view,
            fields: this.allVisibleFields,
            getScrollTop: () => this.$refs.left.$refs.body.scrollTop,
          }
        )
        this.$refs.rowContext.hide()
      } catch (error) {
        notifyIf(error)
      }
      this.deletingRow = false
      return true
    },
    /**
     * Called when the backspace key is pressed while multi-cell select is active.
     * Clears the values of all selected cells by updating them to their null values.
     */
    async clearValuesFromMultipleCellSelection() {
      try {
        this.$store.dispatch('toast/setClearing', true)

        await this.$store.dispatch(
          this.storePrefix + 'view/grid/clearValuesFromMultipleCellSelection',
          {
            table: this.table,
            view: this.view,
            allVisibleFields: this.allVisibleFields,
            allFieldsInTable: this.fields,
            getScrollTop: () => this.$refs.left.$refs.body.scrollTop,
          }
        )
      } catch (error) {
        notifyIf(error, 'view')
      } finally {
        this.$store.dispatch('toast/setClearing', false)
      }
    },
    /**
     * This method figures out whether the first two columns have enough space to be
     * usable using the primary field width. It updates the `canFitInTwoColumns`
     * property accordingly.
     */
    checkCanFitInTwoColumns() {
      // In some cases this method is called when the component hasn't fully been
      // loaded. This will make sure we don't change the state before that initial load.
      if (!this.$el) {
        return
      }

      // We're using `allVisibleFields` because it shouldn't matter if the primary
      // field is in the left or right section.
      const primary = this.allVisibleFields.find((f) => f.primary)
      const maxWidth =
        this.gridViewRowDetailsWidth +
        (primary ? this.getFieldWidth(primary) : 0) +
        300

      this.canFitInTwoColumns = this.$el.clientWidth > maxWidth
    },
    /**
     * Event called when the grid view element window resizes.
     */
    onWindowResize() {
      this.checkCanFitInTwoColumns()

      // Update the window height to dynamically show the right amount of rows.
      const height = this.$refs.left.$refs.body.clientHeight
      this.$store.dispatch(
        this.storePrefix + 'view/grid/setWindowHeight',
        height
      )
    },
    /**
     * Called when the user right clicks after selecting multiple cells.
     * Shows the context menu with the appropriate options.
     */
    getMultiSelectContextItems() {
      const selectedField = this.getSelectedField()
      if (selectedField) {
        const fieldType = this.$registry.get('field', selectedField.type)
        return fieldType.getGridViewContextItemsOnCellsSelection(selectedField)
      } else {
        return []
      }
    },
    /**
     * Returns the selected field if only one field is selected, otherwise returns null.
     */
    getSelectedField() {
      const selectedFields = this.$store.getters[
        this.storePrefix + 'view/grid/getSelectedFields'
      ](this.fields)
      return selectedFields.length === 1 ? selectedFields[0] : null
    },
    async getSelectedRowsFunction() {
      const fieldsAndRows = await this.$store.dispatch(
        this.storePrefix + 'view/grid/getCurrentSelection',
        { fields: this.fields }
      )
      return fieldsAndRows[1]
    },
  },
}
</script>
