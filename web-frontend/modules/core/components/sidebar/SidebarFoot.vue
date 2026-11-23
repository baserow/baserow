<template>
  <div class="sidebar__foot">
    <div class="sidebar__foot-leading">
      <slot name="leading">
        <template v-if="selectedWorkspace">
          <button
            type="button"
            class="sidebar__account-trigger"
            :aria-label="name"
            :aria-expanded="accountContextOpen"
            @click="
              $refs.accountContext.toggle(
                $event.currentTarget,
                'top',
                'left',
                6
              )
            "
          >
            <Avatar
              :initials="$filters.nameAbbreviation(name)"
              color="purple"
              rounded
              aria-hidden="true"
            ></Avatar>
            <span v-show="!collapsed" class="sidebar__account-name">{{
              firstName
            }}</span>
            <span
              v-if="hasUnreadNotifications"
              class="sidebar__unread-notifications-icon"
            ></span>
          </button>
          <SidebarAccountMenu
            ref="accountContext"
            :selected-workspace="selectedWorkspace"
            @toggle-admin="$emit('toggle-admin', $event)"
            @shown="accountContextOpen = true"
            @hidden="accountContextOpen = false"
          ></SidebarAccountMenu>
        </template>
        <div v-else class="sidebar__logo">
          <ExternalLinkBaserowLogo />
        </div>
      </slot>
    </div>
    <div class="sidebar__foot-links">
      <a
        class="sidebar__foot-link"
        :class="{
          'sidebar__foot-link--loading': undoLoading,
        }"
        @click="undo(false)"
      >
        <i class="sidebar__foot-link-icon iconoir-undo"></i>
      </a>
      <a
        class="sidebar__foot-link"
        :class="{
          'sidebar__foot-link--loading': redoLoading,
        }"
        @click="redo(false)"
      >
        <i class="sidebar__foot-link-icon iconoir-redo"></i>
      </a>
      <template v-if="!collapsed && width > 224">
        <div class="sidebar__foot-separator"></div>
        <a class="sidebar__foot-link" @click="$emit('set-col1-width', 52)">
          <i class="sidebar__foot-link-icon baserow-icon-sidebar"></i>
        </a>
      </template>
      <template v-if="collapsed">
        <div class="sidebar__foot-separator"></div>
        <a class="sidebar__foot-link" @click="$emit('set-col1-width', 240)">
          <i class="sidebar__foot-link-icon baserow-icon-sidebar"></i>
        </a>
      </template>
    </div>
  </div>
</template>

<script>
import { mapGetters } from 'vuex'
import undoRedo from '@baserow/modules/core/mixins/undoRedo'
import ExternalLinkBaserowLogo from '@baserow/modules/core/components/ExternalLinkBaserowLogo'
import SidebarAccountMenu from '@baserow/modules/core/components/sidebar/SidebarAccountMenu.vue'

export default {
  name: 'SidebarFoot',
  components: { ExternalLinkBaserowLogo, SidebarAccountMenu },
  mixins: [undoRedo],
  props: {
    selectedWorkspace: {
      type: Object,
      default: null,
    },
    hasUnreadNotifications: {
      type: Boolean,
      default: false,
    },
    collapsed: {
      type: Boolean,
      required: false,
      default: () => false,
    },
    width: {
      type: Number,
      required: true,
    },
  },
  emits: ['set-col1-width', 'toggle-admin'],
  data() {
    return { accountContextOpen: false }
  },
  computed: {
    ...mapGetters({ name: 'auth/getName' }),
    firstName() {
      return this.name.trim().split(/\s+/)[0]
    },
  },
}
</script>
