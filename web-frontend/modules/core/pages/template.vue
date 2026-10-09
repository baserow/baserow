<template>
  <TemplatePage v-if="$featureFlagIsEnabled(FF_USER_TEMPLATES)" />
  <LegacyTemplatePage v-else />
</template>

<script setup>
// TODO: render only `TemplatePage` once the `user_templates` feature flag is removed.
import { FF_USER_TEMPLATES } from '@baserow/modules/core/plugins/featureFlags'
import TemplatePage from '@baserow/modules/core/components/template/TemplatePage'
import LegacyTemplatePage from '@baserow/modules/core/components/template/legacy/LegacyTemplatePage'
import workspacesAndApplications from '@baserow/modules/core/middleware/workspacesAndApplications'

// Loads the workspaces of a logged in user, so that they can choose where to
// install the template. The legacy page can't install, so it skips it.
// TODO: use `middleware: ['workspacesAndApplications']` once the flag is removed.
definePageMeta({
  middleware: [
    (to, from) => {
      if (useNuxtApp().$featureFlagIsEnabled(FF_USER_TEMPLATES)) {
        return workspacesAndApplications(to, from)
      }
    },
  ],
})
</script>
