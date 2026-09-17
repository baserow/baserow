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
import { useStore } from 'vuex'
import { useNuxtApp, navigateTo } from '#app'
import { useHead } from '#imports'

import RecentlyViewed from '@baserow/modules/core/components/recentlyViewed/RecentlyViewed'
import { CORE_ACTION_SCOPES } from '@baserow/modules/core/utils/undoRedoConstants'

definePageMeta({
  layout: 'app',
  sidebarType: 'all-workspaces',
  middleware: [
    'settings',
    'authenticated',
    'impersonate',
    'workspacesAndApplications',
    'pendingJobs',
  ],
})

const store = useStore()
const { $i18n } = useNuxtApp()

// The page is workspace agnostic, so the undo/redo buttons in the sidebar footer
// must not act on the scope of a previously visited workspace.
store.dispatch(
  'undoRedo/updateCurrentScopeSet',
  CORE_ACTION_SCOPES.workspace(null)
)

useHead(() => ({
  title: $i18n.t('recentlyViewed.title'),
}))
</script>
