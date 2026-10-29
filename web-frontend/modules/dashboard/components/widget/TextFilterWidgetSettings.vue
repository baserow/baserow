<template>
  <FormSection>
    <FormGroup
      small-label
      :label="$t('textFilterWidget.placeholder')"
      class="margin-bottom-2"
    >
      <FormInput
        :model-value="widget.placeholder"
        @blur="updateSetting('placeholder', $event.target.value)"
      />
    </FormGroup>
    <FormGroup small-label :label="$t('textFilterWidget.defaultValue')">
      <FormInput
        :model-value="widget.default_value"
        @blur="updateSetting('default_value', $event.target.value)"
      />
    </FormGroup>
    <FormGroup
      small-label
      :label="$t('textFilterWidget.targets')"
      class="margin-top-2"
    >
      <SidebarExpandable
        v-for="candidate in targets"
        :key="candidate.id"
        class="dashboard-widget-filter-target"
        :show-handle="false"
        :force-expanded="candidate.id === targetId"
        @toggle="toggleTarget(candidate)"
      >
        <template #title>
          <SwitchInput
            v-tooltip="
              !canFilter(candidate) ? unavailableTargetReason(candidate) : null
            "
            :model-value="configured(candidate.id)"
            :disabled="!canFilter(candidate) && !configured(candidate.id)"
            small
            role="switch"
            :aria-label="
              $t('textFilterWidget.enableTarget', { widget: candidate.title })
            "
            :aria-checked="configured(candidate.id)"
            :aria-disabled="!canFilter(candidate) && !configured(candidate.id)"
            :tabindex="
              canFilter(candidate) || configured(candidate.id) ? 0 : -1
            "
            @click.stop
            @update:model-value="setTargetEnabled(candidate, $event)"
            @keydown.enter.stop.prevent="
              setTargetEnabled(candidate, !configured(candidate.id))
            "
            @keydown.space.stop.prevent="
              setTargetEnabled(candidate, !configured(candidate.id))
            "
          />
          <span class="dashboard-widget-filter-target__name">{{
            candidate.title
          }}</span>
        </template>
        <template v-if="candidate.id === targetId" #default>
          <p v-if="!configured(candidate.id)" class="margin-bottom-2">
            {{
              canFilter(candidate)
                ? $t('textFilterWidget.enableTargetHelp')
                : unavailableTargetReason(candidate)
            }}
          </p>
          <template v-else>
            <FormGroup
              small-label
              :label="$t('textFilterWidget.emptyBehavior')"
              class="margin-bottom-2"
            >
              <Dropdown
                :model-value="link.empty_behavior"
                @update:model-value="updateEmptyBehavior"
              >
                <DropdownItem
                  v-for="policy in policies"
                  :key="policy"
                  :name="$t(`textFilterWidget.${policy}`)"
                  :value="policy"
                />
              </Dropdown>
            </FormGroup>
            <div v-if="fieldsLoading" class="loading" />
            <Alert
              v-else-if="hasIncompatibleConditions"
              type="warning"
              class="margin-bottom-2"
            >
              {{ $t('textFilterWidget.incompatibleConditions') }}
            </Alert>
            <div v-if="!fieldsLoading" class="service-form__filter-buttons">
              <span class="service-form__filter-title">{{
                $t('serviceRefinementForms.refinements')
              }}</span>
              <a
                class="header__filter-link"
                :class="{ 'active active--success': filterCount > 0 }"
                role="button"
                tabindex="0"
                :aria-label="$t('textFilterWidget.configureFilters')"
                @click.prevent="openFilters"
                @keydown.enter.prevent="openFilters"
                @keydown.space.prevent="openFilters"
              >
                <i class="header__filter-icon iconoir-filter" />
                <span class="header__filter-name">{{
                  $t(
                    'serviceRefinementForms.filterTabTitle',
                    { count: filterCount },
                    filterCount
                  )
                }}</span>
              </a>
            </div>
          </template>
        </template>
      </SidebarExpandable>
    </FormGroup>
    <WidgetFilterConfigurationModal
      v-if="target && source"
      ref="groupModal"
      :widget="widget"
      :dashboard="dashboard"
      :target="target"
      :source="source"
      :link="link"
      :fields="fields"
      :readonly-groups="readonlyGroups"
      @update="updateLink"
    />
  </FormSection>
</template>

<script setup>
import SidebarExpandable from '@baserow/modules/core/components/SidebarExpandable.vue'
import WidgetFilterConfigurationModal from '@baserow/modules/dashboard/components/widget/WidgetFilterConfigurationModal'
import FieldService from '@baserow/modules/database/services/field'
import { notifyIf } from '@baserow/modules/core/utils/error'

const props = defineProps({
  widget: { type: Object, required: true },
  dashboard: { type: Object, required: true },
  storePrefix: { type: String, default: '' },
})
const { $store, $client, $registry, $i18n } = useNuxtApp()
const targetId = ref(null)
const groupModal = ref(null)
const fields = ref([])
const fieldsLoading = ref(false)
const policies = ['apply_nothing', 'apply_alternative']
const emptyGroup = () => ({
  filters: [],
  filter_groups: [],
  filter_type: 'AND',
})
const getSource = (widget) =>
  $registry.get('dashboardWidget', widget.type).isDisplayWidget &&
  $store.getters[`${props.storePrefix}dashboardApplication/getDataSourceById`](
    $registry.get('dashboardWidget', widget.type).getDataSourceId(widget)
  )
const canFilter = (widget) =>
  Boolean(
    $registry.get('dashboardWidget', widget.type).isDisplayWidget &&
    getSource(widget)?.table_id &&
    Array.isArray(getSource(widget)?.filters)
  )
const unavailableTargetReason = (widget) =>
  $i18n.t(
    Array.isArray(getSource(widget)?.filters)
      ? 'textFilterWidget.configureSourceFirst'
      : 'textFilterWidget.unsupportedTarget'
  )
const targets = computed(() =>
  $store.getters[`${props.storePrefix}dashboardApplication/getWidgets`].filter(
    (widget) => widget.id !== props.widget.id
  )
)
const target = computed(() =>
  targets.value.find((widget) => widget.id === targetId.value)
)
const source = computed(() => target.value && getSource(target.value))
const hasConditions = (group) => Boolean(group?.filters?.length)
/** Show existing source and other owners' contributions without granting edit access. */
const readonlyGroups = computed(() => {
  const groups = hasConditions(source.value)
    ? [
        {
          key: 'permanent',
          title: $i18n.t('textFilterWidget.permanentGroup'),
          group: source.value,
          owner: null,
        },
      ]
    : []
  for (const owner of $store.getters[
    `${props.storePrefix}dashboardApplication/getWidgets`
  ]) {
    if (
      owner.id === props.widget.id ||
      !$registry.get('dashboardWidget', owner.type).isFilterWidget
    )
      continue
    const contribution = (owner.target_filters || []).find(
      (item) => item.target_widget_id === targetId.value
    )
    if (!contribution) continue
    for (const key of ['group', 'alternative_group']) {
      if (
        key === 'alternative_group' &&
        contribution.empty_behavior !== 'apply_alternative'
      )
        continue
      if (!hasConditions(contribution[key])) continue
      groups.push({
        key: `${owner.id}-${key}`,
        title:
          key === 'group'
            ? owner.title
            : `${owner.title} · ${$i18n.t('textFilterWidget.alternativeGroup')}`,
        group: contribution[key],
        owner,
      })
    }
  }
  return groups
})
const filterCount = computed(() =>
  [
    ...readonlyGroups.value.map((context) => context.group),
    link.value.group,
    ...(link.value.empty_behavior === 'apply_alternative'
      ? [link.value.alternative_group]
      : []),
  ].reduce((count, group) => count + (group?.filters?.length || 0), 0)
)
const openFilters = () => groupModal.value.show()
watch(targetId, () => groupModal.value?.hide())

const hasIncompatibleConditions = computed(() =>
  [link.value.group, link.value.alternative_group]
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
const configured = (id) =>
  (props.widget.target_filters || []).some(
    (link) => link.target_widget_id === id
  )
const link = computed(
  () =>
    (props.widget.target_filters || []).find(
      (link) => link.target_widget_id === targetId.value
    ) || {
      target_widget_id: targetId.value,
      group: emptyGroup(),
      empty_behavior: 'apply_nothing',
    }
)
watch(
  () => props.widget.id,
  () => {
    targetId.value = null
  }
)
watch(
  () => source.value?.table_id,
  async (tableId) => {
    fields.value = []
    if (!tableId) return
    fieldsLoading.value = true
    try {
      const { data } = await FieldService($client).fetchAll(tableId)
      if (source.value?.table_id === tableId) fields.value = data
    } catch (error) {
      notifyIf(error, 'dashboard')
    } finally {
      if (source.value?.table_id === tableId) fieldsLoading.value = false
    }
  }
)
const toggleTarget = (widget) => {
  targetId.value = targetId.value === widget.id ? null : widget.id
}
const updateLink = (value) =>
  updateSetting('target_filters', [
    ...(props.widget.target_filters || []).filter(
      (item) => item.target_widget_id !== targetId.value
    ),
    {
      ...value,
      ...(value.empty_behavior === 'apply_alternative'
        ? { alternative_group: value.alternative_group || emptyGroup() }
        : {}),
    },
  ])
/** Open the alternative editor immediately after enabling its empty-input policy. */
const updateEmptyBehavior = async (empty_behavior) => {
  const selectedTargetId = targetId.value
  await updateLink({ ...link.value, empty_behavior })
  if (
    empty_behavior === 'apply_alternative' &&
    link.value.empty_behavior === 'apply_alternative' &&
    targetId.value === selectedTargetId
  ) {
    openFilters()
  }
}
/** Explicitly opt a target in or remove its contributed group. */
const setTargetEnabled = (candidate, enabled) => {
  if (enabled && !canFilter(candidate)) return
  if (enabled === configured(candidate.id)) return
  const links = props.widget.target_filters || []
  const updated = enabled
    ? [
        ...links,
        {
          target_widget_id: candidate.id,
          group: emptyGroup(),
          empty_behavior: 'apply_nothing',
        },
      ]
    : links.filter((link) => link.target_widget_id !== candidate.id)
  if (enabled) targetId.value = candidate.id
  else if (targetId.value === candidate.id) targetId.value = null
  return updateSetting('target_filters', updated)
}
/** Save configuration through the shared undoable widget update flow. */
async function updateSetting(field, value) {
  if (value === props.widget[field]) return
  try {
    await $store.dispatch(
      `${props.storePrefix}dashboardApplication/updateWidget`,
      {
        widgetId: props.widget.id,
        values: {
          placeholder: props.widget.placeholder,
          default_value: props.widget.default_value,
          target_filters: props.widget.target_filters || [],
          [field]: value,
        },
        originalValues: {
          placeholder: props.widget.placeholder,
          default_value: props.widget.default_value,
          target_filters: props.widget.target_filters || [],
        },
      }
    )
  } catch (error) {
    notifyIf(error, 'dashboard')
  }
}
</script>
