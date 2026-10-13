<template>
  <div>
    <h2 class="box__title">{{ $t('inviteModal.emailTitle') }}</h2>
    <Error :error="error"></Error>
    <InviteInput
      ref="input"
      :workspace="workspace"
      :roles="roles"
      :member-emails="memberEmails"
      :pending-emails="pendingEmails"
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
import emailInvitations from '@baserow/modules/core/mixins/emailInvitations'
import error from '@baserow/modules/core/mixins/error'
import WorkspaceService from '@baserow/modules/core/services/workspace'
import { notifyIf } from '@baserow/modules/core/utils/error'

/**
 * Invites people into the workspace by email. One input takes any number of
 * addresses, typed or pasted, and every address gets its own invitation with
 * the chosen role. The modal closes once all of them were sent; after a
 * failure the addresses that were not invited yet stay in the input. An address
 * with a pending invitation is pointed out instead of being invited again.
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
    memberEmails() {
      return (this.workspace.users || []).map(({ email }) => email)
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
