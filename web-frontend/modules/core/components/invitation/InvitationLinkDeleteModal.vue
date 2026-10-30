<template>
  <Modal ref="modal">
    <h2 class="box__title">{{ $t('invitationLinkDeleteModal.title') }}</h2>
    <Error :error="error"></Error>
    <div>
      <p>
        {{
          $t('invitationLinkDeleteModal.deleteWarning', {
            workspaceName: workspace.name,
          })
        }}
      </p>
      <div class="actions">
        <div class="align-right">
          <Button
            type="danger"
            size="large"
            :loading="loading"
            :disabled="loading"
            @click="deleteInvitationLink()"
          >
            {{ $t('invitationLinkDeleteModal.delete') }}
          </Button>
        </div>
      </div>
    </div>
  </Modal>
</template>

<script>
import modal from '@baserow/modules/core/mixins/modal'
import error from '@baserow/modules/core/mixins/error'

/**
 * Asks before an invitation link is deleted, because everyone it was shared with
 * can't join through it anymore, and deletes it once confirmed.
 */
export default {
  name: 'InvitationLinkDeleteModal',
  mixins: [modal, error],
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
  emits: ['deleted'],
  data() {
    return {
      loading: false,
      invitationLink: null,
    }
  },
  methods: {
    show(invitationLink, ...args) {
      this.invitationLink = invitationLink
      this.hideError()
      return modal.methods.show.call(this, ...args)
    },
    async deleteInvitationLink() {
      this.hideError()
      this.loading = true

      try {
        await this.targetType.deleteInvitationLink(
          this.workspace,
          this.target,
          this.invitationLink
        )
        this.$emit('deleted', this.invitationLink)
        this.hide()
      } catch (error) {
        this.handleError(error)
      }

      this.loading = false
    },
  },
}
</script>
