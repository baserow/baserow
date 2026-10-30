<template>
  <div class="dashboard-filter-settings">
    <FormGroup
      :label="$t('dashboardFilter.label')"
      required
      small-label
      class="margin-bottom-2"
    >
      <FormInput
        v-model="label"
        :maxlength="255"
        :error="!label?.trim()"
        :disabled="!canEdit"
        @blur="saveLabel"
        @keydown.enter.prevent="saveLabel"
      />
    </FormGroup>
    <FormGroup
      :label="$t('dashboardFilter.type')"
      small-label
      required
      class="margin-bottom-2"
    >
      <Dropdown
        :model-value="filter.type"
        :disabled="!canEdit || savingFormat"
        @update:model-value="changeType"
      >
        <DropdownItem
          value="text"
          :name="$t('dashboardFilter.text')"
          icon="iconoir-text"
        />
        <DropdownItem
          value="number"
          :name="$t('dashboardFilter.number')"
          icon="baserow-icon-hashtag"
        />
        <DropdownItem
          value="date"
          :name="$t('dashboardFilter.date')"
          icon="iconoir-calendar"
        />
      </Dropdown>
    </FormGroup>
    <FormGroup
      :label="$t('dashboardFilter.operator')"
      small-label
      required
      class="margin-bottom-2"
    >
      <Dropdown
        :model-value="filter.operator || 'equal'"
        :disabled="!canEdit || savingFormat"
        @update:model-value="changeOperator"
      >
        <DropdownItem
          v-for="operator in operators"
          :key="operator.type"
          :value="operator.type"
          :name="operator.getName()"
        />
      </Dropdown>
    </FormGroup>
    <FormGroup
      v-if="filterHasValue(filter)"
      :label="$t('dashboardFilter.mode')"
      small-label
      required
      class="margin-bottom-2"
    >
      <SegmentControl
        :segments="[
          { label: $t('dashboardFilter.dropdown') },
          { label: $t('dashboardFilter.input') },
        ]"
        :active-index="filter.mode === 'dropdown' ? 0 : 1"
        @update:active-index="
          requestFormatChange({ mode: $event === 0 ? 'dropdown' : 'input' })
        "
      />
    </FormGroup>
    <FormGroup
      v-if="filterHasOptions(filter)"
      :label="$t('dashboardFilter.usersCanPick')"
      small-label
      required
      class="margin-bottom-2"
    >
      <SegmentControl
        :segments="[
          { label: $t('dashboardFilter.multiple') },
          { label: $t('dashboardFilter.single') },
        ]"
        :active-index="filter.multiple ? 0 : 1"
        @update:active-index="requestFormatChange({ multiple: $event === 0 })"
      />
    </FormGroup>
    <DashboardFilterOptionsForm
      v-if="filterHasOptions(filter)"
      :filter="filter"
      :disabled="!canEdit"
      @save="save"
    />
    <Modal
      ref="confirmation"
      small
      :can-close="!savingFormat"
      role="dialog"
      aria-modal="true"
      :aria-label="pendingFormatCopy.title"
      @hidden="pendingFormat = null"
    >
      <h2 class="box__title">
        {{ pendingFormatCopy.title }}
      </h2>
      <p>
        {{
          $t(
            filter.mode === 'input'
              ? 'dashboardFilter.confirmResetInputMessage'
              : 'dashboardFilter.confirmResetMessage',
            { filter: filter.label }
          )
        }}
      </p>
      <div class="actions actions--right actions--gap margin-bottom-0">
        <Button
          type="secondary"
          :disabled="savingFormat"
          @click="confirmation.hide()"
        >
          {{ $t('action.cancel') }}
        </Button>
        <Button
          type="primary"
          :loading="savingFormat"
          :disabled="savingFormat || !canEdit || !pendingFormat"
          @click="confirmFormatChange"
        >
          {{ pendingFormatCopy.action }}
        </Button>
      </div>
    </Modal>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, provide, ref, watch } from 'vue'
import { useNuxtApp } from '#app'
import DashboardFilterOptionsForm from '@baserow/modules/dashboard/components/filter/DashboardFilterOptionsForm'
import DashboardFormulaInput from '@baserow/modules/dashboard/components/DashboardFormulaInput'
import {
  filterHasOptions,
  filterHasValue,
  shouldResetFilterValues,
} from '@baserow/modules/dashboard/utils/filter'
import { notifyIf } from '@baserow/modules/core/utils/error'

const props = defineProps({
  filter: { type: Object, required: true },
  dashboard: { type: Object, required: true },
  storePrefix: { type: String, default: '' },
})
const { $store, $hasPermission, $i18n, $registry } = useNuxtApp()
const operators = computed(() =>
  Object.values($registry.getAll('viewFilter')).filter(
    (operator) =>
      !operator.isDeprecated() &&
      operator.fieldIsCompatible({ type: props.filter.type })
  )
)
const label = ref(props.filter.label)
const confirmation = ref(null)
const pendingFormat = ref(null)
const savingFormat = ref(false)
const pendingFormatCopy = computed(() => {
  if (!pendingFormat.value) return { title: '', action: '' }
  const { type, mode, multiple, operator } = pendingFormat.value
  const target =
    (type ? 'Type' : null) ??
    (operator ? 'Operator' : null) ??
    { dropdown: 'Dropdown', input: 'Input' }[mode] ??
    (multiple ? 'Multiple' : 'Single')
  return {
    title: $i18n.t(`dashboardFilter.confirm${target}Title`),
    action: $i18n.t(`dashboardFilter.confirm${target}`),
  }
})
provide('formulaComponent', DashboardFormulaInput)
provide('dataProvidersAllowed', ['table'])
provide(
  'dashboardApplicationContext',
  computed(() => ({
    dashboard: props.dashboard,
    storePrefix: props.storePrefix,
  }))
)
const canEdit = computed(() =>
  $hasPermission(
    'dashboard.filter.update',
    props.filter,
    props.dashboard.workspace.id
  )
)
watch(
  () => [props.filter.id, props.filter.label],
  () => {
    label.value = props.filter.label
  }
)
watch(
  [
    () => props.dashboard.id,
    () => props.filter.id,
    () => props.filter.type,
    () => props.filter.mode,
    () => props.filter.multiple,
    () => props.filter.operator,
  ],
  () => confirmation.value?.hide()
)
onBeforeUnmount(() => confirmation.value?.hide())
function requestFormatChange(values) {
  if (
    !canEdit.value ||
    savingFormat.value ||
    pendingFormat.value ||
    !shouldResetFilterValues(props.filter, { ...props.filter, ...values })
  )
    return
  if (!props.filter.values?.length) return saveFormatChange(values)
  pendingFormat.value = values
  confirmation.value.show()
}
function changeOperator(operator) {
  if (operator === props.filter.operator) return
  const values = { operator }
  if (shouldResetFilterValues(props.filter, { ...props.filter, ...values })) {
    requestFormatChange(values)
  } else {
    save(values)
  }
}
function changeType(type) {
  if (type === props.filter.type) return
  requestFormatChange({ type, operator: type === 'date' ? 'date_is' : 'equal' })
}
async function confirmFormatChange() {
  if (!canEdit.value || savingFormat.value || !pendingFormat.value) return
  const updated = await saveFormatChange(pendingFormat.value)
  if (updated) confirmation.value?.hide()
}
async function saveFormatChange(values) {
  savingFormat.value = true
  try {
    return await save(values)
  } finally {
    savingFormat.value = false
  }
}
async function save(values) {
  if (!canEdit.value) return
  try {
    return await $store.dispatch(
      `${props.storePrefix}dashboardApplication/updateFilter`,
      { filterId: props.filter.id, values }
    )
  } catch (error) {
    label.value = props.filter.label
    notifyIf(error, 'dashboard')
  }
}
function saveLabel() {
  if (label.value?.trim() && label.value !== props.filter.label)
    return save({ label: label.value })
}
</script>
