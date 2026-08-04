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
    <span
      v-if="isLayoutEditable"
      class="dashboard-widget__drag-handle"
      :data-testid="`dashboard-widget-drag-handle-${widget.id}`"
      :aria-label="$t('widget.dragWidget')"
      :title="$t('widget.dragWidget')"
    >
      <i class="iconoir-drag" aria-hidden="true"></i>
    </span>
    <div v-if="isSelected && isEditMode" class="dashboard-widget__name">
      {{ widgetType.name }}
    </div>
    <component
      :is="widgetComponent(widget.type)"
      :dashboard="dashboard"
      :widget="widget"
      :store-prefix="storePrefix"
      :loading="isLoading"
      :edit-mode="isEditMode"
      @delete-widget="$emit('delete-widget', $event)"
    />
  </div>
</template>

<script>
export default {
  name: 'DashboardWidget',
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
