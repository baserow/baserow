<template>
  <TemplateModal
    v-if="$featureFlagIsEnabled(FF_USER_TEMPLATES)"
    ref="modal"
    :workspace="workspace"
  />
  <LegacyTemplateModal v-else ref="modal" :workspace="workspace" />
</template>

<script setup>
/**
 * Opens the new template browser when the `user_templates` feature flag is enabled,
 * otherwise the legacy one. Remove together with the flag: point the users of this
 * component at `TemplateModal`.
 */
import { ref } from 'vue'

import { FF_USER_TEMPLATES } from '@baserow/modules/core/plugins/featureFlags'
import TemplateModal from '@baserow/modules/core/components/template/TemplateModal'
import LegacyTemplateModal from '@baserow/modules/core/components/template/legacy/LegacyTemplateModal'

defineProps({
  // When no workspace is provided, the user must choose the workspace to install
  // the template into.
  workspace: {
    type: Object,
    required: false,
    default: null,
  },
})

const modal = ref(null)

const show = (...args) => modal.value.show(...args)
const hide = (...args) => modal.value.hide(...args)

defineExpose({ show, hide })
</script>
