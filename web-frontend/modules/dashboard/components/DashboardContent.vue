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
              :is-creating-widget="isCreatingWidget"
              @widget-variation-selected="
                $emit('widget-variation-selected', $event)
              "
            />
            <template v-else>
              <WidgetBoard :dashboard="dashboard" :store-prefix="storePrefix" />
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
import DashboardSidebar from '@baserow/modules/dashboard/components/DashboardSidebar'
import DashboardContentHeader from '@baserow/modules/dashboard/components/DashboardContentHeader'
import WidgetBoard from '@baserow/modules/dashboard/components/WidgetBoard'

export default {
  name: 'DashboardContent',
  components: {
    EmptyDashboard,
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
    isCreatingWidget: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  emits: ['widget-variation-selected'],
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
}
</script>
