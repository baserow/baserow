<template>
  <Context ref="context" overflow-scroll max-height-if-outside-viewport>
    <ul class="context__menu">
      <li v-if="canAddFilter" class="context__menu-item">
        <a
          class="context__menu-item-link"
          :class="{ disabled: isCreatingWidget }"
          :aria-disabled="isCreatingWidget"
          role="button"
          tabindex="0"
          @click="addFilter()"
          @keydown.enter.prevent="addFilter()"
        >
          <i class="context__menu-item-icon iconoir-filter"></i>
          {{ $t('widgetContext.addFilter') }}
        </a>
      </li>
      <li v-if="canBeDeleted" class="context__menu-item">
        <a
          class="context__menu-item-link context__menu-item-link--delete"
          @click="deleteWidget()"
        >
          <i class="context__menu-item-icon iconoir-bin"></i>
          {{ $t('widgetContext.delete') }}
        </a>
      </li>
    </ul>
  </Context>
</template>

<script>
import { inject } from 'vue'
import context from '@baserow/modules/core/mixins/context'
import { FF_DASHBOARD_FILTERS } from '@baserow/modules/core/plugins/featureFlags'
import { notifyIf } from '@baserow/modules/core/utils/error'

export default {
  name: 'WidgetContext',
  mixins: [context],
  inject: {
    widgetCreation: { from: 'dashboardWidgetCreation', default: null },
    createDashboardWidget: { default: null },
  },
  props: {
    dashboard: {
      type: Object,
      required: true,
    },
    widget: {
      type: Object,
      required: true,
    },
  },
  emits: ['delete-widget'],
  setup() {
    return { storePrefix: inject('storePrefix', '') }
  },
  computed: {
    prefix() {
      return this.storePrefix?.value ?? this.storePrefix ?? ''
    },
    isCreatingWidget() {
      return this.widgetCreation?.loading ?? false
    },
    /** Display widgets showing a table can get a filter of their own. */
    canAddFilter() {
      const type = this.$registry.get('dashboardWidget', this.widget.type)
      if (
        !this.createDashboardWidget ||
        !type.isDisplayWidget ||
        !this.$featureFlagIsEnabled(FF_DASHBOARD_FILTERS) ||
        !this.$hasPermission(
          'dashboard.create_widget',
          this.dashboard,
          this.dashboard.workspace.id
        )
      ) {
        return false
      }
      return Boolean(this.tableId)
    },
    tableId() {
      const type = this.$registry.get('dashboardWidget', this.widget.type)
      if (!type.isDisplayWidget) return null
      return (
        this.$store.getters[
          `${this.prefix}dashboardApplication/getDataSourceById`
        ](type.getDataSourceId(this.widget))?.table_id || null
      )
    },
    canBeDeleted() {
      return this.$hasPermission(
        'dashboard.widget.delete',
        this.widget,
        this.dashboard.workspace.id
      )
    },
  },
  methods: {
    /** Create a filter of this widget's table, applied to this widget. */
    async addFilter() {
      if (!this.canAddFilter || this.isCreatingWidget) return
      this.hide()
      try {
        await this.createDashboardWidget({
          type: 'text_filter',
          params: {
            target_filters: [
              {
                target_widget_id: this.widget.id,
                enabled: true,
                empty_behavior: 'apply_nothing',
                group: { filter_type: 'AND', filters: [], filter_groups: [] },
              },
            ],
          },
        })
      } catch (error) {
        notifyIf(error, 'dashboard')
      }
    },
    deleteWidget() {
      this.$emit('delete-widget', this.widget.id)
      if (this.$refs.context) {
        this.hide()
      }
    },
  },
}
</script>
