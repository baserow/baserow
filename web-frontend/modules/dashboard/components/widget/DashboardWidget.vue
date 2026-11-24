<template>
  <div
    v-skeleton="{ loading: isInitialLoading, height: '100%' }"
    class="dashboard-widget"
    :class="{
      'dashboard-widget--selected': isSelected,
      'dashboard-widget--selectable': isSelectable,
      'dashboard-widget--layout-editable': isLayoutEditable,
      'dashboard-widget--plain': !widgetType.hasCard,
      'dashboard-widget--filter-target': isFilterTarget,
    }"
    @click="selectWidgetIfAllowed(widget.id)"
    @focusin="leaveLockedControl"
  >
    <div
      v-if="widgetType.hasCard && isSelected && isEditMode"
      class="dashboard-widget__name"
    >
      {{ widgetType.name }}
    </div>
    <div
      v-if="widgetType.hasCard"
      class="widget__header"
      :class="{
        'widget__header--edit-mode': isEditMode,
        'widget__header--no-border': !widgetType.showHeaderBorder,
      }"
    >
      <div class="widget__header-main">
        <div class="widget__header-title-wrapper">
          <div class="widget__header-title">{{ widget.title }}</div>
          <span
            v-if="isFiltered"
            v-tooltip="filterStatusLabel"
            class="dashboard-widget__filter-status"
            :class="{
              'dashboard-widget__filter-status--values': activeFilterValues,
            }"
            role="img"
            :aria-label="filterStatusLabel"
          >
            <i class="iconoir-filter" aria-hidden="true"></i>
            <span
              v-if="activeFilterValues"
              class="dashboard-widget__filter-values"
              >{{ activeFilterValues }}</span
            >
          </span>
          <span
            v-if="isMisconfigured"
            v-tooltip="$t('widget.fixConfiguration')"
            class="dashboard-widget__configuration-status"
            role="img"
            :aria-label="$t('widget.fixConfiguration')"
          >
            <i class="iconoir-warning-circle" aria-hidden="true"></i>
          </span>
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
    <span
      v-if="isLoading && !isInitialLoading"
      class="dashboard-widget__refreshing"
      role="status"
      :aria-label="$t('dashboard.widgetsLoading')"
    ></span>
    <component
      :is="widgetComponent(widget.type)"
      :widget="widget"
      :store-prefix="storePrefix"
      :loading="isInitialLoading"
      :class="{ 'dashboard-widget__content--locked': areControlsLocked }"
    >
      <template v-if="!widgetType.hasCard && isEditMode" #actions>
        <WidgetContextMenu
          class="dashboard-widget__actions"
          :widget="widget"
          :dashboard="dashboard"
          @delete-widget="$emit('delete-widget', $event)"
        />
      </template>
    </component>
  </div>
</template>

<script>
import WidgetContextMenu from '@baserow/modules/dashboard/components/widget/WidgetContextMenu'
import { getFiltersOfWidget } from '@baserow/modules/dashboard/utils/widgetFilters'

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
    /**
     * While editing, a click selects the widget instead of using its controls,
     * and they can't take focus. The actions it is given stay usable.
     */
    areControlsLocked() {
      return this.isEditMode && this.widgetType.hasControls
    },
    isLoading() {
      return this.widgetType.isLoading(
        this.widget,
        this.widgetData,
        this.withoutLiveData
      )
    },
    withoutLiveData() {
      return this.$store.getters[
        `${this.storePrefix}dashboardApplication/isWithoutLiveData`
      ]
    },
    isInitialLoading() {
      return (
        this.isLoading &&
        !this.widgetType.hasLoadedData(this.widget, this.widgetData)
      )
    },
    widgetData() {
      return this.$store.getters[
        `${this.storePrefix}dashboardApplication/getData`
      ]
    },
    isFiltered() {
      return (
        this.widgetType.isDisplayWidget &&
        this.widgetType.getDataSourceData(this.widget, this.widgetData)
          ?._is_filtered === true
      )
    },
    filters() {
      return getFiltersOfWidget(
        this.$store.getters[
          `${this.storePrefix}dashboardApplication/getWidgets`
        ],
        this.widget.id,
        this.$registry
      )
    },
    /** The values of the filters currently narrowing this widget down. */
    activeFilterValues() {
      const values =
        this.$store.getters[
          `${this.storePrefix}dashboardApplication/getWidgetValues`
        ]
      return this.filters
        .flatMap((filter) => {
          const value =
            values[filter.id] ??
            this.$registry
              .get('dashboardWidget', filter.type)
              .getDefaultValue(filter)
          return Array.isArray(value) ? value : value ? [value] : []
        })
        .join(', ')
    },
    filterStatusLabel() {
      return this.filters.length
        ? this.$t('widget.filteredBy', {
            filters: this.filters.map((filter) => filter.title).join(', '),
          })
        : this.$t('widget.filteredResults')
    },
    /** Shows which widgets the selected filter applies to while editing. */
    isFilterTarget() {
      if (!this.isEditMode || this.selectedWidgetId === this.widget.id) {
        return false
      }
      const selected = this.$store.getters[
        `${this.storePrefix}dashboardApplication/getWidgets`
      ].find((widget) => widget.id === this.selectedWidgetId)
      const type =
        selected && this.$registry.get('dashboardWidget', selected.type)
      return Boolean(
        type?.isFilterWidget &&
        type.getTargetWidgetIds(selected).includes(this.widget.id)
      )
    },
    isMisconfigured() {
      return this.widgetType.isMisconfigured(this.widget, this.widgetData)
    },
  },
  methods: {
    widgetComponent(type) {
      const widgetType = this.$registry.get('dashboardWidget', type)
      return widgetType.component
    },
    /** A label or the keyboard can still focus a locked control: leave it. */
    leaveLockedControl(event) {
      if (
        this.areControlsLocked &&
        event.target.closest('.dashboard-widget__content--locked') &&
        !event.target.closest('.dashboard-widget__actions')
      ) {
        event.target.blur()
      }
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
