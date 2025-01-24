<template>
  <Modal>
    <h2 class="box__title">
      {{ $t('deleteWorkspaceModal.title', workspace) }}
    </h2>
    <Error :error="error"></Error>
    <div>
      <i18n path="deleteWorkspaceModal.confirmation" tag="p">
        <template #name>
          <strong>{{ workspace.name }}</strong>
        </template>
      </i18n>
      <p>
        {{ $t('deleteWorkspaceModal.comment') }}
      </p>
      <div class="actions">
        <div class="align-right">
          <Button
            type="danger"
            size="large"
            full-width
            :disabled="loading"
            :loading="loading"
            @click.prevent="deleteWorkspace()"
          >
            {{ $t('deleteWorkspaceModal.delete', workspace) }}</Button
          >
        </div>
      </div>
    </div>
  </Modal>
</template>

<script>
import modal from '@baserow/modules/core/mixins/modal'
import error from '@baserow/modules/core/mixins/error'
import WorkspacesAdminService from '@baserow/modules/core/services/admin/workspaces'

export default {
  name: 'DeleteWorkspaceModal',
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
    async deleteWorkspace() {
      this.hideError()
      this.loading = true

      try {
        await WorkspacesAdminService(this.$client).delete(this.workspace.id)
        this.$emit('workspace-deleted', this.workspace.id)
        this.hide()
      } catch (error) {
        this.handleError(error, 'workspace')
      }

      this.loading = false
    },
  },
}
</script>
