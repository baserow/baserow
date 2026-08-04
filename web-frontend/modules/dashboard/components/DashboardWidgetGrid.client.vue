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
        :data-testid="`dashboard-widget-grid-item-${layoutItem.i}`"
        drag-allow-from=".dashboard-widget__drag-handle"
        @move="startInteraction"
        @resize="startInteraction"
        @moved="persistLayout"
        @resized="persistLayout"
      >
        <DashboardWidget
          v-if="getWidget(layoutItem)"
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
    syncLayoutFromWidgets() {
      this.layout = createWidgetGridLayout(this.widgets, this.columns)
    },
    startInteraction() {
      if (this.canManipulateLayout) {
        this.isInteracting = true
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

      const previousLayout = this.layout.map((item) => ({ ...item }))
      this.isPersisting = true
      this.layout = this.layout.filter((item) => Number(item.i) !== widgetId)

      await this.$nextTick()
      try {
        await this.$store.dispatch(
          `${this.storePrefix}dashboardApplication/deleteWidgetWithLayout`,
          {
            dashboardId: this.dashboard.id,
            widgetId,
            layout: toWidgetLayoutPayload(this.layout),
          }
        )
      } catch (error) {
        this.layout = previousLayout
        notifyIf(error, 'dashboard')
      } finally {
        this.isPersisting = false
        this.syncLayoutFromWidgets()
      }
    },
  },
}
</script>
