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

const { $store } = useNuxtApp()

// Must precede the stylesheets and scripts, or they send the token as Referer.
// A number does that; aliases like 'critical' don't.
useHead({
  meta: [{ name: 'referrer', content: 'no-referrer', tagPriority: 0 }],
})

// The middlewares refreshed the permissions without the token.
if ($store.getters['auth/isAuthenticated']) {
  await $store.dispatch('auth/refresh').catch(() => {})
}
</script>
