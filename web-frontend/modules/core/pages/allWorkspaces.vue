<template>
  <div class="layout__col-2-scroll layout__col-2-scroll--white-background">
    <DashboardVerifyEmail
      class="margin-top-0 margin-bottom-0"
    ></DashboardVerifyEmail>
    <WorkspaceInvitation
      v-for="invitation in workspaceInvitations"
      :key="'invitation-' + invitation.id"
      :invitation="invitation"
      class="margin-top-0 margin-bottom-0"
    ></WorkspaceInvitation>
    @TODO
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useStore } from 'vuex'

import DashboardVerifyEmail from '@baserow/modules/core/components/dashboard/DashboardVerifyEmail'
import WorkspaceInvitation from '@baserow/modules/core/components/workspace/WorkspaceInvitation'
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

// The page is workspace agnostic, so the undo/redo buttons in the sidebar footer
// must not act on the scope of a previously visited workspace.
store.dispatch(
  'undoRedo/updateCurrentScopeSet',
  CORE_ACTION_SCOPES.workspace(null)
)

const workspaceInvitations = computed(
  () => store.getters['auth/getWorkspaceInvitations']
)

await store.dispatch('auth/fetchWorkspaceInvitations')
</script>
