<template>
  <div>
    <div v-if="!isLoading">
      <div class="layout__col-2-2 dashboard-app__layout">
        <div
          ref="scrollable"
          class="dashboard-app__layout-scrollable"
          :style="{ width: `calc(100% - ${sidebarWidth}px)` }"
        >
          <div class="dashboard-app__content" :style="contentAppStyle">
            <DashboardContentHeader :dashboard="dashboard" />
            <EmptyDashboard
              v-if="isEmpty"
              :dashboard="dashboard"
              @widget-type-selected="createWidget($event)"
            />
            <template v-else>
              <WidgetBoard
                :dashboard="dashboard"
                @delete-widget="deleteWidget($event)"
              />
              <CreateWidgetButton
                v-if="isEditMode"
                :dashboard="dashboard"
                @widget-type-selected="createWidget($event)"
              />
            </template>
          </div>
        </div>
        <DashboardSidebar
          v-if="isEditMode"
          :dashboard="dashboard"
          style="width: 352px"
        /><!-- TODO: fix hardcoded width -->
      </div>
    </div>
    <div v-else>Loading...</div>
  </div>
</template>

<script>
import EmptyDashboard from '@baserow/modules/dashboard/components/EmptyDashboard'
import CreateWidgetButton from '@baserow/modules/dashboard/components/CreateWidgetButton'
import DashboardSidebar from '@baserow/modules/dashboard/components/DashboardSidebar'
import DashboardContentHeader from '@baserow/modules/dashboard/components/DashboardContentHeader'
import WidgetBoard from '@baserow/modules/dashboard/components/WidgetBoard'
import { mapGetters, mapActions } from 'vuex'
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
  },
  data() {
    return {
      contentHeight: 0,
    }
  },
  computed: {
    ...mapGetters({
      isEditMode: 'dashboardApplication/isEditMode',
      isEmpty: 'dashboardApplication/isEmpty',
      isLoading: 'dashboardApplication/isLoading',
    }),
    sidebarWidth() {
      if (this.isEditMode) {
        return 352
      }
      return 0
    },
    contentAppStyle() {
      const styles = {}
      if (this.isEmpty) {
        styles.height = '100%'
      }
      return styles
    },
  },
  // mounted() {
  //   window.addEventListener('resize', this.handleResizeEvent)
  //   this.handleResizeEvent()
  // },
  // unmounted() {
  //   window.removeEventListener('resize', this.handleResizeEvent)
  // },
  methods: {
    ...mapActions({
      toggleEditMode: 'dashboardApplication/toggleEditMode',
      enterEditMode: 'dashboardApplication/enterEditMode',
    }),
    // TODO:
    // handleResizeEvent() {
    //   if (this.$refs.scrollable) {
    //     const minHeight = window.innerHeight - 100
    //     const contentHeight = this.$refs.scrollable.scrollHeight - 48
    //     this.contentHeight = Math.max(minHeight, contentHeight)
    //   }
    // },
    async createWidget(widgetType) {
      const typeFromRegistry = this.$registry.get(
        'dashboard_widget',
        widgetType
      )
      try {
        await this.$store.dispatch('dashboardApplication/createWidget', {
          dashboard: this.dashboard,
          widget: { title: typeFromRegistry.name, type: widgetType },
        })
        this.enterEditMode()
      } catch (error) {
        notifyIf(error, 'dashboard')
      }
    },
    async deleteWidget(widgetId) {
      try {
        await this.$store.dispatch(
          'dashboardApplication/deleteWidget',
          widgetId
        )
      } catch (error) {
        notifyIf(error, 'dashboard')
      }
    },
  },
}
</script>
