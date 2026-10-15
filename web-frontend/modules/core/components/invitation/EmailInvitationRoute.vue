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
    />
    <CaptchaWidget
      ref="captchaWidget"
      class="margin-top-2"
      context="workspace_invitation"
      @token="onCaptchaToken"
    />
    <h3 class="invite-list__title">{{ $t('inviteModal.pendingTitle') }}</h3>
    <div v-if="loading" class="loading"></div>
    <div v-else-if="invitations.length === 0" class="invite-list__empty">
      <div>{{ $t('inviteModal.pendingEmptyTitle') }}</div>
      <div>{{ $t('inviteModal.pendingEmptyDescription') }}</div>
    </div>
    <ul v-else class="invite-list__items">
      <li
        v-for="invitation in invitations"
        :key="invitation.id"
        class="invite-list__item"
      >
        <div class="invite-list__subject">
          <Avatar icon="iconoir-mail" color="neutral" rounded size="large" />
          <div>
            <div class="invite-list__name">{{ invitation.email }}</div>
            <div class="invite-list__subtitle">
              {{ roleName(invitation.permissions) }}
            </div>
          </div>
        </div>
      </li>
    </ul>
  </div>
</template>

<script>
import CaptchaWidget from '@baserow/modules/core/components/auth/CaptchaWidget'
import InviteInput from '@baserow/modules/core/components/invitation/InviteInput'
import emailInvitations from '@baserow/modules/core/mixins/emailInvitations'
import error from '@baserow/modules/core/mixins/error'
import WorkspaceService from '@baserow/modules/core/services/workspace'
import { notifyIf } from '@baserow/modules/core/utils/error'

// The role uid of an invitation that only gives access to specific items.
const NO_WORKSPACE_ROLE_UID = 'NO_ROLE_LOW_PRIORITY'

/**
 * Invites people into the workspace by email. One input takes any number of
 * addresses, typed or pasted, and every address gets its own invitation with
 * the chosen role. The modal closes once all of them were sent; after a
 * failure the addresses that were not invited yet stay in the input. The
 * members of the workspace and the pending invitations are known to the input
 * by address only, as a reason not to invite them again. Below it, the pending
 * invitations are listed with their role.
 */
export default {
  name: 'EmailInvitationRoute',
  components: { CaptchaWidget, InviteInput },
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
  emits: ['submitted'],
  data() {
    return {
      inviting: false,
      loading: true,
      invitations: [],
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
     * The name of the role an invitation grants, looked up in every role of
     * the workspace as an older invitation can hold one that isn't offered.
     * An invitation without a workspace role can still hold roles on specific
     * items through scoped invitations, so it says so rather than "No role".
     */
    roleName(uid) {
      if (uid === NO_WORKSPACE_ROLE_UID) {
        return this.$t('inviteModal.pendingNoWorkspaceRole')
      }
      return (
        this.workspace._.roles.find((role) => role.uid === uid)?.name ?? uid
      )
    },
    async invite(picks, roleUid) {
      this.inviting = true
      this.hideError()
      const invitations = []

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
          invitations.push(invitation)
        })
        this.$refs.input.reset()
        this.$emit('submitted', invitations)
      } catch (error) {
        this.handleInvitationError(error)
      } finally {
        this.inviting = false
      }
    },
  },
}
</script>
