<template>
  <div class="dashboard-widget-filters__conditions">
    <Alert v-if="unavailableReason" type="warning">{{
      unavailableReason
    }}</Alert>
    <div v-else-if="fieldsLoading" class="loading" />
    <Alert v-else-if="fieldsError" type="error">
      <p>{{ $t('textFilterWidget.fieldsError') }}</p>
      <Button
        type="secondary"
        size="small"
        @click="loadFields(source?.table_id)"
        >{{ $t('action.retry') }}</Button
      >
    </Alert>
    <template v-else>
      <Alert
        v-if="hasIncompatibleConditions"
        type="warning"
        class="margin-bottom-2"
        >{{ $t('textFilterWidget.incompatibleConditions') }}</Alert
      >
      <section class="dashboard-widget-filters__case">
        <h3 class="dashboard-widget-filters__case-title">
          {{ $t('textFilterWidget.withValueTitle') }}
        </h3>
        <p class="dashboard-widget-filters__case-help margin-bottom-2">
          {{ $t('textFilterWidget.withValueHelp') }}
        </p>
        <TargetFilterGroup
          ref="normalGroup"
          :key="`${target.id}-normal`"
          :group="link.group"
          :fields="fields"
          :dashboard="dashboard"
          :owner="widget"
          @update="$emit('update', { ...link, group: $event })"
        />
      </section>
      <section class="dashboard-widget-filters__case">
        <div class="dashboard-widget-filters__case-header">
          <div>
            <h3 class="dashboard-widget-filters__case-title">
              {{ $t('textFilterWidget.whenEmptyTitle') }}
            </h3>
            <p class="dashboard-widget-filters__case-help">
              {{
                link.empty_behavior === 'apply_alternative'
                  ? $t('textFilterWidget.whenEmptyAlternativeHelp')
                  : $t('textFilterWidget.whenEmptyNothingHelp')
              }}
            </p>
          </div>
          <Dropdown
            class="dashboard-widget-filters__empty-behavior"
            :aria-label="$t('textFilterWidget.emptyBehavior')"
            :model-value="link.empty_behavior"
            @update:model-value="updateEmptyBehavior"
          >
            <DropdownItem
              v-for="policy in ['apply_nothing', 'apply_alternative']"
              :key="policy"
              :name="$t(`textFilterWidget.${policy}`)"
              :value="policy"
            />
          </Dropdown>
        </div>
        <TargetFilterGroup
          v-if="link.empty_behavior === 'apply_alternative'"
          :key="`${target.id}-alternative`"
          :group="link.alternative_group || emptyGroup()"
          :fields="fields"
          :dashboard="dashboard"
          :owner="widget"
          @update="$emit('update', { ...link, alternative_group: $event })"
        />
      </section>
      <WidgetFilterGroups
        :groups="readonlyGroups"
        :dashboard="dashboard"
        :fields="fields"
        :filter-type="source?.filter_type || 'AND'"
        :title="$t('textFilterWidget.otherConditions')"
        :show-edit-links="false"
      />
    </template>
  </div>
</template>

<script setup>
/**
 * The conditions a filter widget applies to one of its target widgets: when it
 * has a value, when it is empty, and the other conditions narrowing it down.
 */
import FieldService from '@baserow/modules/database/services/field'
import { getWidgetFilterGroups } from '@baserow/modules/dashboard/utils/widgetFilters'
import TargetFilterGroup from '@baserow/modules/dashboard/components/widget/TargetFilterGroup'
import WidgetFilterGroups from '@baserow/modules/dashboard/components/widget/WidgetFilterGroups'

const props = defineProps({
  widget: { type: Object, required: true },
  dashboard: { type: Object, required: true },
  target: { type: Object, required: true },
  source: { type: Object, default: null },
  storePrefix: { type: String, default: '' },
  unavailableReason: { type: String, default: null },
  link: { type: Object, required: true },
  /** Start a link without conditions with one, like other filter forms do. */
  addFirstFilter: { type: Boolean, default: false },
})
const emit = defineEmits(['update'])
const { $store, $client, $registry, $i18n } = useNuxtApp()
const fields = ref([])
const fieldsLoading = ref(false)
const fieldsError = ref(false)

const hasConditions = (group) => Boolean(group?.filters?.length)
/** Show existing source and other owners' contributions without granting edit access. */
const readonlyGroups = computed(() => {
  const groups = hasConditions(props.source)
    ? [
        {
          key: 'permanent',
          title: $i18n.t('textFilterWidget.permanentGroup'),
          group: props.source,
          owner: null,
        },
      ]
    : []
  return [
    ...groups,
    ...getWidgetFilterGroups(
      $store.getters[`${props.storePrefix}dashboardApplication/getWidgets`],
      props.target.id,
      $registry,
      props.widget.id
    ),
  ]
})
const hasIncompatibleConditions = computed(() =>
  [props.link.group, props.link.alternative_group]
    .filter(Boolean)
    .some((group) =>
      group.filters.some((condition) => {
        const field = fields.value.find((field) => field.id === condition.field)
        return (
          !field ||
          !$registry.get('viewFilter', condition.type).fieldIsCompatible(field)
        )
      })
    )
)
let fieldsRequest = 0
/** Load the target table's fields and ignore superseded requests. */
async function loadFields(tableId) {
  const request = ++fieldsRequest
  fields.value = []
  fieldsError.value = false
  fieldsLoading.value = Boolean(tableId)
  if (!tableId) return
  try {
    const { data } = await FieldService($client).fetchAll(tableId)
    if (request === fieldsRequest) fields.value = data
  } catch (error) {
    if (request === fieldsRequest) fieldsError.value = true
  } finally {
    if (request === fieldsRequest) fieldsLoading.value = false
  }
}
watch(() => props.source?.table_id, loadFields, { immediate: true })
onBeforeUnmount(() => {
  fieldsRequest++
})

const normalGroup = ref(null)
let firstFilterAdded = false
watch(
  normalGroup,
  (group) => {
    const { filters = [], filter_groups: groups = [] } = props.link.group || {}
    if (
      !group ||
      !props.addFirstFilter ||
      firstFilterAdded ||
      filters.length ||
      groups.length
    )
      return
    firstFilterAdded = true
    group.addFirstFilter()
  },
  { flush: 'post' }
)

const emptyGroup = () => ({
  filters: [],
  filter_groups: [],
  filter_type: 'AND',
})
const updateEmptyBehavior = (empty_behavior) =>
  emit('update', {
    ...props.link,
    empty_behavior,
    ...(empty_behavior === 'apply_alternative'
      ? { alternative_group: props.link.alternative_group || emptyGroup() }
      : {}),
  })
</script>
