<template>
  <div
    class="dashboard-widget-grid"
    data-testid="dashboard-widget-grid"
    :style="{
      '--dashboard-widget-grid-columns': columns,
      '--dashboard-widget-grid-gap': `${gridGap}px`,
      '--dashboard-widget-grid-row-height': `${gridRowHeight}px`,
    }"
    :class="{
      'dashboard-widget-grid--interacting': isInteracting,
      'dashboard-widget-grid--layout-ready': isLayoutReady,
      'dashboard-widget-grid--resizing': resizeState !== null,
    }"
  >
    <DashboardWidgetGridLoading
      v-if="!isLayoutReady && (widgets.length > 0 || pendingWidget)"
      :class="{
        'dashboard-widget-grid__loading--overlay': hasMeasuredDimensions,
      }"
    />
    <GridLayout
      v-if="hasMeasuredDimensions && displayedLayout.length > 0"
      ref="grid"
      v-model:layout="displayedLayout"
      :col-num="columns"
      :row-height="gridRowHeight"
      :margin="[gridGap, gridGap]"
      :vertical-compact="columns === DASHBOARD_GRID_COLUMNS"
      :is-draggable="canManipulateLayout"
      :is-resizable="canManipulateLayout"
      :use-style-cursor="false"
      @layout-ready="markLayoutReady"
      @layout-updated="persistLayout"
    >
      <GridItem
        v-for="layoutItem in displayedLayout"
        :key="layoutItem.i"
        v-bind="getWidgetGridItemConstraints(getWidget(layoutItem), layoutItem)"
        :i="layoutItem.i"
        :x="layoutItem.x"
        :y="layoutItem.y"
        :w="layoutItem.w"
        :h="layoutItem.h"
        :is-draggable="canManipulateLayout"
        :is-resizable="canManipulateLayout"
        :class="{
          'dashboard-widget-grid__item--compact': layoutItem.h === 2,
          'dashboard-widget-grid__item--snap-resizing':
            isResizingWidget(layoutItem),
          'dashboard-widget-grid__item--placing': placingItemIds.includes(
            String(layoutItem.i)
          ),
        }"
        :style="getGridItemResizeStyle(layoutItem)"
        :data-testid="`dashboard-widget-grid-item-${layoutItem.i}`"
        drag-allow-from=".widget__header, .dashboard-text-filter-widget > .control__label"
        drag-ignore-from=".widget__header-context-menu, a, button"
        @pointerdown.capture="startResize(layoutItem, $event)"
        @pointerup.capture="clearResizeState"
        @pointercancel.capture="clearResizeState"
        @move="startInteraction"
        @resize="updateResizeState"
      >
        <div
          v-if="layoutItem.i === PENDING_WIDGET_ID"
          class="dashboard-widget"
          role="status"
          aria-busy="true"
          :aria-label="
            $t('dashboard.creatingWidget', { name: pendingWidget.title })
          "
        >
          <SkeletonBlock height="100%" />
        </div>
        <DashboardWidget
          v-else-if="getWidget(layoutItem)"
          :widget="getWidget(layoutItem)"
          :dashboard="dashboard"
          :store-prefix="storePrefix"
          :data-testid="`dashboard-widget-${layoutItem.i}`"
          :is-layout-editable="canManipulateLayout"
          @delete-widget="deleteWidget"
        />
      </GridItem>
    </GridLayout>
  </div>
</template>

<script>
import { reactive } from 'vue'
import { GridItem, GridLayout } from 'grid-layout-plus'

import DashboardWidget from '@baserow/modules/dashboard/components/widget/DashboardWidget'
import DashboardWidgetGridLoading from '@baserow/modules/dashboard/components/DashboardWidgetGridLoading'
import { dimensionMixin } from '@baserow/modules/core/mixins/dimensions'
import {
  DASHBOARD_GRID_COLUMNS,
  createWidgetGridLayout,
  getWidgetGridItemConstraints,
  getWidgetPreviewPosition,
  resizeWidgetGridLayout,
  toWidgetLayoutPayload,
} from '@baserow/modules/dashboard/utils/widgetGridLayout'
import { notifyIf } from '@baserow/modules/core/utils/error'

const GRID_GAP = 16
const GRID_ROW_HEIGHT = 24
const PENDING_WIDGET_ID = 'pending'

export default {
  name: 'DashboardWidgetGrid',
  components: {
    DashboardWidget,
    DashboardWidgetGridLoading,
    GridItem,
    GridLayout,
  },
  mixins: [dimensionMixin],
  inject: {
    widgetCreation: { from: 'dashboardWidgetCreation', default: null },
  },
  props: {
    dashboard: {
      type: Object,
      required: true,
    },
    storePrefix: {
      type: String,
      required: false,
      default: '',
    },
  },
  data() {
    return {
      isInteracting: false,
      isPersisting: false,
      hasMeasuredDimensions: false,
      isLayoutReady: false,
      layoutReadyFrame: null,
      layout: [],
      revealedWidgetId: null,
      // Widgets added after the first layout, until the grid placed them.
      placingItemIds: [],
      placingFrames: [],
      resizeState: null,
      DASHBOARD_GRID_COLUMNS,
      PENDING_WIDGET_ID,
      gridGap: GRID_GAP,
      gridRowHeight: GRID_ROW_HEIGHT,
    }
  },
  computed: {
    columns() {
      if (this.isEditMode || this.dimensions.width >= 1100) {
        return DASHBOARD_GRID_COLUMNS
      }
      return this.dimensions.width >= 700 ? 2 : 1
    },
    pendingWidget() {
      return this.widgetCreation?.widgetId === null ? this.widgetCreation : null
    },
    widgets() {
      return this.$store.getters[
        `${this.storePrefix}dashboardApplication/getWidgets`
      ]
    },
    displayedLayout: {
      get() {
        if (!this.pendingWidget) return this.layout

        const preview = getWidgetPreviewPosition(
          this.layout,
          this.pendingWidget.size,
          this.columns
        )
        // The grid mutates its items during compaction. Keep that work separate
        // from the layout being saved while the preview is shown.
        return reactive([
          ...this.layout.map((item) => ({ ...item })),
          { i: PENDING_WIDGET_ID, ...preview },
        ])
      },
      set(layout) {
        if (!this.pendingWidget) this.layout = layout
      },
    },
    placedCreationItemId() {
      const id = this.pendingWidget
        ? PENDING_WIDGET_ID
        : this.widgetCreation?.widgetId
      return id != null &&
        id !== this.revealedWidgetId &&
        this.isLayoutReady &&
        this.displayedLayout.some((item) => item.i === id) &&
        !this.placingItemIds.includes(String(id))
        ? id
        : null
    },
    widgetsById() {
      return Object.fromEntries(
        this.widgets.map((widget) => [String(widget.id), widget])
      )
    },
    isEditMode() {
      return this.$store.getters[
        `${this.storePrefix}dashboardApplication/isEditMode`
      ]
    },
    canUpdateLayout() {
      return this.$hasPermission(
        'dashboard.update_widget_layout',
        this.dashboard,
        this.dashboard.workspace.id
      )
    },
    canManipulateLayout() {
      return (
        this.isEditMode &&
        this.canUpdateLayout &&
        !this.isPersisting &&
        !this.pendingWidget
      )
    },
  },
  watch: {
    pendingWidget(widget) {
      if (widget && this.isLayoutReady) this.markPlacing([PENDING_WIDGET_ID])
    },
    placedCreationItemId: {
      flush: 'post',
      handler(id) {
        if (id == null) return
        const element = this.$refs.grid?.getItem(id)?.wrapper
        if (!element) return
        element.scrollIntoView({ block: 'nearest', inline: 'nearest' })
        if (id !== PENDING_WIDGET_ID) {
          this.revealedWidgetId = id
        }
      },
    },
    columns() {
      this.syncLayoutFromWidgets()
    },
    isEditMode() {
      // Leaving edit mode cancels any unfinished pointer operation.
      this.isInteracting = false
      this.clearResizeState()
      this.syncLayoutFromWidgets()
    },
    widgets: {
      handler() {
        if (!this.isInteracting && !this.isPersisting) {
          this.syncLayoutFromWidgets()
        }
      },
      deep: true,
    },
  },
  mounted() {
    this.syncLayoutFromWidgets()
    window.addEventListener('pointerup', this.clearResizeState, true)
    window.addEventListener('pointercancel', this.clearResizeState, true)
    window.addEventListener('blur', this.clearResizeState)
  },
  beforeUnmount() {
    if (this.layoutReadyFrame !== null) {
      cancelAnimationFrame(this.layoutReadyFrame)
    }
    this.placingFrames.forEach((frame) => cancelAnimationFrame(frame))
    this.clearResizeState()
    window.removeEventListener('pointerup', this.clearResizeState, true)
    window.removeEventListener('pointercancel', this.clearResizeState, true)
    window.removeEventListener('blur', this.clearResizeState)
  },
  methods: {
    getWidgetGridItemConstraints,
    updateElementSize(entries) {
      dimensionMixin.methods.updateElementSize.call(this, entries)
      if (
        entries.some(
          (entry) =>
            entry.target === (this.dimensions.targetElement || this.$el)
        )
      ) {
        this.hasMeasuredDimensions = true
      }
    },
    getWidget(layoutItem) {
      return this.widgetsById[String(layoutItem.i)]
    },
    canDeleteWidget(widgetId) {
      const widget = this.widgetsById[String(widgetId)]
      return (
        widget &&
        this.$hasPermission(
          'dashboard.widget.delete',
          widget,
          this.dashboard.workspace.id
        )
      )
    },
    getGridItemResizeStyle(layoutItem) {
      if (!this.isResizingWidget(layoutItem)) {
        return {}
      }

      const { width, height } = this.resizeState
      const widthPercentage = (width / this.columns) * 100
      const widthGap = this.gridGap * (width / this.columns + 1)

      return {
        '--dashboard-widget-grid-resize-width': `calc(${widthPercentage}% - ${widthGap}px)`,
        '--dashboard-widget-grid-resize-height': `${
          height * this.gridRowHeight + (height - 1) * this.gridGap
        }px`,
      }
    },
    isResizingWidget(layoutItem) {
      return (
        this.resizeState !== null &&
        String(this.resizeState.widgetId) === String(layoutItem.i)
      )
    },
    syncLayoutFromWidgets() {
      const previousIds = new Set(this.layout.map((item) => String(item.i)))
      this.layout = createWidgetGridLayout(this.widgets, this.columns)
      if (this.isLayoutReady) {
        this.markPlacing(
          this.layout
            .map((item) => String(item.i))
            .filter((id) => !previousIds.has(id))
        )
      }
    },
    /**
     * A grid item mounts at the grid's origin and gets its position a tick
     * later, which its position transition would animate as a slide. Turn the
     * transition off until that first position is painted.
     */
    markPlacing(ids) {
      if (!ids.length) return
      this.placingItemIds = [...this.placingItemIds, ...ids]
      const first = requestAnimationFrame(() => {
        const second = requestAnimationFrame(() => {
          this.placingItemIds = this.placingItemIds.filter(
            (id) => !ids.includes(id)
          )
          this.placingFrames = this.placingFrames.filter(
            (frame) => frame !== second
          )
        })
        this.placingFrames = [
          ...this.placingFrames.filter((frame) => frame !== first),
          second,
        ]
      })
      this.placingFrames = [...this.placingFrames, first]
    },
    markLayoutReady() {
      if (this.layoutReadyFrame !== null) {
        cancelAnimationFrame(this.layoutReadyFrame)
      }

      // Keep the loader for one final frame so geometry observers owned by
      // widget content (notably Chart.js) can redraw before the grid is revealed.
      this.layoutReadyFrame = requestAnimationFrame(() => {
        this.isLayoutReady = true
        this.layoutReadyFrame = null
      })
    },
    startInteraction() {
      if (this.canManipulateLayout) {
        this.isInteracting = true
      }
    },
    startResize(layoutItem, event) {
      if (
        !this.canManipulateLayout ||
        !event.target.closest?.('.vgl-item__resizer')
      ) {
        return
      }

      this.resizeState = {
        widgetId: layoutItem.i,
        width: layoutItem.w,
        height: layoutItem.h,
      }
      document.body.classList.add('dashboard-widget-grid--resizing')
    },
    updateResizeState(widgetId, height, width) {
      if (!this.canManipulateLayout || !this.widgetsById[String(widgetId)]) {
        return
      }

      const resizedLayout = resizeWidgetGridLayout(
        createWidgetGridLayout(this.widgets),
        widgetId,
        width,
        height
      )
      const resizedById = new Map(
        resizedLayout.map((item) => [String(item.i), item])
      )
      // GridItem emits resize before GridLayout compacts its shared layout.
      // Update the existing objects so that compaction sees collision-free positions.
      this.layout.forEach((item) => {
        Object.assign(item, resizedById.get(String(item.i)))
      })

      this.resizeState = {
        widgetId,
        width,
        height,
      }

      this.startInteraction()
    },
    clearResizeState() {
      this.resizeState = null
      document.body.classList.remove('dashboard-widget-grid--resizing')
    },
    async persistLayout(layout) {
      if (!this.isInteracting || !this.canManipulateLayout) {
        return
      }

      // GridLayout emits after compaction, even when a gesture returns to its
      // starting geometry and GridItem does not emit moved or resized.
      this.isPersisting = true
      try {
        await this.$store.dispatch(
          `${this.storePrefix}dashboardApplication/updateWidgetLayout`,
          {
            dashboardId: this.dashboard.id,
            layout: toWidgetLayoutPayload(layout),
          }
        )
      } catch (error) {
        notifyIf(error, 'dashboard')
      } finally {
        this.isPersisting = false
        this.isInteracting = false
        this.clearResizeState()
        this.syncLayoutFromWidgets()
      }
    },
    async deleteWidget(widgetId) {
      if (!this.canDeleteWidget(widgetId) || this.isPersisting) {
        return
      }

      this.isPersisting = true
      try {
        await this.$store.dispatch(
          `${this.storePrefix}dashboardApplication/deleteWidget`,
          widgetId
        )
      } catch (error) {
        notifyIf(error, 'dashboard')
      } finally {
        this.isPersisting = false
        this.syncLayoutFromWidgets()
      }
    },
  },
}
</script>
