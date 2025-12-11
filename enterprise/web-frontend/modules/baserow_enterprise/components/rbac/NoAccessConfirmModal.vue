<template>
  <Modal small>
    <h2 class="box__title">
      {{ $t('noAccessConfirmModal.title') }}
    </h2>
    <p>
      {{ $t('noAccessConfirmModal.message') }}
    </p>
    <div>
      <div class="actions">
        <ul class="action__links">
          <li>
            <a @click.prevent="cancel()">{{
              $t('noAccessConfirmModal.cancel')
            }}</a>
          </li>
        </ul>

        <Button type="danger" @click.prevent="confirm()">
          {{ $t('noAccessConfirmModal.confirm') }}
        </Button>
      </div>
    </div>
  </Modal>
</template>

<script>
import modal from '@baserow/modules/core/mixins/modal'

export default {
  name: 'NoAccessConfirmModal',
  mixins: [modal],
  methods: {
    cancel() {
      this.$emit('cancel')
      this.hide()
    },
    confirm() {
      this.$emit('confirm')
      this.hide()
    },
  },
}
</script>
