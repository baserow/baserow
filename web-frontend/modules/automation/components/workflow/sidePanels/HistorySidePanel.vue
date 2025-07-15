<template>
  <div
    v-if="!workflowHistoryItems.length"
    class="empty-automation-side-panel-state"
  >
    <i
      class="baserow-icon-automation empty-automation-side-panel-state__icon"
    ></i>
    <h4>{{ $t('historySidePanel.noRunsTitle') }}</h4>
    <p class="margin-top-0">
      {{ $t('historySidePanel.noRunsDescription') }}
    </p>
  </div>
  <div v-else>
    <HistorySection
      v-for="item in workflowHistoryItems"
      :key="item.id"
      :item="item"
    />
  </div>
</template>

<script setup>
import { computed, useStore } from '@nuxtjs/composition-api'
import HistorySection from '@baserow/modules/automation/components/workflow/sidePanels/HistorySection'
const store = useStore()

const workflowHistoryItems = computed(() => {
  const history = store.getters['automationHistory/getWorkflowHistory']()
  return history?.results || []
})
</script>
