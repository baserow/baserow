<template>
  <div class="dashboard-app">
    <DashboardHeader
      :dashboard="dashboard"
      :loading="loading"
      :is-creating-widget="isCreatingWidget"
      :store-prefix="storePrefix"
      @widget-variation-selected="addWidget"
    />
    <DashboardContent
      :dashboard="dashboard"
      :loading="loading"
      :is-creating-widget="isCreatingWidget"
      :store-prefix="storePrefix"
      @widget-variation-selected="addWidget"
    />
  </div>
</template>

<script>
import { computed, reactive } from 'vue'
import DashboardHeader from '@baserow/modules/dashboard/components/DashboardHeader'
import DashboardContent from '@baserow/modules/dashboard/components/DashboardContent'
import { notifyIf } from '@baserow/modules/core/utils/error'

export default {
  name: 'Dashboard',
  components: { DashboardHeader, DashboardContent },
  provide() {
    return {
      storePrefix: computed(() => this.storePrefix),
      dashboardWidgetCreation: computed(() => this.widgetCreation),
      createDashboardWidget: this.createWidget,
    }
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
    loading: {
      type: Boolean,
      required: true,
    },
  },
  data() {
    return {
      widgetCreation: null,
    }
  },
  computed: {
    isCreatingWidget() {
      return this.widgetCreation?.loading ?? false
    },
  },
  watch: {
    'dashboard.id'() {
      this.widgetCreation = null
    },
  },
  beforeUnmount() {
    this.widgetCreation = null
  },
  methods: {
    async addWidget(variation) {
      try {
        await this.createWidget({
          type: variation.type.getType(),
          params: variation.params,
        })
      } catch (error) {
        notifyIf(error, 'dashboard')
      }
    },
    async createWidget({ type: widgetType, params, select = true }) {
      if (this.isCreatingWidget) {
        return
      }

      const dashboard = this.dashboard
      const store = `${this.storePrefix}dashboardApplication`
      const type = this.$registry.get('dashboardWidget', widgetType)
      const widget = {
        title: type.name,
        type: widgetType,
        ...params,
      }
      const creation = reactive({
        title: widget.title,
        size: type.initialGridSize,
        widgetId: null,
        loading: true,
      })
      const wasEditing = this.$store.getters[`${store}/isEditMode`]
      this.widgetCreation = creation
      try {
        await this.$store.dispatch(`${store}/enterEditMode`)
        return await this.$store.dispatch(`${store}/createWidget`, {
          dashboard,
          widget,
          select,
          onCreated: (widgetId) => {
            creation.widgetId = widgetId
          },
        })
      } catch (error) {
        if (
          this.widgetCreation === creation &&
          creation.widgetId === null &&
          !wasEditing &&
          this.$store.getters[`${store}/getDashboardId`] === dashboard.id &&
          this.$store.getters[`${store}/isEditMode`]
        ) {
          this.$store.dispatch(`${store}/toggleEditMode`)
        }
        throw error
      } finally {
        creation.loading = false
        if (this.widgetCreation === creation && creation.widgetId === null) {
          this.widgetCreation = null
        }
      }
    },
  },
}
</script>
