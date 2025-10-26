<template>
  <div class="sidebar" :class="{ 'sidebar--collapsed': collapsed }">
    <component
      :is="component"
      v-for="(component, index) in impersonateComponent"
      :key="index"
    ></component>
    <template v-if="showAdmin">
      <div class="sidebar__head">
        <a href="#" class="sidebar__back" @click="setShowAdmin(false)">
          <i class="sidebar__back-icon iconoir-nav-arrow-left"></i>
        </a>
        <div v-show="!collapsed" class="sidebar__title">
          {{ $t('sidebar.adminSettings') }}
        </div>
      </div>
      <SidebarAdmin v-show="!collapsed"></SidebarAdmin>
    </template>
    <template v-if="!showAdmin">
      <a
        ref="workspaceContextAnchor"
        class="sidebar__workspaces-selector"
        data-highlight="workspaces"
        @click="
          $refs.workspacesContext.toggle(
            $refs.workspaceContextAnchor,
            'bottom',
            'left',
            8,
            16
          )
        "
      >
        <Avatar
          :initials="selectedWorkspace.name || name | nameAbbreviation"
        ></Avatar>
        <span
          v-show="!collapsed"
          class="sidebar__workspaces-selector-selected-workspace"
          >{{ selectedWorkspace.name || name }}</span
        >
        <span
          v-show="!collapsed"
          v-if="unreadNotificationsInOtherWorkspaces"
          class="sidebar__unread-notifications-icon"
        ></span>
        <i
          v-show="!collapsed"
          class="sidebar__workspaces-selector-icon baserow-icon-up-down-arrows"
        ></i>
      </a>
      <SidebarUserContext
        ref="workspacesContext"
        :workspaces="workspaces"
        :selected-workspace="selectedWorkspace"
        @toggle-admin="setShowAdmin($event)"
      ></SidebarUserContext>

      <SidebarMenu
        v-show="!collapsed"
        v-if="hasSelectedWorkspace"
        :selected-workspace="selectedWorkspace"
        :right-sidebar-open="rightSidebarOpen"
        @open-workspace-search="$emit('open-workspace-search')"
      ></SidebarMenu>

      <SidebarWithWorkspace
        v-show="!collapsed"
        v-if="hasSelectedWorkspace"
        :applications="applications"
        :selected-workspace="selectedWorkspace"
      ></SidebarWithWorkspace>

      <SidebarWithoutWorkspace
        v-show="!collapsed"
        v-if="!hasSelectedWorkspace"
        :workspaces="workspaces"
      ></SidebarWithoutWorkspace>
    </template>
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
import SidebarWithWorkspace from '@baserow/modules/core/components/sidebar/SidebarWithWorkspace'
import SidebarWithoutWorkspace from '@baserow/modules/core/components/sidebar/SidebarWithoutWorkspace'
import SidebarAdmin from '@baserow/modules/core/components/sidebar/SidebarAdmin'
import SidebarFoot from '@baserow/modules/core/components/sidebar/SidebarFoot'
import SidebarMenu from '@baserow/modules/core/components/sidebar/SidebarMenu'
import SidebarAdminItem from './SidebarAdminItem.vue'

export default {
  name: 'Sidebar',
  components: {
    SidebarAdmin,
    SidebarWithoutWorkspace,
    SidebarWithWorkspace,
    SidebarUserContext,
    SidebarMenu,
    SidebarFoot,
  },
  props: {
    applications: {
      type: Array,
      required: true,
    },
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
    rightSidebarOpen: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  data() {
    return {
      showAdmin: false,
    }
  },

  computed: {
    SidebarAdminItem() {
      return SidebarAdminItem
    },
    impersonateComponent() {
      return Object.values(this.$registry.getAll('plugin'))
        .map((plugin) => plugin.getImpersonateComponent())
        .filter((component) => component !== null)
    },
    hasSelectedWorkspace() {
      return Object.prototype.hasOwnProperty.call(this.selectedWorkspace, 'id')
    },
    ...mapGetters({
      name: 'auth/getName',
      unreadNotificationsInOtherWorkspaces:
        'notification/anyOtherWorkspaceWithUnread',
    }),
  },
  created() {
    // Checks whether the rendered page is an admin page. If so, switch the left sidebar
    // navigation to the admin.
    this.showAdmin = Object.values(this.$registry.getAll('admin')).some(
      (adminType) => {
        return this.$route.matched.some(
          ({ name }) => name === adminType.routeName
        )
      }
    )
  },
  methods: {
    setShowAdmin(value) {
      this.showAdmin = value
      this.$forceUpdate()
    },
  },
}
</script>
