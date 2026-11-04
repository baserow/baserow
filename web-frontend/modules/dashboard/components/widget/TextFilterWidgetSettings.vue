<template>
  <FormSection>
    <FormGroup
      small-label
      :label="$t('textFilterWidget.placeholder')"
      class="margin-bottom-2"
      required
    >
      <FormInput
        :model-value="widget.placeholder"
        @blur="updateSetting('placeholder', $event.target.value)"
      />
    </FormGroup>
    <FormGroup
      small-label
      :label="$t('textFilterWidget.defaultValue')"
      class="margin-bottom-2"
      required
    >
      <FormInput
        :model-value="widget.default_value"
        @blur="updateSetting('default_value', $event.target.value)"
      />
    </FormGroup>
    <FormGroup
      small-label
      :label="$t('textFilterWidget.filterType')"
      class="margin-bottom-2"
      required
    >
      <SegmentControl
        :segments="[
          { label: $t('textFilterWidget.input') },
          { label: $t('textFilterWidget.dropdown') },
        ]"
        :active-index="widget.mode === 'dropdown' ? 1 : 0"
        @update:active-index="
          updateSetting('mode', $event === 1 ? 'dropdown' : 'input')
        "
      />
    </FormGroup>
    <FormGroup
      v-if="widget.mode === 'dropdown'"
      small-label
      :label="$t('textFilterWidget.selection')"
      class="margin-bottom-2"
      required
    >
      <SegmentControl
        :segments="[
          { label: $t('textFilterWidget.singleValue') },
          { label: $t('textFilterWidget.multipleValues') },
        ]"
        :active-index="widget.multiple ? 1 : 0"
        @update:active-index="updateSetting('multiple', $event === 1)"
      />
    </FormGroup>
    <FormGroup
      v-if="widget.mode === 'dropdown'"
      small-label
      :label="$t('textFilterWidget.filterValues')"
      :helper-text="$t('textFilterWidget.filterValuesHelp')"
      class="margin-bottom-2"
      required
    >
      <DashboardFormulaInput
        allow-node-selection="value"
        placeholder=""
        :model-value="widget.options || {}"
        :data-providers-allowed="['table']"
        @input="updateSetting('options', $event)"
      />
    </FormGroup>
    <FormGroup small-label required>
      <template #label>{{ $t('textFilterWidget.targets') }}</template>
      <template #after-label
        ><Badge size="small">{{ linkedTargets.length }}</Badge></template
      >
      <p class="dashboard-widget-filter-targets__help">
        {{ $t('textFilterWidget.targetsHelp') }}
      </p>
      <div class="dashboard-widget-filter-targets__list">
        <ItemCard
          v-for="candidate in linkedTargets"
          :key="candidate.id"
          :name="candidate.title"
          :title="candidate.title"
          :show-icon="false"
          role="button"
          class="dashboard-widget-filter-target"
          @click="openFilters(candidate)"
        >
          <template #meta>
            <span
              :class="{
                'dashboard-widget-filter-target__pending':
                  !conditionCount(candidate.id) || !canFilter(candidate),
              }"
            >
              {{
                !canFilter(candidate)
                  ? unavailableTargetReason(candidate)
                  : conditionCount(candidate.id)
                    ? $t(
                        'textFilterWidget.conditionCount',
                        { count: conditionCount(candidate.id) },
                        conditionCount(candidate.id)
                      )
                    : $t('textFilterWidget.setUpConditions')
              }}
            </span>
          </template>
          <template #actions>
            <i
              class="iconoir-nav-arrow-right dashboard-widget-filter-target__chevron"
            />
            <ButtonIcon
              size="small"
              icon="baserow-icon-more-vertical"
              :aria-label="
                $t('textFilterWidget.targetOptions', {
                  widget: candidate.title,
                })
              "
              @click.stop="openTargetMenu(candidate, $event)"
            />
          </template>
        </ItemCard>
        <p
          v-if="!linkedTargets.length"
          class="dashboard-widget-filter-targets__empty"
        >
          {{ $t('textFilterWidget.noTargets') }}
        </p>
      </div>
      <Button
        type="secondary"
        icon="iconoir-plus"
        full-width
        class="margin-top-1"
        @click="openTargetPicker"
        >{{ $t('textFilterWidget.addWidgets') }}</Button
      >
      <Dropdown
        ref="targetPicker"
        v-model="selectedTargets"
        :show-input="false"
        :tabindex="-1"
        multiple
        show-search
        show-footer
        fixed-items
      >
        <DropdownItem
          v-for="candidate in availableTargets"
          :key="candidate.id"
          :name="candidate.title"
          :value="candidate.id"
          :disabled="!canFilter(candidate)"
          :description="
            !canFilter(candidate) ? unavailableTargetReason(candidate) : null
          "
        />
        <template #emptyState>{{
          $t('textFilterWidget.noAvailableTargets')
        }}</template>
        <template #footer>
          <div class="dashboard-widget-filter-targets__actions">
            <Button
              type="secondary"
              size="small"
              @click="targetPicker.hide()"
              >{{ $t('action.cancel') }}</Button
            >
            <Button
              size="small"
              :disabled="!selectedTargets.length"
              :loading="targetsSaving"
              @click="addTargets"
              >{{ $t('action.add') }}</Button
            >
          </div>
        </template>
      </Dropdown>
    </FormGroup>
    <Context ref="targetMenu">
      <ul v-if="menuTarget" class="context__menu">
        <li class="context__menu-item">
          <a
            class="context__menu-item-link"
            role="button"
            tabindex="0"
            @click="openFilters(menuTarget)"
            @keydown.enter.prevent="openFilters(menuTarget)"
          >
            <i class="context__menu-item-icon iconoir-filter" />{{
              $t('textFilterWidget.configureFilters')
            }}
          </a>
        </li>
        <li class="context__menu-item context__menu-item--with-separator">
          <a
            class="context__menu-item-link context__menu-item-link--delete"
            :class="{ 'context__menu-item-link--loading': targetsSaving }"
            role="button"
            tabindex="0"
            @click="removeTarget"
            @keydown.enter.prevent="removeTarget"
          >
            <i class="context__menu-item-icon iconoir-bin" />{{
              $t('textFilterWidget.removeLink')
            }}
          </a>
        </li>
      </ul>
    </Context>
    <WidgetFilterConfigurationModal
      v-if="target"
      ref="groupModal"
      :widget="widget"
      :dashboard="dashboard"
      :target="target"
      :source="source"
      :link="link"
      :fields="fields"
      :readonly-groups="readonlyGroups"
      :fields-loading="fieldsLoading"
      :unavailable-reason="
        !canFilter(target) ? unavailableTargetReason(target) : null
      "
      :fields-error="fieldsError"
      :has-incompatible-conditions="hasIncompatibleConditions"
      @retry="loadFields(source?.table_id)"
      @update="updateLink"
    />
  </FormSection>
</template>

<script setup>
import ItemCard from '@baserow/modules/core/components/ItemCard'
import DashboardFormulaInput from '@baserow/modules/dashboard/components/DashboardFormulaInput'
import WidgetFilterConfigurationModal from '@baserow/modules/dashboard/components/widget/WidgetFilterConfigurationModal'
import FieldService from '@baserow/modules/database/services/field'
import { notifyIf } from '@baserow/modules/core/utils/error'
import { getWidgetFilterGroups } from '@baserow/modules/dashboard/utils/widgetFilters'

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
const fieldsError = ref(false)
const targetPicker = ref(null)
const targetMenu = ref(null)
const menuTarget = ref(null)
const selectedTargets = ref([])
const targetsSaving = ref(false)
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
    (widget) => $registry.get('dashboardWidget', widget.type).isDisplayWidget
  )
)
const configured = (id) =>
  (props.widget.target_filters || []).some(
    (link) => link.target_widget_id === id
  )
const target = computed(() =>
  targets.value.find(
    (widget) => widget.id === targetId.value && configured(widget.id)
  )
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
  return [
    ...groups,
    ...getWidgetFilterGroups(
      $store.getters[`${props.storePrefix}dashboardApplication/getWidgets`],
      targetId.value,
      $registry,
      props.widget.id
    ),
  ]
})
const linkedTargets = computed(() =>
  targets.value.filter((widget) => configured(widget.id))
)
const availableTargets = computed(() =>
  targets.value.filter((widget) => !configured(widget.id))
)
const conditionCount = (id) => {
  const contribution = props.widget.target_filters?.find(
    (link) => link.target_widget_id === id
  )
  return (
    (contribution?.group?.filters?.length || 0) +
    (contribution?.empty_behavior === 'apply_alternative'
      ? contribution.alternative_group?.filters?.length || 0
      : 0)
  )
}
const openFilters = async (candidate) => {
  targetMenu.value?.hide()
  targetId.value = candidate.id
  await nextTick()
  groupModal.value?.show()
}
watch(target, (value) => {
  if (!value) groupModal.value?.hide()
})

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
    menuTarget.value = null
    selectedTargets.value = []
    targetMenu.value?.hide()
    targetPicker.value?.hide()
  }
)
let fieldsRequest = 0
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
watch(() => source.value?.table_id, loadFields)
onBeforeUnmount(() => {
  fieldsRequest++
})
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
const openTargetPicker = (event) => {
  selectedTargets.value = []
  targetPicker.value.show(event.currentTarget)
}
const openTargetMenu = (candidate, event) => {
  menuTarget.value = candidate
  targetMenu.value.toggle(event.currentTarget, 'bottom', 'right', 4)
}
async function addTargets() {
  if (targetsSaving.value) return
  const candidates = availableTargets.value.filter(
    (candidate) =>
      selectedTargets.value.includes(candidate.id) && canFilter(candidate)
  )
  if (!candidates.length) return
  targetsSaving.value = true
  try {
    const saved = await updateSetting('target_filters', [
      ...(props.widget.target_filters || []),
      ...candidates.map((candidate) => ({
        target_widget_id: candidate.id,
        group: emptyGroup(),
        empty_behavior: 'apply_nothing',
      })),
    ])
    if (saved) targetPicker.value?.hide()
  } finally {
    targetsSaving.value = false
  }
}
async function removeTarget() {
  if (targetsSaving.value || !menuTarget.value) return
  const id = menuTarget.value.id
  targetsSaving.value = true
  try {
    const saved = await updateSetting(
      'target_filters',
      (props.widget.target_filters || []).filter(
        (link) => link.target_widget_id !== id
      )
    )
    if (saved) {
      targetMenu.value?.hide()
      if (targetId.value === id) {
        groupModal.value?.hide()
        targetId.value = null
      }
    }
  } finally {
    targetsSaving.value = false
  }
}
/** Save configuration through the shared undoable widget update flow. */
async function updateSetting(field, value) {
  if (value === props.widget[field]) return
  const settings = {
    mode: props.widget.mode || 'input',
    multiple: props.widget.multiple || false,
    options: props.widget.options || {},
    placeholder: props.widget.placeholder,
    default_value: props.widget.default_value,
    target_filters: props.widget.target_filters || [],
  }
  try {
    await $store.dispatch(
      `${props.storePrefix}dashboardApplication/updateWidget`,
      {
        widgetId: props.widget.id,
        values: { ...settings, [field]: value },
        originalValues: settings,
      }
    )
    return true
  } catch (error) {
    notifyIf(error, 'dashboard')
    return false
  }
}
</script>
