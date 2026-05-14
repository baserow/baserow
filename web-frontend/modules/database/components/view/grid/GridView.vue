<template>
  <div
    ref="gridView"
    v-scroll="scroll"
    class="grid-view"
    :class="[
      {
        'grid-view--disable-selection': isMultiSelectActive,
      },
      'grid-view--row-height-' + view.row_height_size,
    ]"
  >
    <GridGrouped
      v-if="useGroupedV2"
      :view="view"
      :database="database"
      :table="table"
      :visible-fields="allVisibleFields"
      :all-fields-in-table="fields"
      :field-options="fieldOptions"
      :store-prefix="storePrefix"
      :workspace-id="database.workspace.id"
      :read-only="readOnly"
      @edit-start="onGroupedEditStart"
      @refresh="$emit('refresh', $event)"
      @field-created="fieldCreated"
    />
    <!--
      We keep the legacy GridViewSection-based body mounted even when
      ``useGroupedV2`` is active, hidden via ``display: none``. Several
      legacy methods + watchers reach into ``$refs.left`` / ``$refs.right``
      / ``$refs.scrollbars`` without guards — switching with ``v-if``
      tears those refs out and an in-flight watcher (e.g. the
      ``row`` deep-watcher, or any of the scroll handlers fired during
      the transition) immediately crashes with
      ``this.$refs.right.$refs`` undefined. Hiding instead of
      destroying keeps the refs alive for the duration of the
      session; the v2 path renders on top and owns the visible
      viewport. A follow-up extracting the legacy body into its own
      component will let us actually unmount it again.
    -->
    <div v-show="!useGroupedV2" class="grid-view__legacy-body">
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
        :all-visible-fields="allVisibleFields"
        :all-fields-in-table="fields"
        :decorations-by-place="decorationsByPlace"
        :database="database"
        :table="table"
        :view="view"
        :include-row-details="!viewHasGroupBys"
        :include-grid-view-identifier-dropdown="!viewHasGroupBys"
        :include-group-by="true"
        :can-order-fields="frozenColumnCount > 1"
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
        @field-dragging="startCrossSectionFieldDrag($event.field, $event.event)"
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
      <GridViewFreezeHandle
        v-if="
          canFitFrozenColumns &&
          !viewHasGroupBys &&
          allDraggableFields.length > 0
        "
        :view="view"
        :database="database"
        :fields="fields"
        :field-options="fieldOptions"
        :read-only="
          readOnly ||
          !$hasPermission(
            'database.table.view.update',
            view,
            database.workspace.id
          )
        "
        :row-details-width="gridViewRowDetailsWidth"
        :left-width="leftWidth"
        :get-field-width="getFieldWidth"
        @frozen-count-change="onFrozenCountDragChange"
      ></GridViewFreezeHandle>
      <HorizontalResize
        v-else-if="viewHasGroupBys && leftFields.length === 0"
        class="grid-view__divider-width"
        :style="{ left: leftWidth + 'px' }"
        :width="activeGroupBys[activeGroupBys.length - 1].width"
        :min="GRID_VIEW_MIN_FIELD_WIDTH"
        @move="
          moveGroupWidth(
            activeGroupBys[activeGroupBys.length - 1],
            view,
            $event
          )
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
        :all-visible-fields="allVisibleFields"
        :all-fields-in-table="fields"
        :decorations-by-place="decorationsByPlace"
        :database="database"
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
        @field-dragging="startCrossSectionFieldDrag($event.field, $event.event)"
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
      <GridViewFieldDragging
        ref="crossSectionFieldDragging"
        :view="view"
        :fields="allDraggableFields"
        :offset="crossSectionDraggingOffset"
        :read-only="
          readOnly ||
          !$hasPermission(
            'database.table.view.update_field_options',
            view,
            database.workspace.id
          )
        "
        :store-prefix="storePrefix"
        :get-scroll-element="getCrossSectionScrollElement"
        :get-scrollable-element="getCrossSectionScrollableElement"
        :frozen-section-width="leftWidth"
        @scroll="scroll(0, $event.pixelX)"
      ></GridViewFieldDragging>
      <GridViewRowDragging
        ref="rowDragging"
        :table="table"
        :view="view"
        :all-visible-fields="allVisibleFields"
        :all-fields-in-table="fields"
        :store-prefix="storePrefix"
        :offset="activeGroupByWidth"
        :get-scroll-element="getVerticalScrollbarElement"
        @scroll="scroll($event.pixelY, $event.pixelX)"
      ></GridViewRowDragging>
      <Context ref="rowContext" overflow-scroll max-height-if-outside-viewport>
        <ul v-show="isMultiSelectActive" class="context__menu">
          <component
            :is="contextItemComponent"
            v-for="(
              contextItemComponent, index
            ) in getMultiSelectContextItems()"
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
        <GridRowContextItems
          v-show="!isMultiSelectActive"
          :row="selectedRow"
          :read-only="readOnly"
          :can-create-row="canCreateRowFlat"
          :can-delete-row="canDeleteRowFlat"
          :can-select-row="true"
          @select-row="onContextSelectRow"
          @insert-above="onContextInsertAbove"
          @insert-below="onContextInsertBelow"
          @duplicate-row="onContextDuplicateRow"
          @copy-row-url="copyLinkToSelectedRow({}, $event)"
          @open-row-modal="onContextOpenRowModal"
          @delete-row="deleteRow($event)"
        />
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
        @navigate-previous="
          $emit('navigate-previous', $event, activeSearchTerm)
        "
        @navigate-next="$emit('navigate-next', $event, activeSearchTerm)"
        @refresh-row="refreshRow"
      ></RowEditModal>
    </div>
  </div>
</template>

<script>
import { mapGetters } from 'vuex'

import { notifyIf } from '@baserow/modules/core/utils/error'
import GridViewSection from '@baserow/modules/database/components/view/grid/GridViewSection'
import GridGrouped from '@baserow/modules/database/components/view/grid/GridGrouped'
import HorizontalResize from '@baserow/modules/core/components/HorizontalResize'
import GridViewFieldDragging from '@baserow/modules/database/components/view/grid/GridViewFieldDragging'
import GridViewFreezeHandle from '@baserow/modules/database/components/view/grid/GridViewFreezeHandle'
import GridViewRowDragging from '@baserow/modules/database/components/view/grid/GridViewRowDragging'
import RowEditModal from '@baserow/modules/database/components/row/RowEditModal'
import gridViewHelpers from '@baserow/modules/database/mixins/gridViewHelpers'
import { sortFieldsByOrderAndIdFunction } from '@baserow/modules/database/utils/view'
import { filterGridViewVisibleFieldsFunction } from '@baserow/modules/database/components/view/grid/utils'
import viewHelpers from '@baserow/modules/database/mixins/viewHelpers'
import { isElement } from '@baserow/modules/core/utils/dom'
import viewDecoration from '@baserow/modules/database/mixins/viewDecoration'
import { populateRow } from '@baserow/modules/database/store/view/grid'
import { clone } from '@baserow/modules/core/utils/object'
import copyPasteHelper from '@baserow/modules/database/mixins/copyPasteHelper'
import GridViewRowsAddContext from '@baserow/modules/database/components/view/grid/fields/GridViewRowsAddContext'
import GridRowContextItems from '@baserow/modules/database/components/view/grid/GridRowContextItems'
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
    GridViewFieldDragging,
    GridViewFreezeHandle,
    GridViewRowsAddContext,
    GridViewSection,
    GridViewRowDragging,
    RowEditModal,
    GridGrouped,
    GridRowContextItems,
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
  emits: ['navigate-next', 'navigate-previous', 'refresh', 'selected-row'],
  data() {
    return {
      lastHoveredRow: null,
      selectedRow: null,
      deletingRow: false,
      showHiddenFieldsInRowModal: false,
      // Whether the frozen columns fit in the viewport with enough remaining
      // space for the scrollable section. When false, frozen columns are disabled.
      canFitFrozenColumns: true,
      // When a cell is selected, the component will be propagated and stored into this
      // array until it's unselected. Having these components here can be useful if a
      // global keyboard shortcut must be blocked if a single line text field cell is
      // in an editing state for example.
      selectedCellComponents: [],
      // Set to true when the row is being refreshed to avoid multiple fields
      // submitting multiple refresh requests at the same time.
      refreshingRow: false,
      resizeObserver: null,
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
        .filter(filterGridViewVisibleFieldsFunction(fieldOptions))
        .sort(sortFieldsByOrderAndIdFunction(fieldOptions, true))
    },
    /**
     * Returns only the hidden fields in the correct order.
     */
    hiddenFields() {
      const fieldOptions = this.fieldOptions
      const isFieldVisible = filterGridViewVisibleFieldsFunction(fieldOptions)
      return this.rightFields
        .filter((field) => !isFieldVisible(field))
        .sort(sortFieldsByOrderAndIdFunction(fieldOptions))
    },
    viewHasGroupBys() {
      return this.activeGroupBys.length > 0
    },
    // Permission flags consumed by the shared `GridRowContextItems`
    // menu — same checks the inline lis used to do.
    canCreateRowFlat() {
      if (this.readOnly) return false
      if (this.table?.data_sync && !this.table.data_sync.two_way_sync)
        return false
      return (
        this.$hasPermission(
          'database.table.create_row',
          this.table,
          this.database.workspace.id
        ) ||
        this.$hasPermission(
          'database.table.view.create_row',
          this.view,
          this.database.workspace.id
        )
      )
    },
    canDeleteRowFlat() {
      if (this.readOnly) return false
      if (this.table?.data_sync && !this.table.data_sync.two_way_sync)
        return false
      return (
        this.$hasPermission(
          'database.table.delete_row',
          this.table,
          this.database.workspace.id
        ) ||
        this.$hasPermission(
          'database.table.view.delete_row',
          this.view,
          this.database.workspace.id
        )
      )
    },
    useGroupedV2() {
      // Whenever a group-by is configured, hand the body off to the
      // new Airtable-style `GridGrouped` component. Flat (no
      // group-by) views stay on the legacy two-pane layout, which is
      // why this module's name leads with V2 — it is opt-in by view
      // configuration, not by user toggle.
      return this.viewHasGroupBys
    },
    frozenColumnCount() {
      return this.view.frozen_column_count ?? 1
    },
    hasFrozenColumns() {
      return (
        this.canFitFrozenColumns &&
        !this.viewHasGroupBys &&
        this.frozenColumnCount > 0
      )
    },
    isEditable() {
      return (
        !this.readOnly &&
        this.$hasPermission(
          'database.table.view.update',
          this.view,
          this.database.workspace.id
        )
      )
    },
    /**
     * Returns the fields that should be displayed in the frozen left section.
     * Takes the first N fields visible in the grid in sort order. The primary
     * field is always included, even if its field options mark it as hidden.
     */
    leftFields() {
      if (!this.hasFrozenColumns) {
        return []
      }
      const fieldOptions = this.fieldOptions
      const sorted = this.fields
        .slice()
        .filter(filterGridViewVisibleFieldsFunction(fieldOptions))
        .sort(sortFieldsByOrderAndIdFunction(fieldOptions, true))
      return sorted.slice(0, this.frozenColumnCount)
    },
    /**
     * Returns the fields that should be displayed in the scrollable right section.
     */
    rightFields() {
      if (!this.hasFrozenColumns) {
        return this.fields
      }
      const leftIds = new Set(this.leftFields.map((f) => f.id))
      return this.fields.filter((f) => !leftIds.has(f.id))
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
    /**
     * All non-primary visible fields in order, used by the cross-section
     * field dragging component when frozen columns > 1.
     */
    allDraggableFields() {
      return this.allVisibleFields.filter((f) => !f.primary)
    },
    crossSectionDraggingOffset() {
      const primary = this.fields.find((f) => f.primary)
      return (
        this.activeGroupByWidth +
        this.gridViewRowDetailsWidth +
        (primary ? this.getFieldWidth(primary) : 0)
      )
    },
    activeSearchTerm() {
      return this.$store.getters[
        `${this.storePrefix}view/grid/getActiveSearchTerm`
      ]
    },
    allRows() {
      return this.$store.getters[this.storePrefix + 'view/grid/getAllRows']
    },
    isMultiSelectActive() {
      return this.$store.getters[
        this.storePrefix + 'view/grid/isMultiSelectActive'
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
    'view.frozen_column_count'() {
      // When the frozen column count changes (e.g. real-time sync from another
      // user), recalculate the viewport fit and update scrollbars. Use $nextTick
      // so the DOM reflects the new leftWidth before scrollbar recalculates.
      this.$nextTick(() => this.fieldsUpdated())
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
    useGroupedV2(now) {
      // Switching the view from "no group-by" to "grouped" (or back)
      // needs to re-seed the gridGrouped module so the right group
      // tree + collapse state are in place for the new shape.
      if (now) this.initializeGroupedV2()
    },
    activeGroupBys: {
      deep: true,
      handler(now, prev) {
        if (!this.useGroupedV2) return
        // Detect any change to the group-by config — added, removed,
        // reordered, or a field was swapped for another.
        const changed =
          !prev ||
          now.length !== prev.length ||
          now.some(
            (gb, i) =>
              gb.field !== prev[i]?.field || gb.order !== prev[i]?.order
          )
        if (changed) this.initializeGroupedV2()
      },
    },
  },
  /*beforeCreate() {
    this.$options.computed = {
      ...(this.$options.computed || {}),
      ...mapGetters({
        allRows: this.$options.propsData.storePrefix + 'view/grid/getAllRows',
        isMultiSelectActive:
          this.$options.propsData.storePrefix + 'view/grid/isMultiSelectActive',
      }),
    }
  },*/
  created() {
    // When the grid view is created we want to update the scrollbars.
    this.fieldsUpdated()
  },
  beforeMount() {
    this.$bus.$on('field-deleted', this.fieldDeleted)
  },
  mounted() {
    this.resizeObserver = new ResizeObserver(this.onWindowResize)
    this.resizeObserver.observe(this.$refs.gridView)
    window.addEventListener('keydown', this.keyDownEvent)
    window.addEventListener('copy', this.copySelection)
    window.addEventListener('paste', this.pasteFromMultipleCellSelection)
    window.addEventListener('click', this.cancelMultiSelectIfActive)
    window.addEventListener('mouseup', this.multiSelectStop)
    this.$store.dispatch(
      this.storePrefix + 'view/grid/fetchAllFieldAggregationData',
      { view: this.view }
    )
    this.onWindowResize()

    if (this.row !== null) {
      this.populateAndEditRow(this.row)
    }
    if (this.useGroupedV2) {
      this.initializeGroupedV2()
    }
  },
  beforeUnmount() {
    if (this.resizeObserver !== null) {
      this.resizeObserver.disconnect()
      this.resizeObserver = null
    }
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
    initializeGroupedV2() {
      const groupByFields = (this.activeGroupBys ?? [])
        .map((gb) => this.fields.find((f) => f.id === gb.field))
        .filter(Boolean)
      const collapseMode = groupByFields.length > 0 ? 'collapse' : 'expand'
      this.$store.dispatch(this.storePrefix + 'view/gridGrouped/initialize', {
        gridId: this.view.id,
        groupByFields,
        sortings: this.view.sortings,
        collapseMode,
        registry: this.$registry,
      })
    },
    onGroupedEditStart({ row } = {}) {
      // The row edit modal is owned by GridView (it's mounted once
      // for both grid variants). When the grouped grid wants to open
      // a row, it emits `edit-start` and we forward to the same
      // `openRowEditModal` the flat grid uses. The modal's update
      // flow routes back through `updateValue`, which dispatches the
      // grouped store action when V2 is active.
      if (!row) return
      this.openRowEditModal(row)
    },
    onFrozenCountDragChange() {
      // During drag we don't persist anything — the freeze handle component
      // handles the optimistic save on mouseup.
    },
    /**
     * Returns a non-scrolling element for the cross-section field dragging.
     * The grid view container itself doesn't scroll horizontally, which is
     * correct since the dragging operates across both sections.
     */
    getCrossSectionScrollElement() {
      return this.$refs.gridView
    },
    getCrossSectionScrollableElement() {
      return this.$refs.right.$el
    },
    /**
     * Called when a non-primary field header is dragged in either section.
     * Delegates to the shared cross-section field dragging component.
     */
    startCrossSectionFieldDrag(field, event) {
      if (this.$refs.crossSectionFieldDragging && !field.primary) {
        this.$refs.crossSectionFieldDragging.start(field, event)
      }
    },
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
        if (elementLeft < 0 && (!this.hasFrozenColumns || !fieldPrimary)) {
          // If the field isn't visible in the viewport we need to scroll left in order
          // to show it.
          this.horizontalScroll(
            elementLeft + horizontalContainer.scrollLeft - 20
          )
          this.$refs.scrollbars.updateHorizontal()
        } else if (
          elementRight > horizontalContainerWidth &&
          (!this.hasFrozenColumns || !fieldPrimary)
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
    // Adapter handlers for the shared `GridRowContextItems` menu.
    // The menu component emits the row only; we synthesise a stub
    // event so existing handlers that read `preventFieldCellUnselect`
    // keep working (the flag was set on the click event inside the
    // shared component before dispatch).
    onContextSelectRow(row) {
      this.selectRow(this._stubMenuEvent(), row)
      this.$refs.rowContext.hide()
    },
    onContextInsertAbove(row) {
      this.addRowAboveSelectedRow(this._stubMenuEvent(), row)
    },
    onContextInsertBelow(row) {
      this.addRowBelowSelectedRow(this._stubMenuEvent(), row)
    },
    onContextDuplicateRow(row) {
      this.duplicateSelectedRow(this._stubMenuEvent(), row)
    },
    _stubMenuEvent() {
      // The shared `GridRowContextItems` component already sets
      // `preventFieldCellUnselect = true` on the actual click event
      // before emitting, so we only need a stub with the
      // `stopPropagation` no-op the existing `selectRow` calls.
      return { preventFieldCellUnselect: true, stopPropagation: () => {} }
    },
    onContextOpenRowModal(row) {
      this.openRowEditModal(row)
      this.$refs.rowContext.hide()
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
        this.$config.public.baserowEmbeddedShareUrl +
        this.$router.resolve({
          name: 'database-table-row',
          params: { ...this.$route.params, rowId: selectedRow.id },
        }).href
      copyToClipboard(url)
      this.$store.dispatch('toast/info', {
        title: this.$t('gridView.copiedRowURL'),
        message: this.$t('gridView.copiedRowURLMessage', {
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
      // GridGrouped owns its own scrollbars/layout; the legacy
      // scrollbars + frozen-column refs simply aren't mounted while
      // the grouped path is active. Bail before touching them.
      if (this.useGroupedV2) return
      const scrollbars = this.$refs.scrollbars
      // Vue can sometimes trigger this via watch before the child component
      // scrollbars has been created, check it exists and has the expected method
      if (scrollbars && scrollbars.update) {
        scrollbars.update()
      }

      // When anything related to the fields has been updated, it could be that it
      // doesn't fit in two columns anymore. Calling this method checks that.
      this.checkCanFitFrozenColumns()
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
        const action = this.useGroupedV2
          ? this.storePrefix + 'view/gridGrouped/updateRowValue'
          : this.storePrefix + 'view/grid/updateRowValue'
        await this.$store.dispatch(action, {
          table: this.table,
          view: this.view,
          fields: this.fields,
          row,
          field,
          value,
          oldValue,
          isRowOpenedInModal: this.isRowOpenedInModal,
        })
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
      // Grouped path owns its own scroll container — let the wheel
      // event flow to the browser instead of swallowing it. The
      // directive `v-scroll` only calls `preventDefault` when this
      // returns falsy.
      if (this.useGroupedV2) return true
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

      if (
        row === undefined ||
        !Object.prototype.hasOwnProperty.call(row, 'id')
      ) {
        return
      }

      if (this.useGroupedV2) {
        this.$store.dispatch(
          this.storePrefix + 'view/gridGrouped/refreshRowAfterChange',
          { rowId: row.id }
        )
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
      if (this.useGroupedV2) {
        await this.$store.dispatch(
          this.storePrefix + 'view/gridGrouped/refreshForViewConfigChange',
          { sortings: clone(this.view.sortings || []) }
        )
        return
      }
      await this.$store.dispatch(
        this.storePrefix + 'view/grid/visibleByScrollTop',
        this.$refs.right.$refs.body.scrollTop
      )
      // The grid view store keeps a copy of the group bys that must only be updated
      // after the refresh of the page. This is because the group by depends on the rows
      // being sorted, and this will only be the case after a refresh.
      await this.$store.dispatch(
        this.storePrefix + 'view/grid/updateActiveGroupBys',
        clone(this.view.group_bys || [])
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
        (!isElement(this.$refs.gridView, event.target) ||
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
      const pageSizeLimit = this.$config.public.baserowRowPageSizeLimit
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
            fields: this.fields,
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
     * Checks whether the frozen columns fit in the viewport with at least 300px
     * remaining for the scrollable section. Updates `canFitFrozenColumns`.
     */
    checkCanFitFrozenColumns() {
      if (!this.$refs.gridView) {
        return
      }

      const fieldOptions = this.fieldOptions
      const sorted = this.fields
        .slice()
        .filter(filterGridViewVisibleFieldsFunction(fieldOptions))
        .sort(sortFieldsByOrderAndIdFunction(fieldOptions, true))
      const frozenWidth = sorted
        .slice(0, this.frozenColumnCount)
        .reduce((sum, field) => sum + this.getFieldWidth(field), 0)
      const maxWidth = this.gridViewRowDetailsWidth + frozenWidth + 300
      this.canFitFrozenColumns = this.$refs.gridView.clientWidth > maxWidth
    },
    /**
     * Event called when the grid view element window resizes.
     */
    onWindowResize() {
      this.checkCanFitFrozenColumns()
      // GridGrouped owns its own viewport sizing; the legacy
      // left/right refs don't exist when its branch is active. Bail
      // out before reading them.
      if (this.useGroupedV2) return

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
