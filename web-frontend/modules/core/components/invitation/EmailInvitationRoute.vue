<template>
  <div>
    <h2 class="box__title">{{ $t('inviteModal.emailTitle') }}</h2>
    <Error :error="error"></Error>
    <InviteInput
      ref="input"
      :workspace="workspace"
      :roles="roles"
      :options="options"
      :disabled="inviting"
      @add="invite"
    >
      <CaptchaWidget
        ref="captchaWidget"
        class="margin-top-2"
        context="workspace_invitation"
        @token="onCaptchaToken"
      />
      <h3 class="invite-list__title">{{ $t('inviteModal.pendingTitle') }}</h3>
      <div v-if="loading" class="loading"></div>
      <ScopeAccessList
        v-else
        :items="accessItems"
        :roles="roles"
        :workspace="workspace"
        :empty-title="$t('inviteModal.pendingEmptyTitle')"
        :empty-description="$t('inviteModal.pendingEmptyDescription')"
        @role-updated="updateItemRole"
      />
    </InviteInput>
  </div>
</template>

<script>
import CaptchaWidget from '@baserow/modules/core/components/auth/CaptchaWidget'
import InviteInput from '@baserow/modules/core/components/invitation/InviteInput'
import ScopeAccessList from '@baserow/modules/core/components/invitation/ScopeAccessList'
import emailInvitations from '@baserow/modules/core/mixins/emailInvitations'
import error from '@baserow/modules/core/mixins/error'
import WorkspaceService from '@baserow/modules/core/services/workspace'
import { notifyIf } from '@baserow/modules/core/utils/error'

/**
 * Invites people into the workspace by email and manages the pending
 * invitations. One input takes any number of addresses, typed or pasted, and
 * every address gets its own invitation with the chosen role. Once sent they
 * join the pending invitations listed below the input, where their role can be
 * changed or the invitation cancelled; after a failure the addresses that were
 * not invited yet stay in the input. The members of the workspace and the
 * pending invitations are known to the input by address only, as a reason not
 * to invite them again.
 */
export default {
  name: 'EmailInvitationRoute',
  components: { CaptchaWidget, ScopeAccessList, InviteInput },
  mixins: [error, emailInvitations],
  props: {
    workspace: {
      type: Object,
      required: true,
    },
    target: {
      type: Object,
      required: true,
    },
    targetType: {
      type: Object,
      required: true,
    },
  },
  data() {
    return {
      inviting: false,
      loading: true,
      invitations: [],
      updatingInvitationIds: [],
    }
  },
  computed: {
    roles() {
      return this.targetType.getRoles(this.workspace, this.target)
    },
    pendingEmails() {
      return this.invitations.map(({ email }) => email)
    },
    /**
     * Workspace invitations use the same rows as scoped access. Editing and
     * cancellation are independent capabilities on each invitation; cancelling
     * here removes the whole invitation, including any pending scoped grants.
     */
    accessItems() {
      return this.invitations.map((invitation) => {
        const canUpdate = this.$hasPermission(
          'invitation.update',
          invitation,
          this.workspace.id
        )
        const canRemove = this.$hasPermission(
          'invitation.delete',
          invitation,
          this.workspace.id
        )
        return {
          key: `invitation:${invitation.id}`,
          name: invitation.email,
          subtitle:
            this.workspace._.roles.find(
              (role) => role.uid === invitation.permissions
            )?.invitationSubtitle ?? null,
          icon: 'iconoir-mail',
          color: 'neutral',
          roleUid: invitation.permissions,
          roles: canUpdate ? this.roles : [],
          allowRemovingRole: canRemove,
          disabled:
            this.inviting ||
            this.updatingInvitationIds.includes(invitation.id) ||
            (!canUpdate && !canRemove),
          invitation,
        }
      })
    },
    /**
     * Nothing here can be picked: the modal invites by address, and these are
     * the addresses that already belong to someone.
     */
    options() {
      const userType = this.$registry.get('subject', 'auth.User')
      return [
        ...(this.workspace.users || []).map((user) => ({
          ...userType.getInviteOption(user),
          // Only the address matters when inviting by email.
          search: user.email,
          disabledReason: this.$t('inviteInput.alreadyMember'),
          disabledHint: this.$t('inviteInput.memberHint'),
        })),
        ...this.pendingEmails.map((email) => ({
          key: `invitation:${email}`,
          type: 'email',
          email,
          name: email,
          search: email,
          initials: '',
          icon: 'iconoir-mail',
          color: 'neutral',
          disabledReason: this.$t('inviteInput.alreadyInvited'),
          disabledHint: this.$t('inviteInput.invitedHint'),
        })),
      ]
    },
  },
  async mounted() {
    try {
      const { data } = await WorkspaceService(this.$client).fetchAllInvitations(
        this.workspace.id
      )
      this.invitations = data
    } catch (error) {
      notifyIf(error, 'workspace')
    } finally {
      this.loading = false
    }
  },
  methods: {
    /**
     * Updates a workspace invitation or cancels it entirely. Keep the row until
     * the request succeeds so a failure preserves both the role and the pending
     * address. The busy row prevents overlapping changes to the same invitation.
     */
    async updateItemRole(item, roleUid) {
      const invitation = this.invitations.find(
        ({ id }) => id === item.invitation.id
      )
      if (
        !invitation ||
        this.updatingInvitationIds.includes(invitation.id) ||
        !this.$hasPermission(
          roleUid === null ? 'invitation.delete' : 'invitation.update',
          invitation,
          this.workspace.id
        )
      ) {
        return
      }
      this.updatingInvitationIds.push(invitation.id)
      try {
        const service = WorkspaceService(this.$client)
        if (roleUid === null) {
          await service.deleteInvitation(invitation.id)
          this.invitations = this.invitations.filter(
            ({ id }) => id !== invitation.id
          )
          this.$bus.$emit('invite-deleted', invitation)
        } else {
          const { data } = await service.updateInvitation(invitation.id, {
            permissions: roleUid,
          })
          const index = this.invitations.findIndex(
            ({ id }) => id === invitation.id
          )
          this.invitations.splice(index, 1, data)
          this.$bus.$emit('invite-updated', data)
        }
      } catch (error) {
        notifyIf(error, 'workspace')
      } finally {
        this.updatingInvitationIds = this.updatingInvitationIds.filter(
          (id) => id !== invitation.id
        )
      }
    },
    async invite(picks, roleUid) {
      this.inviting = true
      this.hideError()

      try {
        await this.sendInvitations(picks, roleUid, (pick, invitation) => {
          this.$refs.input.remove(pick)
          const index = this.invitations.findIndex(
            ({ id }) => id === invitation.id
          )
          if (index === -1) {
            this.invitations.push(invitation)
          } else {
            this.invitations[index] = invitation
          }
        })
        this.$refs.input.reset()
      } catch (error) {
        this.handleInvitationError(error)
      } finally {
        this.inviting = false
      }
    },
  },
}
</script>
