<template>
  <Alert v-if="warning" type="warning">
    {{ warning }}
  </Alert>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useNuxtApp } from '#app'
import SnapshotsService from '@baserow/modules/core/services/snapshots'

/**
 * Warns, before an application is added, when its max snapshots takes the workspace over
 * its snapshot allowance. A new application follows the workspace default max snapshots.
 */
const props = defineProps({
  workspace: {
    type: Object,
    required: true,
  },
})

const { $client, $hasPermission } = useNuxtApp()
const { t } = useI18n()

const settings = ref(null)

const warning = computed(() => {
  if (!settings.value) {
    return ''
  }
  const {
    used,
    limit,
    default_max_snapshots: defaultMaxSnapshots,
  } = settings.value
  if (limit === null || limit === 0 || defaultMaxSnapshots === 0) {
    return ''
  }
  if (used + defaultMaxSnapshots <= limit) {
    return ''
  }
  return t('snapshotAllowanceWarning.overAllowance', {
    maxSnapshots: defaultMaxSnapshots,
    used: used + defaultMaxSnapshots,
    limit,
  })
})

onMounted(async () => {
  // Only workspace admins can read the snapshot settings. The warning is extra
  // context, so anyone else can add applications without it.
  if (
    !$hasPermission(
      'workspace.read_snapshot_settings',
      props.workspace,
      props.workspace.id
    )
  ) {
    return
  }
  try {
    const { data } = await SnapshotsService($client).getWorkspaceSettings(
      props.workspace.id
    )
    settings.value = data
  } catch {
    settings.value = null
  }
})
</script>
