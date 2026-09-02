<template>
  <div class="sidebar" :class="{ 'sidebar--collapsed': collapsed }">
    <component
      :is="component"
      v-for="(component, index) in impersonateComponent"
      :key="index"
    ></component>
    <a
      ref="userContextAnchor"
      class="sidebar__workspaces-selector"
      @click="
        $refs.userContext.toggle(
          $refs.userContextAnchor,
          'bottom',
          'left',
          4,
          16
        )
      "
    >
      <Avatar :initials="$filters.nameAbbreviation(name)"></Avatar>
      <span
        v-show="!collapsed"
        class="sidebar__workspaces-selector-selected-workspace"
        >{{ name }}</span
      >
      <span
        v-show="!collapsed"
        v-if="unreadNotificationsInAnyWorkspace"
        class="sidebar__unread-notifications-icon"
      ></span>
      <i
        v-show="!collapsed"
        class="sidebar__workspaces-selector-icon baserow-icon-up-down-arrows"
      ></i>
    </a>
    <SidebarUserContext
      ref="userContext"
      :workspaces="workspaces"
      :selected-workspace="selectedWorkspace"
    ></SidebarUserContext>

    <SidebarAllWorkspacesMenu v-show="!collapsed"></SidebarAllWorkspacesMenu>

    <SidebarFoot
      :collapsed="collapsed"
      :width="width"
      @set-col1-width="$emit('set-col1-width', $event)"
    ></SidebarFoot>
  </div>
</template>

<script>
import { mapGetters } from 'vuex'

import SidebarUserContext from '@baserow/modules/core/components/sidebar/SidebarUserContext'
import SidebarAllWorkspacesMenu from '@baserow/modules/core/components/sidebar/SidebarAllWorkspacesMenu'
import SidebarFoot from '@baserow/modules/core/components/sidebar/SidebarFoot'

export default {
  name: 'SidebarAllWorkspaces',
  components: {
    SidebarUserContext,
    SidebarAllWorkspacesMenu,
    SidebarFoot,
  },
  props: {
    workspaces: {
      type: Array,
      required: true,
    },
    selectedWorkspace: {
      type: Object,
      required: true,
    },
    collapsed: {
      type: Boolean,
      required: false,
      default: () => false,
    },
    width: {
      type: Number,
      required: false,
      default: 240,
    },
  },
  emits: ['set-col1-width'],
  computed: {
    impersonateComponent() {
      return Object.values(this.$registry.getAll('plugin'))
        .map((plugin) => plugin.getImpersonateComponent())
        .filter((component) => component !== null)
    },
    // Not `notification/anyOtherWorkspaceWithUnread`: that excludes the
    // notification store's current workspace, which on this workspace agnostic
    // page is stale from the last visited one and must count as well.
    unreadNotificationsInAnyWorkspace() {
      return this.workspaces.some((workspace) =>
        this.$store.getters['notification/workspaceHasUnread'](workspace.id)
      )
    },
    ...mapGetters({
      name: 'auth/getName',
    }),
  },
}
</script>
