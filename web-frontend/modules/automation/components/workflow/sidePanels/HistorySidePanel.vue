<template>
  <div v-if="loading" class="history-side-panel__empty">
    <div class="loading"></div>
  </div>
  <div
    v-else-if="!workflowHistoryItems.length"
    class="history-side-panel__empty"
  >
    <Icon
      class="history-side-panel__empty-icon"
      icon="baserow-icon-automation"
      type="secondary"
    />
    <h4>{{ $t('historySidePanel.noRunsTitle') }}</h4>
    <p class="margin-top-0">
      {{ $t('historySidePanel.noRunsDescription') }}
    </p>
  </div>
  <div v-else>
    <div class="history-side-panel__title">
      <span>
        {{ $t('historySidePanel.title') }}
        <Icon icon="iconoir-refresh" type="secondary" @click="refreshData()" />
      </span>

      <a role="button" @click="closeHistory()">
        <Icon icon="iconoir-cancel" type="secondary" />
      </a>
    </div>

    <div class="history-side-panel__divider"></div>

    <div class="history-side-panel__counts">
      <div class="history-side-panel__counts-runs">
        <div class="history-side-panel__counts-runs-label">
          {{ $t('historySidePanel.successfulRuns') }}
        </div>
        <div class="history-side-panel__counts-runs-total">
          {{ history.success_count }}
        </div>
      </div>
      <div class="history-side-panel__counts-runs">
        <div class="history-side-panel__counts-runs-label">
          {{ $t('historySidePanel.failedRuns') }}
        </div>
        <div class="history-side-panel__counts-runs-total">
          {{ history.fail_count }}
        </div>
      </div>
    </div>

    <WorkflowHistory
      v-for="item in workflowHistoryItems"
      :key="item.id"
      :item="item"
    />
  </div>
</template>

<script setup>
import { useStore } from 'vuex'
import WorkflowHistory from '@baserow/modules/automation/components/workflow/sidePanels/WorkflowHistory'
const store = useStore()

const workflow = inject('workflow')

const loading = ref(false)

const history = computed(() => {
  return store.getters['automationHistory/getWorkflowHistory']()
})

const workflowHistoryItems = computed(() => {
  return history.value?.results || []
})

const refreshData = async () => {
  loading.value = true
  try {
    await store.dispatch('automationHistory/fetchWorkflowHistory', {
      workflowId: workflow.value.id,
    })
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  refreshData()
})

const closeHistory = () => {
  store.dispatch('automationWorkflow/setActiveSidePanel', null)
}
</script>
