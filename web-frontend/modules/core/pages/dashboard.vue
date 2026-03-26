<template>
  <div class="dashboard__container">
    <div class="dashboard__main">
      <DashboardVerifyEmail class="margin-top-0 margin-bottom-0" />

      <WorkspaceInvitation
        v-for="invitation in workspaceInvitations"
        :key="'invitation-' + invitation.id"
        :invitation="invitation"
        class="margin-top-0 margin-bottom-0"
      />

      <div class="dashboard__wrapper">
        <div class="dashboard__no-application">
          <img
            src="@baserow/modules/core/assets/images/empty_workspace_illustration.png"
            srcset="
              @baserow/modules/core/assets/images/empty_workspace_illustration@2x.png 2x
            "
          />

          <h4>{{ t('dashboard.noWorkspace') }}</h4>

          <p v-if="$hasPermission('create_workspace')">
            {{ t('dashboard.noWorkspaceDescription') }}
          </p>

          <span
            v-if="$hasPermission('create_workspace')"
            ref="createApplicationContextLink2"
          >
            <Button icon="iconoir-plus" tag="a" @click="modal?.show()">
              {{ t('dashboard.addNew') }}
            </Button>
          </span>
        </div>
      </div>
    </div>

    <CreateWorkspaceModal ref="modal" />
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useStore } from 'vuex'
import { useI18n } from 'vue-i18n'
import { useNuxtApp } from '#imports'

import CreateWorkspaceModal from '@baserow/modules/core/components/workspace/CreateWorkspaceModal'
import DashboardVerifyEmail from '@baserow/modules/core/components/dashboard/DashboardVerifyEmail'
import WorkspaceInvitation from '@baserow/modules/core/components/workspace/WorkspaceInvitation'

definePageMeta({
  layout: 'app',
  middleware: [
    'settings',
    'authenticated',
    'impersonate',
    'workspacesAndApplications',
    'pendingJobs',
    'dashboardRedirect',
  ],
})

const store = useStore()
const { t } = useI18n()
const { $hasPermission } = useNuxtApp()

const modal = ref(null)

const workspaceInvitations = computed(
  () => store.getters['auth/getWorkspaceInvitations']
)

// If we reach here, no workspace redirect happened — fetch invitations
await store.dispatch('auth/fetchWorkspaceInvitations')
</script>
