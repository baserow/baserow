<template>
  <Modal ref="modal" wide :can-close="!busy" @hidden="discard">
    <div v-if="widget && filter" class="configure-filter-target">
      <div class="configure-filter-target__header">
        <h2 class="box__title">
          {{ $t('configureFilterTargetModal.title', { filter: filter.title }) }}
        </h2>
        <p class="configure-filter-target__subtitle">
          {{
            $t('configureFilterTargetModal.subtitle', { filter: filter.title })
          }}
        </p>
      </div>
      <section class="configure-filter-target__widget">
        <h3 class="configure-filter-target__section-title">
          {{ $t('configureFilterTargetModal.widget') }}
        </h3>
        <WidgetSettings
          ref="settings"
          :widget="widget"
          :dashboard="dashboard"
          :store-prefix="storePrefix"
          :link-filter-widget-id="filter.id"
          :show-own-filters="false"
        />
      </section>
      <section
        v-if="link && source"
        class="configure-filter-target__conditions"
      >
        <div class="configure-filter-target__conditions-header">
          <span class="configure-filter-target__conditions-icon">
            <i class="iconoir-filter"></i>
          </span>
          <div>
            <h3 class="configure-filter-target__conditions-title">
              {{
                $t('configureFilterTargetModal.conditions', {
                  filter: filter.title,
                })
              }}
            </h3>
            <p class="configure-filter-target__conditions-help">
              {{ $t('configureFilterTargetModal.conditionsHelp') }}
            </p>
          </div>
        </div>
        <WidgetFilterConditions
          :key="source.table_id"
          :widget="filter"
          :dashboard="dashboard"
          :target="widget"
          :source="source"
          :store-prefix="storePrefix"
          :link="link"
          add-first-filter
          @update="updateLink"
        />
      </section>
      <Alert v-if="failedSaves.size" type="error" class="margin-top-2">
        {{ $t('configureFilterTargetModal.saveFailed') }}
      </Alert>
      <div class="configure-filter-target__footer">
        <Button type="secondary" :disabled="busy" @click="hide()">{{
          $t('action.cancel')
        }}</Button>
        <Button
          :loading="busy"
          :disabled="busy || failedSaves.size > 0"
          @click="finish"
          >{{ $t('configureFilterTargetModal.add') }}</Button
        >
      </div>
    </div>
  </Modal>
</template>

<script setup>
/**
 * Sets up a widget created from a filter's settings, and how the filter
 * narrows it down, in one go. The widget is linked to the filter as soon as it
 * shows a table. Closing the modal without adding the widget deletes it.
 */
import WidgetSettings from '@baserow/modules/dashboard/components/widget/WidgetSettings'
import WidgetFilterConditions from '@baserow/modules/dashboard/components/widget/WidgetFilterConditions'
import { notifyIf } from '@baserow/modules/core/utils/error'

const props = defineProps({
  dashboard: { type: Object, required: true },
  widgetId: { type: Number, required: true },
  /** The filter widget the new widget is added to. */
  linkFilterWidgetId: { type: Number, required: true },
  storePrefix: { type: String, default: '' },
  loading: { type: Boolean, default: false },
})
const emit = defineEmits(['configured', 'hidden'])
const { $store, $registry } = useNuxtApp()
const modal = ref(null)
const settings = ref(null)
const pending = reactive(new Set())
const failedSaves = reactive(new Set())
let added = false
const prefix = computed(() => `${props.storePrefix}dashboardApplication`)
const findWidget = (id) =>
  $store.getters[`${prefix.value}/getWidgets`].find((item) => item.id === id)
const widget = computed(() => findWidget(props.widgetId))
const filter = computed(() => findWidget(props.linkFilterWidgetId))
const sourceId = computed(
  () =>
    widget.value &&
    $registry
      .get('dashboardWidget', widget.value.type)
      .getDataSourceId(widget.value)
)
const source = computed(() =>
  $store.getters[`${prefix.value}/getDataSourceById`](sourceId.value)
)
const link = computed(() =>
  source.value?.table_id
    ? (filter.value?.target_filters || []).find(
        (item) => item.target_widget_id === props.widgetId
      )
    : null
)
const busy = computed(() => props.loading || pending.size > 0)
watch([widget, filter], ([target, owner]) => {
  if (!target || !owner) modal.value?.hide()
})

/** Track the saves of the widget, its source and the filter's links. */
const unsubscribe = $store.subscribeAction({
  before(action) {
    if (
      (action.type === `${prefix.value}/updateWidget` &&
        [props.widgetId, props.linkFilterWidgetId].includes(
          action.payload.widgetId
        )) ||
      (action.type === `${prefix.value}/updateDataSource` &&
        action.payload.dataSourceId === sourceId.value)
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

const emptyGroup = () => ({
  filters: [],
  filter_groups: [],
  filter_type: 'AND',
})
/** Save the conditions the filter applies to the new widget. */
async function updateLink(value) {
  const links = filter.value.target_filters || []
  try {
    await $store.dispatch(`${prefix.value}/updateWidget`, {
      widgetId: filter.value.id,
      values: {
        target_filters: [
          ...links.filter((item) => item.target_widget_id !== props.widgetId),
          {
            ...value,
            ...(value.empty_behavior === 'apply_alternative'
              ? { alternative_group: value.alternative_group || emptyGroup() }
              : {}),
          },
        ],
      },
      originalValues: { target_filters: links },
    })
  } catch (error) {
    notifyIf(error, 'dashboard')
  }
}

async function finish() {
  // Let blur/change handlers start their save before checking pending work.
  await nextTick()
  if (busy.value || failedSaves.size || !settings.value?.validate()) return
  if (!link.value) return
  added = true
  emit('configured', widget.value)
}

/** The widget only exists for this modal: closing it without adding removes it. */
async function discard() {
  if (!added && widget.value) {
    try {
      await $store.dispatch(`${prefix.value}/deleteWidget`, props.widgetId)
    } catch (error) {
      notifyIf(error, 'dashboard')
    }
  }
  emit('hidden')
}

const hide = () => modal.value?.hide()
defineExpose({
  show: () => modal.value.show(),
  hide,
})
</script>
