<template>
  <InviteInput
    ref="input"
    :workspace="workspace"
    :roles="roles"
    :options="options"
    :tabs="tabs"
    :email-role-uids="emailRoleUids"
    :placeholder="placeholder"
    :no-results-text="noResultsText"
    :disabled="disabled"
    @add="(selection, roleUid) => $emit('add', selection, roleUid)"
  >
    <template #submit-label="{ count, role }">
      {{
        count === 0
          ? $t('shareScope.add')
          : $t('shareScope.addAs', { count, role })
      }}
    </template>
    <template #email-description="{ role }">
      {{
        $t('shareScope.inviteEmailDescription', { role, type: scopeTypeName })
      }}
    </template>
  </InviteInput>
</template>

<script>
import InviteInput from '@baserow/modules/core/components/invitation/InviteInput'
import nameAbbreviation from '@baserow/modules/core/filters/nameAbbreviation'

/**
 * The input of the share dialog: the common invite input listing the members,
 * teams and agents of the workspace next to new email addresses. A subject
 * whose key is in `assignedKeys` already holds a role on the object and an
 * address in `pendingEmails` already has an invitation on it, so both are
 * listed with that reason rather than offered. Submitting emits `add` with the
 * picked items and the chosen role uid; the parent calls `remove()` and
 * `reset()` once they were added.
 *
 * Agents are only mentioned, searched and offered while `agentsEnabled` is set,
 * which the parent ties to the agents feature flag.
 */
export default {
  name: 'ShareScopeInput',
  components: { InviteInput },
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
    /**
     * The `<subject type>:<id>` keys of the subjects with a role on the object.
     */
    assignedKeys: {
      type: Array,
      required: false,
      default: () => [],
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
    /**
     * The uids of the roles a new address can be invited with, see the roles
     * of the scope invitation target.
     */
    emailRoleUids: {
      type: Array,
      required: false,
      default: null,
    },
    disabled: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  emits: ['add'],
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
    options() {
      const agents = this.agentsEnabled ? this.agents : []
      const subjects = [
        ...this.users.map((user) => ({
          key: `auth.User:${user.user_id}`,
          type: 'auth.User',
          id: user.user_id,
          name: user.name,
          email: user.email,
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
      const assigned = this.$t('shareScope.alreadyAssigned', {
        type: this.scopeTypeName,
      })
      const pending = this.$t('shareScope.alreadyInvited', {
        type: this.scopeTypeName,
      })
      return [
        ...subjects.map((option) =>
          this.assignedKeys.includes(option.key)
            ? { ...option, disabledReason: assigned }
            : option
        ),
        ...this.pendingEmails.map((email) => ({
          key: `invitation:${email}`,
          type: 'email',
          email,
          name: email,
          search: email,
          initials: '',
          icon: 'iconoir-mail',
          color: 'neutral',
          disabledReason: pending,
        })),
      ]
    },
  },
  methods: {
    focus() {
      this.$refs.input.focus()
    },
    remove(item) {
      this.$refs.input.remove(item)
    },
    reset() {
      this.$refs.input.reset()
    },
  },
}
</script>
