<template>
  <FormGroup
    class="dashboard-text-filter-widget"
    :label="widget.title"
    small-label
    required
  >
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
      v-model="value"
      class="dashboard-text-filter-widget__input"
      :class="{ 'dashboard-text-filter-widget__input--active': value !== '' }"
      icon-left="iconoir-filter"
      :placeholder="widget.placeholder"
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
import { computed } from 'vue'
import { getTextFilterDefaultValue } from '@baserow/modules/dashboard/utils/widgetFilters'
import { useWidgetOptions } from '@baserow/modules/dashboard/composables/useWidgetOptions'
import { useStore } from 'vuex'
import FormGroup from '@baserow/modules/core/components/FormGroup'
import FormInput from '@baserow/modules/core/components/FormInput'

const props = defineProps({
  widget: { type: Object, required: true },
  storePrefix: { type: String, default: '' },
  loading: { type: Boolean, default: false },
})

const store = useStore()
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
const hasValue = computed(() => value.value.length > 0)
const displayValue = computed(() =>
  Array.isArray(value.value) ? value.value.join(', ') : value.value
)
</script>
