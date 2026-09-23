<template>
  <div class="layout__col-2-scroll layout__col-2-scroll--white-background">
    <div class="recently-viewed-page">
      <RecentlyViewed
        :title="$t('recentlyViewed.title')"
        view-mode-preference-key="recently_viewed_view_mode"
      >
        <template #empty-action>
          <Button
            type="secondary"
            tag="a"
            @click="navigateTo({ name: 'all-workspaces' })"
            >{{ $t('recentlyViewed.goToWorkspaces') }}</Button
          >
        </template>
      </RecentlyViewed>
    </div>
  </div>
</template>

<script setup>
import { useNuxtApp, navigateTo } from '#app'
import { useHead } from '#imports'

import RecentlyViewed from '@baserow/modules/core/components/recentlyViewed/RecentlyViewed'
import { SIDEBAR_TYPES } from '@baserow/modules/core/utils/constants'

definePageMeta({
  layout: 'app',
  sidebarType: SIDEBAR_TYPES.ALL_WORKSPACES,
  middleware: [
    'settings',
    'authenticated',
    'impersonate',
    'workspacesAndApplications',
    'pendingJobs',
  ],
})

const { $i18n } = useNuxtApp()

useHead(() => ({
  title: $i18n.t('recentlyViewed.title'),
}))
</script>
