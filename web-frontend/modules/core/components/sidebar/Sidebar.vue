<template>
  <div class="sidebar" :class="{ 'sidebar--collapsed': collapsed }">
    <component
      :is="component"
      v-for="(component, index) in impersonateComponent"
      :key="index"
    ></component>
    <template v-if="showAdmin">
      <div class="sidebar__head">
        <a class="sidebar__back" @click="leaveAdmin()">
          <i class="iconoir-nav-arrow-left"></i>
        </a>
        <div v-show="!collapsed" class="sidebar__title">
          {{ $t('sidebar.adminSettings') }}
        </div>
      </div>
      <SidebarAdmin v-show="!collapsed"></SidebarAdmin>
    </template>
    <template v-if="!showAdmin">
      <div
        v-if="hasSelectedWorkspace"
        class="sidebar__workspace-breadcrumb"
        data-highlight="workspaces"
      >
        <div class="sidebar__workspace-home-slot">
          <nuxt-link
            v-tooltip="$t('sidebar.allWorkspaces')"
            tooltip-position="right"
            tooltip-no-arrow
            tooltip-show-delay="500"
            class="sidebar__workspace-home"
            :aria-label="$t('sidebar.allWorkspaces')"
            :to="{ name: 'all-workspaces' }"
          >
            <span
              class="sidebar__workspace-home-icon"
              aria-hidden="true"
            ></span>
          </nuxt-link>
        </div>
        <span
          v-show="!collapsed"
          class="sidebar__workspace-breadcrumb-separator"
          aria-hidden="true"
        ></span>
        <button
          type="button"
          class="sidebar__workspace-trigger"
          :aria-label="collapsed ? selectedWorkspace.name : undefined"
          :aria-expanded="workspaceContextOpen"
          @click="
            $refs.workspacesContext.toggle(
              $event.currentTarget,
              'bottom',
              'left',
              4
            )
          "
        >
          <Avatar
            v-if="collapsed"
            :initials="$filters.nameAbbreviation(selectedWorkspace.name)"
            aria-hidden="true"
          ></Avatar>
          <span v-show="!collapsed" class="sidebar__workspace-name">{{
            selectedWorkspace.name
          }}</span>
          <span
            v-show="!collapsed && width >= 200"
            v-if="workspacePlanBadges.length"
            class="sidebar__workspace-plan"
          >
            <component
              :is="badge"
              v-for="(badge, index) in workspacePlanBadges"
              :key="index"
              :workspace="selectedWorkspace"
            ></component>
          </span>
          <span
            v-show="!collapsed"
            v-if="unreadNotificationsInOtherWorkspaces"
            class="sidebar__unread-notifications-icon"
          ></span>
          <i
            v-show="!collapsed"
            class="sidebar__workspace-trigger-icon baserow-icon-up-down-arrows"
            aria-hidden="true"
          ></i>
        </button>
      </div>
      <div
        v-else
        ref="workspaceContextAnchor"
        class="sidebar__workspaces-selector"
        data-highlight="workspaces"
      >
        <nuxt-link
          v-show="!collapsed"
          v-tooltip="$t('sidebar.backToHome')"
          tooltip-position="right"
          tooltip-no-arrow
          tooltip-show-delay="500"
          class="sidebar__back"
          :aria-label="$t('sidebar.backToHome')"
          :to="{ name: 'all-workspaces' }"
        >
          <i class="iconoir-nav-arrow-left"></i>
        </nuxt-link>
        <button
          type="button"
          class="sidebar__workspaces-selector-link"
          :aria-label="selectedWorkspace.name || name"
          :aria-expanded="workspaceContextOpen"
          @click="toggleWorkspaceContext"
        >
          <Avatar
            :initials="
              $filters.nameAbbreviation(selectedWorkspace.name || name)
            "
            aria-hidden="true"
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
        </button>
      </div>
      <SidebarUserContext
        ref="workspacesContext"
        :workspaces="workspaces"
        :selected-workspace="selectedWorkspace"
        @shown="workspaceContextOpen = true"
        @hidden="workspaceContextOpen = false"
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
      :selected-workspace="showAdmin ? null : selectedWorkspace"
      @set-col1-width="$emit('set-col1-width', $event)"
      @toggle-admin="setShowAdmin($event)"
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
  emits: ['open-workspace-search', 'set-col1-width'],
  data() {
    return {
      showAdmin: false,
      workspaceContextOpen: false,
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
    workspacePlanBadges() {
      return Object.values(this.$registry.getAll('plugin'))
        .map((plugin) => plugin.getSidebarWorkspacePlanBadge())
        .filter((component) => component !== null)
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
    toggleWorkspaceContext(event) {
      const trigger = event.currentTarget
      const anchorRect =
        this.$refs.workspaceContextAnchor.getBoundingClientRect()
      const triggerRect = trigger.getBoundingClientRect()
      this.$refs.workspacesContext.toggle(
        trigger,
        'bottom',
        'left',
        4 + anchorRect.bottom - triggerRect.bottom,
        16 + anchorRect.left - triggerRect.left
      )
    },
    setShowAdmin(value) {
      this.showAdmin = value
      this.$forceUpdate()
    },
    /**
     * If no workspace is selected, for example when an admin page was loaded
     * directly, then toggling back would show an empty workspace sidebar, so the
     * user is navigated to the all workspaces homepage instead.
     */
    leaveAdmin() {
      if (this.hasSelectedWorkspace) {
        this.setShowAdmin(false)
      } else {
        this.$router.push({ name: 'all-workspaces' })
      }
    },
  },
}
</script>
