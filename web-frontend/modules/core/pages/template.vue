<template>
  <TemplatePage v-if="$featureFlagIsEnabled(FF_USER_TEMPLATES)" />
  <LegacyTemplatePage v-else :key="route.params.slug" />
</template>

<script setup>
// TODO: render only `TemplatePage` once the `user_templates` feature flag is removed.
import { FF_USER_TEMPLATES } from '@baserow/modules/core/plugins/featureFlags'
import TemplatePage from '@baserow/modules/core/components/template/TemplatePage'
import LegacyTemplatePage from '@baserow/modules/core/components/template/legacy/LegacyTemplatePage'

const route = useRoute()

// Keeps the page mounted when another template is opened from its list, so that
// the list keeps its search and category. The legacy page is keyed by the slug.
definePageMeta({
  key: 'template',
  middleware: [
    (to) => {
      const { $store, $featureFlagIsEnabled } = useNuxtApp()
      if (
        $featureFlagIsEnabled(FF_USER_TEMPLATES) &&
        $store.getters['auth/isAuthenticated'] &&
        $store.getters['auth/getUserObject'].completed_onboarding
      ) {
        return navigateTo(
          { name: 'all-workspaces', query: { template: to.params.slug } },
          { replace: true }
        )
      }
    },
  ],
})
</script>
