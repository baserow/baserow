<template>
  <div class="sidebar" :class="{ 'sidebar--collapsed': collapsed }">
    <component
      :is="component"
      v-for="(component, index) in impersonateComponent"
      :key="index"
    ></component>
    <nuxt-link
      class="sidebar__brand"
      :to="{ name: 'all-workspaces' }"
      :aria-label="$t('sidebar.allWorkspaces')"
    >
      <img
        v-if="collapsed"
        src="@baserow/modules/core/static/img/logoOnly.svg?url"
        alt=""
        width="16"
        height="16"
      />
      <Logo v-else height="13" alt="" />
    </nuxt-link>

    <SidebarAllWorkspacesMenu v-show="!collapsed"></SidebarAllWorkspacesMenu>

    <SidebarFoot
      :collapsed="collapsed"
      :width="width"
      :selected-workspace="selectedWorkspace"
      :has-unread-notifications="unreadNotificationsInAnyWorkspace"
      @set-col1-width="$emit('set-col1-width', $event)"
    ></SidebarFoot>
  </div>
</template>

<script>
import { mapGetters } from 'vuex'

import Logo from '@baserow/modules/core/components/Logo'
import SidebarAllWorkspacesMenu from '@baserow/modules/core/components/sidebar/SidebarAllWorkspacesMenu'
import SidebarFoot from '@baserow/modules/core/components/sidebar/SidebarFoot'

export default {
  name: 'SidebarAllWorkspaces',
  components: {
    Logo,
    SidebarAllWorkspacesMenu,
    SidebarFoot,
  },
  props: {
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
    ...mapGetters({
      unreadNotificationsInAnyWorkspace: 'notification/anyWorkspaceWithUnread',
    }),
  },
}
</script>
