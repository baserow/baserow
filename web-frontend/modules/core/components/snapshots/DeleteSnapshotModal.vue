<template>
  <Modal ref="modal" :tiny="true" :close-button="false">
    <h3>{{ $t('deleteSnapshotModal.title') }}</h3>
    <p>
      {{ $t('deleteSnapshotModal.content', { name: snapshot.name }) }}
    </p>
    <div class="actions margin-bottom-0">
      <ul class="action__links">
        <li>
          <a @click.prevent="hide">{{ $t('action.cancel') }}</a>
        </li>
      </ul>

      <Button
        type="danger"
        :loading="loading"
        :disabled="loading"
        @click.prevent="confirm"
      >
        {{ $t('deleteSnapshotModal.confirm') }}</Button
      >
    </div>
  </Modal>
</template>

<script>
import modal from '@baserow/modules/core/mixins/modal'
import Modal from '@baserow/modules/core/components/Modal'
import SnapshotsService from '@baserow/modules/core/services/snapshots'
import { notifyIf } from '@baserow/modules/core/utils/error'

export default {
  components: {
    Modal,
  },
  mixins: [modal],
  props: {
    snapshot: {
      type: Object,
      required: true,
    },
  },
  emits: ['snapshot-deleted'],
  data() {
    return {
      loading: false,
    }
  },
  methods: {
    async confirm() {
      this.loading = true

      try {
        await SnapshotsService(this.$client).delete(this.snapshot.id)
        this.$emit('snapshot-deleted', this.snapshot)
        this.hide()
      } catch (error) {
        notifyIf(error)
      } finally {
        this.loading = false
      }
    },
  },
}
</script>
