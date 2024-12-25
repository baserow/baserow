<template>
  <Context overflow-scroll max-height-if-outside-viewport>
    <template v-if="Object.keys(workspace).length > 0">
      <div class="context__menu-title">
        {{ workspace.name }} ({{ workspace.id }})
      </div>
      <ul class="context__menu">
        <li class="context__menu-item context__menu-item--with-separator">
          <a
            class="context__menu-item-link context__menu-item-link--delete"
            @click.prevent="showDeleteModal"
          >
            <i class="context__menu-item-icon iconoir-bin"></i>
            {{ $t('editWorkspaceContext.delete') }}
          </a>
        </li>
      </ul>
      <DeleteWorkspaceModal
        ref="deleteWorkspaceModal"
        :workspace="workspace"
        @workspace-deleted="$emit('workspace-deleted', $event)"
      ></DeleteWorkspaceModal>
    </template>
  </Context>
</template>

<script>
import context from '@baserow/modules/core/mixins/context'
import DeleteWorkspaceModal from '@baserow/modules/core/components/admin/workspaces/modals/DeleteWorkspaceModal'

export default {
  name: 'EditWorkspaceContext',
  components: { DeleteWorkspaceModal },
  mixins: [context],
  props: {
    workspace: {
      required: true,
      type: Object,
    },
  },
  methods: {
    showDeleteModal() {
      this.hide()
      this.$refs.deleteWorkspaceModal.show()
    },
  },
}
</script>
