<template>
  <Modal ref="modal" wide :can-close="!busy" @hidden="$emit('hidden')">
    <template v-if="widget">
      <h2 class="box__title">
        {{ $t('textFilterWidget.configureNewWidget') }}
      </h2>
      <WidgetSettings
        ref="settings"
        :widget="widget"
        :dashboard="dashboard"
        :store-prefix="storePrefix"
        :small="false"
        :exclude-filter-widget-id="excludeFilterWidgetId"
      />
      <Alert v-if="failedSaves.size" type="error" class="margin-top-2">
        {{ $t('textFilterWidget.configurationSaveFailed') }}
      </Alert>
      <div class="align-right margin-top-3">
        <Button
          :loading="busy"
          :disabled="busy || failedSaves.size > 0"
          @click="finish"
          >{{ $t('textFilterWidget.addToFilter') }}</Button
        >
      </div>
    </template>
  </Modal>
</template>

<script setup>
import WidgetSettings from '@baserow/modules/dashboard/components/widget/WidgetSettings'

const props = defineProps({
  dashboard: { type: Object, required: true },
  widgetId: { type: Number, required: true },
  storePrefix: { type: String, default: '' },
  loading: { type: Boolean, default: false },
  excludeFilterWidgetId: { type: Number, default: null },
})
const emit = defineEmits(['configured', 'hidden'])
const { $store, $registry } = useNuxtApp()
const modal = ref(null)
const settings = ref(null)
const pending = reactive(new Set())
const failedSaves = reactive(new Set())
const prefix = computed(() => `${props.storePrefix}dashboardApplication`)
const widget = computed(() =>
  $store.getters[`${prefix.value}/getWidgets`].find(
    (item) => item.id === props.widgetId
  )
)
const busy = computed(() => props.loading || pending.size > 0)
watch(widget, (value) => {
  if (!value) modal.value?.hide()
})

/** Track the ordinary settings saves, including debounced widget updates. */
const unsubscribe = $store.subscribeAction({
  before(action) {
    const sourceId =
      widget.value &&
      $registry
        .get('dashboardWidget', widget.value.type)
        .getDataSourceId(widget.value)
    if (
      (action.type === `${prefix.value}/updateWidget` &&
        action.payload.widgetId === props.widgetId) ||
      (action.type === `${prefix.value}/updateDataSource` &&
        action.payload.dataSourceId === sourceId)
    ) {
      pending.add(action)
      failedSaves.delete(action.type)
    }
  },
  after(action) {
    pending.delete(action)
  },
  error(action) {
    if (pending.delete(action)) failedSaves.add(action.type)
  },
})
onBeforeUnmount(unsubscribe)

async function finish() {
  // Let blur/change handlers start their save before checking pending work.
  await nextTick()
  if (busy.value || failedSaves.size || !settings.value?.validate()) return
  emit('configured', widget.value)
}
defineExpose({
  show: () => modal.value.show(),
  hide: () => modal.value.hide(),
})
</script>
