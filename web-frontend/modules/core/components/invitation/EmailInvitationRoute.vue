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
  </div>
</template>

<script>
import CaptchaWidget from '@baserow/modules/core/components/auth/CaptchaWidget'
import InviteInput from '@baserow/modules/core/components/invitation/InviteInput'
import nameAbbreviation from '@baserow/modules/core/filters/nameAbbreviation'
import emailInvitations from '@baserow/modules/core/mixins/emailInvitations'
import error from '@baserow/modules/core/mixins/error'
import WorkspaceService from '@baserow/modules/core/services/workspace'
import { notifyIf } from '@baserow/modules/core/utils/error'

/**
 * Invites people into the workspace by email. One input takes any number of
 * addresses, typed or pasted, and every address gets its own invitation with
 * the chosen role. The modal closes once all of them were sent; after a
 * failure the addresses that were not invited yet stay in the input. The
 * members of the workspace and the pending invitations are listed by address
 * only, as a reason not to invite them again.
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
      pendingEmails: [],
    }
  },
  computed: {
    roles() {
      return this.targetType.getRoles(this.workspace, this.target)
    },
    /**
     * Nothing here can be picked: the modal invites by address, and these are
     * the addresses that already belong to someone.
     */
    options() {
      return [
        ...(this.workspace.users || []).map((user) => ({
          key: `auth.User:${user.user_id}`,
          type: 'auth.User',
          id: user.user_id,
          name: user.name,
          email: user.email,
          search: user.email,
          initials: nameAbbreviation(user.name),
          icon: 'iconoir-user',
          color: 'blue',
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
      this.pendingEmails = data.map(({ email }) => email)
    } catch (error) {
      notifyIf(error, 'workspace')
    }
  },
  methods: {
    async invite(picks, roleUid) {
      this.inviting = true
      this.hideError()
      const invitations = []

      try {
        await this.sendInvitations(picks, roleUid, (pick, invitation) => {
          this.$refs.input.remove(pick)
          this.pendingEmails.push(invitation.email)
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
