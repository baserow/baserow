<template>
  <div
    class="dashboard-widget"
    :class="{
      'dashboard-widget--selected': isSelected,
      'dashboard-widget--selectable': isSelectable,
      'dashboard-widget--layout-editable': isLayoutEditable,
    }"
    @click="selectWidgetIfAllowed(widget.id)"
  >
    <div v-if="isSelected && isEditMode" class="dashboard-widget__name">
      {{ widgetType.name }}
    </div>
    <div
      class="widget__header"
      :class="{
        'widget__header--edit-mode': isEditMode,
        'widget__header--no-border': widget.type === 'summary',
      }"
    >
      <div class="widget__header-main">
        <div class="widget__header-title-wrapper">
          <div class="widget__header-title">{{ widget.title }}</div>

          <Badge
            v-if="dataSourceMisconfigured"
            color="red"
            :size="widget.type === 'summary' ? 'regular' : 'small'"
            indicator
            rounded
            >{{ $t('widget.fixConfiguration') }}</Badge
          >
        </div>
        <div v-if="widget.description" class="widget__header-description">
          {{ widget.description }}
        </div>
      </div>
      <WidgetContextMenu
        v-if="isEditMode"
        :widget="widget"
        :dashboard="dashboard"
        @delete-widget="$emit('delete-widget', $event)"
      ></WidgetContextMenu>
    </div>
    <component
      :is="widgetComponent(widget.type)"
      :widget="widget"
      :store-prefix="storePrefix"
      :loading="isLoading"
    />
  </div>
</template>

<script>
import WidgetContextMenu from '@baserow/modules/dashboard/components/widget/WidgetContextMenu'

export default {
  name: 'DashboardWidget',
  components: { WidgetContextMenu },
  props: {
    dashboard: {
      type: Object,
      required: true,
    },
    widget: {
      type: Object,
      required: true,
    },
    storePrefix: {
      type: String,
      required: false,
      default: '',
    },
    isLayoutEditable: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  emits: ['delete-widget'],
  computed: {
    isSelected() {
      return this.selectedWidgetId === this.widget.id && this.isEditMode
    },
    isSelectable() {
      return this.selectedWidgetId !== this.widget.id && this.isEditMode
    },
    widgetType() {
      return this.$registry.get('dashboardWidget', this.widget.type)
    },
    selectedWidgetId() {
      return this.$store.getters[
        `${this.storePrefix}dashboardApplication/getSelectedWidgetId`
      ]
    },
    isEditMode() {
      return this.$store.getters[
        `${this.storePrefix}dashboardApplication/isEditMode`
      ]
    },
    isLoading() {
      return this.widgetType.isLoading(
        this.widget,
        this.$store.getters[`${this.storePrefix}dashboardApplication/getData`]
      )
    },
    dataSource() {
      return this.$store.getters[
        `${this.storePrefix}dashboardApplication/getDataSourceById`
      ](this.widget.data_source_id)
    },
    dataForDataSource() {
      return this.$store.getters[
        `${this.storePrefix}dashboardApplication/getDataForDataSource`
      ](this.dataSource?.id)
    },
    dataSourceMisconfigured() {
      return Boolean(this.dataForDataSource?._error)
    },
  },
  methods: {
    widgetComponent(type) {
      const widgetType = this.$registry.get('dashboardWidget', type)
      return widgetType.component
    },
    selectWidgetIfAllowed(widgetId) {
      if (this.canSelectWidget()) {
        this.$store.dispatch(
          `${this.storePrefix}dashboardApplication/selectWidget`,
          widgetId
        )
      }
    },
    canSelectWidget() {
      return this.$hasPermission(
        'dashboard.widget.update',
        this.widget,
        this.dashboard.workspace.id
      )
    },
  },
}
</script>
