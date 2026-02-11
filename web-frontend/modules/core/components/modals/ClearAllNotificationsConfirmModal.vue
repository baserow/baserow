<template>
  <Modal ref="modal" small>
    <h2 class="box__title">
      {{ $t('clearAllNotificationsConfirmModal.title') }}
    </h2>
    <p>
      {{ $t('clearAllNotificationsConfirmModal.message') }}
    </p>
    <div>
      <div class="actions">
        <ul class="action__links">
          <li>
            <a @click.prevent="onCancel">{{ $t('action.cancel') }}</a>
          </li>
        </ul>

        <Button type="danger" @click.prevent="onConfirm">
          {{ $t('action.delete') }}
        </Button>
      </div>
    </div>
  </Modal>
</template>

<script>
import modal from '@baserow/modules/core/mixins/modal'

export default {
  name: 'ClearAllNotificationsConfirmModal',
  mixins: [modal],
  emits: ['cancel', 'confirm'],
  methods: {
    onCancel($event) {
      this.$emit('cancel', $event)
      this.hide()
    },
    onConfirm($event) {
      this.$emit('confirm', $event)
      this.hide()
    },
  },
}
</script>
