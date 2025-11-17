<template>
  <div class="sidebar__section" ph-autocapture="sidebar" data-highlight="menu">
    <ul class="tree">
      <SidebarSearch
        :selected-workspace="selectedWorkspace"
        @open-workspace-search="openWorkspaceSearch"
      />
      <nuxt-link
        v-slot="{ href, navigate, isExactActive }"
        :to="{
          name: 'workspace',
          params: {
            workspaceId: selectedWorkspace.id,
          },
        }"
      >
        <li
          class="tree__item"
          :class="{
            active: isExactActive,
          }"
        >
          <div class="tree__action sidebar__action">
            <a :href="href" class="tree__link" @click="navigate">
              <i class="tree__icon iconoir-home-simple"></i>
              <span class="tree__link-text">
                <span class="sidebar__item-name">{{ $t('sidebar.home') }}</span>
              </span>
            </a>
          </div>
        </li>
      </nuxt-link>

      <li class="tree__item">
        <div class="tree__action tree__action--has-counter">
          <a
            class="tree__link"
            @click="$refs.notificationPanel.toggle($event.currentTarget)"
          >
            <i class="tree__icon tree__icon--type iconoir-bell"></i>
            <span class="tree__link-text">{{
              $t('sidebar.notifications')
            }}</span>
          </a>
          <BadgeCounter
            v-show="unreadNotificationCount"
            class="tree__counter"
            :count="unreadNotificationCount"
            :limit="10"
          >
          </BadgeCounter>
        </div>
        <NotificationPanel ref="notificationPanel" />
      </li>

      <nuxt-link
        v-if="
          $hasPermission(
            'workspace.list_workspace_users',
            selectedWorkspace,
            selectedWorkspace.id
          )
        "
        v-slot="{ href, navigate, isExactActive }"
        :to="{
          name: 'settings-members',
          params: {
            workspaceId: selectedWorkspace.id,
          },
        }"
      >
        <li
          class="tree__item"
          :class="{
            active: isExactActive,
          }"
          data-highlight="members"
        >
          <div class="tree__action sidebar__action">
            <a :href="href" class="tree__link" @click="navigate">
              <i class="tree__icon iconoir-group"></i>
              <span class="tree__link-text">
                <span class="sidebar__item-name">{{
                  $t('sidebar.members')
                }}</span>
              </span>
              <span
                v-if="selectedWorkspace.users.length"
                class="sidebar__item-count"
              >
                {{ selectedWorkspace.users.length }}</span
              >
            </a>
          </div>
        </li>
      </nuxt-link>

      <li
        v-if="
          $hasPermission(
            'workspace.create_invitation',
            selectedWorkspace,
            selectedWorkspace.id
          )
        "
        class="tree__item"
      >
        <div class="tree__action sidebar__action">
          <a class="tree__link" @click="$refs.inviteModal.show()">
            <i class="tree__icon iconoir-add-user"></i>
            <span class="tree__link-text">
              <span class="sidebar__item-name">{{
                $t('sidebar.inviteOthers')
              }}</span>
            </span>
          </a>
        </div>

        <WorkspaceMemberInviteModal
          ref="inviteModal"
          :workspace="selectedWorkspace"
          @invite-submitted="handleInvite"
        />
      </li>
      <component
        :is="component"
        v-for="(component, index) in sidebarWorkspaceComponents"
        :key="'sidebarWorkspaceComponents' + index"
        :workspace="selectedWorkspace"
        :right-sidebar-open="rightSidebarOpen"
      ></component>
      <li class="tree__item">
        <div class="tree__action sidebar__action">
          <a class="tree__link" @click="$refs.trashModal.show()">
            <i class="tree__icon iconoir-bin"></i>
            <span class="tree__link-text">
              <span class="sidebar__item-name">{{ $t('sidebar.trash') }}</span>
            </span>
          </a>
          <TrashModal
            ref="trashModal"
            :initial-workspace="selectedWorkspace"
          ></TrashModal>
        </div>
      </li>
    </ul>
  </div>
</template>

<script>
import { mapGetters } from 'vuex'

import TrashModal from '@baserow/modules/core/components/trash/TrashModal'
import NotificationPanel from '@baserow/modules/core/components/NotificationPanel'
import WorkspaceMemberInviteModal from '@baserow/modules/core/components/workspace/WorkspaceMemberInviteModal'
import BadgeCounter from '@baserow/modules/core/components/BadgeCounter'
import SidebarSearch from '@baserow/modules/core/components/sidebar/SidebarSearch'

export default {
  name: 'SidebarMenu',
  components: {
    TrashModal,
    NotificationPanel,
    WorkspaceMemberInviteModal,
    BadgeCounter,
    SidebarSearch,
  },
  props: {
    selectedWorkspace: {
      type: Object,
      required: true,
    },
    rightSidebarOpen: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  computed: {
    sidebarWorkspaceComponents() {
      return Object.values(this.$registry.getAll('plugin'))
        .flatMap((plugin) =>
          plugin.getSidebarWorkspaceComponents(this.selectedWorkspace)
        )
        .filter((component) => component !== null)
    },
    ...mapGetters({
      unreadNotificationCount: 'notification/getUnreadCount',
    }),
  },
  methods: {
    openWorkspaceSearch() {
      this.$emit('open-workspace-search')
    },

    handleInvite(event) {
      if (this.$route.name !== 'settings-invites') {
        this.$router.push({
          name: 'settings-invites',
          params: {
            workspaceId: this.selectedWorkspace.id,
          },
        })
      }
    },
  },
}
</script>
