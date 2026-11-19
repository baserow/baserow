<template>
  <div
    class="workspace-integration-details-field data-table__text-field"
    :class="{ 'workspace-integration-details-field--error': errorMessage }"
    :title="details"
  >
    {{ details }}
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useNuxtApp } from '#app'
import { showIntegrationErrors } from '@baserow/modules/core/utils/integration'

const props = defineProps({
  row: { type: Object, required: true },
  column: { type: Object, required: true },
})

const nuxtApp = useNuxtApp()

const integrationType = computed(() =>
  nuxtApp.$registry.get('integration', props.row.type)
)

const errorMessage = computed(
  () =>
    (showIntegrationErrors(nuxtApp) &&
      integrationType.value.getErrorMessage(props.row)) ||
    null
)

/**
 * Why the integration can't be used when it's in error, otherwise who or what it
 * runs as in the applications of the workspace, or its summary.
 */
const details = computed(
  () =>
    errorMessage.value ||
    integrationType.value.getWorkspaceHint(props.row) ||
    integrationType.value.getSummary(props.row)
)
</script>
