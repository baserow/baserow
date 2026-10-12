<template>
  <div class="share-scope-input">
    <div class="share-scope-input__row">
      <div
        class="share-scope-input__field"
        :class="{ 'share-scope-input__field--focused': open }"
        @click="focus"
      >
        <span
          v-for="item in selected"
          :key="item.key"
          class="share-scope-input__chip"
        >
          <i class="share-scope-input__chip-icon" :class="item.icon"></i>
          {{ item.name }}
          <a class="share-scope-input__chip-remove" @click.stop="remove(item)">
            <i class="iconoir-cancel"></i>
          </a>
        </span>
        <input
          ref="input"
          v-model="query"
          class="share-scope-input__input"
          :placeholder="selected.length === 0 ? placeholder : ''"
          :disabled="disabled"
          @focus="open = true"
          @blur="open = false"
          @keydown.enter.prevent="selectEmailOption"
          @keydown.escape="open = false"
          @keydown.delete="removeLastWhenEmpty"
        />
      </div>
      <WorkspaceRoleSelector
        v-model="roleUid"
        class="share-scope-input__role"
        :workspace="workspace"
        :roles="roles"
      />
      <Button
        type="primary"
        :disabled="selected.length === 0 || disabled"
        @click="submit"
      >
        {{ addLabel }}
      </Button>
    </div>
    <div v-show="open" class="share-scope-input__results" @mousedown.prevent>
      <div class="share-scope-input__tabs">
        <a
          v-for="tab in tabs"
          :key="tab.value"
          class="share-scope-input__tab"
          :class="{ 'share-scope-input__tab--active': activeTab === tab.value }"
          @click="activeTab = tab.value"
        >
          {{ tab.label }}
        </a>
      </div>
      <ul class="share-scope-input__list">
        <li
          v-if="pendingEmail"
          class="share-scope-input__item share-scope-input__item--pending"
        >
          <Avatar icon="iconoir-mail" color="neutral" rounded size="medium" />
          <div class="share-scope-input__item-text">
            <div class="share-scope-input__item-title">{{ pendingEmail }}</div>
            <div class="share-scope-input__item-subtitle">
              {{ $t('shareScope.alreadyInvited', { type: scopeTypeName }) }}
            </div>
          </div>
        </li>
        <li
          v-if="emailOption"
          class="share-scope-input__item"
          @click="toggle(emailOption)"
        >
          <Avatar icon="iconoir-mail" color="neutral" rounded size="medium" />
          <div class="share-scope-input__item-text">
            <div class="share-scope-input__item-title">
              {{ $t('shareScope.inviteEmail', { email: emailOption.name }) }}
            </div>
            <div class="share-scope-input__item-subtitle">
              {{
                $t('shareScope.inviteEmailDescription', {
                  role: roleName,
                  type: scopeTypeName,
                })
              }}
            </div>
          </div>
          <Checkbox
            :checked="isSelected(emailOption)"
            @click.stop
            @update:model-value="toggle(emailOption)"
          ></Checkbox>
        </li>
        <li
          v-for="option in visibleOptions"
          :key="option.key"
          class="share-scope-input__item"
          @click="toggle(option)"
        >
          <Avatar
            :initials="option.initials"
            :icon="option.initials ? '' : option.icon"
            :color="option.color"
            rounded
            size="medium"
          />
          <div class="share-scope-input__item-text">
            <div class="share-scope-input__item-title">{{ option.name }}</div>
            <div
              v-if="option.subtitle"
              class="share-scope-input__item-subtitle"
            >
              {{ option.subtitle }}
            </div>
          </div>
          <Checkbox
            :checked="isSelected(option)"
            @click.stop
            @update:model-value="toggle(option)"
          ></Checkbox>
        </li>
      </ul>
      <div
        v-if="!emailOption && !pendingEmail && visibleOptions.length === 0"
        class="share-scope-input__empty"
      >
        {{ noResultsText }}
      </div>
    </div>
  </div>
</template>

<script>
import WorkspaceRoleSelector from '@baserow/modules/core/components/workspace/WorkspaceRoleSelector'
import nameAbbreviation from '@baserow/modules/core/filters/nameAbbreviation'
import { isValidEmail } from '@baserow/modules/core/utils/string'

const TAB_ALL = 'all'

/**
 * One input that searches the workspace members, teams and agents that don't
 * have a role on the object yet, and accepts a new email address. Everything
 * picked is shown as a chip. Submitting emits `add` with the picked items and
 * the chosen role uid; the parent calls `reset()` once they were added. An
 * address in `pendingEmails` already has an invitation on the object, so it is
 * shown as such instead of being offered again.
 *
 * Agents are only mentioned, searched and offered while `agentsEnabled` is set,
 * which the parent ties to the agents feature flag.
 *
 * A result row toggles on click, and so does its checkbox. The checkbox is a
 * label around a native input, whose click would bubble to the row and toggle
 * it back, so the checkbox keeps its click to itself and toggles through its
 * own change event instead.
 */
export default {
  name: 'ShareScopeInput',
  components: { WorkspaceRoleSelector },
  props: {
    workspace: {
      type: Object,
      required: true,
    },
    scopeTypeName: {
      type: String,
      required: true,
    },
    users: {
      type: Array,
      required: false,
      default: () => [],
    },
    teams: {
      type: Array,
      required: false,
      default: () => [],
    },
    agents: {
      type: Array,
      required: false,
      default: () => [],
    },
    agentsEnabled: {
      type: Boolean,
      required: false,
      default: false,
    },
    pendingEmails: {
      type: Array,
      required: false,
      default: () => [],
    },
    roles: {
      type: Array,
      required: true,
    },
    disabled: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  emits: ['add'],
  data() {
    return {
      query: '',
      open: false,
      activeTab: TAB_ALL,
      selected: [],
      roleUid: this.defaultRoleUid(this.roles),
    }
  },
  computed: {
    placeholder() {
      return this.agentsEnabled
        ? this.$t('shareScope.searchPlaceholder')
        : this.$t('shareScope.searchPlaceholderWithoutAgents')
    },
    noResultsText() {
      return this.agentsEnabled
        ? this.$t('shareScope.noResults')
        : this.$t('shareScope.noResultsWithoutAgents')
    },
    tabs() {
      const tabs = [
        { value: TAB_ALL, label: this.$t('shareScope.tabAll') },
        { value: 'auth.User', label: this.$t('shareScope.tabMembers') },
        {
          value: 'baserow_enterprise.Team',
          label: this.$t('shareScope.tabTeams'),
        },
      ]
      if (this.agentsEnabled) {
        tabs.push({
          value: 'core.Agent',
          label: this.$t('shareScope.tabAgents'),
        })
      }
      return tabs
    },
    roleName() {
      return this.roles.find((role) => role.uid === this.roleUid)?.name || ''
    },
    addLabel() {
      if (this.selected.length === 0) {
        return this.$t('shareScope.add')
      }
      return this.$t('shareScope.addAs', {
        count: this.selected.length,
        role: this.roleName,
      })
    },
    options() {
      const agents = this.agentsEnabled ? this.agents : []
      return [
        ...this.users.map((user) => ({
          key: `auth.User:${user.user_id}`,
          type: 'auth.User',
          id: user.user_id,
          name: user.name,
          subtitle: user.email,
          search: `${user.name} ${user.email}`,
          initials: nameAbbreviation(user.name),
          icon: 'iconoir-user',
          color: 'blue',
          subject: user,
        })),
        ...this.teams.map((team) => ({
          key: `baserow_enterprise.Team:${team.id}`,
          type: 'baserow_enterprise.Team',
          id: team.id,
          name: team.name,
          subtitle: this.$t('shareScope.teamMembers', {
            count: team.subject_count,
          }),
          search: team.name,
          initials: '',
          icon: 'iconoir-community',
          color: 'neutral',
          subject: team,
        })),
        ...agents.map((agent) => ({
          key: `core.Agent:${agent.id}`,
          type: 'core.Agent',
          id: agent.id,
          name: agent.name,
          subtitle: this.$t('shareScope.agentBadge'),
          search: agent.name,
          initials: '',
          icon: 'iconoir-sparks',
          color: 'purple',
          subject: agent,
        })),
      ]
    },
    normalizedQuery() {
      return this.query.trim().toLowerCase()
    },
    visibleOptions() {
      return this.options.filter(
        (option) =>
          (this.activeTab === TAB_ALL || option.type === this.activeTab) &&
          option.search.toLowerCase().includes(this.normalizedQuery)
      )
    },
    /**
     * The query, when it is an email address that already has a pending
     * invitation on the object.
     */
    pendingEmail() {
      const email = this.normalizedQuery
      const pending =
        isValidEmail(email) &&
        this.pendingEmails.some((pendingEmail) => {
          return pendingEmail.toLowerCase() === email
        })
      return pending ? email : null
    },
    /**
     * Offered when the query is an email address that doesn't belong to a
     * workspace member and isn't invited yet, so a new person can be invited
     * with a role on the object.
     */
    emailOption() {
      const email = this.normalizedQuery
      if (
        !isValidEmail(email) ||
        this.pendingEmail ||
        this.users.some((user) => user.email.toLowerCase() === email)
      ) {
        return null
      }
      return {
        key: `email:${email}`,
        type: 'email',
        email,
        name: email,
        icon: 'iconoir-mail',
      }
    },
  },
  watch: {
    roles(roles) {
      if (!roles.some((role) => role.uid === this.roleUid)) {
        this.roleUid = this.defaultRoleUid(roles)
      }
    },
  },
  methods: {
    /**
     * The last active role is the one with the least access, the safest default.
     */
    defaultRoleUid(roles) {
      const active = roles.filter((role) => !role.isDeactivated)
      return active.length > 0 ? active[active.length - 1].uid : null
    },
    focus() {
      this.$refs.input.focus()
    },
    isSelected(option) {
      return this.selected.some((item) => item.key === option.key)
    },
    toggle(option) {
      if (this.isSelected(option)) {
        this.remove(option)
      } else {
        this.selected.push(option)
        if (option.type === 'email') {
          this.query = ''
        }
      }
      this.focus()
    },
    remove(item) {
      this.selected = this.selected.filter(({ key }) => key !== item.key)
    },
    selectEmailOption() {
      if (this.emailOption && !this.isSelected(this.emailOption)) {
        this.toggle(this.emailOption)
      }
    },
    removeLastWhenEmpty() {
      if (this.query === '' && this.selected.length > 0) {
        this.selected.pop()
      }
    },
    submit() {
      if (this.selected.length === 0 || this.disabled) {
        return
      }
      this.$emit('add', [...this.selected], this.roleUid)
    },
    reset() {
      this.selected = []
      this.query = ''
    },
  },
}
</script>
