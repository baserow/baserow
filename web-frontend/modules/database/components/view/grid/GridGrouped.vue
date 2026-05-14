<template>
  <div class="grid-grouped">
    <Scrollbars
      ref="scrollbars"
      vertical="getScrollEl"
      horizontal="getScrollEl"
      @vertical="onScrollbarVertical"
      @horizontal="onScrollbarHorizontal"
    />
    <div
      class="grid-grouped__head"
      :style="{
        transform: 'translateX(' + -horizontalScroll + 'px)',
        width: canvasWidth + 'px',
      }"
    >
      <GridViewHead
        :visible-fields="visibleFields"
        :database="database"
        :table="table"
        :view="view"
        :all-fields-in-table="allFieldsInTable"
        :include-row-details="true"
        :include-group-by="false"
        :include-add-field="false"
        :include-grid-view-identifier-dropdown="false"
        :read-only="readOnly"
        :store-prefix="storePrefix"
        @refresh="$emit('refresh', $event)"
        @field-created="$emit('field-created', $event)"
        @dragging="onFieldDragStart"
      />
    </div>
    <div ref="scroll" class="grid-grouped__scroll" @scroll.passive="onScroll">
      <div
        class="grid-grouped__canvas"
        :style="{
          height: totalHeight + 'px',
          width: canvasWidth + 'px',
        }"
      >
        <template v-for="item in visibleItems" :key="itemKey(item)">
          <GridGroupedBanner
            v-if="item.type === 'header'"
            :item="item"
            :group-by-fields="groupByFields"
            :total-width="canvasWidth"
            :primary-field-width="primaryFieldWidth"
            :id-lane-width="idLaneWidth"
            :workspace-id="workspaceId"
            @toggle="onToggleCollapse"
          />
          <GridGroupedRow
            v-else-if="item.type === 'row'"
            :item="item"
            :visible-fields="visibleFields"
            :all-fields-in-table="allFieldsInTable"
            :field-options="fieldOptions"
            :workspace-id="workspaceId"
            :store-prefix="storePrefix"
            :read-only="readOnly"
            :can-drag="canDragRow"
            :table="table"
            :decorations-by-place="decorationsByPlace"
            :selected-cell="selectedCell"
            @cell-select="onCellSelect"
            @cell-unselect="onCellUnselect"
            @cell-selected-presence="onCellSelectedPresence"
            @cell-unselected-presence="onCellUnselectedPresence"
            @update="onCellUpdate"
            @paste="onMultiplePasteFromCell"
            @row-context="onRowContext"
            @row-dragging="onRowDragStart"
            @edit-modal="onOpenRowModal"
            @cell-mousedown-left="onAreaMousedown"
            @cell-mouseover="onAreaMouseover"
            @cell-mouseup-left="onAreaMouseup"
            @cell-shift-click="onAreaShiftClick"
          />
          <GridGroupedPlaceholder
            v-else-if="item.type === 'placeholder'"
            :item="item"
          />
          <GridGroupedRowAdd
            v-else-if="item.type === 'addRow'"
            :item="item"
            :total-width="canvasWidth"
            :id-lane-width="idLaneWidth"
            @add-row="onAddRowToGroup"
          />
        </template>
        <GridGroupedRowDragging
          ref="rowDragging"
          :table="table"
          :view="view"
          :store-prefix="storePrefix"
          :width="canvasWidth"
          :visible-items="visibleItems"
          :all-fields-in-table="allFieldsInTable"
          :get-scroll-element="getScrollEl"
          @scroll="onDragAutoScroll"
        />
        <GridViewFieldDragging
          ref="fieldDragging"
          :view="view"
          :fields="visibleFields"
          :read-only="readOnly"
          :store-prefix="storePrefix"
          :get-scroll-element="getScrollEl"
          :get-scrollable-element="getScrollEl"
          :frozen-section-width="0"
          :offset="idLaneWidth"
          @scroll="onFieldDragScroll"
        />
      </div>
    </div>
    <Context ref="rowContext" overflow-scroll max-height-if-outside-viewport>
      <GridMultiRowContextItems
        v-if="multiRowSelectionActive"
        :can-delete-rows="canDeleteRow"
        :loading="bulkDeleting"
        @copy-cells="onCopyCellsFromSelection(false)"
        @copy-cells-with-header="onCopyCellsFromSelection(true)"
        @delete-rows="onDeleteSelectedRows"
      />
      <GridRowContextItems
        v-else
        :row="contextRow"
        :read-only="readOnly"
        :can-create-row="canCreateRow"
        :can-delete-row="canDeleteRow"
        :can-select-row="true"
        @select-row="onSelectRow"
        @insert-above="onInsertAbove"
        @insert-below="onInsertBelow"
        @duplicate-row="onDuplicateRow"
        @copy-row-url="onCopyRowURL"
        @open-row-modal="onOpenRowModal"
        @delete-row="onDeleteContextRow"
      />
    </Context>
    <div
      class="grid-view__foot grid-grouped__foot"
      :style="{
        transform: 'translateX(' + -horizontalScroll + 'px)',
        width: canvasWidth + 'px',
      }"
    >
      <div
        class="grid-view__foot-info"
        :style="{ width: idLaneWidth + 'px' }"
      >
        {{ $t('gridView.rowCount', { count: totalRowCount }) }}
      </div>
      <div
        v-for="field in visibleFields"
        :key="'foot-' + field.id"
        :style="{ width: cellWidth(field) + 'px' }"
      >
        <GridViewFieldFooter
          :database="database"
          :field="field"
          :view="view"
          :store-prefix="storePrefix"
        />
      </div>
    </div>
  </div>
</template>

<script>
/**
 * Container for the Airtable-style grouped grid view.
 *
 * Pulls state from the `page/view/gridGrouped` Vuex module + a few
 * config props (visibleFields, fieldOptions, sortings) and feeds them
 * through the pure render core to derive a flat list of DOM-shape
 * items: `header`, `row`, `placeholder`. Each item type maps to its
 * dedicated component (Banner / Row / Placeholder).
 *
 * State subscriptions are all `computed` properties so the items list
 * re-derives automatically when any input changes — there is no
 * imperative "update the DOM after this mutation" code path.
 *
 * Per-section caching: row buckets live in the store as
 * `Map<sectionKey, Map<position, row>>` and are invariant of which
 * other groups are expanded. Toggling a group's collapse no longer
 * invalidates anything — the bucket survives.
 *
 * Scroll handling: native scroll event → `SET_VIEWPORT` mutation →
 * `visibleItems` re-derives. The intrinsic scroll height is the
 * layout's `totalHeight` so the scrollbar reflects the full content
 * size, including collapsed groups (their headers still contribute
 * pixels — the collapsed content does not).
 */
import GridGroupedBanner from '@baserow/modules/database/components/view/grid/GridGroupedBanner'
import GridGroupedRow from '@baserow/modules/database/components/view/grid/GridGroupedRow'
import GridGroupedPlaceholder from '@baserow/modules/database/components/view/grid/GridGroupedPlaceholder'
import GridGroupedRowAdd from '@baserow/modules/database/components/view/grid/GridGroupedRowAdd'
import GridGroupedRowDragging from '@baserow/modules/database/components/view/grid/GridGroupedRowDragging'
import GridViewFieldDragging from '@baserow/modules/database/components/view/grid/GridViewFieldDragging'
import GridViewHead from '@baserow/modules/database/components/view/grid/GridViewHead'
import GridViewFieldFooter from '@baserow/modules/database/components/view/grid/GridViewFieldFooter'
import GridRowContextItems from '@baserow/modules/database/components/view/grid/GridRowContextItems'
import GridMultiRowContextItems from '@baserow/modules/database/components/view/grid/GridMultiRowContextItems'
import Scrollbars from '@baserow/modules/core/components/Scrollbars'
import Context from '@baserow/modules/core/components/Context'
import { copyToClipboard } from '@baserow/modules/database/utils/clipboard'
import {
  renderViewport,
  pathKey,
  isPathCollapsed,
} from '@baserow/modules/database/utils/gridGroupedRender'
import { notifyIf } from '@baserow/modules/core/utils/error'
import {
  GRID_VIEW_MULTI_SELECT_AREA,
  GRID_VIEW_SIZE_TO_ROW_HEIGHT_MAPPING,
} from '@baserow/modules/database/constants'
import copyPasteHelper from '@baserow/modules/database/mixins/copyPasteHelper'

export default {
  name: 'GridGrouped',
  components: {
    GridGroupedBanner,
    GridGroupedRow,
    GridGroupedPlaceholder,
    GridGroupedRowAdd,
    GridGroupedRowDragging,
    GridViewFieldDragging,
    GridViewHead,
    GridViewFieldFooter,
    GridRowContextItems,
    GridMultiRowContextItems,
    Scrollbars,
    Context,
  },
  props: {
    storePrefix: {
      type: String,
      default: 'page/',
    },
    view: {
      type: Object,
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
    visibleFields: {
      type: Array,
      required: true,
    },
    fieldOptions: {
      type: Object,
      default: () => ({}),
    },
    workspaceId: {
      type: null,
      default: null,
    },
    allFieldsInTable: {
      type: Array,
      default: () => [],
    },
    readOnly: {
      type: Boolean,
      default: false,
    },
  },
  mixins: [copyPasteHelper],
  emits: ['edit-start', 'refresh', 'field-created'],
  data() {
    return {
      // Horizontal scroll position; mirrors `scroll.scrollLeft` so the
      // column header strip translates in sync with the body without
      // sitting inside the scroller (which would let it scroll
      // vertically too).
      horizontalScroll: 0,
      // Row whose right-click menu is currently open. Cleared when
      // the Context hides.
      contextRow: null,
      // True while the multi-row "Delete rows" action is pending.
      bulkDeleting: false,
      // Drag-select auto-scroll state. Non-reactive on purpose —
      // re-rendering doesn't depend on these and we want the
      // requestAnimationFrame loop to read fresh values without
      // wrestling Vue's reactivity tracking.
      _autoScrollHandle: null,
      _lastDragY: null,
      _dragAnchor: null,
    }
  },
  computed: {
    storeNs() {
      return this.storePrefix + 'view/gridGrouped'
    },
    layout() {
      return this.$store.getters[this.storeNs + '/layout']
    },
    collapse() {
      return this.$store.getters[this.storeNs + '/collapse']
    },
    sectionRows() {
      return this.$store.getters[this.storeNs + '/sectionRows']
    },
    pendingMutations() {
      return this.$store.getters[this.storeNs + '/pendingMutations']
    },
    viewport() {
      return this.$store.getters[this.storeNs + '/viewport']
    },
    groupByFields() {
      return this.$store.getters[this.storeNs + '/groupByFields']
    },
    selectedCell() {
      return this.$store.getters[this.storeNs + '/selectedCell']
    },
    activeSearchTerm() {
      return this.$store.getters[
        this.storePrefix + 'view/grid/getActiveSearchTerm'
      ]
    },
    hideRowsNotMatchingSearch() {
      return this.$store.getters[
        this.storePrefix + 'view/grid/isHidingRowsNotMatchingSearch'
      ]
    },
    // View decorations grouped by their `place` (first_cell, wrapper).
    // Mirrors the flat grid's `viewDecoration` mixin — inlined here
    // to avoid the mixin's `fields` prop coupling.
    decorationsByPlace() {
      const decorations = this.view?.decorations ?? []
      const grouped = {}
      for (const decoration of decorations) {
        const decoratorType = this.$registry.get(
          'viewDecorator',
          decoration.type
        )
        if (decoratorType.isDeactivated(this.database.workspace.id)) continue
        if (!decoration.value_provider_type) continue
        const valueProviderType = this.$registry.get(
          'decoratorValueProvider',
          decoration.value_provider_type
        )
        const deco = {
          decoration,
          decoratorType,
          valueProviderType,
          component: decoratorType.getComponent(this.database.workspace.id),
          place: decoratorType.getPlace(),
          propsFn: (row) => ({
            value: valueProviderType.getValue({
              row,
              fields: this.allFieldsInTable,
              options: decoration.value_provider_conf,
            }),
          }),
        }
        const place = deco.place
        grouped[place] = [...(grouped[place] ?? []), deco]
      }
      return grouped
    },
    visibleItems() {
      return renderViewport({
        layout: this.layout,
        sectionRows: this.sectionRows,
        pending: this.pendingMutations,
        viewport: this.viewport,
        fields: this.groupByFields,
        rowHeight: this.rowHeight,
      })
    },
    rowHeight() {
      return this.$store.getters[this.storeNs + '/rowHeight']
    },
    totalHeight() {
      return this.layout.totalHeight
    },
    totalRowCount() {
      return this.$store.getters[this.storeNs + '/totalRowCount']
    },
    idLaneWidth() {
      return 72
    },
    canvasWidth() {
      const cellsWidth = this.visibleFields.reduce(
        (sum, f) => sum + (this.fieldOptions[f.id]?.width ?? 200),
        0
      )
      return this.idLaneWidth + cellsWidth
    },
    primaryFieldWidth() {
      const primary = this.visibleFields[0]
      return primary ? (this.fieldOptions[primary.id]?.width ?? 200) : 200
    },
    canCreateRow() {
      // Mirrors the permission check the flat grid uses for "+Add row"
      // / "insert above" / "insert below" / "duplicate".
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
    canDeleteRow() {
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
    canDragRow() {
      if (this.readOnly) return false
      return this.$hasPermission(
        'database.table.update_row',
        this.table,
        this.database.workspace.id
      )
    },
    // Checkbox selection lives in the flat `view/grid` store (single
    // source of truth across both grids). When one or more rows are
    // checked, the right-click menu pivots to multi-row actions.
    checkboxSelectedRowIds() {
      return (
        this.$store.getters[
          this.storePrefix + 'view/grid/getCheckboxSelectedRowsIds'
        ] ?? []
      )
    },
    areaSelectionActive() {
      return this.$store.getters[
        this.storePrefix + 'view/grid/isMultiSelectActive'
      ]
    },
    multiRowSelectionActive() {
      // Either: explicit checkbox selection (Set<rowId>) or an
      // active area rectangle. Both trigger the multi-row menu
      // variant so users get the same set of bulk actions.
      return (
        this.checkboxSelectedRowIds.length > 0 || this.areaSelectionActive
      )
    },
    // Row ids inside the current area selection — used by the
    // multi-row delete / copy when triggered from a rectangle (not
    // from explicit checkbox ticks).
    selectionRowIds() {
      if (this.checkboxSelectedRowIds.length > 0) {
        return this.checkboxSelectedRowIds
      }
      if (!this.areaSelectionActive) return []
      const slots =
        this.$store.getters[this.storeNs + '/linearisedRowSlots']
      const [minRow, maxRow] =
        this.$store.getters[
          this.storePrefix + 'view/grid/getMultiSelectRowIndexSorted'
        ]
      const ids = []
      for (let i = minRow; i <= maxRow && i < slots.length; i++) {
        const id = slots[i]?.rowId
        if (id != null) ids.push(id)
      }
      return ids
    },
  },
  mounted() {
    this.syncViewport()
    if (typeof ResizeObserver !== 'undefined') {
      this._resizeObserver = new ResizeObserver(() => {
        this.syncViewport()
        if (this.$refs.scrollbars && this.$refs.scrollbars.update) {
          this.$refs.scrollbars.update()
        }
      })
      this._resizeObserver.observe(this.$refs.scroll)
      const canvas = this.$refs.scroll?.firstElementChild
      if (canvas) this._resizeObserver.observe(canvas)
    }
    window.addEventListener('keydown', this.onKeyDown)
    window.addEventListener('mouseup', this.onWindowMouseUp)
    window.addEventListener('click', this.onWindowClick)
    window.addEventListener('copy', this.onCopyEvent)
    window.addEventListener('paste', this.onPasteEvent)
  },
  beforeUnmount() {
    if (this._resizeObserver) {
      this._resizeObserver.disconnect()
      this._resizeObserver = null
    }
    if (this._ensureFetchTimer) {
      clearTimeout(this._ensureFetchTimer)
      this._ensureFetchTimer = null
    }
    this.stopDragAutoScroll()
    window.removeEventListener('keydown', this.onKeyDown)
    window.removeEventListener('mouseup', this.onWindowMouseUp)
    window.removeEventListener('click', this.onWindowClick)
    window.removeEventListener('copy', this.onCopyEvent)
    window.removeEventListener('paste', this.onPasteEvent)
  },
  watch: {
    viewport() {
      this.scheduleEnsureRowsForViewport()
    },
    totalHeight() {
      this.scheduleEnsureRowsForViewport()
      this.$nextTick(() => {
        if (this.$refs.scrollbars && this.$refs.scrollbars.update) {
          this.$refs.scrollbars.update()
        }
      })
    },
    canvasWidth() {
      this.$nextTick(() => {
        if (this.$refs.scrollbars && this.$refs.scrollbars.update) {
          this.$refs.scrollbars.update()
        }
      })
    },
    // View filters / sortings reload — group sizes + sort order
    // change, so every section needs a fresh fetch. Deep-watched
    // because `view.filters` is an array of objects that gets
    // patched in place when the user edits a value.
    'view.filters': {
      deep: true,
      handler() {
        this.$store.dispatch(this.storeNs + '/refreshForViewConfigChange', {})
      },
    },
    'view.filter_type': {
      handler() {
        this.$store.dispatch(this.storeNs + '/refreshForViewConfigChange', {})
      },
    },
    'view.filters_disabled': {
      handler() {
        this.$store.dispatch(this.storeNs + '/refreshForViewConfigChange', {})
      },
    },
    'view.sortings': {
      deep: true,
      handler(sortings) {
        this.$store.dispatch(this.storeNs + '/refreshForViewConfigChange', {
          sortings,
        })
      },
    },
    // Row height size changed (small/medium/large). Map to the
    // shared pixel constants and push into the grouped store, then
    // re-render. The cells themselves honour the size via the
    // `.grid-view--row-height-{size}` class on a flat ancestor; the
    // grouped layout just needs the matching height for its
    // absolute-positioned shells.
    'view.row_height_size': {
      immediate: true,
      handler(size) {
        const px = GRID_VIEW_SIZE_TO_ROW_HEIGHT_MAPPING[size] ?? 33
        this.$store.commit(this.storeNs + '/SET_ROW_HEIGHT', px)
      },
    },
    // Group-by config changed (different field, re-order, or
    // add/remove). Resolve each group_by entry's `field` id to its
    // full field object so the grouped store can compute leaf paths
    // and sort functions against the new fields. A change here
    // structurally invalidates the tree + section buckets — the
    // store's `refreshForViewConfigChange` action resets them.
    'view.group_bys': {
      deep: true,
      handler(groupBys) {
        if (!Array.isArray(groupBys)) return
        const resolved = groupBys
          .map((gb) => this.allFieldsInTable.find((f) => f.id === gb.field))
          .filter(Boolean)
        const current = this.groupByFields
        const sameLength = current.length === resolved.length
        const sameIds =
          sameLength &&
          current.every((f, i) => f.id === resolved[i].id)
        if (sameIds) return
        this.$store.dispatch(this.storeNs + '/refreshForViewConfigChange', {
          groupByFields: resolved,
        })
      },
    },
    // Search: react to changes from the global search bar. The flat
    // store owns `activeSearchTerm` + `hideRowsNotMatchingSearch`; we
    // mirror them into the grouped store via `setActiveSearch`,
    // which structurally refetches when hide-mode is on (BE filters
    // out non-matching rows so row counts shrink) and re-runs the
    // per-row `_.matchSearch` flags for highlight rendering when
    // hide-mode is off.
    activeSearchTerm: {
      handler() {
        this.onSearchChange()
      },
    },
    hideRowsNotMatchingSearch: {
      handler() {
        this.onSearchChange()
      },
    },
  },
  methods: {
    cellWidth(field) {
      return this.fieldOptions[field.id]?.width ?? 200
    },
    syncViewport() {
      const el = this.$refs.scroll
      if (!el) return
      this.$store.commit(this.storeNs + '/SET_VIEWPORT', {
        scrollTop: el.scrollTop,
        clientHeight: el.clientHeight,
      })
      this.horizontalScroll = el.scrollLeft
    },
    onScroll() {
      this.syncViewport()
      if (this.$refs.scrollbars && this.$refs.scrollbars.update) {
        this.$refs.scrollbars.update()
      }
    },
    getScrollEl() {
      return this.$refs.scroll
    },
    refreshGroupedSearchMatches() {
      const flatStore = this.storePrefix + 'view/grid/'
      // Iterate every loaded row across every section bucket and run
      // the same per-row search match the flat grid runs. The
      // mutation mutates `row._.matchSearch` directly, and the row
      // reference is shared with the grouped section bucket, so the
      // cell re-renders via Vue's reactivity.
      for (const bucket of this.sectionRows.values()) {
        for (const row of bucket.values()) {
          this.$store.dispatch(flatStore + 'updateSearchMatchesForRow', {
            row,
            fields: this.allFieldsInTable,
            forced: true,
          })
        }
      }
    },
    async onSearchChange() {
      await this.$store.dispatch(this.storeNs + '/setActiveSearch', {
        activeSearchTerm: this.activeSearchTerm,
        hideRowsNotMatchingSearch: this.hideRowsNotMatchingSearch,
      })
      // In highlight-mode (hide off), `setActiveSearch` does no BE
      // refetch — the BE still returns every row in each section.
      // Apply the per-row match flags client-side so cells render
      // the yellow highlight without waiting for new data.
      if (!this.hideRowsNotMatchingSearch) {
        this.refreshGroupedSearchMatches()
      }
    },
    onScrollbarVertical(top) {
      if (this.$refs.scroll) this.$refs.scroll.scrollTop = top
    },
    onScrollbarHorizontal(left) {
      if (this.$refs.scroll) this.$refs.scroll.scrollLeft = left
    },
    async onToggleCollapse(path) {
      // Collapse changes the linearised row index of every following
      // row, which invalidates an active area selection. Clear it
      // before mutating layout — same hook the flat grid uses on
      // sort/filter/view changes.
      this.$store.dispatch(
        this.storePrefix + 'view/grid/clearAndDisableMultiSelect'
      )
      const fields = this.groupByFields
      const scrollEl = this.$refs.scroll
      const targetKey = pathKey(path, fields.slice(0, Object.keys(path).length))
      const wasCollapsed = isPathCollapsed(path, this.collapse, fields)

      // Capture the banner's screen-relative offset before the toggle.
      // The clicked banner's absolute y doesn't change across the
      // toggle (only stuff after it shifts), so anchoring the banner
      // back to its previous screen offset preserves the user's
      // visual context.
      const bannerBefore = this.layout.items.find(
        (it) =>
          it.type === 'header' &&
          pathKey(it.path, fields.slice(0, Object.keys(it.path).length)) ===
            targetKey
      )
      const scrollTopBefore = scrollEl?.scrollTop ?? 0
      const bannerScreenOffset = bannerBefore
        ? bannerBefore.y - scrollTopBefore
        : 0

      await this.$store.dispatch(this.storeNs + '/toggleCollapse', path)
      await this.$nextTick()

      if (!scrollEl) {
        this.syncViewport()
        return
      }

      const bannerAfter = this.layout.items.find(
        (it) =>
          it.type === 'header' &&
          pathKey(it.path, fields.slice(0, Object.keys(it.path).length)) ===
            targetKey
      )
      if (bannerAfter) {
        let desired
        if (wasCollapsed) {
          // Just expanded: if the banner sat in the lower half of the
          // viewport, the newly-revealed rows would land below the
          // viewport edge — bring the banner to the top so the user
          // immediately sees the first rows of the expanded group.
          // Otherwise leave the banner where it was.
          const inLowerHalf =
            bannerScreenOffset > scrollEl.clientHeight / 2
          desired = inLowerHalf
            ? bannerAfter.y
            : bannerAfter.y - bannerScreenOffset
        } else {
          // Just collapsed: keep the banner at its previous screen
          // position. Browser-clamping at scrollHeight handles the
          // case where the canvas shrank below the old scrollTop.
          desired = bannerAfter.y - bannerScreenOffset
        }
        const clamped = Math.max(
          0,
          Math.min(desired, scrollEl.scrollHeight - scrollEl.clientHeight)
        )
        if (Math.abs(scrollEl.scrollTop - clamped) > 1) {
          scrollEl.scrollTop = clamped
        }
      }
      this.syncViewport()
    },
    onEditStart({ row, field }) {
      this.$emit('edit-start', { row, field })
    },
    onCellSelect({ rowId, fieldId }) {
      if (rowId == null || fieldId == null) return
      this.$store.dispatch(this.storeNs + '/selectCell', { rowId, fieldId })
    },
    onCellUnselect() {
      this.$store.dispatch(this.storeNs + '/clearCellSelection')
    },
    async onCellUpdate({ row, field, value, oldValue }) {
      try {
        await this.$store.dispatch(this.storeNs + '/updateRowValue', {
          table: this.table,
          view: this.view,
          fields: this.allFieldsInTable,
          row,
          field,
          value,
          oldValue,
        })
      } catch (error) {
        notifyIf(error, 'field')
      }
    },
    onRowContext({ row, event }) {
      this.contextRow = row
      this.$refs.rowContext.toggleNextToMouse(event)
    },
    onRowDragStart({ row, event }) {
      this.$refs.rowDragging?.start(row, event)
    },
    onCellSelectedPresence({ row, field }) {
      if (!row || !field) return
      this.$store.dispatch(this.storeNs + '/addRowSelectedBy', { row, field })
    },
    onCellUnselectedPresence({ row, field }) {
      if (!row || !field) return
      this.$store.dispatch(this.storeNs + '/removeRowSelectedBy', { row, field })
    },
    onDragAutoScroll(speed) {
      const el = this.getScrollEl()
      if (!el) return
      el.scrollTop = el.scrollTop + speed
    },
    onFieldDragStart({ field, event }) {
      // Field header dragging: skip the primary field (it's pinned)
      // and hand off to the shared GridViewFieldDragging overlay.
      if (!field || field.primary) return
      this.$refs.fieldDragging?.start(field, event)
    },
    onFieldDragScroll({ pixelX }) {
      const el = this.getScrollEl()
      if (!el || !pixelX) return
      el.scrollLeft = el.scrollLeft + pixelX
    },
    async onDeleteSelectedRows() {
      const ids = [...this.selectionRowIds]
      if (ids.length === 0) return
      this.$refs.rowContext.hide()
      this.bulkDeleting = true
      try {
        // Delete each via the shared lifecycle. Fan out in parallel
        // so the UI updates as each row resolves; tree counts and
        // section buckets stay consistent because each dispatch is
        // atomic in the store.
        const tasks = ids.map(async (rowId) => {
          const idx = this.$store.getters[this.storeNs + '/rowIndex'].get(
            rowId
          )
          if (!idx) return
          const bucket = this.sectionRows.get(idx.sectionKey)
          const row = bucket?.get(idx.position)
          if (!row) return
          await this.$store.dispatch(this.storeNs + '/deleteRow', {
            table: this.table,
            row,
          })
        })
        await Promise.allSettled(tasks)
        // Clear the multi-row selection now that the rows are gone.
        this.$store.dispatch(this.storePrefix + 'view/grid/clearCheckboxSelections')
        this.$store.dispatch(this.storePrefix + 'view/grid/clearAndDisableMultiSelect')
      } catch (error) {
        notifyIf(error, 'row')
      } finally {
        this.bulkDeleting = false
      }
    },
    async onPasteEvent(event) {
      // Window-level Cmd/Ctrl+V. Only fires when no individual cell
      // has registered a paste listener (no single-cell selection) —
      // the cell's listener intercepts and stops propagation for the
      // multi-row case via `onMultiplePasteFromCell`.
      if (
        this.readOnly ||
        !this.areaSelectionActive ||
        !this.$hasPermission(
          'database.table.update_row',
          this.table,
          this.database.workspace.id
        )
      ) {
        return
      }
      const [textData, jsonData] = await this.extractClipboardData(event)
      if (!textData?.length) return
      event.preventDefault()
      try {
        await this.pasteRectangleScoped({ textData, jsonData })
      } catch (error) {
        notifyIf(error, 'view')
      }
    },
    /**
     * The selected cell forwards its `paste` event up the row when
     * the clipboard payload has more than one cell (gridField mixin
     * stops propagation in that case to prevent the cell from
     * pasting the whole rectangle into itself). We anchor the paste
     * rectangle at the emitting cell so it spans the right cells
     * even when no area selection is active.
     */
    async onMultiplePasteFromCell({ data: { textData, jsonData }, row, field }) {
      if (
        this.readOnly ||
        !this.$hasPermission(
          'database.table.update_row',
          this.table,
          this.database.workspace.id
        )
      ) {
        return
      }
      if (!textData?.length) return
      const flatStore = this.storePrefix + 'view/grid/'
      if (!this.areaSelectionActive) {
        // Anchor the paste rectangle at the emitting cell — same
        // behaviour flat's `pasteData(_, _, rowIndex, fieldIndex)`
        // has when called from `multiplePasteFromCell`.
        const rowIndex =
          this.$store.getters[this.storeNs + '/linearisedRowIndexById'](row.id)
        const fieldIndex = this.visibleFields.findIndex(
          (f) => f.id === field.id
        )
        if (rowIndex < 0 || fieldIndex < 0) return
        const rows = textData.length
        const cols = textData[0]?.length ?? 0
        if (rows === 0 || cols === 0) return
        await this.$store.dispatch(flatStore + 'setSelectionType', {
          selectionType: GRID_VIEW_MULTI_SELECT_AREA,
        })
        this.$store.commit(flatStore + 'SET_MULTISELECT_START_ROW_INDEX', rowIndex)
        this.$store.commit(flatStore + 'SET_MULTISELECT_START_FIELD_INDEX', fieldIndex)
        this.$store.commit(flatStore + 'UPDATE_MULTISELECT', {
          position: 'head',
          rowIndex,
          fieldIndex,
        })
        this.$store.commit(flatStore + 'UPDATE_MULTISELECT', {
          position: 'tail',
          rowIndex: rowIndex + rows - 1,
          fieldIndex: fieldIndex + cols - 1,
        })
        this.$store.commit(flatStore + 'SET_MULTISELECT_ACTIVE', true)
      }
      try {
        await this.pasteRectangleScoped({ textData, jsonData })
      } catch (error) {
        notifyIf(error, 'view')
      }
    },
    async pasteRectangleScoped({ textData, jsonData }) {
      const flat = (k) =>
        this.$store.getters[this.storePrefix + 'view/grid/' + k]
      const [minRow, maxRow] = flat('getMultiSelectRowIndexSorted')
      const [minField, maxField] = flat('getMultiSelectFieldIndexSorted')

      const copiedRows = textData.length
      const copiedCols = textData[0].length
      const selectedRows = maxRow - minRow + 1
      const selectedCols = maxField - minField + 1

      // Tile single-cell / single-row clipboard payloads across the
      // selection — same UX as the flat grid.
      const isSingleCell = copiedRows === 1 && copiedCols === 1
      const isSingleRow = copiedRows === 1 && selectedRows > 1
      let effectiveText = textData
      let effectiveJson = jsonData
      if (isSingleCell) {
        const tileRow = new Array(selectedCols).fill(textData[0][0])
        effectiveText = new Array(selectedRows).fill(tileRow)
        if (jsonData) {
          const tileJsonRow = new Array(selectedCols).fill(jsonData[0][0])
          effectiveJson = new Array(selectedRows).fill(tileJsonRow)
        }
      } else if (isSingleRow) {
        effectiveText = new Array(selectedRows).fill(textData[0])
        if (jsonData) effectiveJson = new Array(selectedRows).fill(jsonData[0])
      }

      const rowsAvailable = Math.min(effectiveText.length, selectedRows)
      const colsAvailable = Math.min(
        effectiveText[0]?.length ?? 0,
        selectedCols
      )
      if (rowsAvailable === 0 || colsAvailable === 0) return

      const slots = this.$store.getters[this.storeNs + '/linearisedRowSlots']
      // Build a per-row update list — every cell in the rectangle
      // becomes a `{ field, value, oldValue }` entry on its row's
      // `fieldValuePairs`. The batched action then applies all row
      // patches optimistically and persists with a single
      // `RowService.batchUpdate` call, matching the flat grid's
      // paste UX (everything visibly updates together).
      const updates = []
      for (let r = 0; r < rowsAvailable; r++) {
        const slot = slots[minRow + r]
        if (!slot?.rowId) continue
        const row = this.lookupRowById(slot.rowId)
        if (!row) continue
        const fieldValuePairs = []
        for (let c = 0; c < colsAvailable; c++) {
          const field = this.visibleFields[minField + c]
          if (!field) continue
          const fieldType = this.$registry.get('field', field.type)
          if (!fieldType.canWriteFieldValues?.(field)) continue
          const rawText = effectiveText[r][c] ?? ''
          const rawJson = effectiveJson?.[r]?.[c]
          let value
          try {
            value = fieldType.prepareValueForPaste
              ? fieldType.prepareValueForPaste(field, rawText, rawJson)
              : rawText
          } catch (_) {
            continue
          }
          if (value === undefined) continue
          const fieldKey = `field_${field.id}`
          fieldValuePairs.push({ field, value, oldValue: row[fieldKey] })
        }
        if (fieldValuePairs.length) updates.push({ row, fieldValuePairs })
      }
      if (!updates.length) return
      this.$store.dispatch('toast/setPasting', true)
      try {
        await this.$store.dispatch(this.storeNs + '/batchUpdateRowValues', {
          table: this.table,
          view: this.view,
          fields: this.allFieldsInTable,
          updates,
        })
      } finally {
        this.$store.dispatch('toast/setPasting', false)
      }
    },
    onCopyEvent(event) {
      // Cmd/Ctrl+C: copy the area rectangle (or checkbox-selected
      // rows) via the shared `copyPasteHelper` mixin so the
      // resulting clipboard payload matches what the flat grid
      // produces — including the rich JSON sidecar that lets a
      // later paste recover field-type-specific values.
      if (
        !this.areaSelectionActive &&
        this.checkboxSelectedRowIds.length === 0
      ) {
        return
      }
      event.preventDefault()
      this.copySelectionToClipboard(
        this.resolveSelectionForCopy(),
        /* includeHeader */ false
      )
    },
    onCopyCellsFromSelection(withHeader) {
      if (
        !this.areaSelectionActive &&
        this.checkboxSelectedRowIds.length === 0
      ) {
        return
      }
      this.$refs.rowContext.hide()
      this.copySelectionToClipboard(
        this.resolveSelectionForCopy(),
        withHeader
      )
    },
    resolveSelectionForCopy() {
      // Returns the [fields, rows] tuple the shared mixin expects.
      // Promise-wrapped because the mixin signature is async; we
      // resolve immediately since all data is already in the
      // grouped store.
      let fields = this.visibleFields
      // Area selection (no checkboxes): restrict fields to the
      // rectangle's column range. Checkbox selection covers every
      // visible field — matches the flat grid's behaviour.
      if (
        this.areaSelectionActive &&
        this.checkboxSelectedRowIds.length === 0
      ) {
        const [minField, maxField] =
          this.$store.getters[
            this.storePrefix + 'view/grid/getMultiSelectFieldIndexSorted'
          ]
        fields = this.visibleFields.slice(minField, maxField + 1)
      }
      const rows = this.selectionRowIds
        .map((rowId) => this.lookupRowById(rowId))
        .filter(Boolean)
      return Promise.resolve([fields, rows])
    },
    onSelectRow(row) {
      this.$refs.rowContext.hide()
      if (!row) return
      // Route through the same flat-store action both grids share.
      this.$store.dispatch(
        this.storePrefix + 'view/grid/toggleCheckboxRowSelection',
        { row }
      )
    },
    async onDeleteContextRow(row) {
      this.$refs.rowContext.hide()
      try {
        await this.$store.dispatch(this.storeNs + '/deleteRow', {
          table: this.table,
          row,
        })
      } catch (error) {
        notifyIf(error, 'row')
      } finally {
        this.contextRow = null
      }
    },
    async onInsertAbove(row) {
      this.$refs.rowContext.hide()
      try {
        await this.$store.dispatch(this.storeNs + '/insertRowAboveRow', {
          table: this.table,
          view: this.view,
          fields: this.allFieldsInTable,
          sourceRow: row,
        })
      } catch (error) {
        notifyIf(error, 'row')
      }
    },
    async onInsertBelow(row) {
      this.$refs.rowContext.hide()
      try {
        await this.$store.dispatch(this.storeNs + '/insertRowBelowRow', {
          table: this.table,
          view: this.view,
          fields: this.allFieldsInTable,
          sourceRow: row,
        })
      } catch (error) {
        notifyIf(error, 'row')
      }
    },
    async onDuplicateRow(row) {
      this.$refs.rowContext.hide()
      try {
        await this.$store.dispatch(this.storeNs + '/duplicateRow', {
          table: this.table,
          view: this.view,
          fields: this.allFieldsInTable,
          sourceRow: row,
        })
      } catch (error) {
        notifyIf(error, 'row')
      }
    },
    onCopyRowURL(row) {
      this.$refs.rowContext.hide()
      const url =
        this.$config.public.baserowEmbeddedShareUrl +
        this.$router.resolve({
          name: 'database-table-row',
          params: { ...this.$route.params, rowId: row.id },
        }).href
      copyToClipboard(url)
      this.$store.dispatch('toast/info', {
        title: this.$t('gridView.copiedRowURL'),
        message: this.$t('gridView.copiedRowURLMessage', { id: row.id }),
      })
    },
    onOpenRowModal(row) {
      this.$refs.rowContext.hide()
      // Hand off to the parent view container that owns the row edit
      // modal (it's mounted once for both grid variants).
      this.$emit('edit-start', { row })
    },
    async onAddRowToGroup(groupPath) {
      try {
        await this.$store.dispatch(this.storeNs + '/createRowInGroup', {
          table: this.table,
          view: this.view,
          fields: this.allFieldsInTable,
          groupPath,
        })
      } catch (error) {
        notifyIf(error, 'row')
      }
    },
    scheduleEnsureRowsForViewport() {
      if (this._ensureFetchTimer) clearTimeout(this._ensureFetchTimer)
      this._ensureFetchTimer = setTimeout(() => {
        this._ensureFetchTimer = null
        this.$store.dispatch(this.storeNs + '/ensureRowsForViewport')
      }, 80)
    },
    // ── Area drag-select (Phase 1: single-section clamp) ─────────
    // Wire-up: mousedown captures the anchor (linearised row index,
    // visible field index, section key). mouseover during a held
    // drag extends the tail — but only if the new cell is in the
    // same section as the anchor (Phase 1 limitation). mouseup ends
    // the hold; selection stays "active" until cleared.
    onAreaMousedown({ row, field, rowIndex, fieldIndex }) {
      if (rowIndex < 0 || fieldIndex < 0) return
      // Mirror flat grid's `multiSelectStart`: stash the anchor +
      // hold state, but DON'T set `isMultiSelectActive` yet. It
      // only flips on if/when the user mouses over a different
      // cell. This keeps the right-click menu in single-row mode
      // for a plain click and leaves the single-cell selection
      // intact — only an actual drag triggers area mode.
      this._dragAnchor = {
        rowIndex,
        fieldIndex,
        sectionKey: this.sectionKeyForRow(row?.id),
      }
      const flatStore = this.storePrefix + 'view/grid/'
      this.$store.dispatch(flatStore + 'setSelectionType', {
        selectionType: GRID_VIEW_MULTI_SELECT_AREA,
      })
      this.$store.commit(flatStore + 'SET_MULTISELECT_START_ROW_INDEX', rowIndex)
      this.$store.commit(
        flatStore + 'SET_MULTISELECT_START_FIELD_INDEX',
        fieldIndex
      )
      this.$store.commit(flatStore + 'UPDATE_MULTISELECT', {
        position: 'head',
        rowIndex,
        fieldIndex,
      })
      this.$store.commit(flatStore + 'UPDATE_MULTISELECT', {
        position: 'tail',
        rowIndex,
        fieldIndex,
      })
      this.$store.commit(flatStore + 'SET_MULTISELECT_HOLDING', true)
      this.$store.commit(flatStore + 'SET_MULTISELECT_ACTIVE', false)
      this.startDragAutoScroll()
    },
    onAreaMouseover({ rowIndex, fieldIndex }) {
      const anchor = this._dragAnchor
      if (!anchor) return
      if (rowIndex < 0 || fieldIndex < 0) return
      // Same cell as the anchor → drag hasn't moved yet; don't
      // activate area selection. Matches flat's
      // `setMultiSelectHeadOrTail` behaviour: head/tail computed
      // from the start cell and the hovered cell via min/max, and
      // ACTIVE flips on only once they differ.
      if (rowIndex === anchor.rowIndex && fieldIndex === anchor.fieldIndex) {
        return
      }
      const flatStore = this.storePrefix + 'view/grid/'
      const startRow = anchor.rowIndex
      const startField = anchor.fieldIndex
      this.$store.commit(flatStore + 'UPDATE_MULTISELECT', {
        position: 'head',
        rowIndex: Math.min(startRow, rowIndex),
        fieldIndex: Math.min(startField, fieldIndex),
      })
      this.$store.commit(flatStore + 'UPDATE_MULTISELECT', {
        position: 'tail',
        rowIndex: Math.max(startRow, rowIndex),
        fieldIndex: Math.max(startField, fieldIndex),
      })
      this.$store.commit(flatStore + 'SET_MULTISELECT_ACTIVE', true)
      // Drop the single-cell selection so the area selection owns
      // the visual highlight (flat clears it via SET_SELECTED_CELL
      // {-1, -1}; we use our grouped action for the same effect).
      if (this.selectedCell) {
        this.$store.commit(this.storeNs + '/CLEAR_CELL_SELECTION')
      }
    },
    onAreaMouseup() {
      this._dragAnchor = null
      this.$store.dispatch(this.storePrefix + 'view/grid/setMultiSelectHolding', false)
      this.stopDragAutoScroll()
    },
    onAreaShiftClick({ rowIndex, fieldIndex }) {
      if (rowIndex < 0 || fieldIndex < 0) return
      this.$store.dispatch(
        this.storePrefix + 'view/grid/updateMultipleSelectIndexes',
        {
          position: 'tail',
          rowIndex,
          fieldIndex,
        }
      )
    },
    onWindowMouseUp() {
      // Drag ended even if the user released outside a cell.
      if (this._dragAnchor) this.onAreaMouseup()
    },
    onWindowClick(event) {
      // Same logic as flat's `cancelMultiSelectIfActive`: an area
      // multi-select gets cleared on any click that isn't a
      // shift-extend and didn't land on the grouped grid's body.
      // Clicks on banners, headers, footer, or anywhere outside all
      // count as "outside the rows" and therefore reset the area.
      const flatStore = this.storePrefix + 'view/grid/'
      const selectionType = this.$store.getters[flatStore + 'getSelectionType']
      if (selectionType !== GRID_VIEW_MULTI_SELECT_AREA) return
      if (!this.$store.getters[flatStore + 'isMultiSelectActive']) return
      if (event.shiftKey) return
      const inRow = event.target?.closest?.('.grid-grouped-row')
      if (inRow) return
      const ctx = this.$refs.rowContext?.$el
      if (ctx && ctx.contains(event.target)) return
      this.$store.dispatch(flatStore + 'clearAndDisableMultiSelect')
    },
    sectionKeyForRow(rowId) {
      if (rowId == null) return null
      const idx = this.$store.getters[this.storeNs + '/rowIndex'].get(rowId)
      return idx ? idx.sectionKey : null
    },
    // Auto-scroll the body when the drag cursor approaches the top
    // or bottom edge of the scroll container. Same edge-band trick
    // the flat grid uses to let the user extend a multi-cell
    // selection beyond what's currently visible.
    startDragAutoScroll() {
      if (this._autoScrollHandle !== null) return
      window.addEventListener('mousemove', this._onDragMouseMove)
      const tick = () => {
        if (!this._dragAnchor) {
          this._autoScrollHandle = null
          return
        }
        const scrollEl = this.$refs.scroll
        if (scrollEl && this._lastDragY !== null) {
          const rect = scrollEl.getBoundingClientRect()
          const threshold = 60
          let dy = 0
          if (this._lastDragY < rect.top + threshold) {
            dy = -Math.max(6, (rect.top + threshold - this._lastDragY) / 3)
          } else if (this._lastDragY > rect.bottom - threshold) {
            dy = Math.max(6, (this._lastDragY - (rect.bottom - threshold)) / 3)
          }
          if (dy !== 0) scrollEl.scrollTop += dy
        }
        this._autoScrollHandle = requestAnimationFrame(tick)
      }
      this._autoScrollHandle = requestAnimationFrame(tick)
    },
    stopDragAutoScroll() {
      if (this._autoScrollHandle !== null) {
        cancelAnimationFrame(this._autoScrollHandle)
        this._autoScrollHandle = null
      }
      window.removeEventListener('mousemove', this._onDragMouseMove)
      this._lastDragY = null
    },
    _onDragMouseMove(event) {
      this._lastDragY = event.clientY
    },
    onKeyDown(event) {
      const sel = this.selectedCell
      // Skip when the user is typing in an input/textarea/etc. — the
      // cell's edit component owns the keys then.
      const target = event.target
      if (
        target &&
        (target.tagName === 'INPUT' ||
          target.tagName === 'TEXTAREA' ||
          target.isContentEditable)
      ) {
        return
      }
      const moveMap = {
        ArrowUp: 'up',
        ArrowDown: 'down',
        ArrowLeft: 'left',
        ArrowRight: 'right',
        Tab: event.shiftKey ? 'left' : 'right',
      }
      const dirMap = {
        ArrowLeft: 'previous',
        ArrowRight: 'next',
        ArrowUp: 'above',
        ArrowDown: 'below',
      }
      // Backspace / Delete with an area selection: clear every cell
      // in the rectangle via the shared updateRowValue lifecycle.
      // No-op when only a single cell is selected (the cell's own
      // editor handles the key).
      if (
        (event.key === 'Backspace' || event.key === 'Delete') &&
        this.areaSelectionActive
      ) {
        event.preventDefault()
        this.clearValuesInAreaSelection()
        return
      }
      // Shift+arrow: extend / contract the area selection. Uses the
      // same "head vs tail moves based on start" logic the flat
      // grid uses, but with bounds derived from the grouped layout's
      // linearised row index and visible-field count.
      if (event.shiftKey && dirMap[event.key]) {
        if (this.extendAreaSelection(dirMap[event.key])) {
          event.preventDefault()
        }
        return
      }
      if (!sel || sel.rowId == null) return
      if (event.key === 'Tab') {
        const next = this.findCellViaTab(sel, event.shiftKey)
        if (next) {
          event.preventDefault()
          this.$store.dispatch(this.storeNs + '/selectCell', next)
          this.$nextTick(() => this.scrollSelectedCellIntoView(next))
        }
        return
      }
      if (moveMap[event.key]) {
        const next = this.findAdjacentCell(sel, moveMap[event.key])
        if (next) {
          event.preventDefault()
          this.$store.dispatch(this.storeNs + '/selectCell', next)
          this.$nextTick(() => this.scrollSelectedCellIntoView(next))
        }
        return
      }
      if (event.key === 'Escape') {
        event.preventDefault()
        this.$store.dispatch(this.storeNs + '/clearCellSelection')
        return
      }
      if (event.key === 'Enter') {
        event.preventDefault()
        // Hand the editing intent up to the parent, same as a
        // double-click on a cell would.
        const row = this.lookupRowById(sel.rowId)
        const field = this.visibleFields.find((f) => f.id === sel.fieldId)
        if (row && field) this.$emit('edit-start', { row, field })
      }
    },
    async clearValuesInAreaSelection() {
      if (this.readOnly) return
      const flat = (k) =>
        this.$store.getters[this.storePrefix + 'view/grid/' + k]
      const [minRow, maxRow] = flat('getMultiSelectRowIndexSorted')
      const [minField, maxField] = flat('getMultiSelectFieldIndexSorted')
      const slots = this.$store.getters[this.storeNs + '/linearisedRowSlots']
      const tasks = []
      for (let r = minRow; r <= maxRow && r < slots.length; r++) {
        const slot = slots[r]
        if (!slot?.rowId) continue
        const row = this.lookupRowById(slot.rowId)
        if (!row) continue
        for (let c = minField; c <= maxField; c++) {
          const field = this.visibleFields[c]
          if (!field) continue
          const fieldType = this.$registry.get('field', field.type)
          if (!fieldType.canWriteFieldValues?.(field)) continue
          const fieldKey = `field_${field.id}`
          const oldValue = row[fieldKey]
          const cleared = fieldType.getEmptyValue
            ? fieldType.getEmptyValue(field)
            : null
          if (JSON.stringify(oldValue) === JSON.stringify(cleared)) continue
          tasks.push(
            this.$store.dispatch(this.storeNs + '/updateRowValue', {
              table: this.table,
              view: this.view,
              fields: this.allFieldsInTable,
              row,
              field,
              value: cleared,
              oldValue,
            })
          )
        }
      }
      this.$store.dispatch('toast/setClearing', true)
      try {
        await Promise.allSettled(tasks)
      } finally {
        this.$store.dispatch('toast/setClearing', false)
      }
    },
    extendAreaSelection(direction) {
      const flat = (k) => this.$store.getters[this.storePrefix + 'view/grid/' + k]
      const flatStore = this.storePrefix + 'view/grid/'

      // First-time activation: bootstrap from the current single-cell
      // selection. Anchor (start) is the cell the user had focused;
      // head + tail collapse to that cell to begin with.
      if (!flat('isMultiSelectActive')) {
        const sel = this.selectedCell
        if (!sel?.rowId) return false
        const rowIdx =
          this.$store.getters[
            this.storeNs + '/linearisedRowIndexById'
          ](sel.rowId)
        const fieldIdx = this.visibleFields.findIndex(
          (f) => f.id === sel.fieldId
        )
        if (rowIdx < 0 || fieldIdx < 0) return false
        this.$store.commit(flatStore + 'SET_MULTISELECT_START_ROW_INDEX', rowIdx)
        this.$store.commit(
          flatStore + 'SET_MULTISELECT_START_FIELD_INDEX',
          fieldIdx
        )
        this.$store.commit(flatStore + 'UPDATE_MULTISELECT', {
          position: 'head',
          rowIndex: rowIdx,
          fieldIndex: fieldIdx,
        })
        this.$store.commit(flatStore + 'UPDATE_MULTISELECT', {
          position: 'tail',
          rowIndex: rowIdx,
          fieldIndex: fieldIdx,
        })
        this.$store.commit(flatStore + 'SET_MULTISELECT_ACTIVE', true)
        this.$store.dispatch(flatStore + 'setSelectionType', {
          selectionType: GRID_VIEW_MULTI_SELECT_AREA,
        })
      }

      const tailRow = flat('getMultiSelectTailRowIndex')
      const tailField = flat('getMultiSelectTailFieldIndex')
      const headRow = flat('getMultiSelectHeadRowIndex')
      const headField = flat('getMultiSelectHeadFieldIndex')
      const startRow = flat('getMultiSelectStartRowIndex')
      const startField = flat('getMultiSelectStartFieldIndex')

      const totalRows = this.$store.getters[
        this.storeNs + '/linearisedRowSlots'
      ].length
      const totalFields = this.visibleFields.length

      let positionToMove
      let newRow
      let newField
      // Mirrors `multiSelectShiftChange` from the flat grid: the
      // anchor (start) determines which end moves on each direction
      // so the user can shrink the rectangle by moving back toward
      // the anchor.
      if (direction === 'below') {
        positionToMove = headRow === startRow ? 'tail' : 'head'
        newRow = (positionToMove === 'tail' ? tailRow : headRow) + 1
        newField = positionToMove === 'tail' ? tailField : headField
      } else if (direction === 'above') {
        positionToMove = tailRow === startRow ? 'head' : 'tail'
        newRow = (positionToMove === 'tail' ? tailRow : headRow) - 1
        newField = positionToMove === 'tail' ? tailField : headField
      } else if (direction === 'next') {
        positionToMove = headField === startField ? 'tail' : 'head'
        newRow = positionToMove === 'tail' ? tailRow : headRow
        newField = (positionToMove === 'tail' ? tailField : headField) + 1
      } else if (direction === 'previous') {
        positionToMove = tailField === startField ? 'head' : 'tail'
        newRow = positionToMove === 'tail' ? tailRow : headRow
        newField = (positionToMove === 'tail' ? tailField : headField) - 1
      } else {
        return false
      }

      if (
        newRow < 0 ||
        newRow >= totalRows ||
        newField < 0 ||
        newField >= totalFields
      ) {
        return true // handled but didn't extend — at the bounds
      }

      this.$store.commit(flatStore + 'UPDATE_MULTISELECT', {
        position: positionToMove,
        rowIndex: newRow,
        fieldIndex: newField,
      })
      // Scroll the affected row into view so the user sees the
      // extension. The moved end (head or tail) is what we want
      // visible.
      const slot = this.$store.getters[this.storeNs + '/linearisedRowSlots'][newRow]
      if (slot?.rowId != null) {
        this.$nextTick(() =>
          this.scrollSelectedCellIntoView({
            rowId: slot.rowId,
            fieldId: this.visibleFields[newField]?.id,
          })
        )
      }
      return true
    },
    findCellViaTab(selectedCell, reverse) {
      // Tab: column right, wrapping into the first column of the
      // next row. Shift+Tab: column left, wrapping into the last
      // column of the previous row. Matches the flat grid.
      const rowIndex =
        this.$store.getters[this.storeNs + '/rowIndex']
      const idx = rowIndex.get(selectedCell.rowId)
      if (!idx) return null
      const fieldsList = this.visibleFields
      const fieldIdx = fieldsList.findIndex((f) => f.id === selectedCell.fieldId)
      if (fieldIdx === -1) return null

      if (!reverse && fieldIdx < fieldsList.length - 1) {
        return {
          rowId: selectedCell.rowId,
          fieldId: fieldsList[fieldIdx + 1].id,
        }
      }
      if (reverse && fieldIdx > 0) {
        return {
          rowId: selectedCell.rowId,
          fieldId: fieldsList[fieldIdx - 1].id,
        }
      }
      // Wrap to next/previous row.
      const nextRowId = this.findRowInDirection(
        idx.sectionKey,
        idx.position,
        reverse ? 'up' : 'down'
      )
      if (nextRowId == null) return null
      return {
        rowId: nextRowId,
        fieldId: reverse
          ? fieldsList[fieldsList.length - 1].id
          : fieldsList[0].id,
      }
    },
    findAdjacentCell(selectedCell, direction) {
      // Single-cell navigation that respects grouped layout: vertical
      // arrows step row-by-row across section boundaries, horizontal
      // arrows step field-by-field within the visible fields list.
      const rowIndex =
        this.$store.getters[this.storeNs + '/rowIndex']
      const idx = rowIndex.get(selectedCell.rowId)
      if (!idx) return null
      const fieldsList = this.visibleFields
      const fieldIdx = fieldsList.findIndex((f) => f.id === selectedCell.fieldId)
      if (fieldIdx === -1) return null

      if (direction === 'left' && fieldIdx > 0) {
        return {
          rowId: selectedCell.rowId,
          fieldId: fieldsList[fieldIdx - 1].id,
        }
      }
      if (direction === 'right' && fieldIdx < fieldsList.length - 1) {
        return {
          rowId: selectedCell.rowId,
          fieldId: fieldsList[fieldIdx + 1].id,
        }
      }
      if (direction === 'up' || direction === 'down') {
        const nextRowId = this.findRowInDirection(
          idx.sectionKey,
          idx.position,
          direction
        )
        if (nextRowId != null) {
          return { rowId: nextRowId, fieldId: selectedCell.fieldId }
        }
      }
      return null
    },
    findRowInDirection(sectionKey, position, direction) {
      // Walk the layout in `direction` (up/down) to find the next
      // visible row. Crosses section boundaries — the next row up
      // from position 0 of section X is the last row of the
      // immediately preceding visible section.
      const layout = this.layout
      const sections = layout.items.filter((it) => it.type === 'rowSection')
      const currentIdx = sections.findIndex(
        (s) => pathKey(s.path, this.groupByFields) === sectionKey
      )
      if (currentIdx === -1) return null
      const currentSection = sections[currentIdx]

      if (direction === 'up') {
        if (position > 0) {
          return this.lookupRowAtPosition(sectionKey, position - 1)
        }
        // Walk back across sections for the previous loaded row.
        for (let i = currentIdx - 1; i >= 0; i--) {
          const s = sections[i]
          const lastPos = s.rowCount - 1
          if (lastPos < 0) continue
          const rowId = this.lookupRowAtPosition(
            pathKey(s.path, this.groupByFields),
            lastPos
          )
          if (rowId != null) return rowId
        }
        return null
      }
      if (direction === 'down') {
        if (position < currentSection.rowCount - 1) {
          return this.lookupRowAtPosition(sectionKey, position + 1)
        }
        for (let i = currentIdx + 1; i < sections.length; i++) {
          const s = sections[i]
          if (s.rowCount === 0) continue
          const rowId = this.lookupRowAtPosition(
            pathKey(s.path, this.groupByFields),
            0
          )
          if (rowId != null) return rowId
        }
        return null
      }
      return null
    },
    lookupRowAtPosition(sectionKey, position) {
      const bucket = this.sectionRows.get(sectionKey)
      const row = bucket?.get(position)
      return row?.id ?? null
    },
    lookupRowById(rowId) {
      const rowIndex = this.$store.getters[this.storeNs + '/rowIndex']
      const idx = rowIndex.get(rowId)
      if (!idx) return null
      const bucket = this.sectionRows.get(idx.sectionKey)
      return bucket?.get(idx.position) ?? null
    },
    scrollSelectedCellIntoView(sel) {
      // Compute the row's y from the layout + scroll the container
      // so the selected cell stays in view.
      const rowIndex =
        this.$store.getters[this.storeNs + '/rowIndex']
      const idx = rowIndex.get(sel.rowId)
      if (!idx) return
      const section = this.layout.items.find(
        (it) =>
          it.type === 'rowSection' &&
          pathKey(it.path, this.groupByFields) === idx.sectionKey
      )
      if (!section) return
      const rowY = section.y + idx.position * 33 // ROW_HEIGHT
      const scrollEl = this.$refs.scroll
      if (!scrollEl) return
      const top = scrollEl.scrollTop
      const bottom = top + scrollEl.clientHeight
      if (rowY < top) scrollEl.scrollTop = rowY
      else if (rowY + 33 > bottom)
        scrollEl.scrollTop = rowY + 33 - scrollEl.clientHeight
    },
    itemKey(item) {
      if (item.type === 'row') return 'r' + item.row.id
      if (item.type === 'header') {
        return 'h' + item.depth + ':' + JSON.stringify(item.path)
      }
      return 'p' + item.indexInSection + ':' + JSON.stringify(item.path)
    },
  },
}
</script>

<style lang="scss" scoped>
.grid-grouped {
  position: relative;
  display: flex;
  flex-direction: column;
  width: 100%;
  height: 100%;
  background: #ffffff;
  overflow: hidden;
}

.grid-grouped__head {
  flex: 0 0 auto;
  position: relative;
  z-index: 1;
  height: 33px;
  background: #ffffff;
  border-bottom: 1px solid #e5e7eb;
}

.grid-grouped__scroll {
  flex: 1 1 auto;
  overflow: auto;
  scrollbar-width: none;
  &::-webkit-scrollbar {
    width: 0;
    height: 0;
    display: none;
  }
}

.grid-grouped__canvas {
  position: relative;
}

.grid-grouped__foot {
  flex: 0 0 auto;
  position: relative;
  z-index: 1;
}
</style>
