<template>
  <FormGroup
    class="dashboard-filter"
    :class="{
      'dashboard-filter--selected': selected,
      'dashboard-filter--movable': editMode && canReorder && !busy,
    }"
    :label="filter.label"
    :helper-text="upperCaseFirst(operatorName)"
    small-label
    required
  >
    <Dropdown
      ref="dropdown"
      :class="{ 'dashboard-filter__control--active': appliedValues.length }"
      :tooltip="hasUnavailable ? $t('dashboardFilter.unavailableHelp') : null"
      :before-show="beforeShow"
      :disabled="busy || (!editMode && !canApply)"
      :loading="busy && !isOpen"
      @show="onShown"
      @hide="onHidden"
    >
      <template #display>
        <i class="dropdown__selected-icon iconoir-filter" />
        <span
          class="dropdown__selected-text dashboard-filter__value"
          :class="{ 'dropdown__selected-placeholder': !appliedValues.length }"
          >{{
            !filterHasValue(filter)
              ? $t(
                  appliedValues.length
                    ? 'dashboardFilter.active'
                    : 'dashboardFilter.inactive'
                )
              : appliedValues.length > 1
                ? $t('dashboardFilter.selections', {
                    count: appliedValues.length,
                  })
                : displayValue(appliedValues[0]) || $t('dashboardFilter.choose')
          }}</span
        >
        <i
          v-if="hasUnavailable"
          class="iconoir-info-empty dashboard-filter__info"
          :aria-label="$t('dashboardFilter.unavailable')"
        />
      </template>
      <template
        v-if="
          (editMode && (canDuplicate || canDelete)) ||
          (!editMode && canApply && appliedValues.length)
        "
        #suffix
      >
        <ButtonIcon
          v-if="editMode"
          ref="menuTrigger"
          class="dashboard-filter__action"
          type="secondary"
          size="small"
          icon="iconoir-more-vert"
          :aria-label="$t('dashboardFilter.actions')"
          :aria-expanded="menuOpen"
          :disabled="busy || actionsDisabled"
          @click.stop="toggleMenu"
        />
        <ButtonIcon
          v-else
          class="dashboard-filter__action"
          type="secondary"
          size="small"
          icon="iconoir-cancel"
          :aria-label="$t('dashboardFilter.clear')"
          :disabled="busy"
          @click="clear"
        />
      </template>
      <template #content>
        <div
          class="dashboard-filter__context"
          :class="{
            'dashboard-filter__context--dropdown': filter.mode === 'dropdown',
            'dashboard-filter__context--date': usesDateInput,
          }"
        >
          <form novalidate @submit.prevent="apply">
            <div v-if="!filterHasValue(filter)" class="dashboard-filter__input">
              <Checkbox
                :model-value="draft.length > 0"
                :disabled="busy"
                @update:model-value="draft = $event ? ['true'] : []"
              >
                {{ operatorName }}
              </Checkbox>
            </div>
            <template v-else-if="filter.mode === 'dropdown'">
              <SelectSearch
                v-model="search"
                :disabled="busy"
                :aria-label="$t('action.search')"
              />
              <div class="dashboard-filter__operator">
                {{ operatorName }}...
              </div>
              <div class="dashboard-filter__choices">
                <div
                  v-for="value in displayedOptions"
                  :key="value"
                  class="dashboard-filter__choice"
                  :class="{
                    'dashboard-filter__choice--single': !filter.multiple,
                  }"
                >
                  <Checkbox
                    v-if="filter.multiple"
                    :model-value="draft.includes(value)"
                    :disabled="busy"
                    @update:model-value="toggle(value, $event)"
                  >
                    <span class="dashboard-filter__option-value">{{
                      displayValue(value)
                    }}</span>
                  </Checkbox>
                  <Button
                    v-else
                    type="secondary"
                    button-type="button"
                    full-width
                    :disabled="busy"
                    :append-icon="draft.includes(value) ? 'iconoir-check' : ''"
                    class="dashboard-filter__single-choice"
                    :aria-pressed="draft.includes(value)"
                    @click="toggle(value, !draft.includes(value))"
                  >
                    <span class="dashboard-filter__option-value">{{
                      displayValue(value)
                    }}</span>
                  </Button>
                  <span
                    v-if="optionState.unavailable.includes(value)"
                    v-tooltip.focus="$t('dashboardFilter.unavailableHelp')"
                    class="dashboard-filter__unavailable"
                    tabindex="0"
                    :aria-label="$t('dashboardFilter.unavailableHelp')"
                    >{{ $t('dashboardFilter.unavailable') }}</span
                  >
                </div>
                <div
                  v-if="optionState.loading"
                  class="dashboard-filter__message"
                  role="status"
                >
                  {{ $t('dashboardFilter.loading') }}
                </div>
                <div
                  v-else-if="optionState.error"
                  class="dashboard-filter__message"
                  role="status"
                >
                  {{ optionsErrorMessage }}
                  <Button
                    type="secondary"
                    size="small"
                    button-type="button"
                    :disabled="busy"
                    @click="requestOptions()"
                    >{{ $t('action.retry') }}</Button
                  >
                </div>
                <div
                  v-else-if="!displayedOptions.length"
                  class="dashboard-filter__message"
                >
                  {{ $t('dashboardFilter.noOptions') }}
                </div>
                <Button
                  v-if="
                    optionState.next &&
                    !optionState.loading &&
                    !optionState.error
                  "
                  type="secondary"
                  size="small"
                  class="dashboard-filter__more"
                  button-type="button"
                  :disabled="busy"
                  @click="requestOptions(true)"
                  >{{ $t('dashboardFilter.more') }}</Button
                >
              </div>
            </template>
            <div v-else class="dashboard-filter__input">
              <FormGroup
                :label="`${upperCaseFirst(operatorName)}...`"
                small-label
                required
                :error-message="
                  !draftIsValid ? $t('dashboardFilter.invalidDateValue') : ''
                "
              >
                <component
                  :is="operator.getInputComponent(inputField)"
                  v-if="usesDateInput && isOpen"
                  :filter="{
                    field: filter.id,
                    type: filter.operator,
                    value: draft[0] || defaultDateValue,
                  }"
                  :fields="[inputField]"
                  :disabled="busy"
                  :read-only="false"
                  @draft-change="updateDateDraft"
                />
                <FormInput
                  v-else-if="!usesDateInput"
                  ref="input"
                  :type="inputType"
                  :model-value="inputValue"
                  :placeholder="$t('dashboardFilter.inputPlaceholder')"
                  :maxlength="10000"
                  :disabled="busy"
                  @update:model-value="updateInput"
                />
              </FormGroup>
            </div>
            <div class="dashboard-filter__footer">
              <Button
                :disabled="!canApply || busy || !changed || !draftIsValid"
                :loading="busy"
                button-type="submit"
                >{{
                  $t(
                    appliedValues.length
                      ? 'dashboardFilter.update'
                      : 'dashboardFilter.apply'
                  )
                }}</Button
              >
            </div>
          </form>
        </div>
      </template>
    </Dropdown>
    <Context
      v-if="editMode && (canDuplicate || canDelete)"
      ref="menu"
      overflow-scroll
      max-height-if-outside-viewport
      @shown="focusFirstOption"
      @hidden="menuOpen = false"
      @keydown.esc.prevent.stop="closeMenu"
    >
      <ul class="context__menu">
        <li v-if="canDuplicate" class="context__menu-item">
          <button
            ref="duplicateOption"
            type="button"
            class="context__menu-item-link dashboard-filter__menu-option"
            :disabled="busy || actionsDisabled"
            @click="duplicate"
          >
            <i class="context__menu-item-icon iconoir-copy" />
            {{ $t('action.duplicate') }}
          </button>
        </li>
        <li
          v-if="canDelete"
          class="context__menu-item"
          :class="{ 'context__menu-item--with-separator': canDuplicate }"
        >
          <button
            ref="deleteOption"
            type="button"
            class="context__menu-item-link context__menu-item-link--delete dashboard-filter__menu-option"
            :disabled="busy || actionsDisabled"
            @click="remove"
          >
            <i class="context__menu-item-icon iconoir-bin" />
            {{ $t('action.delete') }}
          </button>
        </li>
      </ul>
    </Context>
  </FormGroup>
</template>

<script setup>
import { computed, nextTick, ref, watch } from 'vue'
import Dropdown from '@baserow/modules/core/components/Dropdown'
import Checkbox from '@baserow/modules/core/components/Checkbox'
import FormInput from '@baserow/modules/core/components/FormInput'
import FormGroup from '@baserow/modules/core/components/FormGroup'
import Button from '@baserow/modules/core/components/Button'
import ButtonIcon from '@baserow/modules/core/components/ButtonIcon'
import SelectSearch from '@baserow/modules/core/components/SelectSearch'
import Context from '@baserow/modules/core/components/Context'
import ViewFilterTypeNumber from '@baserow/modules/database/components/view/ViewFilterTypeNumber'
import moment from '@baserow/modules/core/moment'
import {
  DateFilterOperators,
  prepareMultiStepDateValue,
  splitMultiStepDateValue,
  splitTimezoneAndFilterValue,
} from '@baserow/modules/database/utils/date'
import { upperCaseFirst } from '@baserow/modules/core/utils/string'
import { useNuxtApp } from '#app'
import {
  filterHasOptions,
  filterHasDateValue,
  filterHasValue,
  shouldResetFilterValues,
} from '@baserow/modules/dashboard/utils/filter'

const props = defineProps({
  filter: { type: Object, required: true },
  appliedValues: { type: Array, default: () => [] },
  optionState: {
    type: Object,
    default: () => ({
      results: [],
      unavailable: [],
      next: null,
      loading: false,
      error: false,
    }),
  },
  editMode: Boolean,
  selected: Boolean,
  canApply: Boolean,
  canReorder: Boolean,
  canDuplicate: Boolean,
  canDelete: Boolean,
  actionsDisabled: Boolean,
  busy: Boolean,
  // The owner reports save errors and resolves false so the draft stays editable.
  saveValues: { type: Function, required: true },
})
const emit = defineEmits(['select', 'options', 'duplicate', 'delete'])
const { $registry, $i18n } = useNuxtApp()
const operator = computed(() =>
  $registry.get('viewFilter', props.filter.operator || 'equal')
)
const operatorName = computed(() => operator.value.getName())
const inputField = computed(() => ({
  id: props.filter.id,
  type: props.filter.type || 'text',
  date_format: 'ISO',
}))
const usesDateInput = computed(
  () => props.filter.mode === 'input' && filterHasDateValue(props.filter)
)
const usesDayOfMonth = computed(
  () => props.filter.operator === 'date_equals_day_of_month'
)
const defaultDateValue = computed(() =>
  prepareMultiStepDateValue(
    '',
    moment.tz.guess(),
    DateFilterOperators.EXACT_DATE.value
  )
)
const inputType = computed(() =>
  usesDayOfMonth.value ||
  operator.value.getInputComponent(inputField.value) === ViewFilterTypeNumber
    ? 'number'
    : 'text'
)
const inputValue = computed(() =>
  usesDayOfMonth.value
    ? splitTimezoneAndFilterValue(draft.value[0] || '')[1]
    : draft.value[0] || ''
)
const dropdown = ref(null)
const input = ref(null)
const menu = ref(null)
const menuTrigger = ref(null)
const duplicateOption = ref(null)
const deleteOption = ref(null)
const menuOpen = ref(false)
const isOpen = ref(false)
const draft = ref([])
const dateDraft = ref(null)
const search = ref('')
const normalizedDraft = computed(() => {
  if (usesDateInput.value && dateDraft.value?.empty) return []
  return props.filter.mode === 'input'
    ? draft.value.map((value) => value.trim()).filter(Boolean)
    : draft.value
})
const dateOperators = Object.values(DateFilterOperators)
const draftIsValid = computed(
  () => !usesDateInput.value || dateDraft.value?.valid !== false
)
const changed = computed(
  () =>
    JSON.stringify(normalizedDraft.value) !==
    JSON.stringify(props.appliedValues)
)
const optionsErrorMessage = computed(() => {
  const key =
    {
      ERROR_DASHBOARD_FILTER_OPTIONS_TOO_LARGE: 'optionsTooLarge',
      ERROR_DASHBOARD_FILTER_OPTIONS_EXPIRED: 'optionsExpired',
    }[props.optionState.errorCode] ?? 'optionsError'
  return $i18n.t(`dashboardFilter.${key}`)
})
const displayedOptions = computed(() => {
  const query = search.value.toLowerCase()
  return [...new Set([...props.optionState.results, ...draft.value])].filter(
    (value) => displayValue(value).toLowerCase().includes(query)
  )
})
const hasUnavailable = computed(
  () =>
    filterHasOptions(props.filter) &&
    props.appliedValues.some((value) =>
      props.optionState.unavailable.includes(value)
    )
)
const requestOptions = (more = false, useCache = false) =>
  emit('options', {
    more,
    selected: [...new Set([...props.appliedValues, ...draft.value])],
    ...(useCache ? { useCache: true } : {}),
  })

watch(
  () => props.filter,
  (filter, previous) => {
    if (!shouldResetFilterValues(previous, filter)) return
    draft.value = []
    search.value = ''
    dropdown.value?.hide()
  }
)

watch(
  () => props.optionState,
  (options) => {
    if (
      isOpen.value &&
      filterHasOptions(props.filter) &&
      !options.loaded &&
      !options.loading &&
      !options.error
    )
      requestOptions(false, true)
  }
)

function beforeShow() {
  if (props.editMode) {
    emit('select')
    return false
  }
  if (!props.canApply || props.busy) return false
}
function displayValue(value = '') {
  if (usesDayOfMonth.value) return splitTimezoneAndFilterValue(value)[1]
  if (!filterHasDateValue(props.filter)) return value
  const [, dateValue, operatorValue] = splitMultiStepDateValue(value)
  const dateOperator = dateOperators.find(
    ({ value }) => value === operatorValue
  )
  if (!dateOperator) return value
  if (dateOperator.hasDateInputValue) return dateValue
  const label = $i18n.t(dateOperator.stringKey)
  return dateOperator.hasNrInputValue ? `${dateValue} ${label}` : label
}
function updateDateDraft(state) {
  dateDraft.value = state
  draft.value = [state.value]
}
function updateInput(value) {
  if (usesDayOfMonth.value && value !== '') {
    const [timezone] = splitTimezoneAndFilterValue(draft.value[0] || '')
    draft.value = [`${timezone || moment.tz.guess()}?${value}`]
  } else {
    draft.value = [value]
  }
}
function toggleMenu(event) {
  if (!props.busy && !props.actionsDisabled) {
    menu.value.toggle(event.currentTarget, 'bottom', 'right', 8, -8)
  }
}
async function focusFirstOption() {
  menuOpen.value = true
  await nextTick()
  const firstOption = duplicateOption.value || deleteOption.value
  firstOption?.focus()
}
function closeMenu() {
  menu.value.hide()
  menuTrigger.value?.$el.focus()
}
function duplicate() {
  if (
    !props.editMode ||
    !props.canDuplicate ||
    props.busy ||
    props.actionsDisabled
  )
    return
  closeMenu()
  emit('duplicate')
}
function remove() {
  if (
    !props.editMode ||
    !props.canDelete ||
    props.busy ||
    props.actionsDisabled
  )
    return
  closeMenu()
  emit('delete')
}
async function onShown() {
  isOpen.value = true
  draft.value = [...props.appliedValues]
  dateDraft.value = null
  search.value = ''
  if (filterHasOptions(props.filter)) requestOptions(false, true)
  await nextTick()
  input.value?.focus()
}
function onHidden() {
  isOpen.value = false
  draft.value = [...props.appliedValues]
}
function toggle(value, checked) {
  draft.value = checked
    ? props.filter.multiple
      ? [...draft.value, value]
      : [value]
    : draft.value.filter((item) => item !== value)
}
async function apply() {
  if (!props.canApply || props.busy || !changed.value || !draftIsValid.value)
    return
  if (await props.saveValues([...normalizedDraft.value])) close()
}
function clear() {
  if (!props.canApply || props.busy) return
  return props.saveValues([])
}
function close() {
  dropdown.value?.close()
}
</script>
