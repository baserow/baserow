<template>
  <KumaContextButton
    ref="kumaPrompt"
    :key="`${target?.kind}:${target?.id}:${actionParameters.table_id}`"
    :label="target?.name || ''"
    :enabled="Boolean(target?.id)"
    :title="$t('serviceFilterKumaPrompt.title')"
    :placeholder="$t('serviceFilterKumaPrompt.placeholder')"
    :blocked-message="blockedMessage"
    action="update_service_filters"
    :parameters="actionParameters"
    @active="filterForm?.setFrozen($event)"
  />
</template>

<script setup>
import { computed, inject, onBeforeUnmount, ref, toValue, watch } from 'vue'
import KumaContextButton from '@baserow_enterprise/components/assistant/KumaContextButton'

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

// A manual edit becomes the latest action in the shared undo history.
watch(hasUnsavedChanges, (unsaved) => {
  if (unsaved) {
    kumaPrompt.value?.dismiss()
  }
})
onBeforeUnmount(() => filterForm?.setFrozen(false))

const actionParameters = computed(() => ({
  kind: target.value?.kind,
  id: target.value?.id,
  table_id: serviceFilters?.getSelectedTableId?.() ?? null,
}))
</script>
