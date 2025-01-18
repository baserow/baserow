<template>
  <div class="dashboard__container">
    <div class="dashboard__main">
      <DashboardVerifyEmail
        class="margin-top-0 margin-bottom-0"
      ></DashboardVerifyEmail>
      <WorkspaceInvitation
        v-for="invitation in workspaceInvitations"
        :key="'invitation-' + invitation.id"
        :invitation="invitation"
        class="margin-top-0 margin-bottom-0"
      ></WorkspaceInvitation>
      <div class="dashboard__wrapper">
        <div class="dashboard__no-application">
          <img
            src="@baserow/modules/core/assets/images/empty_workspace_illustration.png"
            srcset="
              @baserow/modules/core/assets/images/empty_workspace_illustration@2x.png 2x
            "
          />
          <h4>{{ $t('dashboard.noWorkspace') }}</h4>
          <p v-if="$hasPermission('create_workspace')">
            {{ $t('dashboard.noWorkspaceDescription') }}
          </p>
          <span
            v-if="$hasPermission('create_workspace')"
            ref="createApplicationContextLink2"
          >
            <Button icon="iconoir-plus" tag="a" @click="$refs.modal.show()">{{
              $t('dashboard.addNew')
            }}</Button>
          </span>
        </div>
      </div>
    </div>
    <CreateWorkspaceModal ref="modal"></CreateWorkspaceModal>
  </div>
</template>

<script>
import { mapGetters } from 'vuex'

import CreateWorkspaceModal from '@baserow/modules/core/components/workspace/CreateWorkspaceModal'
import DashboardVerifyEmail from '@baserow/modules/core/components/dashboard/DashboardVerifyEmail'
import WorkspaceInvitation from '@baserow/modules/core/components/workspace/WorkspaceInvitation'

/**
 * The main purpose of the dashboard is to either redirect the user to the correct
 * workspace homepage or show a message if the user doesn't have a workspace.
 */
export default {
  components: {
    CreateWorkspaceModal,
    DashboardVerifyEmail,
    WorkspaceInvitation,
  },
  layout: 'app',
  async asyncData({ query, store, redirect }) {
    const selectedWorkspace = store.getters['workspace/getSelected']
    const allWorkspaces = store.getters['workspace/getAll']

    // If there is a selected workspace, we'll redirect the user to that homepage.
    if (Object.keys(selectedWorkspace).length > 0) {
      return redirect({
        name: 'workspace',
        params: {
          workspaceId: selectedWorkspace.id,
        },
        query,
      })
    }

    // If there isn't a selected workspace, but one does exist, we'll select the first
    // one.
    if (allWorkspaces.length > 0) {
      return redirect({
        name: 'workspace',
        params: {
          workspaceId: allWorkspaces[0].id,
        },
        query,
      })
    }

    await store.dispatch('auth/fetchWorkspaceInvitations')
  },
  computed: {
    ...mapGetters({
      workspaceInvitations: 'auth/getWorkspaceInvitations',
    }),
  },
}
</script>
