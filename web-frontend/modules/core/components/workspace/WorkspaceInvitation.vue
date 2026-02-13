<template>
  <Alert type="info-primary">
    <template #title>
      {{
        $t('workspaceInvitation.message', {
          by: invitation.invited_by,
          workspace: invitation.workspace,
        })
      }}</template
    >

    <p v-if="invitation.message !== ''" class="quote">
      "{{ invitation.message }}"
    </p>

    <template #actions>
      <Button
        type="primary"
        size="small"
        :disabled="acceptLoading || rejectLoading"
        :loading="acceptLoading"
        @click="!rejectLoading && !acceptLoading && accept(invitation)"
      >
        {{ $t('workspaceInvitation.accept') }}
      </Button>
      <ButtonText
        class="alert__actions-button-text"
        type="primary"
        size="small"
        :disabled="rejectLoading || acceptLoading"
        :loading="rejectLoading"
        @click="!acceptLoading && !rejectLoading && reject(invitation)"
      >
        {{ $t('workspaceInvitation.reject') }}
      </ButtonText>
    </template>
  </Alert>
</template>

<script>
import ApplicationService from '@baserow/modules/core/services/application'
import { notifyIf } from '@baserow/modules/core/utils/error'
import { pageFinished } from '@baserow/modules/core/utils/routing'
import { nextTick } from '#imports'

export default {
  name: 'WorkspaceInvitation',
  props: {
    invitation: {
      type: Object,
      required: true,
    },
  },
  emits: ['invitation-accepted'],
  data() {
    return {
      rejectLoading: false,
      acceptLoading: false,
    }
  },
  methods: {
    async reject(invitation) {
      this.rejectLoading = true

      try {
        await this.$store.dispatch(
          'auth/rejectWorkspaceInvitation',
          invitation.id
        )
      } catch (error) {
        this.rejectLoading = false
        notifyIf(error, 'workspace')
      }
    },
    /**
     * Accepts the invitation to join the workspace and populates the stores with the new
     * workspace and applications.
     */
    async accept(invitation) {
      this.acceptLoading = true

      try {
        const workspace = await this.$store.dispatch(
          'auth/acceptWorkspaceInvitation',
          invitation.id
        )

        this.$emit('invitation-accepted', { workspace })

        // The accept endpoint returns a workspace user object that we can add to the
        // store. Also the applications that we just fetched can be added to the
        // store.
        await this.$store.dispatch('workspace/forceCreate', workspace)
        await this.$store.dispatch('workspace/fetchPermissions', workspace)
        await this.$store.dispatch('workspace/fetchRoles', workspace)

        if (
          this.$hasPermission(
            'workspace.list_applications',
            workspace,
            workspace.id
          )
        ) {
          // After the invitation is accepted and workspace is received we can immediately
          // fetch the applications that belong to the workspace.
          const { data: applications } = await ApplicationService(
            this.$client
          ).fetchAll(workspace.id)

          applications.forEach((application) => {
            this.$store.dispatch('application/forceCreate', application)
          })
        }

        await this.$router.push({
          name: 'workspace',
          params: {
            workspaceId: workspace.id,
          },
        })
        await pageFinished()
        await nextTick()
      } catch (error) {
        this.acceptLoading = false
        notifyIf(error, 'workspace')
      }
    },
  },
}
</script>
