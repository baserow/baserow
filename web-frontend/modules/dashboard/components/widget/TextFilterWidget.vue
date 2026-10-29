<template>
  <div class="dashboard-text-filter-widget">
    <input
      v-model="value"
      class="dashboard-text-filter-widget__input"
      type="text"
      :aria-label="widget.title"
      :placeholder="widget.placeholder"
      @pointerdown.stop
      @mousedown.stop
    />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useStore } from 'vuex'

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
