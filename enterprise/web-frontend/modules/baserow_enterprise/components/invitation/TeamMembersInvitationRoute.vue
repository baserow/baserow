<template>
  <div class="share-scope">
    <Error :error="error"></Error>
    <InviteInput
      v-if="canAddMembers"
      ref="input"
      :workspace="workspace"
      :roles="[]"
      :options="options"
      :tabs="tabs"
      :email-disabled-reason="$t('teamMembersRoute.emailDisabled')"
      :placeholder="$t('teamMembersRoute.placeholder')"
      :no-results-text="$t('teamMembersRoute.noResults')"
      :disabled="loading || adding"
      @add="add"
    >
      <template #submit-label="{ count }">
        {{
          count === 0
            ? $t('teamMembersRoute.add')
            : $t('teamMembersRoute.addCount', { count })
        }}
      </template>
    </InviteInput>
    <h3 class="invite-list__title">
      {{ $t('teamMembersRoute.membersTitle') }}
    </h3>
    <div v-if="loading" class="loading"></div>
    <ScopeAccessList
      v-else
      :items="memberItems"
      :roles="[]"
      :empty-title="$t('teamMembersRoute.emptyTitle')"
      :empty-description="$t('teamMembersRoute.emptyDescription')"
      :workspace="workspace"
      @role-updated="removeMember"
    />
  </div>
</template>

<script>
import InviteInput from '@baserow/modules/core/components/invitation/InviteInput'
import ScopeAccessList from '@baserow/modules/core/components/invitation/ScopeAccessList'
import error from '@baserow/modules/core/mixins/error'
import { FF_AGENTS } from '@baserow/modules/core/plugins/featureFlags'
import { notifyIf } from '@baserow/modules/core/utils/error'
import TeamService from '@baserow_enterprise/services/team'
import { getTeamSubjectKey } from '@baserow_enterprise/utils/teamSubjects'

/**
 * The members of one team. One input adds members and agents of the workspace
 * to the team, and every member is listed below it with a button to remove
 * them. Each change is saved right away. Members get the team's own role, so
 * there is no role to choose, and new people can't be added by email, as only
 * members of the workspace can join a team.
 *
 * Every change is announced with the `team-members-updated` event on the bus,
 * with the id of the team, so that the list of teams can refresh its counts.
 */
export default {
  name: 'TeamMembersInvitationRoute',
  components: { InviteInput, ScopeAccessList },
  mixins: [error],
  props: {
    workspace: {
      type: Object,
      required: true,
    },
    target: {
      type: Object,
      required: true,
    },
    targetType: {
      type: Object,
      required: true,
    },
  },
  emits: ['navigate', 'close'],
  data() {
    return {
      loading: false,
      adding: false,
      teamSubjects: [],
      subjects: {},
    }
  },
  computed: {
    team() {
      return this.target.team
    },
    canAddMembers() {
      return this.$hasPermission(
        'enterprise.teams.create_subject',
        this.workspace,
        this.workspace.id
      )
    },
    canRemoveMembers() {
      return this.$hasPermission(
        'enterprise.teams.delete_subject',
        this.workspace,
        this.workspace.id
      )
    },
    subjectTypes() {
      return this.$registry
        .getOrderedList('subject')
        .filter(
          (subjectType) =>
            subjectType.canJoinTeam &&
            subjectType.isEnabled(this.workspace) &&
            (subjectType.type !== 'core.Agent' ||
              this.$featureFlagIsEnabled(FF_AGENTS))
        )
    },
    tabs() {
      return this.subjectTypes.map((subjectType) => ({
        value: subjectType.type,
        label: subjectType.getTabDisplayName(),
      }))
    },
    memberKeys() {
      return new Set(this.teamSubjects.map(getTeamSubjectKey))
    },
    /**
     * The members and agents of the workspace, where those already in the team
     * are listed as such rather than offered.
     */
    options() {
      return this.subjectTypes.flatMap((subjectType) =>
        (this.subjects[subjectType.type] || []).map((subject) => {
          const option = subjectType.getInviteOption(subject)
          if (!this.memberKeys.has(option.key)) {
            return option
          }
          return {
            ...option,
            disabledReason: this.$t('teamMembersRoute.alreadyInTeam'),
            disabledHint: this.$t('teamMembersRoute.inTeamHint'),
          }
        })
      )
    },
    /**
     * The rows of the members list. A member who isn't among the fetched
     * subjects, such as an agent while agents are off, is still listed by type
     * and id, so that they can be removed.
     */
    memberItems() {
      return this.teamSubjects.map((teamSubject) => {
        const key = getTeamSubjectKey(teamSubject)
        const subjectType = this.$registry.get(
          'subject',
          teamSubject.subject_type
        )
        const subject = (this.subjects[teamSubject.subject_type] || []).find(
          (subject) => subjectType.getKey(subject) === key
        )
        const item = {
          key,
          roleUid: null,
          removeOnly: true,
          disabled: !this.canRemoveMembers,
          teamSubject,
        }
        if (!subject) {
          return {
            ...item,
            name: `${subjectType.getTypeDisplayName()} (${teamSubject.subject_id})`,
            initials: '',
            icon: subjectType.iconClass,
            color: 'neutral',
          }
        }
        return {
          ...item,
          name: subjectType.getDisplayName(subject),
          subtitle: subjectType.getSubtitle(subject),
          badge: subjectType.getBadge(),
          badgeColor: 'neutral',
          avatarComponent: subjectType.avatarComponent,
          subject,
        }
      })
    },
  },
  async mounted() {
    this.loading = true
    try {
      await Promise.all([
        this.fetchTeamSubjects(),
        ...this.subjectTypes.map((subjectType) =>
          this.fetchSubjects(subjectType)
        ),
      ])
    } finally {
      this.loading = false
    }
  },
  methods: {
    async fetchTeamSubjects() {
      try {
        const { data } = await TeamService(this.$client).fetchAllSubjects(
          this.team.id
        )
        this.teamSubjects = data
      } catch (error) {
        this.handleError(error, 'team')
      }
    },
    /**
     * Fetches the subjects of one type that can join the team. Without them the
     * members are still listed, so a failure only notifies.
     */
    async fetchSubjects(subjectType) {
      try {
        this.subjects[subjectType.type] =
          await subjectType.fetchAssignableSubjects(this.workspace)
      } catch (error) {
        this.subjects[subjectType.type] = []
        notifyIf(error, 'team')
      }
    },
    /**
     * Adds the picks to the team one after the other. Every pick leaves the
     * input as soon as it was added, so after a failure exactly what wasn't
     * added yet is still picked.
     */
    async add(selection) {
      this.adding = true
      this.hideError()
      const service = TeamService(this.$client)
      try {
        for (const item of selection) {
          const { data } = await service.createSubject(this.team.id, {
            subject_id: item.id,
            subject_type: item.type,
          })
          this.teamSubjects.push(data)
          this.$refs.input.remove(item)
        }
        this.$refs.input.reset()
      } catch (error) {
        this.handleError(error, 'team')
      } finally {
        this.adding = false
        this.$bus.$emit('team-members-updated', this.team.id)
      }
    },
    async removeMember({ teamSubject }) {
      const index = this.teamSubjects.findIndex(
        ({ id }) => id === teamSubject.id
      )
      if (index === -1) {
        return
      }
      this.teamSubjects.splice(index, 1)
      try {
        await TeamService(this.$client).deleteSubject(
          this.team.id,
          teamSubject.id
        )
        this.$bus.$emit('team-members-updated', this.team.id)
      } catch (error) {
        this.teamSubjects.splice(index, 0, teamSubject)
        notifyIf(error, 'team')
      }
    },
  },
}
</script>
