<template>
  <FormGroup
    class="dashboard-text-filter-widget"
    :label="widget.title"
    small-label
    required
  >
    <template v-if="isNotApplied" #after-label>
      <Badge
        v-tooltip="$t('textFilterWidget.notAppliedHelp')"
        color="yellow"
        size="small"
        class="dashboard-text-filter-widget__not-applied"
        >{{ $t('textFilterWidget.notApplied') }}</Badge
      >
    </template>
    <div
      v-if="widget.mode === 'dropdown'"
      class="dashboard-text-filter-widget__dropdown-wrapper"
      @pointerdown.stop
      @mousedown.stop
    >
      <Dropdown
        v-model="value"
        :multiple="multiple"
        class="dashboard-text-filter-widget__dropdown"
        :class="{
          'dashboard-text-filter-widget__dropdown--active': hasValue,
        }"
        :show-footer="hasValue || optionState.error"
        :loading="optionState.loading"
      >
        <template #selectedValue>
          <i class="dropdown__selected-icon iconoir-filter" />
          <span class="dropdown__selected-text" :title="displayValue">{{
            displayValue
          }}</span>
        </template>
        <template #defaultValue>
          <i class="dropdown__selected-icon iconoir-filter" />
          <span
            class="dropdown__selected-text"
            :class="{ 'dropdown__selected-placeholder': !hasValue }"
            :title="displayValue"
            >{{
              displayValue || widget.placeholder || $t('action.makeChoice')
            }}</span
          >
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
              v-if="hasValue"
              type="secondary"
              size="small"
              button-type="button"
              @click="value = multiple ? [] : ''"
              >{{ $t('textFilterWidget.clear') }}</Button
            >
          </div>
        </template>
      </Dropdown>
      <div class="dashboard-text-filter-widget__actions">
        <slot name="actions" />
      </div>
    </div>
    <FormInput
      v-else
      v-model="inputValue"
      :error="numberInputError"
      class="dashboard-text-filter-widget__input"
      :class="{ 'dashboard-text-filter-widget__input--active': value !== '' }"
      icon-left="iconoir-filter"
      :placeholder="
        widget.placeholder || $t('textFilterWidget.inputDefaultPlaceholder')
      "
      :maxlength="TEXT_FILTER_MAX_VALUE_LENGTH"
      @blur="onInputBlur"
      @pointerdown.stop
      @mousedown.stop
    >
      <template #suffix>
        <slot name="actions" />
      </template>
    </FormInput>
  </FormGroup>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import {
  getTextFilterDefaultValue,
  isTextFilterNumberInput,
  normalizeTextFilterNumber,
  TEXT_FILTER_MAX_VALUE_LENGTH,
} from '@baserow/modules/dashboard/utils/widgetFilters'
import { useWidgetOptions } from '@baserow/modules/dashboard/composables/useWidgetOptions'
import { useStore } from 'vuex'
import { useNuxtApp } from '#app'
import FormGroup from '@baserow/modules/core/components/FormGroup'
import FormInput from '@baserow/modules/core/components/FormInput'

const props = defineProps({
  widget: { type: Object, required: true },
  storePrefix: { type: String, default: '' },
  loading: { type: Boolean, default: false },
})

const store = useStore()
const { $registry } = useNuxtApp()
const isEditMode = computed(
  () => store.getters[`${props.storePrefix}dashboardApplication/isEditMode`]
)
const hasConditions = (group) =>
  Boolean(group?.filters?.length || group?.filter_groups?.length)
/**
 * Editors see when the filter changes nothing on the dashboard: it links no
 * widget, or only links without any condition.
 */
const isNotApplied = computed(() => {
  if (!isEditMode.value) return false
  const links = props.widget.target_filters
  if (!links) {
    return !$registry
      .get('dashboardWidget', props.widget.type)
      .getTargetWidgetIds(props.widget).length
  }
  return !links.some(
    (link) =>
      link.enabled !== false &&
      (hasConditions(link.group) ||
        (link.empty_behavior === 'apply_alternative' &&
          hasConditions(link.alternative_group)))
  )
})
const multiple = computed(
  () => props.widget.mode === 'dropdown' && props.widget.multiple === true
)
const { optionState, options } = useWidgetOptions(props)
const value = computed({
  get: () =>
    store.getters[`${props.storePrefix}dashboardApplication/getWidgetValues`][
      props.widget.id
    ] ?? getTextFilterDefaultValue(props.widget),
  set: (value) =>
    store.dispatch(`${props.storePrefix}dashboardApplication/setWidgetValue`, {
      widgetId: props.widget.id,
      value,
    }),
})
const numberInput = computed(() => isTextFilterNumberInput(props.widget))
const numberDraft = ref(null)
const numberInputError = ref(false)
const inputValue = computed({
  get: () =>
    numberInput.value ? (numberDraft.value ?? value.value) : value.value,
  set: (draft) => {
    if (!numberInput.value) {
      value.value = draft
      return
    }
    numberDraft.value = draft
    numberInputError.value = false
    const normalized = normalizeTextFilterNumber(draft)
    if (normalized !== null && normalized !== value.value) {
      value.value = normalized
    }
  },
})

function onInputBlur() {
  if (!numberInput.value) return
  numberInputError.value = normalizeTextFilterNumber(inputValue.value) === null
  if (!numberInputError.value) numberDraft.value = null
}

watch(numberInput, () => {
  numberDraft.value = null
  numberInputError.value = false
})

const hasValue = computed(() => value.value.length > 0)
const displayValue = computed(() =>
  Array.isArray(value.value) ? value.value.join(', ') : value.value
)
</script>
