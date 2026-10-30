<template>
  <FormGroup
    class="dashboard-text-filter-widget"
    :label="widget.title"
    small-label
    required
  >
    <FormInput
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
import { useStore } from 'vuex'
import FormGroup from '@baserow/modules/core/components/FormGroup'
import FormInput from '@baserow/modules/core/components/FormInput'

const props = defineProps({
  widget: { type: Object, required: true },
  storePrefix: { type: String, default: '' },
  loading: { type: Boolean, default: false },
})

const store = useStore()
const value = computed({
  get: () =>
    store.getters[`${props.storePrefix}dashboardApplication/getWidgetValues`][
      props.widget.id
    ] ??
    props.widget.default_value ??
    '',
  set: (value) =>
    store.dispatch(`${props.storePrefix}dashboardApplication/setWidgetValue`, {
      widgetId: props.widget.id,
      value,
    }),
})
</script>
