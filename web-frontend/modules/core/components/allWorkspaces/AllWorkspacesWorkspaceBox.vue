<template>
  <div class="workspace-box">
    <div class="workspace-box__header">
      <a class="workspace-box__avatar-link" @click="goToWorkspace()">
        <Avatar :initials="avatarInitials" color="blue" size="x-large"></Avatar>
      </a>

      <div class="workspace-box__title">
        <div class="workspace-box__name-row">
          <div class="workspace-box__name" @click="goToWorkspace()">
            <SearchHighlight
              v-if="highlight !== ''"
              :text="workspace.name"
              :query="highlight"
            ></SearchHighlight>
            <Editable
              v-else
              ref="rename"
              :value="workspace.name"
              @change="renameWorkspace(workspace, $event)"
            ></Editable>
          </div>
          <span
            v-if="hasUnreadNotifications"
            class="workspace-box__unread"
          ></span>
          <span v-if="roleName !== ''" class="workspace-box__role">{{
            roleName
          }}</span>
        </div>
        <div class="workspace-box__meta">
          {{ $t('allWorkspaces.membersCount', { count: memberCount }) }}
          <span class="workspace-box__meta-separator">&#8226;</span>
          {{ $t('allWorkspaces.itemsCount', { count: totalApplicationCount }) }}
        </div>
      </div>

      <div class="workspace-box__actions">
        <Button
          class="workspace-box__action"
          type="secondary"
          size="tiny"
          icon="iconoir-plus"
          tag="a"
          @click="toggleCreateApplication($event)"
          >{{ $t('allWorkspaces.create') }}</Button
        >
        <Button
          class="workspace-box__action workspace-box__action--collapsible"
          type="secondary"
          size="tiny"
          tag="a"
          @click="
            $router.push({
              name: 'settings-members',
              params: { workspaceId: workspace.id },
            })
          "
          >{{ $t('allWorkspaces.members') }}</Button
        >
        <Button
          class="workspace-box__action workspace-box__action--collapsible"
          type="secondary"
          size="tiny"
          tag="a"
          @click="$refs.workspaceSettingsModal.show()"
          >{{ $t('allWorkspaces.settings') }}</Button
        >
        <ButtonIcon
          class="workspace-box__action workspace-box__more"
          type="secondary"
          size="small"
          icon="baserow-icon-more-vertical"
          @click="
            $refs.context.toggle($event.currentTarget, 'bottom', 'right', 4)
          "
        ></ButtonIcon>
        <a
          v-if="!headerOnly"
          class="workspace-box__chevron"
          :class="{ 'workspace-box__chevron--collapsed': collapsed }"
          @click="$emit('toggle-collapsed')"
        >
          <i class="iconoir-nav-arrow-down"></i>
        </a>
      </div>
    </div>

    <template v-if="!headerOnly && !collapsed">
      <div v-if="applications.length > 0" class="workspace-box__body">
        <AllWorkspacesApplicationCard
          v-for="application in visibleApplications"
          :key="application.id"
          :application="application"
          :workspace="workspace"
          @click="$emit('select-application', application)"
        ></AllWorkspacesApplicationCard>
        <div
          v-if="hiddenApplicationCount > 0"
          class="application-card application-card--more"
          role="button"
          tabindex="0"
          @click="revealed = true"
          @keydown.enter.prevent="revealed = true"
          @keydown.space.prevent="revealed = true"
        >
          <div class="application-card__more-label">
            {{
              $t('allWorkspaces.moreElements', {
                count: hiddenApplicationCount,
              })
            }}
            <i class="application-card__more-arrow iconoir-nav-arrow-right"></i>
          </div>
        </div>
      </div>
      <div v-else-if="totalApplicationCount === 0" class="workspace-box__empty">
        <img
          class="workspace-box__empty-image"
          src="@baserow/modules/core/assets/images/empty_workspace_illustration.png"
          srcset="
            @baserow/modules/core/assets/images/empty_workspace_illustration@2x.png 2x
          "
        />
        <div class="workspace-box__empty-title">
          {{ $t('allWorkspaces.noApplications') }}
        </div>
        <Button
          type="secondary"
          size="small"
          icon="iconoir-plus"
          tag="a"
          @click="toggleCreateApplication($event)"
          >{{ $t('allWorkspaces.create') }}</Button
        >
      </div>
      <div v-else class="workspace-box__empty-filter">
        {{ $t('allWorkspaces.noFilterMatches') }}
      </div>
    </template>

    <WorkspaceContext
      ref="context"
      :workspace="workspace"
      @rename="enableRename()"
    ></WorkspaceContext>
    <CreateApplicationContext
      ref="createApplicationContext"
      :workspace="workspace"
    ></CreateApplicationContext>
    <WorkspaceSettingsModal
      ref="workspaceSettingsModal"
      :workspace="workspace"
    ></WorkspaceSettingsModal>
  </div>
</template>

<script>
import editWorkspace from '@baserow/modules/core/mixins/editWorkspace'
import WorkspaceContext from '@baserow/modules/core/components/workspace/WorkspaceContext'
import WorkspaceSettingsModal from '@baserow/modules/core/components/workspace/WorkspaceSettingsModal'
import CreateApplicationContext from '@baserow/modules/core/components/application/CreateApplicationContext'
import SearchHighlight from '@baserow/modules/core/components/SearchHighlight'
import AllWorkspacesApplicationCard from '@baserow/modules/core/components/allWorkspaces/AllWorkspacesApplicationCard'

const COMPACT_APPLICATION_LIMIT = 3

export default {
  name: 'AllWorkspacesWorkspaceBox',
  components: {
    WorkspaceContext,
    WorkspaceSettingsModal,
    CreateApplicationContext,
    SearchHighlight,
    AllWorkspacesApplicationCard,
  },
  mixins: [editWorkspace],
  props: {
    workspace: {
      type: Object,
      required: true,
    },
    roleName: {
      type: String,
      required: false,
      default: '',
    },
    applications: {
      type: Array,
      required: true,
    },
    totalApplicationCount: {
      type: Number,
      required: true,
    },
    collapsed: {
      type: Boolean,
      required: false,
      default: false,
    },
    compact: {
      type: Boolean,
      required: false,
      default: false,
    },
    highlight: {
      type: String,
      required: false,
      default: '',
    },
    headerOnly: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  emits: ['toggle-collapsed', 'select-application'],
  data() {
    return {
      // Whether the compact view shows all applications instead of the first
      // few. It only matters while the body is compact and visible, so it's
      // reset whenever either of those changes.
      revealed: false,
    }
  },
  computed: {
    // The design shows a single letter, not the two letter abbreviation used
    // elsewhere.
    avatarInitials() {
      return this.workspace.name.trim().charAt(0).toUpperCase()
    },
    memberCount() {
      return this.workspace.users?.length ?? 0
    },
    hasUnreadNotifications() {
      return this.$store.getters['notification/workspaceHasUnread'](
        this.workspace.id
      )
    },
    truncated() {
      return (
        this.compact &&
        !this.revealed &&
        this.applications.length > COMPACT_APPLICATION_LIMIT
      )
    },
    visibleApplications() {
      return this.truncated
        ? this.applications.slice(0, COMPACT_APPLICATION_LIMIT)
        : this.applications
    },
    hiddenApplicationCount() {
      return this.truncated
        ? this.applications.length - COMPACT_APPLICATION_LIMIT
        : 0
    },
  },
  watch: {
    compact() {
      this.revealed = false
    },
    collapsed() {
      this.revealed = false
    },
  },
  methods: {
    goToWorkspace() {
      // Clicking inside the name while it's being renamed inline must not
      // navigate away.
      if (this.$refs.rename?.editing) {
        return
      }
      this.$router.push({
        name: 'workspace',
        params: { workspaceId: this.workspace.id },
      })
    },
    // The context must be anchored to the element that was clicked, otherwise
    // the bubbling click counts as an outside click and immediately hides it.
    toggleCreateApplication(event) {
      this.$refs.createApplicationContext.toggle(event.currentTarget)
    },
    enableRename() {
      this.$refs.context.hide()
      // There is no inline editable in search results mode because the name is
      // rendered with the match highlighted.
      this.$refs.rename?.edit()
    },
  },
}
</script>
