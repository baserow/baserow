<template>
  <ServiceRefinementForms
    v-bind="$attrs"
    :values="values"
    :table-fields="tableFields"
    :filter-count-override="filterCount"
  >
    <template v-for="(_, name) in $slots" #[name]="slotProps">
      <slot :name="name" v-bind="slotProps" />
    </template>
    <template #after-filter-form>
      <div
        v-if="inheritedGroups.length"
        class="dashboard-widget-filters dashboard-widget-filters--compact"
        :class="{ 'margin-top-1': !values.filters?.length }"
      >
        <WidgetFilterGroups
          :groups="inheritedGroups"
          :dashboard="dashboard"
          :fields="tableFields"
          :filter-type="values.filter_type"
          :title="$t('dashboardServiceRefinementForms.dashboardFilters')"
          :show-leading-operator="Boolean(values.filters?.length)"
        />
      </div>
    </template>
  </ServiceRefinementForms>
</template>

<script setup>
import ServiceRefinementForms from '@baserow/modules/integrations/localBaserow/components/services/ServiceRefinementForms'
import WidgetFilterGroups from '@baserow/modules/dashboard/components/widget/WidgetFilterGroups'
import {
  countFilterGroupConditions,
  getWidgetFilterGroups,
} from '@baserow/modules/dashboard/utils/widgetFilters'

defineOptions({ inheritAttrs: false })

const props = defineProps({
  values: { type: Object, required: true },
  tableFields: { type: Array, required: true },
  widget: { type: Object, required: true },
  dashboard: { type: Object, required: true },
  storePrefix: { type: String, default: '' },
})
const { $store, $registry } = useNuxtApp()
provide('storePrefix', toRef(props, 'storePrefix'))

const inheritedGroups = computed(() =>
  getWidgetFilterGroups(
    $store.getters[`${props.storePrefix}dashboardApplication/getWidgets`],
    props.widget.id,
    $registry
  )
)
const filterCount = computed(
  () =>
    (props.values.filters?.length || 0) +
    countFilterGroupConditions(inheritedGroups.value)
)
</script>
