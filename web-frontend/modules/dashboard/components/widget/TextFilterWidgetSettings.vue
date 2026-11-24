<template>
  <div class="text-filter-widget-settings">
    <section class="text-filter-widget-settings__section">
      <div class="text-filter-widget-settings__heading">
        <h3 class="text-filter-widget-settings__title">
          {{ $t('textFilterWidget.targets') }}
        </h3>
        <Badge size="small">{{ linkedTargets.length }}</Badge>
      </div>
      <FormGroup>
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
            :class="{
              'dashboard-widget-filter-target--disabled': !targetEnabled(
                candidate.id
              ),
            }"
            @click="openFilters(candidate)"
          >
            <template #meta>
              <span
                :class="{
                  'dashboard-widget-filter-target__pending':
                    targetEnabled(candidate.id) &&
                    (!conditionCount(candidate.id) || !canFilter(candidate)),
                }"
              >
                {{
                  !targetEnabled(candidate.id)
                    ? $t('textFilterWidget.targetDisabled')
                    : !canFilter(candidate)
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
              <SwitchInput
                small
                :model-value="targetEnabled(candidate.id)"
                :disabled="targetsSaving"
                role="switch"
                tabindex="0"
                :aria-checked="targetEnabled(candidate.id)"
                :aria-disabled="targetsSaving"
                :aria-label="
                  $t('textFilterWidget.applyToWidget', {
                    widget: candidate.title,
                  })
                "
                @click.stop
                @update:model-value="setTargetEnabled(candidate.id, $event)"
                @keydown.space.stop.prevent="
                  setTargetEnabled(candidate.id, !targetEnabled(candidate.id))
                "
                @keydown.enter.stop.prevent="
                  setTargetEnabled(candidate.id, !targetEnabled(candidate.id))
                "
              />
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
          <div
            v-if="!linkedTargets.length"
            class="dashboard-widget-filter-targets__empty"
          >
            <p>{{ $t('textFilterWidget.noTargets') }}</p>
          </div>
        </div>
        <Button
          type="secondary"
          icon="iconoir-plus"
          full-width
          class="margin-top-1"
          @click="openTargetPicker"
          >{{ $t('textFilterWidget.addWidgets') }}</Button
        >
        <Checkbox
          :checked="widget.apply_to_new_widgets"
          class="dashboard-widget-filter-targets__apply-new"
          @input="updateSetting('apply_to_new_widgets', $event)"
          >{{ $t('textFilterWidget.applyToNewWidgets') }}</Checkbox
        >
        <Dropdown
          ref="targetPicker"
          :model-value="null"
          :disabled="targetsSaving"
          :show-input="false"
          :tabindex="-1"
          show-search
          show-footer
          fixed-items
          @update:model-value="addTarget"
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
              <ButtonText
                icon="iconoir-plus"
                class="dashboard-widget-filter-targets__create"
                :disabled="!canCreateTarget"
                @click="openCreateWidget"
                >{{ $t('textFilterWidget.createWidget') }}</ButtonText
              >
              <Button
                type="secondary"
                size="small"
                @click="targetPicker.hide()"
                >{{ $t('action.cancel') }}</Button
              >
            </div>
          </template>
        </Dropdown>
      </FormGroup>
    </section>
    <section class="text-filter-widget-settings__section">
      <h3 class="text-filter-widget-settings__title margin-bottom-2">
        {{ $t('textFilterWidget.howItLooks') }}
      </h3>
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
      <!-- A dropdown shows its options, only a typed value needs a hint. -->
      <FormGroup
        v-if="widget.mode !== 'dropdown'"
        small-label
        :label="$t('textFilterWidget.placeholder')"
        class="margin-bottom-2"
        required
      >
        <FormInput
          :model-value="widget.placeholder"
          :placeholder="$t('textFilterWidget.placeholderPlaceholder')"
          @blur="updateSetting('placeholder', $event.target.value)"
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
          :placeholder="$t('textFilterWidget.filterValuesPlaceholder')"
          :model-value="widget.options || {}"
          :data-providers-allowed="['table_context']"
          @input="updateSetting('options', $event)"
        />
      </FormGroup>
      <FormGroup
        small-label
        :label="$t('textFilterWidget.defaultValue')"
        class="margin-bottom-2"
        required
      >
        <Dropdown
          v-if="widget.mode === 'dropdown'"
          :model-value="defaultValue"
          :multiple="widget.multiple"
          :loading="optionState.loading"
          :placeholder="$t('textFilterWidget.defaultValueNone')"
          :show-footer="hasDefaultValue || optionState.error"
          @update:model-value="updateSetting('default_value', $event)"
        >
          <template v-if="hasDefaultValue" #defaultValue>
            <span class="dropdown__selected-text">{{ defaultValueLabel }}</span>
          </template>
          <DropdownItem
            v-for="option in options"
            :key="option"
            :name="option"
            :value="option"
          />
          <template #emptyState>
            {{
              optionState.error
                ? $t('textFilterWidget.optionsError')
                : $t('dropdown.empty')
            }}
          </template>
          <template #footer>
            <div class="dashboard-text-filter-widget__footer">
              <Button
                v-if="hasDefaultValue"
                type="secondary"
                size="small"
                button-type="button"
                @click="
                  updateSetting('default_value', widget.multiple ? [] : '')
                "
                >{{ $t('textFilterWidget.clear') }}</Button
              >
            </div>
          </template>
        </Dropdown>
        <FormInput
          v-else
          :model-value="defaultValue"
          :placeholder="$t('textFilterWidget.defaultValuePlaceholder')"
          @blur="updateSetting('default_value', $event.target.value)"
        />
      </FormGroup>
    </section>
    <FormSection>
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
      <CreateWidgetModal
        ref="createWidgetModal"
        :dashboard="dashboard"
        :loading="isCreatingWidget"
        hide-filters
        @widget-variation-selected="createTarget"
      />
      <ConfigureFilterTargetModal
        v-if="configuringTarget"
        ref="configurationModal"
        :dashboard="dashboard"
        :widget-id="configuringTarget.widgetId"
        :link-filter-widget-id="configuringTarget.filterId"
        :store-prefix="storePrefix"
        @configured="finishTargetCreation"
        @hidden="configuringTarget = null"
      />
      <WidgetFilterConfigurationModal
        v-if="target"
        ref="groupModal"
        :widget="widget"
        :dashboard="dashboard"
        :target="target"
        :source="source"
        :store-prefix="storePrefix"
        :link="link"
        :unavailable-reason="
          !canFilter(target) ? unavailableTargetReason(target) : null
        "
        @update="updateLink"
      />
    </FormSection>
  </div>
</template>

<script setup>
import isEqual from 'lodash/isEqual'
import { useWidgetOptions } from '@baserow/modules/dashboard/composables/useWidgetOptions'
import ItemCard from '@baserow/modules/core/components/ItemCard'
import DashboardFormulaInput from '@baserow/modules/dashboard/components/DashboardFormulaInput'
import ConfigureFilterTargetModal from '@baserow/modules/dashboard/components/widget/ConfigureFilterTargetModal'
import CreateWidgetModal from '@baserow/modules/dashboard/components/CreateWidgetModal'
import WidgetFilterConfigurationModal from '@baserow/modules/dashboard/components/widget/WidgetFilterConfigurationModal'
import { notifyIf } from '@baserow/modules/core/utils/error'
import { getTextFilterDefaultValue } from '@baserow/modules/dashboard/utils/widgetFilters'

const props = defineProps({
  widget: { type: Object, required: true },
  dashboard: { type: Object, required: true },
  storePrefix: { type: String, default: '' },
})
const { $store, $registry, $i18n } = useNuxtApp()
const createDashboardWidget = inject('createDashboardWidget', null)
const widgetCreation = inject('dashboardWidgetCreation', null)
const isCreatingWidget = computed(() => widgetCreation?.value?.loading ?? false)
const { optionState, options } = useWidgetOptions(props)
const defaultValue = computed(() => getTextFilterDefaultValue(props.widget))
const hasDefaultValue = computed(() => defaultValue.value.length > 0)
const defaultValueLabel = computed(() =>
  Array.isArray(defaultValue.value)
    ? defaultValue.value.join(', ')
    : defaultValue.value
)
const targetId = ref(null)
const groupModal = ref(null)
const targetPicker = ref(null)
const targetMenu = ref(null)
const menuTarget = ref(null)
const targetsSaving = ref(false)
const createWidgetModal = ref(null)
const configuringTarget = ref(null)
const configurationModal = ref(null)
const canCreateTarget = computed(
  () =>
    Boolean(createDashboardWidget) &&
    !isCreatingWidget.value &&
    !configuringTarget.value
)
let disposed = false
onBeforeUnmount(() => {
  disposed = true
})
const openCreateWidget = () => {
  if (!canCreateTarget.value) return
  targetPicker.value?.hide()
  createWidgetModal.value?.show()
}
/** Create a widget without leaving the originating filter's settings. */
async function createTarget(variation) {
  const filterId = props.widget.id
  if (!canCreateTarget.value || !variation.type.isDisplayWidget) return
  try {
    const created = await createDashboardWidget({
      type: variation.type.getType(),
      params: variation.params,
      select: false,
    })
    if (!created || disposed || props.widget.id !== filterId) return
    configuringTarget.value = { filterId, widgetId: created.id }
    await nextTick()
    configurationModal.value?.show()
  } catch (error) {
    notifyIf(error, 'dashboard')
  }
}

/** Save a missing association using the filter's current links for undo. */
async function ensureTargetLinked(filterId, targetId) {
  const prefix = `${props.storePrefix}dashboardApplication`
  const filter = $store.getters[`${prefix}/getWidgets`].find(
    (widget) => widget.id === filterId
  )
  if (!filter) return false
  const links = filter.target_filters || []
  if (!links.some((link) => link.target_widget_id === targetId)) {
    await $store.dispatch(`${prefix}/updateWidget`, {
      widgetId: filterId,
      values: {
        target_filters: [
          ...links,
          {
            target_widget_id: targetId,
            enabled: true,
            empty_behavior: 'apply_nothing',
            group: emptyGroup(),
          },
        ],
      },
      originalValues: { target_filters: links },
    })
  }
  return true
}

/** The widget and its conditions are saved as they're set: just close. */
const finishTargetCreation = () => configurationModal.value?.hide()
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
const linkedTargets = computed(() =>
  targets.value.filter((widget) => configured(widget.id))
)
const availableTargets = computed(() =>
  targets.value.filter((widget) => !configured(widget.id))
)
const targetEnabled = (id) =>
  props.widget.target_filters?.find((link) => link.target_widget_id === id)
    ?.enabled !== false
async function setTargetEnabled(id, enabled) {
  if (targetsSaving.value) return
  targetsSaving.value = true
  try {
    await updateSetting(
      'target_filters',
      (props.widget.target_filters || []).map((link) =>
        link.target_widget_id === id ? { ...link, enabled } : link
      )
    )
  } finally {
    targetsSaving.value = false
  }
}
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
    configurationModal.value?.hide()
    configuringTarget.value = null
    targetId.value = null
    menuTarget.value = null
    targetMenu.value?.hide()
    targetPicker.value?.hide()
  }
)
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
  targetPicker.value.show(event.currentTarget)
}
const openTargetMenu = (candidate, event) => {
  menuTarget.value = candidate
  targetMenu.value.toggle(event.currentTarget, 'bottom', 'right', 4)
}
async function addTarget(id) {
  if (targetsSaving.value) return
  const candidate = availableTargets.value.find(
    (widget) => widget.id === id && canFilter(widget)
  )
  if (!candidate) return
  const filterId = props.widget.id
  targetsSaving.value = true
  try {
    const saved = await ensureTargetLinked(filterId, candidate.id)
    if (saved && !disposed && props.widget.id === filterId) {
      targetPicker.value?.hide()
      await openFilters(candidate)
    }
  } catch (error) {
    notifyIf(error, 'dashboard')
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
function updateSetting(field, value) {
  if (isEqual(value, props.widget[field])) return
  return updateSettings({ [field]: value })
}

async function updateSettings(changes) {
  // Only send what changed: a full copy would overwrite settings, like the
  // target links, that another editor changed in the meantime.
  const values = Object.fromEntries(
    Object.entries(changes).filter(
      ([key, value]) => !isEqual(value, props.widget[key])
    )
  )
  if (!Object.keys(values).length) return true
  if (!Object.hasOwn(values, 'default_value')) {
    if (Object.hasOwn(values, 'options')) {
      values.default_value =
        (values.multiple ?? props.widget.multiple) ? [] : ''
    } else if (
      Object.hasOwn(values, 'mode') ||
      Object.hasOwn(values, 'multiple')
    ) {
      values.default_value = getTextFilterDefaultValue({
        ...props.widget,
        ...values,
      })
    }
  }
  const originalValues = Object.fromEntries(
    Object.keys(values).map((key) => [key, props.widget[key]])
  )
  try {
    await $store.dispatch(
      `${props.storePrefix}dashboardApplication/updateWidget`,
      {
        widgetId: props.widget.id,
        values,
        originalValues,
      }
    )
    return true
  } catch (error) {
    notifyIf(error, 'dashboard')
    return false
  }
}
</script>
