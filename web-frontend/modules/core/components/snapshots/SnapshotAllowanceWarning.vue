<template>
  <Alert v-if="warning" type="warning">
    {{ warning }}
  </Alert>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import SnapshotsService from '@baserow/modules/core/services/snapshots'

/**
 * Warns, before an application is added, when its keep takes the workspace over
 * its snapshot allowance. A new application follows the workspace default keep.
 */
const props = defineProps({
  workspace: {
    type: Object,
    required: true,
  },
})

const { $client } = useNuxtApp()
const { t } = useI18n()

const settings = ref(null)

const warning = computed(() => {
  if (!settings.value) {
    return ''
  }
  const { used, limit, default_keep: defaultKeep } = settings.value
  if (limit === null || limit === 0 || defaultKeep === 0) {
    return ''
  }
  if (used + defaultKeep <= limit) {
    return ''
  }
  return t('snapshotAllowanceWarning.overAllowance', {
    keep: defaultKeep,
    used: used + defaultKeep,
    limit,
  })
})

onMounted(async () => {
  try {
    const { data } = await SnapshotsService($client).getWorkspaceSettings(
      props.workspace.id
    )
    settings.value = data
  } catch {
    // Only workspace admins can read the snapshot settings. The warning is extra
    // context, so anyone else can add applications without it.
    settings.value = null
  }
})
</script>
