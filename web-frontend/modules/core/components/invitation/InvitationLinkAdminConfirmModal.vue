<template>
  <Modal ref="modal" small>
    <h2 class="box__title">
      {{ $t('invitationLinkAdminConfirmModal.title') }}
    </h2>
    <p>{{ message }}</p>
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
 * link can then join as an admin. The `message` says what such an admin can do.
 */
export default {
  name: 'InvitationLinkAdminConfirmModal',
  mixins: [modal],
  props: {
    message: {
      type: String,
      required: true,
    },
  },
  emits: ['confirm'],
  methods: {
    onConfirm() {
      this.$emit('confirm')
      this.hide()
    },
  },
}
</script>
