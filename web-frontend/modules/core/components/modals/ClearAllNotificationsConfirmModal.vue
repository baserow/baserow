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
            <a @click.prevent="onClick">{{ $t('action.cancel') }}</a>
          </li>
        </ul>

        <Button type="danger" @click.prevent="onClick">
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
  methods: {
    onClick($event) {
      this.$emit('cancel', $event)
      this.hide()
    },
  },
}
</script>
