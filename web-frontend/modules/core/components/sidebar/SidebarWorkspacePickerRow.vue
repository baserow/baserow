<template>
  <li class="sidebar-workspace-picker__row">
    <button
      v-show="!editing"
      type="button"
      class="sidebar-workspace-picker__item"
      data-workspace-option
      :disabled="editing"
      :aria-current="selected ? 'true' : undefined"
      @click="$emit('select')"
    >
      <Avatar :initials="initial" aria-hidden="true" />
      <span class="sidebar-workspace-picker__name">{{ workspace.name }}</span>
      <span
        v-if="hasUnreadNotifications"
        class="sidebar__unread-notifications-icon"
      ></span>
    </button>
    <div
      v-show="editing"
      class="sidebar-workspace-picker__item"
      @keydown.enter="restoreActionsFocus"
      @keydown.esc.capture.stop.prevent="cancelRename"
    >
      <Avatar :initials="initial" aria-hidden="true" />
      <Editable
        ref="rename"
        class="sidebar-workspace-picker__name"
        :value="workspace.name"
        :aria-label="$t('workspaceContext.renameWorkspace')"
        @editing="editing = $event"
        @change="renameWorkspace(workspace, $event)"
      />
    </div>
    <button
      ref="actions"
      type="button"
      class="sidebar-workspace-picker__actions"
      :aria-label="
        $t('sidebar.workspaceActions', { workspace: workspace.name })
      "
      :aria-expanded="actionsOpen"
      @click="$refs.context.toggle($event.currentTarget, 'bottom', 'left', 4)"
    >
      <i class="baserow-icon-more-vertical" aria-hidden="true"></i>
    </button>
    <i
      v-if="selected"
      class="sidebar-workspace-picker__check iconoir-check"
      aria-hidden="true"
    ></i>
    <WorkspaceContext
      ref="context"
      :workspace="workspace"
      tabindex="-1"
      @rename="enableRename"
      @shown="onActionsShown"
      @hidden="actionsOpen = false"
      @keydown.esc.stop.prevent="closeActions"
    />
  </li>
</template>

<script>
import Editable from '@baserow/modules/core/components/Editable.vue'
import WorkspaceContext from '@baserow/modules/core/components/workspace/WorkspaceContext.vue'
import editWorkspace from '@baserow/modules/core/mixins/editWorkspace'

export default {
  name: 'SidebarWorkspacePickerRow',
  components: { Editable, WorkspaceContext },
  mixins: [editWorkspace],
  props: {
    workspace: {
      type: Object,
      required: true,
    },
    selected: {
      type: Boolean,
      default: false,
    },
    hasUnreadNotifications: {
      type: Boolean,
      default: false,
    },
  },
  emits: ['select'],
  data() {
    return {
      editing: false,
      actionsOpen: false,
    }
  },
  computed: {
    initial() {
      return this.workspace.name.trim().charAt(0).toUpperCase()
    },
  },
  methods: {
    onActionsShown() {
      this.actionsOpen = true
      this.$nextTick(() => {
        if (this.actionsOpen) {
          const menu = this.$refs.context?.getTeleportedElement()
          const target =
            menu?.querySelector('button.context__menu-item-link') ?? menu
          target?.focus()
        }
      })
    },
    closeActions() {
      this.$refs.context.hide()
      this.$refs.actions.focus()
    },
    cancelRename() {
      this.$refs.rename.set(this.workspace.name)
      this.$refs.rename.change()
      this.restoreActionsFocus()
    },
    restoreActionsFocus() {
      this.$nextTick(() => this.$refs.actions?.focus())
    },
  },
}
</script>
