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
      :email-disabled-reason="emailDisabledReason"
      :placeholder="
        canInviteNewUsers
          ? $t('teamMembersRoute.placeholderWithEmail')
          : $t('teamMembersRoute.placeholder')
      "
      :no-results-text="
        canInviteNewUsers
          ? $t('teamMembersRoute.noResultsWithEmail')
          : $t('teamMembersRoute.noResults')
      "
      :disabled="loading || adding"
      @add="add"
    >
      <template #email-description>
        {{
          teamRoleName
            ? $t('teamMembersRoute.inviteEmailDescription', {
                role: teamRoleName,
              })
            : $t('teamMembersRoute.inviteEmailDescriptionNoRole')
        }}
      </template>
      <template #submit-label="{ count }">
        {{
          count === 0
            ? $t('teamMembersRoute.add')
            : $t('teamMembersRoute.addCount', { count })
        }}
      </template>
    </InviteInput>
    <CaptchaWidget
      v-if="canAddMembers && canInviteNewUsers"
      ref="captchaWidget"
      class="margin-top-2"
      context="workspace_invitation"
      @token="onCaptchaToken"
    />
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
      @role-updated="removeItem"
    />
  </div>
</template>

<script>
import CaptchaWidget from '@baserow/modules/core/components/auth/CaptchaWidget'
import InviteInput from '@baserow/modules/core/components/invitation/InviteInput'
import ScopeAccessList from '@baserow/modules/core/components/invitation/ScopeAccessList'
import emailInvitations from '@baserow/modules/core/mixins/emailInvitations'
import error from '@baserow/modules/core/mixins/error'
import { FF_AGENTS } from '@baserow/modules/core/plugins/featureFlags'
import { notifyIf } from '@baserow/modules/core/utils/error'
import TeamService from '@baserow_enterprise/services/team'
import { getTeamSubjectKey } from '@baserow_enterprise/utils/teamSubjects'

/**
 * The members of one team. One input adds members and agents of the workspace
 * to the team and invites new people by email, and every member and pending
 * invitation is listed below it with a button to remove or revoke it. Each
 * change is saved right away. Members get the team's own role, so there is no
 * role to choose. Someone invited by email joins the workspace without a
 * workspace role and lands in the team once they accept.
 *
 * Every change is announced with the `team-members-updated` event on the bus,
 * with the id of the team, so that the list of teams can refresh its counts.
 */
export default {
  name: 'TeamMembersInvitationRoute',
  components: { CaptchaWidget, InviteInput, ScopeAccessList },
  mixins: [error, emailInvitations],
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
      teamInvitations: [],
      subjects: {},
    }
  },
  computed: {
    team() {
      return this.target.team
    },
    /**
     * The name of the role the team gives, which is what someone invited to
     * the team gets.
     */
    teamRoleName() {
      return (
        this.workspace._.roles.find(({ uid }) => uid === this.team.default_role)
          ?.name || null
      )
    },
    canAddMembers() {
      return this.$hasPermission(
        'enterprise.teams.create_subject',
        this.workspace,
        this.workspace.id
      )
    },
    canInviteNewUsers() {
      return this.$hasPermission(
        'workspace.create_invitation',
        this.workspace,
        this.workspace.id
      )
    },
    /**
     * Pending invitations hold email addresses, so they are only listed to who
     * can list the invitations of the workspace.
     */
    canListInvitations() {
      return this.$hasPermission(
        'workspace.list_invitations',
        this.workspace,
        this.workspace.id
      )
    },
    emailDisabledReason() {
      return this.canInviteNewUsers
        ? null
        : this.$t('teamMembersRoute.emailRequiresInvitePermission')
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
     * are listed as such rather than offered, followed by the addresses that
     * already have an invitation to the team, so that they aren't invited
     * twice.
     */
    options() {
      const subjects = this.subjectTypes.flatMap((subjectType) =>
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
      const pending = this.teamInvitations.map(({ email }) => ({
        key: `invitation:${email}`,
        type: 'email',
        email,
        name: email,
        search: email,
        initials: '',
        icon: 'iconoir-mail',
        color: 'neutral',
        disabledReason: this.$t('teamMembersRoute.alreadyInvited'),
        disabledHint: this.$t('inviteInput.invitedHint'),
      }))
      return [...subjects, ...pending]
    },
    /**
     * The rows of the pending invitations, listed above the members.
     */
    invitationItems() {
      return this.teamInvitations.map((teamInvitation) => ({
        key: `invitation:${teamInvitation.id}`,
        kind: 'invitation',
        name: teamInvitation.email,
        subtitle: this.$t('teamMembersRoute.invitedSubtitle'),
        badge: this.$t('teamMembersRoute.invitePending'),
        badgeColor: 'yellow',
        initials: '',
        icon: 'iconoir-mail',
        color: 'neutral',
        roleUid: null,
        removeOnly: true,
        disabled: !this.canAddMembers,
        teamInvitation,
      }))
    },
    /**
     * The rows of the members list. A member who isn't among the fetched
     * subjects, such as an agent while agents are off, is still listed by type
     * and id, so that they can be removed.
     */
    memberItems() {
      const members = this.teamSubjects.map((teamSubject) => {
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
      return [...this.invitationItems, ...members]
    },
  },
  async mounted() {
    this.loading = true
    try {
      await Promise.all([
        this.fetchTeamSubjects(),
        this.fetchTeamInvitations(),
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
     * Fetches the pending invitations to the team, if the user may see them.
     * Without them the members are still listed, so a failure only notifies.
     */
    async fetchTeamInvitations() {
      if (!this.canListInvitations) {
        return
      }
      try {
        const { data } = await TeamService(this.$client).fetchInvitations(
          this.team.id
        )
        this.teamInvitations = data
      } catch (error) {
        notifyIf(error, 'team')
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
     * Adds the picked members and agents to the team one after the other, then
     * sends one invitation per picked email address. Every pick leaves the
     * input as soon as it was added, so after a failure exactly what wasn't
     * added yet is still picked.
     */
    async add(selection) {
      const subjects = selection.filter(({ type }) => type !== 'email')
      const emails = selection.filter(({ type }) => type === 'email')
      this.adding = true
      this.hideError()
      const service = TeamService(this.$client)
      let sendingInvitations = false
      try {
        for (const item of subjects) {
          const { data } = await service.createSubject(this.team.id, {
            subject_id: item.id,
            subject_type: item.type,
          })
          this.teamSubjects.push(data)
          this.$refs.input.remove(item)
        }
        sendingInvitations = true
        await this.sendInvitations(emails, null, (item, teamInvitation) => {
          this.$refs.input.remove(item)
          if (
            !this.teamInvitations.some(({ id }) => id === teamInvitation.id)
          ) {
            this.teamInvitations.push(teamInvitation)
          }
        })
        this.$refs.input.reset()
      } catch (error) {
        if (sendingInvitations) {
          this.handleInvitationError(error)
        } else {
          this.handleError(error, 'team')
        }
      } finally {
        this.adding = false
        this.$bus.$emit('team-members-updated', this.team.id)
      }
    },
    removeItem(item) {
      return item.kind === 'invitation'
        ? this.revokeInvitation(item)
        : this.removeMember(item)
    },
    /**
     * Revokes the invitation to the team. The workspace invitation itself stays
     * pending, as it may still give a workspace role or access elsewhere.
     */
    async revokeInvitation({ teamInvitation }) {
      const index = this.teamInvitations.findIndex(
        ({ id }) => id === teamInvitation.id
      )
      if (index === -1) {
        return
      }
      this.teamInvitations.splice(index, 1)
      try {
        await TeamService(this.$client).deleteInvitation(
          this.team.id,
          teamInvitation.id
        )
      } catch (error) {
        this.teamInvitations.splice(index, 0, teamInvitation)
        notifyIf(error, 'team')
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
