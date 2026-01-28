<template>
  <div class="empty-dashboard">
    <div class="empty-dashboard__content">
      <div class="empty-dashboard__content-title">
        {{ t('emptyDashboard.title') }}
      </div>
      <div v-if="canCreateWidget" class="empty-dashboard__content-subtitle">
        {{ t('emptyDashboard.subtitle') }}
      </div>
      <Button
        v-if="canCreateWidget"
        type="primary"
        icon="iconoir-plus"
        @click="openCreateWidgetModal"
        >{{ t('emptyDashboard.addWidget') }}</Button
      >
    </div>
    <CreateWidgetModal
      ref="createWidgetModal"
      :dashboard="dashboard"
      @widget-variation-selected="$emit('widget-variation-selected', $event)"
    />
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useNuxtApp } from '#app'
import CreateWidgetModal from '@baserow/modules/dashboard/components/CreateWidgetModal'

const props = defineProps({
  dashboard: {
    type: Object,
    required: true,
  },
})

defineEmits(['widget-variation-selected'])

const { t } = useI18n()
const { $hasPermission } = useNuxtApp()

const createWidgetModal = ref(null)

const canCreateWidget = computed(() => {
  if (!props.dashboard?.workspace?.id) {
    return false
  }
  return $hasPermission(
    'dashboard.create_widget',
    props.dashboard,
    props.dashboard.workspace.id
  )
})

const openCreateWidgetModal = () => {
  createWidgetModal.value?.show()
}
</script>
