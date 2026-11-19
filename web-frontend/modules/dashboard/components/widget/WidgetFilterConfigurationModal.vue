<template>
  <Modal ref="modal" wide @hidden="modalOpen = false">
    <div v-if="modalOpen" class="dashboard-widget-filters">
      <div class="dashboard-widget-filters__header">
        <h2 class="box__title">
          {{ $t('textFilterWidget.conditionsFor', { widget: target.title }) }}
        </h2>
        <p class="dashboard-widget-filters__subtitle">
          {{
            $t('textFilterWidget.conditionsSubtitle', { filter: widget.title })
          }}
        </p>
      </div>
      <WidgetFilterConditions
        :widget="widget"
        :dashboard="dashboard"
        :target="target"
        :source="source"
        :store-prefix="storePrefix"
        :unavailable-reason="unavailableReason"
        :link="link"
        @update="$emit('update', $event)"
      />
      <div class="dashboard-widget-filters__footer">
        <Button type="secondary" @click="hide()">{{
          $t('action.close')
        }}</Button>
      </div>
    </div>
  </Modal>
</template>

<script setup>
import WidgetFilterConditions from '@baserow/modules/dashboard/components/widget/WidgetFilterConditions'

defineProps({
  widget: { type: Object, required: true },
  dashboard: { type: Object, required: true },
  target: { type: Object, required: true },
  source: { type: Object, default: null },
  storePrefix: { type: String, default: '' },
  unavailableReason: { type: String, default: null },
  link: { type: Object, required: true },
})
defineEmits(['update'])

const modal = ref(null)
const modalOpen = ref(false)
const show = () => {
  modalOpen.value = true
  modal.value.show()
}
const hide = () => modal.value.hide()

defineExpose({ show, hide })
</script>
