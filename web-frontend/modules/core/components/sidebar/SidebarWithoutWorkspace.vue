<template>
  <div class="sidebar__section sidebar__section--scrollable">
    <div class="sidebar__section-scrollable">
      <div class="sidebar__section-scrollable-inner">
        <p
          v-if="workspaces.length === 0"
          class="margin-left-1 margin-right-1 margin-top-1 margin-bottom-1"
        >
          {{ $t('sidebar.errorNoWorkspace') }}
        </p>
      </div>
    </div>
    <div
      v-if="$hasPermission('create_workspace')"
      class="sidebar__new-wrapper sidebar__new-wrapper--separator"
    >
      <a
        class="sidebar__new"
        @click="whenMounted(() => $refs.createWorkspaceModal.show())"
      >
        <i class="sidebar__new-icon iconoir-plus"></i>
        {{ $t('sidebar.createWorkspace') }}
      </a>
    </div>
    <CreateWorkspaceModal ref="createWorkspaceModal"></CreateWorkspaceModal>
  </div>
</template>

<script>
import CreateWorkspaceModal from '@baserow/modules/core/components/workspace/CreateWorkspaceModal'
import whenMounted from '@baserow/modules/core/mixins/whenMounted'

export default {
  name: 'SidebarWithoutWorkspace',
  components: { CreateWorkspaceModal },
  mixins: [whenMounted],
  props: {
    workspaces: {
      type: Array,
      required: true,
    },
  },
  methods: {
    hasUnreadNotifications(workspaceId) {
      return this.$store.getters['notification/workspaceHasUnread'](workspaceId)
    },
  },
}
</script>
