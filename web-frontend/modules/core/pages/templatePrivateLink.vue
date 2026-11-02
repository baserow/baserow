<template>
  <TemplatePage />
</template>

<script setup>
/**
 * The page of the private link of a template, which shows the template like
 * `/template/<slug>` does, also to a signed out visitor, who signs in to install
 * it. The token of the link is sent with the requests of the page, see
 * `utils/templatePrivateLink`.
 */
import TemplatePage from '@baserow/modules/core/components/template/TemplatePage'
import { FF_USER_TEMPLATES } from '@baserow/modules/core/plugins/featureFlags'

const { $featureFlagIsEnabled, $store } = useNuxtApp()

if (!$featureFlagIsEnabled(FF_USER_TEMPLATES)) {
  throw createError({
    statusCode: 404,
    message: 'Template not found.',
    data: { report: false },
    fatal: true,
  })
}

// The workspaces of the template can only be previewed by a signed-in user once
// the `workspace_template_ids` of the permissions are refreshed with the token,
// which the middlewares before the page didn't send.
if ($store.getters['auth/isAuthenticated']) {
  await $store.dispatch('auth/refresh').catch(() => {})
}
</script>
