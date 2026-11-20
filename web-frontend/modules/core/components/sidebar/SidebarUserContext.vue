<template>
  <Context
    ref="context"
    max-height-if-outside-viewport
    :overflow-scroll="mode === 'account'"
    :class="{
      'sidebar-workspace-picker': mode === 'workspace',
      'sidebar-account-menu': mode === 'account',
    }"
    @shown="onShow"
    @hidden="onHidden"
    @keydown.esc="onEscape"
  >
    <template v-if="mode === 'workspace'">
      <SelectSearch
        ref="search"
        v-model="query"
        :aria-label="$t('action.search')"
        @keydown.down.up="onWorkspaceSearchKeydown"
      />
      <ul
        ref="workspaceOptions"
        class="sidebar-workspace-picker__items"
        @keydown="onWorkspaceOptionKeydown"
      >
        <SidebarWorkspacePickerRow
          v-for="workspace in filteredWorkspaces"
          :key="workspace.id"
          :workspace="workspace"
          :selected="workspace.id === selectedWorkspace.id"
          :has-unread-notifications="hasUnreadNotifications(workspace.id)"
          @select="selectWorkspace(workspace)"
        />
        <li v-if="$hasPermission('create_workspace')">
          <button
            ref="addWorkspace"
            type="button"
            class="sidebar-workspace-picker__add"
            data-workspace-option
            @click="$refs.createWorkspaceModal.show()"
          >
            <span
              class="button-icon button-icon--small sidebar-workspace-picker__add-icon"
              aria-hidden="true"
            >
              <i class="button-icon__icon iconoir-plus"></i>
            </span>
            {{ $t('sidebar.addNewWorkspace') }}
          </button>
        </li>
      </ul>
      <CreateWorkspaceModal
        ref="createWorkspaceModal"
        @created="hide()"
        @hidden="onCreateWorkspaceHidden"
      ></CreateWorkspaceModal>
    </template>
    <div v-else ref="accountMenu" class="sidebar__user">
      <div class="sidebar__user-email">{{ email }}</div>

      <ul class="context__menu">
        <li class="context__menu-item">
          <button
            type="button"
            class="context__menu-item-link"
            @click="$refs.settingsModal.show()"
          >
            <i class="context__menu-item-icon iconoir-user-circle"></i>
            {{ $t('sidebar.settings') }}
          </button>
          <SettingsModal ref="settingsModal"></SettingsModal>
        </li>

        <component
          :is="component"
          v-for="(component, index) in sidebarUserContextComponents"
          :key="'sidebarUserContextComponent' + index"
          @hide="hide()"
        ></component>

        <li v-if="isStaff" class="context__menu-item">
          <button
            ref="adminTrigger"
            type="button"
            class="context__menu-item-link"
            :aria-expanded="adminMenuOpen"
            @click="toggleAdminMenu"
          >
            <i class="context__menu-item-icon iconoir-settings"></i>
            {{ $t('sidebar.adminTools') }}
            <i
              class="sidebar-account-menu__chevron iconoir-nav-arrow-right"
              aria-hidden="true"
            ></i>
          </button>
        </li>

        <li v-if="anyGuidedTourActive" class="context__menu-item">
          <button
            type="button"
            class="context__menu-item-link"
            @click="replayGuidedTour()"
          >
            <i class="context__menu-item-icon iconoir-help-circle"></i>
            {{ $t('sidebar.replayGuidedTour') }}
          </button>
        </li>

        <li class="context__menu-item context__menu-item--with-separator">
          <button
            type="button"
            class="context__menu-item-link"
            :class="{ 'context__menu-item-link--loading': logoffLoading }"
            @click="logoff()"
          >
            <i class="context__menu-item-icon iconoir-log-out"></i>
            {{ $t('sidebar.logoff') }}
          </button>
        </li>
      </ul>
      <Context
        v-if="isStaff"
        ref="adminContext"
        class="sidebar-admin-menu"
        :horizontal-viewport-margin="8"
        max-height-if-outside-viewport
        overflow-scroll
        @shown="onAdminMenuShown"
        @hidden="adminMenuOpen = false"
        @keydown.esc.stop.prevent="closeAdminMenu"
      >
        <SidebarAdmin show-section-separators />
      </Context>
    </div>
  </Context>
</template>

<script>
import { mapGetters } from 'vuex'

import { logoutAndRedirectToLogin } from '@baserow/modules/core/utils/auth'
import context from '@baserow/modules/core/mixins/context'
import SelectSearch from '@baserow/modules/core/components/SelectSearch.vue'
import SidebarAdmin from '@baserow/modules/core/components/sidebar/SidebarAdmin.vue'
import SidebarWorkspacePickerRow from '@baserow/modules/core/components/sidebar/SidebarWorkspacePickerRow.vue'
import SettingsModal from '@baserow/modules/core/components/settings/SettingsModal'
import CreateWorkspaceModal from '@baserow/modules/core/components/workspace/CreateWorkspaceModal'
import { escapeRegExp } from '@baserow/modules/core/utils/string'
import { pageFinished } from '@baserow/modules/core/utils/routing'
import { nextTick, useNuxtApp } from '#imports'

export default {
  name: 'SidebarUserContext',
  components: {
    SelectSearch,
    SidebarAdmin,
    SettingsModal,
    CreateWorkspaceModal,
    SidebarWorkspacePickerRow,
  },
  mixins: [context],
  props: {
    workspaces: {
      type: Array,
      default: () => [],
    },
    selectedWorkspace: {
      type: Object,
      required: true,
    },
    mode: {
      type: String,
      default: 'workspace',
      validator: (value) => ['workspace', 'account'].includes(value),
    },
  },
  emits: ['hidden', 'shown', 'toggle-admin'],
  setup() {
    const nuxtApp = useNuxtApp()
    return { nuxtApp }
  },
  data() {
    return {
      adminMenuOpen: false,
      logoffLoading: false,
      query: '',
    }
  },
  computed: {
    sidebarUserContextComponents() {
      return Object.values(this.$registry.getAll('plugin'))
        .flatMap((plugin) =>
          plugin.getUserContextComponents(this.selectedWorkspace)
        )
        .filter((component) => component !== null)
    },
    /**
     * Replaying only makes sense when a guided tour can actually show on the
     * current page. On the all workspaces homepage, for example, no tour is
     * active, and forcing a start there would show nothing while blocking a later
     * natural start.
     */
    anyGuidedTourActive() {
      return Object.values(this.$registry.getAll('guidedTour')).some((tour) =>
        tour.isActive(this.$route)
      )
    },
    filteredWorkspaces() {
      let workspaces = this.workspaces
      const regex = new RegExp('(' + escapeRegExp(this.query) + ')', 'i')
      if (this.query) {
        workspaces = workspaces.filter((workspace) => {
          return workspace.name.match(regex)
        })
      }
      return workspaces
    },
    ...mapGetters({
      isStaff: 'auth/isStaff',
      email: 'auth/getUsername',
    }),
  },
  watch: {
    '$route.name'(name) {
      if (
        this.adminMenuOpen &&
        Object.values(this.$registry.getAll('admin')).some(
          (adminType) => adminType.routeName === name
        )
      ) {
        this.hide()
        this.$emit('toggle-admin', true)
      }
    },
  },
  methods: {
    getWorkspaceOptions() {
      return Array.from(
        this.$refs.workspaceOptions.querySelectorAll(
          '[data-workspace-option]:not(:disabled)'
        )
      )
    },
    onWorkspaceSearchKeydown(event) {
      if (!event.isComposing) {
        event.preventDefault()
        const index = event.key === 'ArrowDown' ? 0 : -1
        this.getWorkspaceOptions().at(index)?.focus()
      }
    },
    onWorkspaceOptionKeydown(event) {
      if (!['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key)) {
        return
      }

      const options = this.getWorkspaceOptions()
      const index = options.indexOf(event.target)
      if (index === -1) {
        return
      }

      const targets = {
        ArrowDown: options[index + 1] ?? this.$refs.search,
        ArrowUp: options[index - 1] ?? this.$refs.search,
        Home: options[0],
        End: options.at(-1),
      }
      event.preventDefault()
      targets[event.key].focus()
    },
    onCreateWorkspaceHidden() {
      if (this.$refs.context?.open) {
        this.$refs.addWorkspace?.focus()
      }
    },
    onHidden() {
      const adminContext = this.$refs.adminContext
      if (adminContext?.isOpen()) {
        adminContext.hide()
      }
      this.$emit('hidden')
    },
    onShow() {
      this.query = ''
      this.$emit('shown')
      this.$nextTick(() => {
        if (!this.$refs.context?.open) {
          return
        }
        if (this.mode === 'account') {
          this.$refs.accountMenu?.querySelector('button')?.focus()
        } else {
          this.$refs.search?.focus()
        }
      })
    },
    onEscape(event) {
      if (event.defaultPrevented) {
        return
      }
      event.preventDefault()
      event.stopPropagation()
      this.hideAndFocusOpener()
    },
    hideAndFocusOpener() {
      const opener = this.$refs.context.opener
      this.hide()
      opener?.focus()
    },
    async logoff() {
      this.logoffLoading = true
      await logoutAndRedirectToLogin(
        this.$router,
        this.$store,
        false,
        false,
        true
      )
    },
    toggleAdminMenu(event) {
      const trigger = event.currentTarget
      this.$refs.adminContext.toggle(
        trigger,
        'over-top',
        'left',
        0,
        trigger.offsetWidth + 12
      )
    },
    async onAdminMenuShown() {
      if (!this.$refs.context?.isOpen() || !this.$refs.adminContext?.isOpen()) {
        return
      }
      this.adminMenuOpen = true
      await this.$nextTick()
      if (this.adminMenuOpen) {
        this.$refs.adminContext
          ?.getTeleportedElement()
          ?.querySelector('a[href]')
          ?.focus()
      }
    },
    closeAdminMenu() {
      this.$refs.adminContext.hide()
      this.$refs.adminTrigger.focus()
    },
    async replayGuidedTour() {
      this.hide()
      await this.$nextTick()
      await this.$store.dispatch('guidedTour/forceStart')
    },
    hasUnreadNotifications(workspaceId) {
      return this.$store.getters['notification/workspaceHasUnread'](workspaceId)
    },
    async selectWorkspace(workspace) {
      // The workspace can still be selected while the user is on a workspace
      // agnostic page, like the all workspaces homepage, so there must always be
      // navigated to the workspace even if selecting can be skipped.
      if (!workspace._.selected) {
        await this.$store.dispatch('workspace/select', workspace)
      }
      const destination = {
        name: 'workspace',
        params: { workspaceId: workspace.id },
      }
      if (this.$route.fullPath !== this.$router.resolve(destination).fullPath) {
        await this.$router.push(destination)
        await pageFinished(this.nuxtApp)
        await nextTick()
      }
      // The navigation can replace the sidebar, and with it this context, for example
      // when selecting a workspace from the all workspaces homepage. It's then already
      // unmounted and doesn't have to be hidden anymore.
      if (this.$refs.context?.open) {
        this.hideAndFocusOpener()
      }
    },
  },
}
</script>
