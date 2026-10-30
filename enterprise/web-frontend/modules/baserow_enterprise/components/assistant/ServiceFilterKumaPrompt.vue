<template>
  <KumaInlinePrompt
    ref="kumaPrompt"
    :enabled="Boolean(target?.id)"
    :title="$t('serviceFilterKumaPrompt.title')"
    :placeholder="$t('serviceFilterKumaPrompt.placeholder')"
    :submit-label="$t('serviceFilterKumaPrompt.submit')"
    :working-label="$t('serviceFilterKumaPrompt.working')"
    :suggestions="suggestions"
    :blocked-message="blockedMessage"
    :request="updateFilters"
    error-name="dataSource"
    with-divider
    @active="filterForm?.setFrozen($event)"
  />
</template>

<script setup>
import { computed, inject, onBeforeUnmount, ref, toValue, watch } from 'vue'
import AssistantService from '@baserow_enterprise/services/assistant'
import KumaInlinePrompt from '@baserow_enterprise/components/assistant/KumaInlinePrompt'

/**
 * Lets the user describe the filters they want for a data source or automation
 * node, and has Kuma create, change or remove them. Kuma saves the filters, as
 * the same request in a chat would; the open form picks them up through the
 * realtime update.
 *
 * Kuma works from the saved filters, so the filters are frozen while the request
 * is written and sent, and unsaved filter changes must be saved first. A table
 * picked for a data source without one is sent along, and saved with the filters.
 */
const app = useNuxtApp()
const t = (key) => app.$i18n.t(key)

const injectedTarget = inject('serviceFilterTarget', null)
const target = computed(() => toValue(injectedTarget))
const serviceFilters = inject('serviceFilters', null)
const filterForm = inject('serviceFilterForm', null)

const kumaPrompt = ref(null)

const hasUnsavedChanges = computed(
  () => serviceFilters?.hasUnsavedChanges() ?? false
)

const blockedMessage = computed(() => {
  if (serviceFilters?.hasUnsavedTableChange?.()) {
    return t('serviceFilterKumaPrompt.unsavedTable')
  }
  if (hasUnsavedChanges.value) {
    return t('serviceFilterKumaPrompt.unsavedChanges')
  }
  return ''
})

// Undo reverts the latest change, which stops being Kuma's once the user edits the
// filters again, so the summary and its undo go away.
watch(hasUnsavedChanges, (unsaved) => {
  if (unsaved) {
    kumaPrompt.value?.dismiss()
  }
})
onBeforeUnmount(() => filterForm?.setFrozen(false))

const SUGGESTIONS = {
  builder_data_source: ['pageParameter', 'user', 'change'],
  automation_node: ['previousNode', 'change'],
  dashboard_data_source: ['change'],
}

const suggestions = computed(() =>
  (SUGGESTIONS[target.value?.kind] || []).map((key) => ({
    key,
    label: t(`serviceFilterKumaPrompt.suggestion_${key}`),
    prompt: t(`serviceFilterKumaPrompt.suggestion_${key}_prompt`),
  }))
)

function updateFilters(message) {
  return AssistantService(app.$client).updateServiceFilters(
    target.value.kind,
    target.value.id,
    message,
    serviceFilters?.getUnsavedTableId?.() ?? null
  )
}
</script>
