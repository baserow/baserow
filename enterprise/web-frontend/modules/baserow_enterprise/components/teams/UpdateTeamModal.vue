<template>
  <Modal ref="modal">
    <h2 class="margin-bottom-1">
      {{ $t('updateTeamModal.title', { teamName: team.name }) }}
    </h2>
    <p>{{ $t('manageTeamModals.subheading') }}</p>
    <Error :error="error"></Error>
    <ManageTeamForm
      ref="manageForm"
      :workspace="workspace"
      :loading="loading"
      :default-values="team"
      :subjects-loading="subjectsLoading"
      :invited-subjects="invitedSubjects"
      @submitted="updateTeam"
      @remove-subject="removeSubject"
      @invite="$refs.memberAssignmentModal.show()"
    >
    </ManageTeamForm>
    <MemberAssignmentModal
      ref="memberAssignmentModal"
      :members="uninvitedSubjects"
      @select="storeSelectedSubjects"
    />
  </Modal>
</template>

<script>
import modal from '@baserow/modules/core/mixins/modal'
import error from '@baserow/modules/core/mixins/error'
import { ResponseErrorMessage } from '@baserow/modules/core/plugins/clientHandler'
import ManageTeamForm from '@baserow_enterprise/components/teams/ManageTeamForm'
import TeamService from '@baserow_enterprise/services/team'
import MemberAssignmentModal from '@baserow/modules/core/components/workspace/MemberAssignmentModal'
import AgentService from '@baserow/modules/core/services/agent'
import {
  getTeamSubjectKey,
  makeTeamSubject,
} from '@baserow_enterprise/utils/teamSubjects'

export {}

export default {
  name: 'UpdateTeamModal',
  emits: ['updated'],
  components: { ManageTeamForm, MemberAssignmentModal },
  mixins: [modal, error],
  props: {
    team: {
      type: Object,
      required: false,
      default: () => ({}),
    },
    workspace: {
      type: Object,
      required: true,
    },
  },
  data() {
    return {
      loading: false,
      subjectsLoading: false,
      invitedSubjects: [],
      availableSubjects: [],
    }
  },
  computed: {
    uninvitedSubjects() {
      const invitedSubjectKeys = this.invitedSubjects.map(getTeamSubjectKey)
      return this.availableSubjects.filter(
        (subject) => !invitedSubjectKeys.includes(getTeamSubjectKey(subject))
      )
    },
  },
  methods: {
    show(...args) {
      this.hideError()
      this.parseSubjectsAndMembers()
      modal.methods.show.bind(this)(...args)
    },
    removeSubject(removal) {
      // Remove them as an invited subject.
      const removalKey = getTeamSubjectKey(removal)
      this.invitedSubjects = this.invitedSubjects.filter(
        (subject) => getTeamSubjectKey(subject) !== removalKey
      )
    },
    async parseSubjectsAndMembers() {
      this.subjectsLoading = true
      const [{ data: teamSubjects }, { data: agentsResponse }] =
        await Promise.all([
          TeamService(this.$client).fetchAllSubjects(this.team.id),
          AgentService(this.$client).list(this.workspace.id),
        ])
      const userSubjectType = this.$registry.get('subject', 'auth.User')
      const agentSubjectType = this.$registry.get('subject', 'core.Agent')
      const users = this.workspace.users.map((member) =>
        makeTeamSubject(member, userSubjectType)
      )
      const agents = (agentsResponse.results || agentsResponse).map((agent) =>
        makeTeamSubject(
          agent,
          agentSubjectType,
          this.$t('manageTeamForm.agentLabel')
        )
      )
      this.availableSubjects = [...users, ...agents]
      this.subjectsLoading = false
      const subjectsByKey = new Map(
        this.availableSubjects.map((subject) => [
          getTeamSubjectKey(subject),
          subject,
        ])
      )
      this.invitedSubjects = teamSubjects
        .map((subject) => subjectsByKey.get(getTeamSubjectKey(subject)))
        .filter(Boolean)
    },
    storeSelectedSubjects(selections) {
      this.invitedSubjects = this.invitedSubjects.concat(selections)
    },
    async updateTeam(values) {
      this.loading = true

      try {
        const { data } = await TeamService(this.$client).update(this.team.id, {
          name: values.name,
          subjects: values.subjects,
          default_role: values.default_role,
        })
        this.loading = false
        this.$refs.manageForm.reset()
        this.$emit('updated', data)
        this.hide()
      } catch (error) {
        this.loading = false
        this.handleError(error, 'team', {
          ERROR_TEAM_NAME_NOT_UNIQUE: new ResponseErrorMessage(
            this.$t('updateTeamModal.invalidNameTitle'),
            this.$t('updateTeamModal.invalidNameMessage')
          ),
        })
      }
    },
  },
}
</script>
