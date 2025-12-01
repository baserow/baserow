<template>
  <div>
    <div v-if="!isLoading">
      <div class="layout__col-2-2 dashboard-app__layout">
        <div
          class="dashboard-app__layout-scrollable"
          :style="{ width: `calc(100% - ${sidebarWidth}px)` }"
        >
          <div
            class="dashboard-app__content"
            :class="{ 'dashboard-app__content--small': isInTemplate }"
          >
            <DashboardContentHeader
              :dashboard="dashboard"
              :store-prefix="storePrefix"
            />
            <EmptyDashboard
              v-if="isEmpty"
              :dashboard="dashboard"
              @widget-variation-selected="createWidget($event)"
            />
            <template v-else>
              <WidgetBoard :dashboard="dashboard" :store-prefix="storePrefix" />
              <CreateWidgetButton
                v-if="isEditMode && canCreateWidget"
                :dashboard="dashboard"
                :store-prefix="storePrefix"
                @widget-variation-selected="createWidget($event)"
              />
            </template>
          </div>
        </div>
        <DashboardSidebar
          v-if="isEditMode"
          :dashboard="dashboard"
          :store-prefix="storePrefix"
          :style="{ width: `${sidebarWidth}px` }"
        />
      </div>
    </div>
  </div>
</template>

<script>
import EmptyDashboard from '@baserow/modules/dashboard/components/EmptyDashboard'
import CreateWidgetButton from '@baserow/modules/dashboard/components/CreateWidgetButton'
import DashboardSidebar from '@baserow/modules/dashboard/components/DashboardSidebar'
import DashboardContentHeader from '@baserow/modules/dashboard/components/DashboardContentHeader'
import WidgetBoard from '@baserow/modules/dashboard/components/WidgetBoard'
import { notifyIf } from '@baserow/modules/core/utils/error'

export default {
  name: 'DashboardContent',
  components: {
    EmptyDashboard,
    CreateWidgetButton,
    WidgetBoard,
    DashboardContentHeader,
    DashboardSidebar,
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
      contentHeight: 0,
    }
  },
  computed: {
    sidebarWidth() {
      if (this.isEditMode) {
        return 352
      }
      return 0
    },
    isEditMode() {
      return this.$store.getters[
        `${this.storePrefix}dashboardApplication/isEditMode`
      ]
    },
    isEmpty() {
      return this.$store.getters[
        `${this.storePrefix}dashboardApplication/isEmpty`
      ]
    },
    isLoading() {
      return this.$store.getters[
        `${this.storePrefix}dashboardApplication/isLoading`
      ]
    },
    isInTemplate() {
      return this.storePrefix === 'template/'
    },
  },
  methods: {
    toggleEditMode() {
      return this.$store.dispatch(
        `${this.storePrefix}dashboardApplication/toggleEditMode`
      )
    },
    enterEditMode() {
      return this.$store.dispatch(
        `${this.storePrefix}dashboardApplication/enterEditMode`
      )
    },
    canCreateWidget() {
      return this.$hasPermission(
        'dashboard.create_widget',
        this.dashboard,
        this.dashboard.workspace.id
      )
    },
    async createWidget(widgetVariation) {
      const widgetType = widgetVariation.type.getType()
      const typeFromRegistry = this.$registry.get('dashboardWidget', widgetType)
      try {
        await this.$store.dispatch('dashboardApplication/createWidget', {
          dashboard: this.dashboard,
          widget: {
            title: typeFromRegistry.name,
            type: widgetType,
            ...widgetVariation.params,
          },
        })
        this.enterEditMode()
      } catch (error) {
        notifyIf(error, 'dashboard')
      }
    },
  },
}
</script>
