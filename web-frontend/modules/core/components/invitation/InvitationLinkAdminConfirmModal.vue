<template>
  <Modal ref="modal" small>
    <h2 class="box__title">
      {{ $t('invitationLinkAdminConfirmModal.title') }}
    </h2>
    <p>
      {{ $t('invitationLinkAdminConfirmModal.message') }}
    </p>
    <div class="actions">
      <ul class="action__links">
        <li>
          <a @click.prevent="hide()">{{ $t('action.cancel') }}</a>
        </li>
      </ul>
      <Button type="danger" @click.prevent="onConfirm">
        {{ $t('invitationLinkAdminConfirmModal.confirm') }}
      </Button>
    </div>
  </Modal>
</template>

<script>
import modal from '@baserow/modules/core/mixins/modal'

/**
 * Asks before an invitation link grants the admin role, because anyone with the
 * link can then join the workspace as an admin.
 */
export default {
  name: 'InvitationLinkAdminConfirmModal',
  mixins: [modal],
  emits: ['confirm'],
  methods: {
    onConfirm() {
      this.$emit('confirm')
      this.hide()
    },
  },
}
</script>
