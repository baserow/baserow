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
      'dashboard-widget-grid--resizing': resizeState !== null,
    }"
  >
    <GridLayout
      v-if="layout.length > 0"
      v-model:layout="layout"
      :col-num="columns"
      :row-height="gridRowHeight"
      :margin="[gridGap, gridGap]"
      :vertical-compact="true"
      :is-draggable="canManipulateLayout"
      :is-resizable="canManipulateLayout"
      :use-style-cursor="false"
    >
      <GridItem
        v-for="layoutItem in layout"
        :key="layoutItem.i"
        v-bind="
          getWidgetGridItemConstraints(
            getWidget(layoutItem),
            columns,
            layoutItem
          )
        "
        :i="layoutItem.i"
        :x="layoutItem.x"
        :y="layoutItem.y"
        :w="layoutItem.w"
        :h="layoutItem.h"
        :is-draggable="canManipulateLayout"
        :is-resizable="canManipulateLayout"
        :class="{
          'dashboard-widget-grid__item--snap-resizing':
            isResizingWidget(layoutItem),
        }"
        :style="getGridItemResizeStyle(layoutItem)"
        :data-testid="`dashboard-widget-grid-item-${layoutItem.i}`"
        drag-allow-from=".widget__header"
        drag-ignore-from=".widget__header-context-menu, a, button"
        @pointerdown.capture="startResize(layoutItem, $event)"
        @pointerup.capture="clearResizeState"
        @pointercancel.capture="clearResizeState"
        @move="startInteraction"
        @resize="updateResizeState"
        @moved="persistLayout"
        @resized="finishResize"
      >
        <DashboardWidget
          v-if="getWidget(layoutItem)"
          :widget="getWidget(layoutItem)"
          :dashboard="dashboard"
          :store-prefix="storePrefix"
          :data-testid="`dashboard-widget-${layoutItem.i}`"
          :is-layout-editable="canManipulateLayout"
          :is-resizing="isResizingWidget(layoutItem)"
          @delete-widget="deleteWidget"
        />
      </GridItem>
    </GridLayout>
  </div>
</template>

<script>
import { GridItem, GridLayout } from 'grid-layout-plus'

import DashboardWidget from '@baserow/modules/dashboard/components/widget/DashboardWidget'
import {
  createWidgetGridLayout,
  getDashboardGridColumns,
  getWidgetGridItemConstraints,
  toWidgetLayoutPayload,
} from '@baserow/modules/dashboard/utils/widgetGridLayout'
import { notifyIf } from '@baserow/modules/core/utils/error'

const GRID_GAP = 16
const GRID_ROW_HEIGHT = 24

export default {
  name: 'DashboardWidgetGrid',
  components: { DashboardWidget, GridItem, GridLayout },
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
      layout: [],
      resizeState: null,
      gridGap: GRID_GAP,
      gridRowHeight: GRID_ROW_HEIGHT,
      viewportWidth: 0,
    }
  },
  computed: {
    widgets() {
      return this.$store.getters[
        `${this.storePrefix}dashboardApplication/getWidgets`
      ]
    },
    widgetsById() {
      return Object.fromEntries(
        this.widgets.map((widget) => [String(widget.id), widget])
      )
    },
    columns() {
      return getDashboardGridColumns(this.viewportWidth)
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
        this.columns === 6 &&
        this.isEditMode &&
        this.canUpdateLayout &&
        !this.isPersisting
      )
    },
  },
  watch: {
    columns() {
      // A viewport breakpoint can interrupt an active pointer operation.
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
    this.updateViewportWidth()
    window.addEventListener('resize', this.updateViewportWidth)
    this.syncLayoutFromWidgets()
  },
  beforeUnmount() {
    this.clearResizeState()
    window.removeEventListener('resize', this.updateViewportWidth)
  },
  methods: {
    getWidgetGridItemConstraints,
    updateViewportWidth() {
      this.viewportWidth = window.innerWidth
    },
    getWidget(layoutItem) {
      return this.widgetsById[String(layoutItem.i)]
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
      this.layout = createWidgetGridLayout(this.widgets, this.columns)
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
      if (!this.canManipulateLayout) {
        return
      }

      const layoutItem = this.layout.find(
        (item) => String(item.i) === String(widgetId)
      )
      if (!layoutItem) {
        return
      }

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
    async finishResize() {
      try {
        await this.persistLayout()
      } finally {
        this.clearResizeState()
      }
    },
    async persistLayout() {
      if (!this.isInteracting || !this.canManipulateLayout) {
        return
      }

      // GridItem emits its end event just before GridLayout applies the final
      // position and compacts every affected item.
      await this.$nextTick()
      this.isPersisting = true
      try {
        await this.$store.dispatch(
          `${this.storePrefix}dashboardApplication/updateWidgetLayout`,
          {
            dashboardId: this.dashboard.id,
            layout: toWidgetLayoutPayload(this.layout),
          }
        )
      } catch (error) {
        notifyIf(error, 'dashboard')
      } finally {
        this.isPersisting = false
        this.isInteracting = false
        this.syncLayoutFromWidgets()
      }
    },
    async deleteWidget(widgetId) {
      if (!this.canUpdateLayout || this.isPersisting) {
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
