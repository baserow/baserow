<template>
  <InviteInput
    ref="input"
    :workspace="workspace"
    :roles="roles"
    :options="options"
    :tabs="tabs"
    :pending-emails="pendingEmails"
    :member-emails="memberEmails"
    :placeholder="placeholder"
    :pending-text="$t('shareScope.alreadyInvited', { type: scopeTypeName })"
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
 * The input of the share dialog: the common invite input with the workspace
 * members, teams and agents that don't have a role on the object yet as
 * pickable options, next to new email addresses. Submitting emits `add` with
 * the picked items and the chosen role uid; the parent calls `remove()` and
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
    /**
     * Every member of the workspace, so that the address of someone who already
     * has a role on the object is explained rather than invited again.
     */
    memberEmails() {
      return (this.workspace.users || []).map(({ email }) => email)
    },
    options() {
      const agents = this.agentsEnabled ? this.agents : []
      return [
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
