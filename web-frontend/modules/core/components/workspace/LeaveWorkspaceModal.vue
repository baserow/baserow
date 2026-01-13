<template>
  <Modal ref="modal">
    <h2 class="box__title">
      {{ $t('leaveWorkspaceModal.title', { workspace: workspace.name }) }}
    </h2>
    <Error :error="error"></Error>
    <div>
      <p>
        {{ $t('leaveWorkspaceModal.message', { workspace: workspace.name }) }}
      </p>
      <div class="actions">
        <div class="align-right">
          <Button
            type="danger"
            size="large"
            :loading="loading"
            :disabled="loading"
            @click="leaveWorkspace()"
          >
            {{ $t('leaveWorkspaceModal.leave') }}
          </Button>
        </div>
      </div>
    </div>
  </Modal>
</template>

<script>
import modal from '@baserow/modules/core/mixins/modal'
import error from '@baserow/modules/core/mixins/error'
import { pageFinished } from '@baserow/modules/core/utils/routing'
import { nextTick } from '#imports'

export default {
  name: 'LeaveWorkspaceModal',
  mixins: [modal, error],
  props: {
    workspace: {
      type: Object,
      required: true,
    },
  },
  data() {
    return {
      loading: false,
    }
  },
  methods: {
    async leaveWorkspace() {
      this.hideError()
      this.loading = true

      const selected =
        this.$store.getters['workspace/getSelected'].id === this.workspace.id

      try {
        await this.$store.dispatch('workspace/leave', this.workspace)
        if (selected) {
          await this.$router.push({ name: 'dashboard' })
          await pageFinished()
          await nextTick()
        }
        this.hide()
      } catch (error) {
        this.handleError(error, 'view')
      }

      this.loading = false
    },
  },
}
</script>
