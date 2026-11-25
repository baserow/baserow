<template>
  <div
    class="sidebar__section sidebar__section--workspace"
    ph-autocapture="sidebar"
    data-highlight="menu"
  >
    <ul class="tree">
      <SidebarSearch
        :selected-workspace="selectedWorkspace"
        @open-workspace-search="openWorkspaceSearch"
      />
      <nuxt-link
        v-slot="{ href, navigate, isExactActive, prefetch, shouldPrefetch }"
        custom
        prefetch-on="interaction"
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
            <a
              :href="href"
              class="tree__link"
              :aria-current="isExactActive ? 'page' : undefined"
              @click="navigate"
              @pointerenter="shouldPrefetch('interaction') && prefetch()"
              @focus="shouldPrefetch('interaction') && prefetch()"
            >
              <i class="tree__icon iconoir-home-simple" aria-hidden="true"></i>
              <span class="tree__link-text">{{ $t('sidebar.overview') }}</span>
            </a>
          </div>
        </li>
      </nuxt-link>

      <li class="tree__item">
        <div class="tree__action tree__action--has-counter">
          <a
            class="tree__link"
            @click="
              whenMounted(
                (trigger) => $refs.notificationPanel.toggle(trigger),
                $event.currentTarget
              )
            "
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

      <component
        :is="component"
        v-for="(component, index) in sidebarWorkspaceComponents"
        :key="'sidebarWorkspaceComponents' + index"
        :workspace="selectedWorkspace"
        :right-sidebar-open="rightSidebarOpen"
      ></component>
      <li
        class="tree__item"
        :class="{ active: isSettingsPage || openMenu === 'settings' }"
        data-highlight="workspace-settings"
      >
        <div class="tree__action sidebar__menu-action">
          <button
            ref="settingsTrigger"
            type="button"
            class="tree__link sidebar__menu-trigger"
            :aria-expanded="openMenu === 'settings'"
            @click="whenMounted(toggleMenu, 'settings', $event.currentTarget)"
          >
            <i class="tree__icon iconoir-settings" aria-hidden="true"></i>
            <span class="tree__link-text">{{
              $t('sidebar.workspaceSettings')
            }}</span>
            <i
              class="sidebar__menu-chevron iconoir-nav-arrow-right"
              aria-hidden="true"
            ></i>
          </button>
        </div>
        <WorkspaceContext
          :key="selectedWorkspace.id"
          ref="settings"
          :workspace="selectedWorkspace"
          :show-title="false"
          class="sidebar-workspace-menu"
          tabindex="-1"
          :horizontal-viewport-margin="8"
          @shown="onMenuShown('settings')"
          @hidden="onMenuHidden('settings')"
          @keydown.esc.stop.prevent="closeMenu('settings')"
        >
          <template #default="{ actions, hide, additionalComponents }">
            <SidebarWorkspaceSettingsItems
              :actions="actions"
              :workspace="selectedWorkspace"
              :extensions="getMenuComponents('settings')"
              :additional-components="additionalComponents"
              @hide="hide()"
            />
          </template>
        </WorkspaceContext>
      </li>
      <li class="tree__item" :class="{ active: openMenu === 'help' }">
        <div class="tree__action sidebar__menu-action">
          <button
            ref="helpTrigger"
            type="button"
            class="tree__link sidebar__menu-trigger"
            :aria-expanded="openMenu === 'help'"
            @click="whenMounted(toggleMenu, 'help', $event.currentTarget)"
          >
            <i class="tree__icon iconoir-lifebelt" aria-hidden="true"></i>
            <span class="tree__link-text">{{ $t('sidebar.help') }}</span>
            <i
              class="sidebar__menu-chevron iconoir-nav-arrow-right"
              aria-hidden="true"
            ></i>
          </button>
        </div>
        <Context
          :key="selectedWorkspace.id"
          ref="help"
          class="sidebar-workspace-menu"
          tabindex="-1"
          :horizontal-viewport-margin="8"
          overflow-scroll
          max-height-if-outside-viewport
          @shown="onMenuShown('help')"
          @hidden="onMenuHidden('help')"
          @keydown.esc.stop.prevent="closeMenu('help')"
        >
          <ul v-sidebar-tab-order class="context__menu">
            <component
              :is="component"
              v-for="(component, index) in getMenuComponents('help')"
              :key="index"
              :workspace="selectedWorkspace"
              @hide="closeMenu('help')"
            />
            <li class="context__menu-item">
              <a
                class="context__menu-item-link"
                href="https://baserow.io/user-docs"
                target="_blank"
                rel="noopener"
                @click="closeMenu('help')"
              >
                <i
                  class="context__menu-item-icon iconoir-message-text"
                  aria-hidden="true"
                ></i>
                {{ $t('sidebar.knowledgeBase') }}
              </a>
            </li>
            <li
              v-for="resource in workspaceLearningResources"
              :key="resource.url"
              class="context__menu-item"
            >
              <a
                class="context__menu-item-link"
                :href="resource.url"
                target="_blank"
                rel="noopener noreferrer"
                @click="closeMenu('help')"
              >
                <i
                  class="context__menu-item-icon"
                  :class="resource.icon"
                  aria-hidden="true"
                ></i>
                {{ $t(resource.title) }}
              </a>
            </li>
            <li class="context__menu-item">
              <nuxt-link
                class="context__menu-item-link"
                :to="{ name: 'database-api-docs' }"
                target="_blank"
                @click="closeMenu('help')"
              >
                <i
                  class="context__menu-item-icon iconoir-code"
                  aria-hidden="true"
                ></i>
                {{ $t('sidebar.apiDocumentation') }}
              </nuxt-link>
            </li>
          </ul>
        </Context>
      </li>
    </ul>
  </div>
</template>

<script>
import { mapGetters } from 'vuex'
import { workspaceLearningResources } from '@baserow/modules/core/utils/workspaceLearningResources'
import sidebarTabOrder from '@baserow/modules/core/directives/sidebarTabOrder'
import NotificationPanel from '@baserow/modules/core/components/NotificationPanel'
import BadgeCounter from '@baserow/modules/core/components/BadgeCounter'
import SidebarSearch from '@baserow/modules/core/components/sidebar/SidebarSearch'
import SidebarWorkspaceSettingsItems from '@baserow/modules/core/components/sidebar/SidebarWorkspaceSettingsItems.vue'
import WorkspaceContext from '@baserow/modules/core/components/workspace/WorkspaceContext'
import whenMounted from '@baserow/modules/core/mixins/whenMounted'

export default {
  name: 'SidebarMenu',
  directives: { sidebarTabOrder },
  components: {
    NotificationPanel,
    BadgeCounter,
    SidebarSearch,
    SidebarWorkspaceSettingsItems,
    WorkspaceContext,
  },
  mixins: [whenMounted],
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
  emits: ['open-workspace-search'],
  data() {
    return { openMenu: null, workspaceLearningResources }
  },
  computed: {
    isSettingsPage() {
      return [
        'settings-members',
        'settings-teams',
        'settings-identities',
        'workspace-audit-log',
      ].includes(this.$route.name)
    },
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
  watch: {
    'selectedWorkspace.id'() {
      this.openMenu = null
    },
  },
  methods: {
    getMenuComponents(menu) {
      return Object.values(this.$registry.getAll('plugin')).flatMap((plugin) =>
        plugin.getSidebarWorkspaceMenuComponents(this.selectedWorkspace, menu)
      )
    },
    toggleMenu(menu, trigger) {
      if (this.openMenu && this.openMenu !== menu) {
        this.$refs[this.openMenu].hide()
      }
      // Leave 4px after the sidebar's 8px inset and 1px border.
      this.$refs[menu].toggle(
        trigger,
        'over-bottom',
        'left',
        0,
        trigger.offsetWidth + 13
      )
    },
    onMenuShown(menu) {
      this.openMenu = menu
      this.$nextTick(() => {
        if (this.openMenu === menu) {
          const context = this.$refs[menu]?.getTeleportedElement()
          const target =
            context?.querySelector('button:not(:disabled), a[href]') ?? context
          target?.focus()
        }
      })
    },
    onMenuHidden(menu) {
      if (this.openMenu === menu) {
        this.openMenu = null
      }
    },
    closeMenu(menu) {
      this.$refs[menu].hide()
      this.$refs[`${menu}Trigger`].focus()
    },
    openWorkspaceSearch() {
      this.$emit('open-workspace-search')
    },
  },
}
</script>
