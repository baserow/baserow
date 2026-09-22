<template>
  <div class="history-side-panel">
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
          {{ history.success_count || 0 }}
        </div>
      </div>
      <div class="history-side-panel__counts-runs">
        <div class="history-side-panel__counts-runs-label">
          {{ $t('historySidePanel.failedRuns') }}
        </div>
        <div class="history-side-panel__counts-runs-total">
          {{ history.fail_count || 0 }}
        </div>
      </div>
    </div>

    <div ref="content" class="history-side-panel__content">
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
      <div v-else class="history-side-panel__items">
        <WorkflowHistory
          v-for="item in workflowHistoryItems"
          :key="item.id"
          :item="item"
        />
      </div>
    </div>
    <div v-if="history.count" class="history-side-panel__pagination">
      <Paginator
        :page="page"
        :total-pages="totalPages"
        @change-page="changePage"
      />
    </div>
  </div>
</template>

<script setup>
import { useStore } from 'vuex'
import Paginator from '@baserow/modules/core/components/Paginator'
import { WORKFLOW_HISTORY_PAGE_SIZE } from '@baserow/modules/automation/services/history'
import { notifyIf } from '@baserow/modules/core/utils/error'
import WorkflowHistory from '@baserow/modules/automation/components/workflow/sidePanels/WorkflowHistory'
const store = useStore()
const workflow = inject('workflow')
const loading = computed(() => store.state.automationHistory.loading)
const page = computed(() => store.state.automationHistory.page)
const content = ref(null)
const history = computed(() =>
  store.getters['automationHistory/getWorkflowHistory']()
)
const workflowHistoryItems = computed(() => history.value?.results || [])
const totalPages = computed(() =>
  Math.max(
    1,
    Math.ceil((history.value?.count || 0) / WORKFLOW_HISTORY_PAGE_SIZE)
  )
)

const changePage = async (newPage) => {
  try {
    store.dispatch('automationHistory/invalidate')
    const data = await store.dispatch(
      'automationHistory/fetchWorkflowHistory',
      {
        workflowId: workflow.value.id,
        page: newPage,
      }
    )
    if (data && content.value) content.value.scrollTop = 0
  } catch (error) {
    notifyIf(error, 'automationWorkflow')
  }
}
const refreshData = () => changePage(1)
watch(
  () => workflow.value.id,
  () => {
    store.dispatch('automationHistory/reset')
    refreshData()
  },
  { immediate: true }
)
onBeforeUnmount(() => store.dispatch('automationHistory/reset'))
const closeHistory = () =>
  store.dispatch('automationWorkflow/setActiveSidePanel', null)
</script>
